from osint_agent.services import report_builder


def _run(**kw):
    base = {"id": "r1", "target": "example.com", "target_type": "domain", "profile": "quick", "status": "done"}
    base.update(kw)
    return base


def _evidence(kind="domain", value="example.com", tier="direct", source="dns_lookup"):
    return {
        "id": "ev1",
        "evidence_type": kind,
        "value": value,
        "evidence_tier": tier,
        "source_agent": source,
        "source_reference": "tool:dns_lookup",
        "supporting_context": {"output_hash": "sha256:abc"},
    }


def test_report_contains_required_sections():
    report = report_builder.build_report(
        _run(),
        [_evidence(), _evidence(kind="ip", value="1.2.3.4", source="dns_lookup")],
        [{"tool": "dns_lookup", "status": "ok", "output": "A 1.2.3.4", "output_hash": "sha256:abc"}],
        [{"candidate_id": "c1", "status": "CANDIDATE", "entity_ids": ["e1"]}],
    )
    assert "ข้อจำกัดของรายงานนี้" in report
    assert "<untrusted_data>" in report
    assert "sha256:abc" in report
    assert "Identity candidates" in report
    assert "Confirmed" in report  # same type from one source but direct -> Probable; two types no. check below
    assert "Probable" in report


def test_report_maps_tiers_to_confidence_vocabulary():
    report = report_builder.build_report(_run(), [_evidence(tier="inferred", source="x")], [], [])
    assert "Inferred" in report


def test_report_limitations_note_blocked():
    report = report_builder.build_report(
        _run(), [], [{"tool": "x", "status": "blocked", "output": "", "output_hash": ""}], []
    )
    assert "ถูกบล็อก" in report


def test_llm_polish_can_be_disabled(monkeypatch):
    monkeypatch.setenv("OSINT_LLM_REPORT", "0")
    assert report_builder.llm_polish("draft", []) == "draft"
