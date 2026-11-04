import pytest

from osint_agent.profiling.artifacts import Artifact
from osint_agent.services import orchestrator as mod
from osint_agent.services.orchestrator import Orchestrator, RunNotFound
from osint_agent.services.store import RunStore


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "runs.sqlite")


@pytest.fixture
def fake_collectors(monkeypatch):
    calls = {"search": [], "fetch": [], "scan": []}

    def fake_search(query, limit=8):
        calls["search"].append(query)
        return [
            Artifact(
                source_url=f"https://github.com/user?q={len(calls['search'])}",
                source_type="search_result",
                source_tool="search:fake",
                platform="github",
                title="John Doe",
                content="Python developer in Bangkok",
                query=query,
            )
        ]

    def fake_fetch(url):
        calls["fetch"].append(url)
        return Artifact(
            source_url=url,
            source_type="profile",
            source_tool="moli_fetch",
            platform="github",
            title="John Doe",
            author="user",
            content="John Doe\nPython developer\nBangkok\nworks at Acme",
            confidence="Probable",
        )

    def fake_scan(username, timeout=45):
        calls["scan"].append(username)
        return [
            Artifact(
                source_url=f"https://github.com/{username}",
                source_type="profile",
                source_tool="scanner:github",
                platform="github",
                title="John Doe",
                author=username,
                content="John Doe\nPython developer\nBangkok",
                confidence="Probable",
            )
        ]

    monkeypatch.setattr(mod.collectors, "search", fake_search)
    monkeypatch.setattr(mod.collectors, "fetch", fake_fetch)
    monkeypatch.setattr(mod.collectors, "scan_profiles", fake_scan)
    return calls


def test_username_run_builds_corpus_and_dossier(store, fake_collectors):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    result = orchestrator.run(run_id)

    assert result.status == "done"
    report = store.get_report(run_id)
    assert "Subject Intelligence Dossier" in report
    assert "Social Profiles" in report
    assert "john" in report.lower()
    assert fake_collectors["scan"][0] == "johndoe"
    assert store.list_artifacts(run_id)


def test_search_result_urls_are_fetched(store, fake_collectors):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    orchestrator.run(run_id)
    assert fake_collectors["fetch"], "should open ranked results"


def test_deep_fetches_more_than_quick(store, fake_collectors):
    orchestrator = Orchestrator(store)
    quick = orchestrator.start("johndoe", "quick")
    orchestrator.run(quick)
    quick_fetches = len(fake_collectors["fetch"])
    deep = orchestrator.start("johndoe", "deep")
    orchestrator.run(deep)
    assert len(fake_collectors["fetch"]) > quick_fetches


def test_cancel_stops(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")

    def fake_search(query, limit=8):
        orchestrator.cancel(run_id)
        return []

    monkeypatch.setattr(mod.collectors, "search", fake_search)
    result = orchestrator.run(run_id)
    assert result.status == "cancelled"


def test_search_error_does_not_fail_run(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    monkeypatch.setattr(mod.collectors, "search", lambda q, limit=8: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(mod.collectors, "scan_profiles", lambda u, timeout=45: [])
    result = orchestrator.run(run_id)
    assert result.status == "done"
    assert any(f["status"] == "failed" for f in store.list_findings(run_id))


def test_budget_exhaustion_still_reports(store, monkeypatch):
    orchestrator = Orchestrator(store)
    run_id = orchestrator.start("johndoe", "quick")
    tight = mod.budget_mod.Budget(max_steps=1)
    monkeypatch.setattr(
        mod.budget_mod,
        "Budget",
        type("B", (), {"quick": staticmethod(lambda: tight), "standard": staticmethod(lambda: tight), "deep": staticmethod(lambda: tight)}),
    )
    monkeypatch.setattr(mod.collectors, "search", lambda q, limit=8: [])
    result = orchestrator.run(run_id)
    assert result.status == "done"
    assert store.get_report(run_id)


def test_unknown_run(store):
    with pytest.raises(RunNotFound):
        Orchestrator(store).run("missing")
