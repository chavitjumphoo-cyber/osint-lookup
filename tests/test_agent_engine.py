from types import SimpleNamespace

import pytest

from osint_agent.profiling.artifacts import Artifact
from osint_agent.services import agent_engine, agent_tools
from osint_agent.services import budget as budget_mod
from osint_agent.services.agent_state import AgentState
from osint_agent.services.store import RunStore


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def messages_create(self, **kwargs):
        return self.script[min(self.calls, len(self.script) - 1)]

    @property
    def messages(self):
        return SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        response = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return response


def _tool(name, args, tid="t1"):
    return SimpleNamespace(type="tool_use", name=name, input=args, id=tid)


def _resp(*blocks):
    return SimpleNamespace(content=list(blocks))


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "a.db")


@pytest.fixture
def fake_collectors(monkeypatch):
    def search(query, limit=8):
        return [Artifact(source_url="https://github.com/jdoe", source_type="search_result",
                         source_tool="search:fake", platform="github", title="John", content="dev")]

    def fetch(url):
        return Artifact(source_url=url, source_type="profile", source_tool="moli_fetch",
                        platform="github", title="John Doe", author="jdoe",
                        content="John Doe\nPython developer\nBangkok", confidence="Probable")

    monkeypatch.setattr(agent_tools.collectors, "search", search)
    monkeypatch.setattr(agent_tools.collectors, "fetch", fetch)


def test_engine_runs_actions_and_finalizes(store, fake_collectors, monkeypatch):
    monkeypatch.setattr(agent_engine, "seed_queries", lambda state: [])
    run_id = store.create_run("jdoe", "username", "standard")
    run = store.get_run(run_id)
    state = AgentState(run_id=run_id, target="jdoe", target_type="username", store=store)
    script = [
        _resp(_tool("search_web", {"query": "jdoe"})),
        _resp(_tool("fetch_profile", {"url": "https://github.com/jdoe"}, "t2")),
        _resp(_tool("finalize_report", {}, "t3")),
    ]
    engine = agent_engine.AgentEngine(store, run_id, client=FakeClient(script))
    data = engine.run(run, state, budget_mod.RunBudget(budget_mod.Budget()))

    assert state.steps >= 3
    assert [a["action"] for a in state.actions][:2] == ["search_web", "fetch_profile"]
    assert "finalize_report" in [a["action"] for a in state.actions]
    assert store.get_report(run_id)
    assert data["profiles"]
    assert any(f["tool"].startswith("agent:") for f in store.list_findings(run_id))


def test_engine_stops_on_exhausted(store, monkeypatch):
    monkeypatch.setattr(agent_engine, "seed_queries", lambda state: [])
    run_id = store.create_run("jdoe", "username", "standard")
    run = store.get_run(run_id)
    state = AgentState(run_id=run_id, target="jdoe", target_type="username", store=store, max_steps=1)
    script = [_resp(_tool("search_web", {"query": "x"}))]
    agent_engine.AgentEngine(store, run_id, client=FakeClient(script)).run(
        run, state, budget_mod.RunBudget(budget_mod.Budget(max_steps=5))
    )
    assert state.steps == 1
    assert store.get_report(run_id)


def test_tool_error_is_returned(store, monkeypatch):
    monkeypatch.setattr(agent_tools.collectors, "search", lambda q, limit=8: (_ for _ in ()).throw(RuntimeError("boom")))
    run_id = store.create_run("jdoe", "username", "standard")
    run = store.get_run(run_id)
    state = AgentState(run_id=run_id, target="jdoe", target_type="username", store=store)
    script = [_resp(_tool("search_web", {"query": "x"})), _resp(_tool("finalize_report", {}, "t2"))]
    agent_engine.AgentEngine(store, run_id, client=FakeClient(script)).run(
        run, state, budget_mod.RunBudget(budget_mod.Budget())
    )
    assert any(f["status"] == "ok" for f in store.list_findings(run_id))
