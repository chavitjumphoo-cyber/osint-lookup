import json
import time

import pytest
from fastapi.testclient import TestClient

from osint_agent import access, auth
from osint_agent.api.app import create_app
from osint_agent.services.store import RunStore


@pytest.fixture(autouse=True)
def users(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "name": "Admin",
                        "role": "admin",
                        "unit": "HQ",
                        "active": True,
                        "password_hash": auth.hash_password("Admin#1234"),
                    },
                    {
                        "username": "analyst",
                        "name": "Analyst",
                        "role": "analyst",
                        "unit": "Unit",
                        "active": True,
                        "password_hash": auth.hash_password("Analyst#1234"),
                    },
                    {
                        "username": "viewer",
                        "name": "Viewer",
                        "role": "viewer",
                        "unit": "Unit",
                        "active": True,
                        "password_hash": auth.hash_password("Viewer#1234"),
                    },
                    {
                        "username": "inactive",
                        "name": "Inactive",
                        "role": "analyst",
                        "unit": "Unit",
                        "active": False,
                        "password_hash": auth.hash_password("Inactive#1234"),
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OSINT_USERS_FILE", str(path))
    monkeypatch.setenv("OSINT_SECRET_KEY", "test-secret")
    monkeypatch.setattr(access, "AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(access, "AUDIT_FILE", str(tmp_path / "audit" / "audit.jsonl"))
    auth._failures.clear()


@pytest.fixture
def client(tmp_path):
    client = TestClient(create_app(RunStore(tmp_path / "runs.sqlite")))
    token = client.post("/auth/login", json={"username": "admin", "password": "Admin#1234"}).json()[
        "access_token"
    ]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _login(client, username, password, application=None):
    return (application or client).post(
        "/auth/login", json={"username": username, "password": password}
    )


def test_password_hash_roundtrip():
    encoded = auth.hash_password("secret")
    assert auth.verify_password("secret", encoded)
    assert not auth.verify_password("wrong", encoded)
    assert not auth.verify_password("secret", "broken")


def test_authenticate_success_and_case_insensitive():
    user = auth.authenticate("ADMIN", "Admin#1234")
    assert user == {"username": "admin", "name": "Admin", "role": "admin", "unit": "HQ"}


def test_authenticate_rejects_wrong_password_and_inactive():
    assert auth.authenticate("admin", "nope") is None
    assert auth.authenticate("inactive", "Inactive#1234") is None
    assert auth.authenticate("ghost", "x") is None


def test_lockout_after_five_failures():
    for _ in range(5):
        assert auth.authenticate("admin", "wrong") is None
    assert auth.authenticate("admin", "Admin#1234") is None
    auth._failures["admin"] = [time.time() - auth.LOCK_SECONDS - 1]
    assert auth.authenticate("admin", "Admin#1234")


def test_token_roundtrip_and_tamper():
    user = auth.authenticate("analyst", "Analyst#1234")
    token = auth.issue_token(user)
    assert auth.verify_token(token)["username"] == "analyst"
    payload, signature = token.split(".")
    assert auth.verify_token(f"{payload}.{signature[:-1]}x") is None
    assert auth.verify_token("garbage") is None


def test_expired_token_rejected():
    user = auth.authenticate("analyst", "Analyst#1234")
    assert auth.verify_token(auth.issue_token(user, ttl=-1)) is None


def test_permission_matrix():
    viewer = {"role": "viewer"}
    analyst = {"role": "analyst"}
    admin = {"role": "admin"}
    assert auth.has_permission(viewer, "read")
    assert not auth.has_permission(viewer, "investigate")
    assert auth.has_permission(analyst, "investigate")
    assert not auth.has_permission(analyst, "manage_users")
    assert auth.has_permission(admin, "manage_users")
    assert not auth.has_permission(None, "read")


def test_api_requires_login(client):
    anonymous = TestClient(client.app)
    response = anonymous.get("/runs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_api_login_and_me(client):
    response = _login(client, "analyst", "Analyst#1234")
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["username"] == "analyst"
    assert "password_hash" not in me.json()


def test_viewer_read_only(client):
    token = _login(client, "viewer", "Viewer#1234").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/runs", headers=headers).status_code == 200
    forbidden = client.post("/investigate", json={"target": "johndoe"}, headers=headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


def test_admin_lists_users_but_analyst_cannot(client):
    admin_token = client.post("/auth/login", json={"username": "admin", "password": "Admin#1234"}).json()[
        "access_token"
    ]
    assert client.get("/auth/users", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    analyst_token = client.post(
        "/auth/login", json={"username": "analyst", "password": "Analyst#1234"}
    ).json()["access_token"]
    assert client.get("/auth/users", headers={"Authorization": f"Bearer {analyst_token}"}).status_code == 403


def test_login_is_audited(client):
    _login(client, "admin", "Admin#1234")
    _login(client, "admin", "wrong")
    with open(access.AUDIT_FILE, encoding="utf-8") as fh:
        events = [json.loads(line)["event"] for line in fh]
    assert "login" in events and "login_failed" in events
    assert access.verify_audit_chain()[0]
