"""Advanced OSINT Tools — ตามแนวคิด osint-d2
- scan_phone: WhatsApp status check + multi-platform footprint
- compare_avatars: perceptual dHash matching
- stylometry: character n-gram author correlation
"""

import asyncio
import hashlib
import io
import re
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx
import phonenumbers
import requests
from phonenumbers import PhoneNumberType, carrier, geocoder, timezone
from PIL import Image

# Import enhanced phone scanner
from .phone_enhanced import enhanced_phone_scan as _enhanced_scan


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phone Scanner (WhatsApp + Footprint)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class PhoneScanResult:
    raw_input: str
    e164: str
    is_valid: bool
    country_code: int
    country_iso: str
    country_name: str
    carrier_name: str
    line_type: str
    timezones: list[str]
    whatsapp_active: bool | None = None
    whatsapp_url: str | None = None
    footprint_urls: dict[str, str] = field(default_factory=dict)
    associated_names: list[str] = field(default_factory=list)
    error: str | None = None


def _get_line_type_name(num_type: PhoneNumberType) -> str:
    mapping = {
        PhoneNumberType.MOBILE: "มือถือ",
        PhoneNumberType.FIXED_LINE: "โทรศัพท์บ้าน",
        PhoneNumberType.FIXED_LINE_OR_MOBILE: "โทรศัพท์/มือถือ",
        PhoneNumberType.TOLL_FREE: "เบอร์ฟรี",
        PhoneNumberType.VOIP: "VoIP",
        PhoneNumberType.PERSONAL_NUMBER: "เบอร์ส่วนตัว",
    }
    return mapping.get(num_type, "ไม่ทราบ")


def _generate_phone_formats(parsed_num: phonenumbers.PhoneNumber) -> list[str]:
    """สร้างรูปแบบเบอร์หลายแบบสำหรับค้นหา"""
    e164 = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
    national = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.NATIONAL)
    digits_only = re.sub(r"\D", "", e164)
    local_digits = digits_only[len(str(parsed_num.country_code)) :]

    formats = [
        e164,  # +66812345678
        national,  # 081 234 5678
        digits_only,  # 66812345678
        local_digits,  # 812345678
        f"0{local_digits}",  # 0812345678
    ]
    seen = set()
    out = []
    for f in formats:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


