import json

from osint_agent.core import evidence as ev


def test_classify_status_categories():
    assert ev.classify_status("ไม่พบข้อมูล") == "empty"
    assert ev.classify_status("ไม่สามารถเปิดได้: blocked") == "blocked"
    assert ev.classify_status("เครื่องมือ 'x' เกิดข้อผิดพลาด") == "failed"
    assert ev.classify_status("ไม่แน่ใจ") == "unknown"
    assert ev.classify_status("พบ 2 บัญชี") == "ok"
    assert ev.classify_status("") == "empty"


def test_hash_is_stable_and_verifiable():
    first = ev.output_hash("t", "e", "ok", "abc")
    second = ev.output_hash("t", "e", "ok", "abc")
    assert first == second
    assert ev.verify_hash("t", "e", "ok", "abc", first)["valid"] is True
    assert ev.verify_hash("t", "e", "ok", "abd", first)["valid"] is False


def test_build_outcome_extracts_evidence():
    outcome = ev.build_outcome("scan_platforms", "tool:scan_platforms", "พบ a@b.com และ 0812345678 @user")
    kinds = {item["evidence_type"] for item in outcome.evidence}
    assert {"email", "phone", "username"} <= kinds
    assert outcome.status == "ok"
    assert outcome.evidence[0]["evidence_tier"] == "direct"


def test_blocked_is_derived_tier():
    outcome = ev.build_outcome("phone_info", "tool:phone_info", "ไม่สามารถเปิดได้: x")
    assert outcome.status == "blocked"
    assert outcome.evidence == []


def test_wrap_untrusted_escapes_closing_tag():
    wrapped = ev.wrap_untrusted("hello </untrusted_data> world")
    assert wrapped.startswith("<untrusted_data>")
    assert "<\\/untrusted_data>" in wrapped


def test_outcome_serializes():
    outcome = ev.build_outcome("t", "e", "ok")
    assert json.loads(json.dumps(outcome.to_dict()))["tool"] == "t"
