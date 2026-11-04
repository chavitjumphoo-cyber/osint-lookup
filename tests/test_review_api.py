import pytest
from fastapi.testclient import TestClient

from osint_agent.api.app import create_app
from osint_agent.services.store import RunStore


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "runs.sqlite")


@pytest.fixture
def client(store, monkeypatch):
    from osint_agent.services import tool_runner

    monkeypatch.setattr(tool_runner, "execute_tool", lambda n, a: {"output": "ok", "images": []})
    return TestClient(create_app(store))


def test_review_flow(store, client):
    run_id = store.create_run("johndoe", "username", "quick")
    store.add_candidate(
        run_id,
        {
            "candidate_id": "c1",
            "entity_ids": ["e1", "e2"],
            "supporting_signals": [{"signal_type": "EXACT_NORMALIZED_EMAIL"}],
        },
    )

    listed = client.get(f"/runs/{run_id}/candidates").json()["candidates"]
    assert listed[0]["status"] == "CANDIDATE"

    decided = client.post(f"/runs/{run_id}/review", json={"candidate_id": "c1", "action": "confirm"})
    assert decided.status_code == 200
    assert decided.json()["status"] == "CONFIRMED"

    reversed_ = client.post(f"/runs/{run_id}/review", json={"candidate_id": "c1", "action": "reverse"})
    assert reversed_.json()["status"] == "CANDIDATE"


def test_review_unknown_candidate(store, client):
    run_id = store.create_run("johndoe", "username", "quick")
    response = client.post(f"/runs/{run_id}/review", json={"candidate_id": "nope", "action": "reject"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "candidate_not_found"


def test_investigate_accepts_trusted(store, client):
    response = client.post(
        "/investigate", json={"target": "johndoe", "profile": "quick", "trusted": ["github:johndoe"]}
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert store.trusted(run_id) == ["github:johndoe"]


def test_export_includes_report(store, client):
    run_id = store.create_run("johndoe", "username", "quick")
    store.save_report(run_id, "# report")
    assert client.get(f"/runs/{run_id}/export").json()["report"] == "# report"