async def scan_phone(phone_number: str, default_region: str = "TH") -> PhoneScanResult:
    """สแกนเบอร์โทรศัพท์ — Enhanced version พร้อม Thai carrier detection + GetContact + Fraud databases"""

    # ใช้ enhanced scanner
    result = _enhanced_scan(phone_number, default_region)

    # Handle error cases
    if "error" in result:
        return PhoneScanResult(
            raw_input=phone_number,
            e164=result.get("e164", ""),
            is_valid=False,
            country_code=0,
            country_iso="",
            country_name="",
            carrier_name="",
            line_type="รูปแบบไม่ถูกต้อง",
            timezones=[],
            error=result["error"],
        )

    e164 = result["e164"]
    clean_digits = re.sub(r"\D", "", e164)
    footprints = result["footprints"]

    # ตรวจ WhatsApp (probe wa.me)
    whatsapp_active = None
    wa_url = footprints["whatsapp"]
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(wa_url)
            if resp.status_code == 200:
                if "action-send" in resp.text or "send?phone=" in resp.text or "Chat on WhatsApp" in resp.text:
                    whatsapp_active = True
                else:
                    whatsapp_active = False
    except Exception:
        whatsapp_active = None

    # ค้นหา DuckDuckGo เพื่อหาชื่อที่เกี่ยวข้อง
    discovered_names: list[str] = []
    try:
        parsed = phonenumbers.parse(phone_number.strip(), default_region)
        variations = _generate_phone_formats(parsed)
        query_parts = "+OR+".join(f'%22{urllib.parse.quote(v)}%22' for v in variations[:3])

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            ddg_url = f"https://html.duckduckgo.com/html/?q={query_parts}"
            resp = await client.get(ddg_url)
            if resp.status_code == 200:
                text_lower = resp.text.lower()
                name_patterns = [
                    r'<a class="result__a"[^>]*>([^<]+)</a>',
                    r'<b>([A-Z][a-z]+ [A-Z][a-z]+)</b>',
                ]
                for pat in name_patterns:
                    matches = re.findall(pat, resp.text, re.IGNORECASE)
                    discovered_names.extend(m.strip() for m in matches if len(m.strip()) > 5)
    except Exception:
        pass

    discovered_names = list(dict.fromkeys(discovered_names))[:5]

    return PhoneScanResult(
        raw_input=phone_number,
        e164=e164,
        is_valid=result["is_valid"],
        country_code=result["country_code"],
        country_iso=result["country_iso"],
        country_name=result["country_name"],
        carrier_name=result["carrier_name"],
        line_type=result["line_type"],
        timezones=result["timezones"],
        whatsapp_active=whatsapp_active,
        footprint_urls=footprints,
        discovered_names=discovered_names,
    )

    is_valid = phonenumbers.is_valid_number(parsed)
    if not is_valid:
        return PhoneScanResult(
            raw_input=phone_number,
            e164=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            is_valid=False,
            country_code=parsed.country_code or 0,
            country_iso=phonenumbers.region_code_for_number(parsed) or "",
            country_name=geocoder.description_for_number(parsed, "th") or "",
            carrier_name="",
            line_type="เบอร์ไม่ถูกต้อง",
            timezones=[],
            error="เบอร์ไม่ถูกต้องหรือยังไม่ได้จัดสรร",
        )

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    clean_digits = re.sub(r"\D", "", e164)
    c_code = parsed.country_code
    iso = phonenumbers.region_code_for_number(parsed) or ""
    c_name = geocoder.description_for_number(parsed, "th") or geocoder.description_for_number(parsed, "en") or ""
    car_name = carrier.name_for_number(parsed, "th") or carrier.name_for_number(parsed, "en") or ""
    l_type = _get_line_type_name(phonenumbers.number_type(parsed))
    tz_list = list(timezone.time_zones_for_number(parsed))

    # สร้าง footprint URLs
    footprints = {
        "whatsapp": f"https://wa.me/{clean_digits}",
        "telegram": f"https://t.me/+{clean_digits}",
        "truecaller": f"https://www.truecaller.com/search/{iso.lower()}/{clean_digits}",
        "google_exact": f'https://www.google.com/search?q="{e164}"',
        "google_social": f'https://www.google.com/search?q="{clean_digits}"+site:instagram.com+OR+site:facebook.com+OR+site:twitter.com',
    }

    # ตรวจ WhatsApp (probe wa.me)
    whatsapp_active = None
    wa_url = footprints["whatsapp"]
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(wa_url)
            if resp.status_code == 200:
                if "action-send" in resp.text or "send?phone=" in resp.text or "Chat on WhatsApp" in resp.text:
                    whatsapp_active = True
                else:
                    whatsapp_active = False
    except Exception:
        whatsapp_active = None

    # ค้นหา DuckDuckGo เพื่อหาชื่อที่เกี่ยวข้อง
    discovered_names: list[str] = []
    variations = _generate_phone_formats(parsed)
    query_parts = "+OR+".join(f'%22{urllib.parse.quote(v)}%22' for v in variations[:3])

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        search_url = f"https://html.duckduckgo.com/html/?q={query_parts}"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            ddg_resp = await client.get(search_url)
            if ddg_resp.status_code == 200:
                html_text = ddg_resp.text
                # แยกชื่อที่มีตัวพิมพ์ใหญ่
                for title_match in re.finditer(r'<a[^>]+class=\"result__snippet\"[^>]*>(.*?)</a>', html_text, re.DOTALL):
                    snippet = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                    possible_names = re.findall(r'\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?\b', snippet)
                    for name in possible_names:
                        if name not in ("WhatsApp Web", "Google Play", "App Store", "Privacy Policy"):
                            discovered_names.append(name)
    except Exception:
        pass

    return PhoneScanResult(
        raw_input=phone_number,
        e164=e164,
        is_valid=True,
        country_code=c_code,
        country_iso=iso,
        country_name=c_name,
        carrier_name=car_name,
        line_type=l_type,
        timezones=tz_list,
        whatsapp_active=whatsapp_active,
        whatsapp_url=wa_url if whatsapp_active else None,
        footprint_urls=footprints,
        associated_names=list(set(discovered_names))[:5],
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Avatar Analyzer (dHash matching)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compute_dhash(source: str | bytes, hash_size: int = 8) -> str:
    """คำนวณ dHash (Difference Hash) จากรูปภาพ — เทียบได้แม้ resize/recompress"""
    if isinstance(source, str):
        # ถ้าเป็น URL ดาวน์โหลดมาก่อน
        if source.startswith("http"):
            resp = requests.get(source, timeout=10)
            resp.raise_for_status()
            source = resp.content

    if isinstance(source, bytes):
        img = Image.open(io.BytesIO(source))
    else:
        img = Image.open(source)

    # Grayscale + resize
    resized = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = [int(resized.getpixel((x, y))) for y in range(hash_size) for x in range(hash_size + 1)]

    difference = []
    for row in range(hash_size):
        row_start = row * (hash_size + 1)
        for col in range(hash_size):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            difference.append(left > right)

    # แปลง boolean array → hex
    decimal_value = 0
    for index, value in enumerate(difference):
        if value:
            decimal_value += 1 << index
    return f"{decimal_value:0{hash_size * hash_size // 4}x}"


def hamming_distance(hash1: str, hash2: str) -> int:
    """คำนวณ Hamming distance ระหว่าง 2 hash (จำนวน bit ที่ต่างกัน)"""
    if len(hash1) != len(hash2):
        max_len = max(len(hash1), len(hash2))
        hash1 = hash1.zfill(max_len)
        hash2 = hash2.zfill(max_len)

    i1 = int(hash1, 16)
    i2 = int(hash2, 16)
    xor_val = i1 ^ i2
    return bin(xor_val).count("1")


def compare_avatars(
    source1: str | bytes,
    source2: str | bytes,
    match_threshold: int = 10,
) -> dict[str, Any]:
    """เปรียบเทียบ 2 รูปโปรไฟล์ — คืนว่าเป็นรูปเดียวกันหรือไม่"""
    try:
        hash1 = compute_dhash(source1)
        hash2 = compute_dhash(source2)

        distance = hamming_distance(hash1, hash2)
        max_bits = len(hash1) * 4
        similarity = round((1.0 - (distance / max_bits)) * 100, 2)

        return {
            "matched": distance <= match_threshold,
            "hamming_distance": distance,
            "similarity_percentage": similarity,
            "hash1": hash1,
            "hash2": hash2,
        }
    except Exception as exc:
        return {"matched": False, "error": str(exc)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stylometry (Character n-gram correlation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MIN_STYLOMETRY_CHARS = 40


def _ngram_char_tokens(text: str, n: int = 4) -> list[str]:
    """สกัด character n-grams สำหรับวิเคราะห์ลายมือเขียน"""
    clean = re.sub(r"\s+", " ", text.lower().strip())
    if len(clean) < n:
        return [clean] if clean else []
    return [clean[i : i + n] for i in range(len(clean) - n + 1)]


def _cosine_similarity(vec1: dict[str, float], vec2: dict[str, float]) -> float:
    """คำนวณ cosine similarity ระหว่าง 2 vectors"""
    if not vec1 or not vec2:
        return 0.0
    import math

    dot_product = sum(val * vec2.get(k, 0.0) for k, val in vec1.items())
    norm1 = math.sqrt(sum(val * val for val in vec1.values()))
    norm2 = math.sqrt(sum(val * val for val in vec2.values()))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot_product / (norm1 * norm2)


def correlate_stylometry(text1: str, text2: str) -> dict[str, Any]:
    """เทียบลายมือเขียน (stylometry) ระหว่าง 2 ข้อความ — คืน similarity 0.0-1.0"""
    if len(text1.strip()) < MIN_STYLOMETRY_CHARS or len(text2.strip()) < MIN_STYLOMETRY_CHARS:
        return {
            "similarity": 0.0,
            "warning": f"ข้อความสั้นเกินไป (ต้องอย่างน้อย {MIN_STYLOMETRY_CHARS} ตัวอักษร)",
        }

    ngrams1 = _ngram_char_tokens(text1)
    ngrams2 = _ngram_char_tokens(text2)

    counts1 = Counter(ngrams1)
    counts2 = Counter(ngrams2)

    total1 = len(ngrams1) or 1
    total2 = len(ngrams2) or 1

    vec1 = {ng: c / total1 for ng, c in counts1.items()}
    vec2 = {ng: c / total2 for ng, c in counts2.items()}

    score = _cosine_similarity(vec1, vec2)

    return {
        "similarity": round(score, 4),
        "interpretation": (
            "เขียนโดยคนเดียวกันมาก" if score > 0.85 else
            "เขียนโดยคนเดียวกันได้" if score > 0.70 else
            "คล้ายกันปานกลาง" if score > 0.50 else
            "แตกต่างกัน"
        ),
    }

