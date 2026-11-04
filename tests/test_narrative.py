from osint_agent.profiling import narrative


def _profile(**kw):
    base = {"display_names": ["สมชาย ใจดี"], "evidence": ["a1"], "confidence": "Probable",
            "platform": "github", "username": "somchai", "locations": ["Bangkok"],
            "organizations": ["Acme"], "emails": ["a@b.com"], "phones": [],
            "languages": ["python"], "interests": ["tech"], "family_names": ["ใจดี"], "relations": []}
    base.update(kw)
    return base


def _data(profiles=None):
    return {
        "identity": {"names": ["สมชาย ใจดี"], "family_names": ["ใจดี"], "emails": ["a@b.com"],
                     "phones": [], "locations": ["Bangkok"], "organizations": ["Acme"]},
        "profiles_detail": profiles if profiles is not None else [_profile()],
        "interests": ["tech"],
        "cognitive": {"identity": {"assessment": "ok", "confidence": "Probable", "evidence": ["a1"]}},
        "explicit_relations": [{"relationship": "บิดา", "name": "สมชาย", "snippet": "คุณพ่อสมชาย", "artifact_id": "a2"}],
        "contradictions": [], "limitations": [],
    }


def test_narrative_answers_who_with_confidence():
    claims = narrative.build(_data(), [{"artifact_id": "a1"}, {"artifact_id": "a2"}])
    text = claims["identity_answer"]["narrative"]
    assert "สมชาย ใจดี" in text
    assert "Probable" in text


def test_family_uses_explicit_relation():
    claims = narrative.build(_data(), [{"artifact_id": "a1"}, {"artifact_id": "a2"}])
    assert "บิดา" in claims["family"]["narrative"]


def test_surname_alone_is_pivot_not_family():
    data = _data()
    data["explicit_relations"] = []
    claims = narrative.build(data, [{"artifact_id": "a1"}])
    assert "pivot" in claims["family"]["narrative"] or "ยังไม่ยืนยัน" in claims["family"]["narrative"]


def test_validate_drops_unknown_evidence():
    claims = {"identity_answer": {"narrative": "x", "evidence": ["a1", "ghost"]}}
    cleaned = narrative.validate(claims, [{"artifact_id": "a1"}])
    assert cleaned["identity_answer"]["evidence"] == ["a1"]


def test_render_contains_sections():
    claims = narrative.build(_data(), [{"artifact_id": "a1"}, {"artifact_id": "a2"}])
    text = narrative.render(claims)
    assert "บุคคลนี้น่าจะเป็นใคร" in text
    assert "6D" in text
