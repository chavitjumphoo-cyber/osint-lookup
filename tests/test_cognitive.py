from osint_agent.profiling import cognitive


def _artifact(aid, content=""):
    return {"artifact_id": aid, "source_type": "post", "content": content, "source_url": "https://x"}


def test_empty_data_reports_unable():
    result = cognitive.evaluate([], [], [])
    assert all(v["assessment"].startswith("ประเมินไม่ได้") for v in result.values())
    assert set(result) == set(cognitive.DIMENSIONS)


def test_psychological_needs_three_texts():
    arts = [_artifact("a1", "x" * 100), _artifact("a2", "y" * 100)]
    assert "ประเมินไม่ได้" in cognitive.evaluate([], arts, [])["psychological"]["assessment"]
    arts.append(_artifact("a3", "z" * 100))
    result = cognitive.evaluate([], arts, [])["psychological"]
    assert result["confidence"] == "Speculative"
    assert result["metrics"]["samples"] == 3


def test_technical_and_opsec_use_entities():
    arts = [_artifact("a1", "python and rust"), _artifact("a2", "docker")]
    entities = [
        {"type": "email", "value": "a@b.com", "source_artifact": "a1"},
        {"type": "phone", "value": "0812345678", "source_artifact": "a2"},
    ]
    result = cognitive.evaluate([], arts, entities)
    assert "python" in result["technical"]["assessment"]
    assert "อีเมล" in result["opsec"]["assessment"]


def test_identity_and_geo_from_profiles():
    profiles = [
        {"platform": "github", "display_names": ["John"], "evidence": ["a1"],
         "locations": ["Bangkok"], "username": "john"},
        {"platform": "reddit", "display_names": ["John"], "evidence": ["a2"],
         "locations": ["Bangkok"], "username": "john"},
        {"platform": "x", "display_names": ["John"], "evidence": ["a3"],
         "locations": ["Bangkok"], "username": "john"},
    ]
    entities = [{"type": "location", "value": "Bangkok", "source_artifact": "a1"}]
    result = cognitive.evaluate(profiles, [], entities)
    assert result["identity"]["confidence"] == "Probable"
    assert "Bangkok" in result["geo_temporal"]["assessment"]
