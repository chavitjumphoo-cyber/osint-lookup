import json

import pytest
from fastapi.testclient import TestClient

from osint_agent.api.app import create_app
from osint_agent.services import tool_runner as runner
from osint_agent.services.store import RunStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "execute_tool", lambda n, a: {"output": f"{n} ok", "images": []})
    app = create_app(RunStore(tmp_path / "runs.sqlite"))
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
    assert any(item["tool"] == "scan_platforms" for item in findings)
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
