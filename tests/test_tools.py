import time

import pytest

from osint_agent import tools
from osint_agent.graph import _parse_json_block, _sanitize


@pytest.mark.parametrize(
    "host",
    ["localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "0.0.0.0", "::1"],
)
def test_private_hosts_blocked(host):
    assert tools._is_public_host(host) is False


def test_empty_host_blocked():
    assert tools._is_public_host("") is False


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.com", "http://127.0.0.1/admin", "http://169.254.169.254/latest"]
)
def test_check_url_rejects_unsafe(url):
    with pytest.raises(tools.UnsafeURLError):
        tools._check_url(url)


def test_fetch_page_rejects_internal_url():
    out = tools.execute_tool("fetch_page", {"url": "http://127.0.0.1:8501"})
    assert "ไม่สามารถเปิดได้" in out["output"]
    assert out["images"] == []


@pytest.mark.parametrize("name", ["somchai_99", "a.b-c", "X" * 64])
def test_username_valid(name):
    assert tools.USERNAME_RE.match(name)


@pytest.mark.parametrize("name", ["--json", "-v", "a b", "a;rm -rf", "", "x" * 65, "../etc", ".hidden"])
def test_username_rejected(name):
    assert not tools.USERNAME_RE.match(name)


def test_sherlock_rejects_argument_injection():
    out = tools.execute_tool("sherlock_username", {"username": "--json x"})
    assert "อักขระที่ไม่อนุญาต" in out["output"]


def test_rate_limiter_spaces_same_domain():
    limiter = tools.DomainRateLimiter(min_interval=0.2, jitter=0)
    limiter.wait("example.com")
    start = time.monotonic()
    limiter.wait("example.com")
    assert time.monotonic() - start >= 0.18


def test_rate_limiter_independent_domains():
    limiter = tools.DomainRateLimiter(min_interval=1.0, jitter=0)
    limiter.wait("a.com")
    start = time.monotonic()
    limiter.wait("b.com")
    assert time.monotonic() - start < 0.1


def test_phone_info_mobile():
    out = tools.execute_tool("phone_info", {"number": "081-234-5678"})["output"]
    assert "+66812345678" in out
    assert "มือถือ" in out


def test_phone_info_invalid():
    out = tools.execute_tool("phone_info", {"number": "1234"})["output"]
    assert "ไม่ใช่" in out


def test_verify_official_real_domain():
    # KBank ยังไม่ได้ยืนยัน — ควรแสดงว่าอยู่ในรายการอ้างอิงแต่ยังไม่ยืนยัน
    out = tools.execute_tool("verify_official", {"value": "https://www.kasikornbank.com/th"})["output"]
    assert "ตรงกับโดเมนของ" in out and "กสิกร" in out and "ยังไม่ได้ยืนยัน" in out


def test_verify_official_verified_domain():
    # SCB ยืนยันแล้ว — ควรแสดง verified label
    out = tools.execute_tool("verify_official", {"value": "https://www.scb.co.th"})["output"]
    assert "เป็นโดเมนทางการของ" in out and "ไทยพาณิชย์" in out and "ยืนยันจากหน้าเว็บทางการ" in out


def test_verify_official_verified_phone():
    # SCB call center ยืนยันแล้ว
    out = tools.execute_tool("verify_official", {"value": "0 2777 7777"})["output"]
    assert "ตรงกับเบอร์ทางการของ" in out and "ไทยพาณิชย์" in out and "ยืนยันจากหน้าเว็บทางการ" in out


def test_verify_official_unverified_bank():
    # KBank อยู่ในรายการแต่ยังไม่ยืนยัน — เบอร์ 02 8888 888 ไม่มีใน phones: [] ของ KBank จึงควร fail
    out = tools.execute_tool("verify_official", {"value": "02 8888 888"})["output"]
    assert "ไม่ตรงกับเบอร์ทางการในรายการอ้างอิง" in out


def test_verify_official_lookalike_domain():
    out = tools.execute_tool("verify_official", {"value": "kasikornbank-th-secure.com"})["output"]
    assert "ไม่ใช่โดเมนทางการ" in out


def test_verify_official_real_phone():
    # ttb (verified) — เบอร์ 1428
    out = tools.execute_tool("verify_official", {"value": "1428"})["output"]
    assert "ตรงกับเบอร์ทางการของ" in out and "ทีทีบี" in out and "ยืนยันจากหน้าเว็บทางการ" in out


def test_verify_official_unknown_phone():
    out = tools.execute_tool("verify_official", {"value": "0899999999", "claimed_entity": "ธนาคารกสิกรไทย"})["output"]
    assert "ไม่ตรงกับเบอร์ทางการ" in out


def test_breach_check_rejects_bad_email():
    out = tools.execute_tool("breach_check", {"email": "not-an-email"})["output"]
    assert "ไม่ใช่รูปแบบอีเมล" in out


def test_extract_entities():
    out = tools.execute_tool(
        "extract_entities", {"text": "โทร 0812345678 เมล a@b.com https://x.com/abc @scam_page"}
    )["output"]
    assert "0812345678" in out and "a@b.com" in out and "@scam_page" in out


def test_unknown_tool():
    assert "ไม่รู้จักเครื่องมือ" in tools.execute_tool("nope", {})["output"]


def test_graph_sanitize_drops_dangling_edges():
    data = {
        "nodes": [{"id": "target", "label": "T", "group": "identifier"}, {"id": "a", "label": "A", "group": "weird"}],
        "edges": [
            {"from": "target", "to": "a", "label": "x", "confidence": "high"},
            {"from": "target", "to": "missing", "label": "y"},
        ],
    }
    clean = _sanitize(data)
    assert len(clean["edges"]) == 1
    assert clean["nodes"][1]["group"] == "other"


def test_graph_parse_fenced_json():
    assert _parse_json_block('```json\n{"nodes": [], "edges": []}\n```') == {"nodes": [], "edges": []}
