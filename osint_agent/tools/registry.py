"""ทะเบียน tool แบบ lazy import — tool ใดพังไม่ลากทั้งระบบ"""

import importlib

from .base import plain

# name -> (module, schema_attr, run_attr, argument extractor)
TOOLS = {
    "web_search": ("search", "web_search_schema", "run_web_search", ("query", "num_results", "lang", "region")),
    "scan_platforms": ("analysis", "scan_platforms_schema", "run_scan_platforms", ("username",)),
    "sherlock_username": ("search", "sherlock_schema", "run_sherlock", ("username",)),
    "fetch_page": ("http", "fetch_page_schema", "run_fetch", ("url", "focus")),
    "extract_entities": ("search", "extract_entities_schema", "run_extract_entities", ("text",)),
    "phone_info": ("phone", "phone_info_schema", "run_phone_info", ("number",)),
    "verify_official": ("phone", "verify_official_schema", "run_verify_official", ("value", "claimed_entity")),
    "breach_check": ("breach", "breach_check_schema", "run_breach_check", ("email",)),
    "scan_phone_advanced": ("phone", "scan_phone_advanced_schema", "run_scan_phone_advanced", ("phone_number",)),
    "compare_avatars": ("analysis", "compare_avatars_schema", "run_compare_avatars", ("avatar_url_1", "avatar_url_2")),
    "correlate_stylometry": ("analysis", "correlate_stylometry_schema", "run_correlate_stylometry", ("text1", "text2")),
    "username_correlation": ("analysis", "username_correlation_schema", "run_username_correlation", ("username", "collected_text")),
    "email_harvest": ("analysis", "email_harvest_schema", "run_email_harvest", ("domain", "first_name", "last_name")),
    "identity_candidate": ("analysis", "identity_candidate_schema", "run_identity_candidate", ("entities_json",)),
    "darkweb_monitor": ("analysis", "darkweb_monitor_schema", "run_darkweb_monitor", ("target",)),
    "dns_lookup": ("intel", "dns_lookup_schema", "run_dns_lookup", ("domain",)),
    "whois_lookup": ("intel", "whois_lookup_schema", "run_whois_lookup", ("domain",)),
    "wayback_lookup": ("intel", "wayback_lookup_schema", "run_wayback_lookup", ("url", "limit")),
    "github_intel": ("intel", "github_intel_schema", "run_github_intel", ("username",)),
    "gravatar_lookup": ("intel", "gravatar_lookup_schema", "run_gravatar_lookup", ("email",)),
    "search_evidence": ("memory", "search_evidence_schema", "run_search_evidence", ("run_id", "query")),
    "verify_output_integrity": (
        "integrity",
        "verify_output_integrity_schema",
        "run_verify_output_integrity",
        ("tool", "endpoint", "status", "result", "output_hash"),
    ),
}


# ชื่อเดิม → ชื่อใหม่ (ไม่สร้าง schema ซ้ำ)
ALIASES = {"google_search": "web_search"}


def canonical(name: str) -> str:
    return ALIASES.get(name, name)


def _module(name: str):
    return importlib.import_module(f".{TOOLS[name][0]}", __package__)


def build_tool_list():
    """คืน schema ของ tool ทั้งหมด — ข้ามตัวที่ import ไม่ได้ พร้อมเหตุผล"""
    schemas = []
    for name, (_mod, schema_attr, _run, _args) in TOOLS.items():
        try:
            schema_fn = getattr(_module(name), schema_attr)
            schemas.append(schema_fn())
        except Exception:  # noqa: BLE001 — dep ที่ขาดต้องไม่ทำให้ tool อื่นหาย
            continue
    return schemas


def _arguments(name: str, tool_input: dict) -> list:
    _, _, _, specs = TOOLS[name]
    values = []
    for key in specs:
        value = tool_input.get(key)
        if key in ("num_results",):
            values.append(int(value) if value not in (None, "") else 10)
        else:
            values.append("" if value is None else str(value))
    return values


def execute_tool(name: str, tool_input: dict) -> dict:
    """คืน {"output": str, "images": [...]} — ต้องไม่ raise"""
    name = canonical(name)
    if name not in TOOLS:
        return plain(f"ไม่รู้จักเครื่องมือชื่อ '{name}'")

    try:
        module = _module(name)
        runner = getattr(module, TOOLS[name][2])
        return runner(*_arguments(name, tool_input))
    except Exception as exc:  # noqa: BLE001 — tool ต้องไม่ทำให้ agent ล้ม
        return plain(f"เครื่องมือ '{name}' เกิดข้อผิดพลาด: {type(exc).__name__}: {exc}")
