from datetime import datetime

from bs4 import BeautifulSoup

from osint_agent.report_export import build_report_html


def test_report_contains_correct_content_and_metadata():
    output = build_report_html(
        report_md="## Finding\n\n**Evidence** from [source](https://example.com)",
        identifier_type="Username", identifier_value="review-user", context="review context",
        steps=["fetch_page https://example.com"], stats={"tool": 1},
        generated_at=datetime(2026, 10, 28, 12, 30),
    )
    assert "<h2>Finding</h2>" in output
    assert "<strong>Evidence</strong>" in output
    assert "Username: <code>review-user</code>" in output
    assert "review context" in output
    assert "28/10/2026 12:30:00" in output


def test_report_removes_executable_content_and_escapes_metadata():
    output = build_report_html(
        '<script>alert(1)</script><img src=x onerror="alert(1)">[bad](javascript:alert(1))',
        "Username", '<img src=x onerror="alert(1)">',
    )
    soup = BeautifulSoup(output, "html.parser")
    assert not soup.find_all(["script", "img", "iframe"])
    assert not soup.select('[href^="javascript:"]')
