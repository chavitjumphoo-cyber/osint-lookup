from osint_agent.profiling import pivots, profile_extractor, thai_identity


def test_parse_thai_name_with_title():
    parsed = thai_identity.parse_name("นายสมชาย ใจดี")
    assert parsed["given_name"] == "สมชาย"
    assert parsed["family_name"] == "ใจดี"
    assert parsed["name_script"] == "thai"


def test_parse_english_name_and_reject_single():
    assert thai_identity.parse_name("John Doe")["family_name"] == "Doe"
    assert thai_identity.parse_name("Pantip") is None


def test_extract_relations():
    found = thai_identity.extract_relations("สุขสันต์วันเกิดคุณพ่อสมชาย ใจดี")
    assert any(item["relationship"] == "บิดา" for item in found)


def test_surname_queries_include_context():
    queries = thai_identity.surname_queries("ใจดี", ["กรุงเทพ"])
    assert '"ใจดี" ครอบครัว' in queries
    assert '"ใจดี" "กรุงเทพ"' in queries


def test_name_target_uses_surname_pivot():
    queries = pivots.search_queries("สมชาย ใจดี", "name")
    assert any("ครอบครัว" in q for q in queries)


def test_extractor_records_name_and_relation_with_source():
    artifact = {
        "artifact_id": "a1", "source_url": "https://x", "source_type": "profile",
        "title": "สมชาย ใจดี", "author": "somchai",
        "content": "สุขสันต์วันเกิดคุณพ่อสมชาย ใจดี", "metadata": {},
    }
    fields = profile_extractor.extract(artifact)
    assert fields["name_observations"][0]["family_name"] == "ใจดี"
    assert fields["relations"][0]["source_artifact"] == "a1"
