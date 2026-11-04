from osint_agent import platform_scanner as ps


def test_404_is_not_found():
    assert ps._classify(ps.PLATFORMS[0], 404, "") == "not_found"


def test_403_is_blocked():
    assert ps._classify(ps.PLATFORMS[0], 403, "") == "blocked"


def test_200_without_marker_is_unknown():
    platform = ps.Platform("X", "https://example.com/{identifier}")
    assert ps._classify(platform, 200, "<html>ok</html>") == "unknown"


def test_not_found_marker_wins():
    platform = ps.Platform("X", "https://example.com/{identifier}", not_found_marker="not found")
    assert ps._classify(platform, 200, "Sorry, page not found") == "not_found"


def test_required_marker_missing_is_not_found():
    platform = ps.Platform(
        "X", "https://example.com/{identifier}", found_marker="profile", found_marker_required=True
    )
    assert ps._classify(platform, 200, "<html>empty</html>") == "not_found"


def test_required_marker_present_is_found():
    platform = ps.Platform(
        "X", "https://example.com/{identifier}", found_marker="profile", found_marker_required=True
    )
    assert ps._classify(platform, 200, "<div class=profile>") == "found"


def test_format_reports_unknown_separately():
    results = {
        "identifier": "user",
        "identifier_type": "username",
        "scan_time": 1.0,
        "counts": {"found": 1, "not_found": 0, "blocked": 0, "unknown": 1, "error": 0},
        "results": [
            ps.PlatformResult("A", "https://a/u", "found"),
            ps.PlatformResult("B", "https://b/u", "unknown"),
        ],
    }
    text = ps.format_scan_results(results)
    assert "พบโปรไฟล์" in text
    assert "ยืนยันไม่ได้" in text
    assert "ไม่ใช่หลักฐานว่าไม่มีบัญชี" in text
