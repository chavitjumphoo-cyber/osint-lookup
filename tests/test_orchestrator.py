import pytest

from osint_agent.services import orchestrator as mod
from osint_agent.services import tool_runner as runner
from osint_agent.services.orchestrator import Orchestrator, RunNotFound
from osint_agent.services.store import RunStore


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "runs.sqlite")


@pytest.fixture
def fake_tool(monkeypatch):
    calls = []

    def fake(name, args):
        calls.append((name, args))
        return {"output": f"ผลของ {name}", "images": []}

    monkeypatch.setattr(runner, "execute_tool", fake)
    return calls


def test_username_plan_runs_and_records(store, fake_tool):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    result = orchestrator.run(run_id)

    assert result.status == "done"
    assert [name for name, _ in fake_tool] == ["scan_platforms", "sherlock_username"]
    assert store.get_run(run_id)["status"] == "done"
    tools = [finding["tool"] for finding in store.list_findings(run_id)]
    assert "scan_platforms" in tools and "evidence_scoring" in tools
    assert store.get_report(run_id)
    kinds = [event["kind"] for event in store.list_events(run_id)]
    assert "start" in kinds and "done" in kinds


def test_resume_skips_completed_steps(store, fake_tool):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    orchestrator.run(run_id)

    store.set_status(run_id, "queued")
    fake_tool.clear()
    orchestrator.run(run_id)

    assert fake_tool == []
    assert any(event["kind"] == "skip" for event in store.list_events(run_id))


def test_cancel_stops_next_step(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")

    def fake(name, args):
        orchestrator.cancel(run_id)
        return {"output": "ok", "images": []}

    monkeypatch.setattr(runner, "execute_tool", fake)
    result = orchestrator.run(run_id)

    assert result.status == "cancelled"
    assert store.get_run(run_id)["status"] == "cancelled"


def test_budget_exhaustion_finishes_done(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    tight = mod.Budget(max_steps=1)
    monkeypatch.setattr(
        mod,
        "Budget",
        type(
            "B",
            (),
            {
                "quick": staticmethod(lambda: tight),
                "standard": staticmethod(lambda: tight),
                "deep": staticmethod(lambda: tight),
            },
        ),
    )
    monkeypatch.setattr(runner, "execute_tool", lambda n, a: {"output": "x", "images": []})
    result = orchestrator.run(run_id)

    assert result.status == "done"
    assert any(event["kind"] == "budget" for event in store.list_events(run_id))


def test_tool_exception_marks_failed(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    monkeypatch.setattr(runner, "execute_tool", lambda n, a: 1 / 0)
    result = orchestrator.run(run_id)

    assert result.status == "failed"
    assert "ZeroDivisionError" in result.error


def test_unknown_run(store):
    with pytest.raises(RunNotFound):
        Orchestrator(store).run("missing")


def test_invalid_profile(store):
    with pytest.raises(ValueError):
        Orchestrator(store).start("johndoe", "deepest")


def test_deep_domain_uses_deep_playbook_tools(store, fake_tool):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("example.com", "deep")
    orchestrator.run(run_id)
    tools = [name for name, _ in fake_tool]
    assert "whois_lookup" in tools
    assert "wayback_lookup" in tools
    assert "dns_lookup" in tools
    report = store.get_report(run_id)
    assert "ข้อจำกัด" in report


def test_identity_candidate_recorded_from_shared_email(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("a@b.com", "quick")

    def fake(name, args):
        return {"output": "a@b.com และ a@b.com", "images": []}

    from osint_agent.services import tool_runner

    monkeypatch.setattr(tool_runner, "execute_tool", fake)
    orchestrator.run(run_id)
    candidates = store.list_candidates(run_id)
    assert isinstance(candidates, list)
