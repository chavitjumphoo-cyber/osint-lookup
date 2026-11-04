from osint_agent.profiling import profile_extractor


def _artifact():
    return {
        "artifact_id": "a1",
        "source_url": "https://github.com/jdoe",
        "source_type": "profile",
        "title": "John Doe",
        "author": "jdoe",
        "content": "John Doe\nPython developer at Acme\nBangkok\njoined 2020-01-02\nhttps://jdoe.dev",
        "metadata": {"bio": "Python developer"},
    }


def test_extracts_structured_fields_with_evidence():
    fields = profile_extractor.extract(_artifact())
    assert fields["display_names"][0]["value"] == "John Doe"
    assert fields["display_names"][0]["source_artifact"] == "a1"
    assert fields["emails"] == []
    assert any(item["value"] == "Bangkok" for item in fields["locations"])
    assert any("python" in item["value"].lower() for item in fields["languages"])


def test_all_fields_present():
    assert set(profile_extractor.extract(_artifact())) >= set(profile_extractor.FIELDS) | {"artifact_id"}


def test_dedupe_same_value():
    artifact = _artifact()
    artifact["content"] += "\nJohn Doe"
    fields = profile_extractor.extract(artifact)
    values = [item["value"] for item in fields["display_names"]]
    assert values.count("John Doe") == 1
