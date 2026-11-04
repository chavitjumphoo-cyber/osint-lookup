from osint_agent.profiling import research_report


def _run():
    return {"id": "r1", "target": "jdoe", "target_type": "username", "profile": "quick", "status": "done"}


def test_report_contains_required_sections_and_real_stats():
    artifacts = [{"artifact_id": "a1", "source_type": "search_result", "platform": "github", "content": "x"}]
    markdown = research_report.build_markdown(_run(), artifacts, [{"status": "blocked"}], [], [])
    for heading in ("บทคัดย่อ", "วิธีดำเนินการ", "ผลการวิจัย", "ข้อจำกัด", "เอกสารอ้างอิง"):
        assert heading in markdown
    assert "| blocked | 1 |" in markdown


def test_docx_export(tmp_path):
    markdown = research_report.build_markdown(_run(), [], [], [], [])
    path = research_report.to_docx(markdown, tmp_path / "r.docx")
    assert path.exists() and path.stat().st_size > 1000
