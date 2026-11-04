import json

import pytest
from fastapi.testclient import TestClient

from osint_agent.api.app import create_app
from osint_agent.profiling.artifacts import Artifact
from osint_agent.services import orchestrator as orch
from osint_agent.services.store import RunStore


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "runs.sqlite")


@pytest.fixture
def client(store, monkeypatch):
    def fake_search(query, limit=8):
        return [Artifact(source_url="https://github.com/user", source_type="search_result",
                         source_tool="search:fake", platform="github", title="John", content="dev")]

    def fake_fetch(url):
        return Artifact(source_url=url, source_type="profile", source_tool="moli_fetch",
                        platform="github", title="John", author="user", content="John dev Bangkok")

    monkeypatch.setattr(orch.collectors, "search", fake_search)
    monkeypatch.setattr(orch.collectors, "fetch", fake_fetch)
    monkeypatch.setattr(orch.collectors, "scan_profiles", lambda u, timeout=45: [])
    app = create_app(store)
    return TestClient(app)


def _wait(client, run_id):
    for _ in range(100):
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] in {"done", "failed", "cancelled"}:
            return run
        import time

        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_investigate_and_fetch_run(client):
    created = client.post("/investigate", json={"target": "johndoe", "profile": "quick"})
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    run = _wait(client, run_id)
    assert run["status"] == "done"
    assert run["target_type"] == "username"
    findings = client.get(f"/runs/{run_id}/findings").json()["findings"]
    assert any(item["tool"] == "web_search" for item in findings)
    report = client.get(f"/runs/{run_id}/report").json()["markdown"]
    assert "ข้อจำกัด" in report


def test_events_stream(client):
    run_id = client.post("/investigate", json={"target": "johndoe", "profile": "quick"}).json()["run_id"]
    _wait(client, run_id)

    body = client.get(f"/runs/{run_id}/events").text
    assert "event: tool" in body
    assert "event: close" in body
    kinds = [json.loads(line[6:])["kind"] for line in body.splitlines() if line.startswith("data: {") and line != "data: {}"]
    assert "start" in kinds and "done" in kinds


def test_missing_run_is_envelope(client):
    response = client.get("/runs/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


def test_validation_error(client):
    assert client.post("/investigate", json={"target": ""}).status_code == 422


def test_export_shape(client):
    run_id = client.post("/investigate", json={"target": "0812345678", "profile": "quick"}).json()["run_id"]
    _wait(client, run_id)
    data = client.get(f"/runs/{run_id}/export").json()
    assert data["target_type"] == "phone"
    assert data["findings"]


def test_research_report_endpoint(store, client):
    run_id = store.create_run("johndoe", "username", "quick")
    store.add_artifact(
        run_id,
        {"artifact_id": "a1", "source_url": "https://x", "source_type": "search_result", "platform": "github"},
    )
    response = client.get(f"/runs/{run_id}/research-report")
    assert response.status_code == 200
    assert "บทคัดย่อ" in response.json()["markdown"]

    docx = client.get(f"/runs/{run_id}/research-report?format=docx")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"


def test_analysis_and_pivot_endpoints(store, client):
    run_id = store.create_run("jdoe", "username", "quick")
    store.add_artifact(
        run_id,
        {"artifact_id": "a1", "source_url": "https://github.com/jdoe", "source_type": "profile",
         "platform": "github", "title": "John", "author": "jdoe", "content": "John a@b.com"},
    )
    response = client.get(f"/runs/{run_id}/analysis")
    assert response.status_code == 200
    assert any(item["type"] == "email" for item in response.json()["identifiers"])

    pivot = client.post(f"/runs/{run_id}/pivot", json={"identifier": "a@b.com", "identifier_type": "email", "profile": "quick"})
    assert pivot.status_code == 202
    child = store.get_run(pivot.json()["run_id"])
    assert child["parent_run_id"] == run_id
