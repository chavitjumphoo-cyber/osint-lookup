"""สกัดเอนทิตีและสัญญาณโปรไฟล์จากข้อความ

regex เป็นหลัก, ใช้ LLM เสริมเมื่อมี key — ทุกฟิลด์คืนพร้อมหลักฐานกำกับที่ผู้เรียก
"""

from __future__ import annotations

import json
import re

from ..tools.base import EMAIL_RE, HANDLE_RE, PHONE_RE, URL_RE

THAI_PROVINCES = [
    "กรุงเทพ", "เชียงใหม่", "เชียงราย", "ขอนแก่น", "นครราชสีมา", "ชลบุรี", "ภูเก็ต", "สงขลา",
    "นครปฐม", "ปทุมธานี", "นนทบุรี", "สมุทรปราการ", "ระยอง", "อุดรธานี", "หาดใหญ่",
]
CITY_WORDS = {"bangkok": "Bangkok", "chiang mai": "Chiang Mai", "phuket": "Phuket", "pattaya": "Pattaya", "khon kaen": "Khon Kaen", "hat yai": "Hat Yai", "nonthaburi": "Nonthaburi"}

INTERESTS = {
    "crypto": ["crypto", "bitcoin", "ethereum", "blockchain", "คริปโต"],
    "trading": ["forex", "stock", "trader", "ลงทุน", "หุ้น"],
    "gaming": ["gamer", "gaming", "steam", "valorant", "roblox", "เกม"],
    "tech": ["developer", "python", "javascript", "devops", "programmer", "เขียนโปรแกรม"],
    "travel": ["travel", "backpacker", "ท่องเที่ยว"],
    "fitness": ["gym", "fitness", "มวย", "วิ่ง"],
    "football": ["football", "บอล", "เชียร์", "mufc", "liverpool"],
    "cars": ["car", "bike", "บิ๊กไบค์", "รถยนต์"],
    "beauty": ["beauty", "makeup", "ความงาม", "สกินแคร์"],
}

NAME_STOPWORDS = {
    "The", "This", "That", "New", "Free", "Best", "Top", "Home", "About", "Contact",
    "Login", "Sign", "Privacy", "Terms", "Facebook", "Instagram", "GitHub", "Google",
}
NAME_RE = re.compile(r"\b(?:[A-Z][a-z]{1,20}|[ก-๙]{2,20})(?:\s+(?:[A-Z][a-z]{1,20}|[ก-๙]{2,20})){1,2}\b")
DATE_RE = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/(?:25|26)\d{2}|\d{1,2}\s+(?:ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*(?:25|26)\d{2})\b"
)


def _extract_names(text: str, limit: int = 6) -> list[str]:
    names = []
    for match in NAME_RE.finditer(text):
        value = match.group(0).strip()
        if value.split()[0] in NAME_STOPWORDS:
            continue
        if len(value) < 5:
            continue
        if value not in names:
            names.append(value)
        if len(names) >= limit:
            break
    return names


def extract(text: str) -> dict:
    lowered = (text or "").lower()
    locations = [p for p in THAI_PROVINCES if p in text] + [label for key, label in CITY_WORDS.items() if key in lowered]
    interests = [name for name, words in INTERESTS.items() if any(word in lowered for word in words)]

    orgs = []
    for pattern in (
        r"(?:works? at|working at|employed at|@)\s+([A-Z][\w&.\- ]{2,40})",
        r"(?:บริษัท|ที่ทำงาน)\s*([\wก-๙&.\- ]{2,40})",
    ):
        for match in re.finditer(pattern, text or ""):
            org = match.group(1).strip(" .,-")
            if org and org not in orgs:
                orgs.append(org)

    return {
        "names": _extract_names(text),
        "emails": sorted({m.group(0).lower() for m in EMAIL_RE.finditer(text or "")}),
        "phones": sorted({re.sub(r"[\s-]", "", m.group(0)) for m in PHONE_RE.finditer(text or "")}),
        "handles": sorted({m.group(0) for m in HANDLE_RE.finditer(text or "")}),
        "urls": sorted({m.group(0) for m in URL_RE.finditer(text or "")}),
        "locations": list(dict.fromkeys(locations)),
        "organizations": orgs[:5],
        "interests": interests,
        "dates": DATE_RE.findall(text or "")[:10],
    }


def extract_with_llm(text: str, source_url: str = "", client=None) -> dict:
    """สกัดแบบมีโครงสร้างด้วย Claude — คืน {} เมื่อไม่มี key/ล้มเหลว"""
    try:
        from vendor._compat import complete_text

        raw = complete_text(
            "สกัดข้อมูลโปรไฟล์จากข้อความ ตอบ JSON เท่านั้นตาม schema: "
            '{"names":[],"bio":"","locations":[],"organizations":[],"interests":[],'
            '"dates":[],"emails":[],"phones":[],"handles":[]} '
            "ห้ามแต่งข้อมูลที่ไม่มีในข้อความ",
            [{"role": "user", "content": (text or "")[:6000]}],
            max_tokens=1200,
            client=client,
        )
        match = re.search(r"\{.*\}", raw, re.S)
        return json.loads(match.group(0)) if match else {}
    except Exception:  # noqa: BLE001
        return {}


def merge(structured: dict, extra: dict) -> dict:
    merged = {key: list(structured.get(key) or []) for key in structured}
    for key, values in extra.items():
        if isinstance(values, list):
            for value in values:
                if value and value not in merged.setdefault(key, []):
                    merged[key].append(value)
        elif values and not merged.get(key):
            merged[key] = values
    return merged
