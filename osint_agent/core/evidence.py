"""สัญญา evidence กลาง: สร้าง evidence จากผล tool, hash และตรวจสอบ"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from vendor.synint.core.schemas import EvidenceItem

from ..tools.base import EMAIL_RE, HANDLE_RE, PHONE_RE, URL_RE

TIERS = {"direct", "derived", "inferred", "enrichment"}

STATUS_EMPTY = ("ไม่พบ", "ไม่ตรงกับ", "ไม่สามารถสร้าง variants")
STATUS_BLOCKED = ("ไม่สามารถเปิดได้", "ถูกบล็อก", "HTTP 403", "HTTP 429", "ต้องล็อกอิน")
STATUS_FAILED = ("เกิดข้อผิดพลาด", "ข้อผิดพลาด", "เรียกไม่สำเร็จ", "ไม่สำเร็จ")
STATUS_UNKNOWN = ("ไม่แน่ใจ", "ยังสรุปไม่ได้", "ยืนยันไม่ได้")


def classify_status(output: str) -> str:
    text = (output or "").strip()
    if not text:
        return "empty"
    for marker in STATUS_FAILED:
        if marker in text:
            return "failed"
    for marker in STATUS_BLOCKED:
        if marker in text:
            return "blocked"
    for marker in STATUS_EMPTY:
        if marker in text:
            return "empty"
    for marker in STATUS_UNKNOWN:
        if marker in text:
            return "unknown"
    return "ok"


def canonical_payload(tool: str, endpoint: str, status: str, result: str) -> str:
    return json.dumps(
        {"tool": tool, "endpoint": endpoint, "status": status, "result": result},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def output_hash(tool: str, endpoint: str, status: str, result: str) -> str:
    digest = hashlib.sha256(canonical_payload(tool, endpoint, status, result).encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def verify_hash(tool: str, endpoint: str, status: str, result: str, claimed: str) -> dict:
    actual = output_hash(tool, endpoint, status, result)
    return {"valid": actual == claimed, "expected_hash": actual, "claimed_hash": claimed}


@dataclass
class ToolOutcome:
    tool: str
    endpoint: str
    status: str
    result: str
    output_hash: str
    evidence: list[dict] = field(default_factory=list)
    images: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "endpoint": self.endpoint,
            "status": self.status,
            "result": self.result,
            "output_hash": self.output_hash,
            "evidence": self.evidence,
            "images": self.images,
        }


def _tier_for(status: str, tool: str) -> tuple[str, float]:
    if status == "failed":
        return "inferred", 0.2
    if status in {"empty", "blocked", "unknown"}:
        return "derived", 0.35
    if tool in {"scan_platforms", "sherlock_username", "fetch_page", "web_search"}:
        return "direct", 0.6
    return "direct", 0.7


def _items(tool: str, endpoint: str, output: str, status: str) -> list[dict]:
    tier, base = _tier_for(status, tool)
    found: list[tuple[str, str]] = []
    found += [("phone", phone) for phone in PHONE_RE.findall(output)]
    found += [("email", email.lower()) for email in EMAIL_RE.findall(output)]
    found += [("username", handle) for handle in HANDLE_RE.findall(output)]
    found += [("url", url) for url in URL_RE.findall(output)]

    seen = set()
    items = []
    for kind, value in found:
        key = (kind, value.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append(
            EvidenceItem(
                source_agent=tool,
                evidence_type=kind,
                value=value,
                normalized_value=value.lower(),
                confidence=base,
                source_reference=endpoint,
                evidence_tier=tier,
                supporting_context={"status": status},
            ).to_dict()
        )
    return items


def build_outcome(tool: str, endpoint: str, output: str, images: list | None = None) -> ToolOutcome:
    result = output or ""
    status = classify_status(result)
    return ToolOutcome(
        tool=tool,
        endpoint=endpoint,
        status=status,
        result=result,
        output_hash=output_hash(tool, endpoint, status, result),
        evidence=_items(tool, endpoint, result, status),
        images=images or [],
    )


def wrap_untrusted(text: str) -> str:
    return "<untrusted_data>\n" + text.replace("</untrusted_data", "<\\/untrusted_data") + "\n</untrusted_data>"


def clean_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (text or "").strip())
