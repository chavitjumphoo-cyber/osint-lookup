from osint_agent import tools
from osint_agent.tools import registry


def test_build_tool_list_skips_broken_tool(monkeypatch):
    def boom(_name):
        raise ImportError("missing dep")

    monkeypatch.setattr(registry, "_module", boom)
    assert registry.build_tool_list() == []


def test_build_tool_list_has_all_tools():
    names = {schema["name"] for schema in tools.build_tool_list()}
    assert names == set(registry.TOOLS)


def test_unknown_tool_is_safe():
    out = tools.execute_tool("nope", {})
    assert "ไม่รู้จักเครื่องมือ" in out["output"]


def test_tool_error_does_not_raise(monkeypatch):
    def boom(_name):
        raise ImportError("missing dep")

    monkeypatch.setattr(registry, "_module", boom)
    out = tools.execute_tool("phone_info", {"number": "0812345678"})
    assert "เกิดข้อผิดพลาด" in out["output"]


def test_scan_phone_advanced_uses_associated_names():
    out = tools.execute_tool("scan_phone_advanced", {"phone_number": "0812345678"})
    assert "ผิดพลาด" not in out["output"]
    assert "+66812345678" in out["output"]
