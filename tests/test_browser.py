import json
import subprocess

import pytest

from osint_agent.services import browser


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    monkeypatch.delenv("MOLI_BIN", raising=False)


def test_unavailable_without_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(browser.shutil, "which", lambda _name: None)
    monkeypatch.setattr(browser, "FALLBACK_PATHS", (tmp_path / "missing",))
    assert browser.available() is False
    with pytest.raises(browser.BrowserError):
        browser.fetch_json("https://example.com")


def test_fetch_json_parses_payload(monkeypatch):
    class Proc:
        returncode = 0
        stdout = json.dumps({"status": 200, "final_url": "https://x.test/", "html": "<p>hi</p>", "title": "T"})
        stderr = ""

    monkeypatch.setattr(browser, "resolve_binary", lambda: "/bin/moli")
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **k: Proc())
    page = browser.fetch_json("https://x.test")
    assert page.status == 200
    assert page.engine == "moli"
    assert "hi" in page.html


def test_fetch_error_carries_stderr(monkeypatch):
    class Proc:
        returncode = 1
        stdout = ""
        stderr = "Reason: blocked private network address"

    monkeypatch.setattr(browser, "resolve_binary", lambda: "/bin/moli")
    monkeypatch.setattr(browser.subprocess, "run", lambda *a, **k: Proc())
    with pytest.raises(browser.BrowserError, match="blocked private"):
        browser.fetch_json("http://127.0.0.1")


def test_timeout_raises(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("moli", 1)

    monkeypatch.setattr(browser, "resolve_binary", lambda: "/bin/moli")
    monkeypatch.setattr(browser.subprocess, "run", boom)
    with pytest.raises(browser.BrowserError, match="เกิน"):
        browser.fetch_json("https://x.test")


def test_fallback_marks_engine(monkeypatch):
    class Response:
        status_code = 200
        url = "https://x.test/"
        headers = {"Content-Type": "text/html"}
        text = "<p>fallback</p>"

    monkeypatch.setattr("osint_agent.tools.http.safe_get", lambda *a, **k: Response())
    page = browser.fetch_fallback("https://x.test")
    assert page.engine == "requests-fallback"
    assert "fallback" in page.html
