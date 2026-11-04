from osint_agent.profiling import (
    collectors,
    entity_extractor,
    pivots,
    profile_resolver,
    synthesizer,
)
from osint_agent.profiling.artifacts import Artifact
from osint_agent.profiling.corpus import Corpus
from osint_agent.profiling.leads import LeadQueue
from osint_agent.services.store import RunStore


def test_artifact_id_is_stable_and_dedupes(tmp_path):
    store = RunStore(tmp_path / "r.db")
    run_id = store.create_run("x", "text", "quick")
    corpus = Corpus(store, run_id)
    first = Artifact(source_url="https://a.test", source_type="page", source_tool="t", content="same")
    second = Artifact(source_url="https://a.test", source_type="page", source_tool="t", content="same")
    assert corpus.add(first) is True
    assert corpus.add(second) is False
    assert first.artifact_id == second.artifact_id


def test_phone_queries_cover_formats_and_scam_terms():
    queries = pivots.search_queries("0812345678", "phone")
    joined = "\n".join(queries)
    assert "+66812345678" in joined
    assert "081-234-5678" in joined
    assert "มิจฉาชีพ" in joined and "site:facebook.com" in joined


def test_username_queries_and_classify_url():
    queries = pivots.search_queries("jdoe", "username")
    assert any("site:" in q for q in queries)
    assert pivots.classify_url("https://github.com/jdoe") == ("profile", "github")


def test_entity_extractor_finds_profile_fields():
    data = entity_extractor.extract(
        "John Doe — Python developer in Bangkok works at Acme, a@b.com, joined 2020-01-02"
    )
    assert "John Doe" in data["names"]
    assert "Bangkok" in data["locations"]
    assert "Acme" in data["organizations"]
    assert "tech" in data["interests"]


def test_profile_resolver_builds_profile_with_evidence():
    artifacts = [
        {
            "artifact_id": "art_1",
            "source_type": "profile",
            "source_url": "https://github.com/jdoe",
            "platform": "github",
            "author": "jdoe",
            "title": "John Doe",
            "content": "Python developer in Bangkok",
            "confidence": "Probable",
        }
    ]
    entities = profile_resolver.extract_entities(artifacts)
    profiles = profile_resolver.resolve_profiles(artifacts, entities)
    assert profiles[0]["username"] == "jdoe"
    assert "John Doe" in profiles[0]["display_names"]
    assert "art_1" in profiles[0]["evidence"]


def test_synthesizer_renders_all_sections():
    run = {"id": "r", "target": "jdoe", "target_type": "username"}
    data = synthesizer.synthesize(run, [], [], [], [], [], [])
    markdown = synthesizer.render_markdown(data, run)
    for heading in ("Identity", "Social Profiles", "Timeline", "Limitations", "Evidence Sources"):
        assert heading in markdown


def test_lead_queue_dedupes_and_orders():
    queue = LeadQueue()
    assert queue.add("a", "username", "r", priority=0.2)
    assert not queue.add("a", "username", "r", priority=0.9)
    queue.add("b", "url", "r", priority=0.8)
    assert queue.next().value == "b"


def test_collectors_fetch_marks_blocked(monkeypatch):
    class Err(Exception):
        pass

    monkeypatch.setattr(collectors.browser, "fetch_json", lambda *a, **k: (_ for _ in ()).throw(collectors.browser.BrowserError("blocked")))
    artifact = collectors.fetch("https://x.test")
    assert artifact.status == "blocked"


def test_collectors_fetch_profile(monkeypatch):
    class Page:
        status = 200
        html = "<html><title>John</title><body>Python developer</body></html>"
        title = "John"

    monkeypatch.setattr(collectors.browser, "fetch_json", lambda *a, **k: Page())
    artifact = collectors.fetch("https://github.com/jdoe")
    assert artifact.source_type == "profile"
    assert artifact.platform == "github"
