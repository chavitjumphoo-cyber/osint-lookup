from unittest.mock import Mock

import pytest
import requests

from osint_agent import platform_scanner as scanner

URL = "https://example.com/review-user"


def response(html="", status=200, url=URL):
    return Mock(status_code=status, url=url, text=html)


@pytest.mark.parametrize("page", [
    "<title>Sign in</title><form>Login</form>",
    "<title>User not found</title>",
    "<title>Generic landing page</title>",
    '<meta property="og:type" content="profile"><meta property="og:url" content="https://example.com/other-user">',
    '<meta property="profile:username" content="other-user"><meta property="og:type" content="profile"><meta property="og:url" content="https://example.com/review-user">',
])
def test_status_200_without_matching_evidence_is_unknown(page, monkeypatch):
    reply = response(page)
    monkeypatch.setattr(scanner, "safe_get", lambda *args, **kwargs: reply)
    result = scanner.PlatformScanner("Example", "https://example.com/{identifier}").check("review-user")
    assert result["found"] is False
    assert result["status"] == "unknown"
    reply.close.assert_called_once()


def test_matching_profile_metadata_is_found(monkeypatch):
    reply = response('<meta name="octolytics-dimension-user_login" content="review-user">')
    monkeypatch.setattr(scanner, "safe_get", lambda *args, **kwargs: reply)
    result = scanner.PlatformScanner("Example", "https://example.com/{identifier}").check("review-user")
    assert result["found"] is True
    assert result["data"]["checked_url"] == URL


def test_redirect_to_login_is_unknown(monkeypatch):
    reply = response('<meta property="og:type" content="profile">', url="https://example.com/login")
    monkeypatch.setattr(scanner, "safe_get", lambda *args, **kwargs: reply)
    assert scanner.PlatformScanner("Example", "https://example.com/{identifier}").check("review-user")["found"] is False


@pytest.mark.parametrize("status", [404, 410])
def test_explicit_not_found_returns_none(status, monkeypatch):
    monkeypatch.setattr(scanner, "safe_get", lambda *args, **kwargs: response(status=status))
    assert scanner.PlatformScanner("Example", "https://example.com/{identifier}").check("review-user") is None


def test_timeout_is_unknown_not_missing(monkeypatch):
    monkeypatch.setattr(scanner, "safe_get", Mock(side_effect=requests.Timeout()))
    result = scanner.PlatformScanner("Example", "https://example.com/{identifier}").check("review-user")
    assert result["status"] == "unknown"


def test_scan_preserves_found_list_and_reports_unknown_separately(monkeypatch):
    found = {"platform": "Found", "url": URL, "found": True, "status": "found", "data": {}}
    unknown = {"platform": "Unknown", "url": URL, "found": False, "status": "unknown", "data": {}}
    monkeypatch.setattr(scanner, "PLATFORMS", [
        Mock(identifier_type="username", check=Mock(return_value=found)),
        Mock(identifier_type="username", check=Mock(return_value=unknown)),
    ])
    monkeypatch.setattr(scanner.time, "sleep", lambda duration: None)
    assert scanner.scan_multi_platform("review-user") == [found]
    result = scanner.scan_username_advanced("review-user")
    assert result["platforms_found"] == [found]
    assert result["platforms_unknown"] == [unknown]
    assert result["total_found"] == 1
    assert "ห้ามสรุป" in scanner.format_scan_results(result)
