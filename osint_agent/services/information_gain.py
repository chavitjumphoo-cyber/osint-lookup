"""จัดอันดับ lead ตามโอกาสได้ข้อมูลใหม่ ไม่ใช่แค่จำนวนครั้งที่พบ"""

from __future__ import annotations

SOURCE_QUALITY = {
    "profile": 1.0,
    "post": 0.9,
    "page": 0.7,
    "search_result": 0.5,
}
TYPE_WEIGHT = {
    "email": 1.0,
    "phone": 0.98,
    "url": 0.9,
    "username": 0.85,
    "name": 0.7,
    "family_name": 0.6,
    "organization": 0.65,
    "location": 0.5,
}


def score(lead: dict, seen: set[str], artifact: dict | None = None) -> float:
    value = str(lead.get("value") or "").lower()
    novelty = 0.1 if value in seen else 0.3
    source_type = (artifact or {}).get("source_type", lead.get("source_type", "search_result"))
    base = TYPE_WEIGHT.get(lead.get("type", ""), 0.4)
    quality = SOURCE_QUALITY.get(source_type, 0.5)
    direct = 0.15 if lead.get("reason") else 0.0
    return round(min(1.0, base * 0.55 + quality * 0.2 + novelty + direct), 3)


def rank(leads: list[dict], seen: set[str]) -> list[dict]:
    return sorted(leads, key=lambda lead: score(lead, seen), reverse=True)
