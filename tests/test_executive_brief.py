from osint_agent.profiling import executive_brief


def _profile(**kw):
    base = {"platform": "github", "username": "jdoe", "display_names": ["John Doe"],
            "evidence": ["a1", "a2"], "confidence": "Probable", "locations": ["Bangkok"],
            "organizations": ["Acme"], "emails": [], "phones": []}
    base.update(kw)
    return base


def _data(profile=None):
    return {
        "identity": {"names": ["John Doe"], "aliases": ["JD"], "family_names": ["Doe"],
                     "locations": ["Bangkok"], "organizations": ["Acme"], "emails": [], "phones": []},
        "profiles_detail": [profile or _profile()],
        "interests": ["tech"],
        "cognitive": {"identity": {"assessment": "สอดคล้อง", "confidence": "Probable"}},
        "explicit_relations": [{"relationship": "พี่น้อง", "name": "Jane", "snippet": "น้องสาว Jane"}],
        "contradictions": [], "questions_unanswered": ["ยังไม่ยืนยันชื่อจริง"], "next_pivots": ["a@b.com"],
    }


def test_brief_answers_who_in_one_place():
    brief = executive_brief.build(_data(), [{"artifact_id": "a1"}, {"artifact_id": "a2"}])
    assert "John Doe" in brief["identity_answer"]
    assert brief["quick_facts"]
    assert "พี่น้อง" in brief["relationships_summary"]


def test_brief_without_evidence_downgrades():
    brief = executive_brief.validate(
        {"identity_answer": "x", "confidence": "Confirmed", "evidence_ids": ["ghost"]},
        [{"artifact_id": "a1"}], [],
    )
    assert brief["confidence"] == "Unverified"


def test_confirmed_needs_two_platforms():
    profiles = [_profile(confidence="Confirmed")]
    brief = executive_brief.validate(
        {"identity_answer": "x", "confidence": "Confirmed", "evidence_ids": ["a1"]},
        [{"artifact_id": "a1"}], profiles,
    )
    assert brief["confidence"] == "Probable"


def test_brief_states_unknown():
    brief = executive_brief.build(_data(), [{"artifact_id": "a1"}])
    assert brief["unknowns"]


def test_render_has_sections():
    text = executive_brief.render(executive_brief.build(_data(), [{"artifact_id": "a1"}]))
    assert "สรุปหน้าเดียว" in text
    assert "มีความเป็นไปได้" in text
