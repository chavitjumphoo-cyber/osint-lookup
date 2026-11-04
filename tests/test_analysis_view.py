import pytest

from osint_agent.profiling import analysis_view
from osint_agent.services.store import RunStore


def _artifact(aid, url, stype="profile", platform="github", content="John Doe a@b.com", title="John Doe"):
    return {
        "artifact_id": aid, "source_url": url, "source_type": stype, "platform": platform,
        "content": content, "title": title, "confidence": "Probable",
    }


@pytest.fixture
def store(tmp_path):
    return RunStore(tmp_path / "a.db")


def test_build_groups_identifiers_with_sources(store):
    run_id = store.create_run("jdoe", "username", "quick")
    store.add_artifact(run_id, _artifact("a1", "https://github.com/jdoe"))
    store.add_artifact(run_id, _artifact("a2", "https://x.com/jdoe", content="John Doe a@b.com", platform="x"))
    view = analysis_view.build(store, run_id)

    email = next(item for item in view["identifiers"] if item["type"] == "email")
    assert email["occurrences"] == 2
    assert set(email["source_artifacts"]) == {"a1", "a2"}
    assert email["next_pivots"]


def test_profiles_and_who(store):
    run_id = store.create_run("jdoe", "username", "quick")
    store.add_artifact(run_id, _artifact("a1", "https://github.com/jdoe"))
    store.add_artifact(run_id, _artifact("a2", "https://x.com/jdoe", platform="x"))
    view = analysis_view.build(store, run_id)
    assert view["profiles"]
    assert "John Doe" in view["who"]["likely_names"]
    assert view["ownership"]


def test_missing_run(store):
    with pytest.raises(KeyError):
        analysis_view.build(store, "nope")
