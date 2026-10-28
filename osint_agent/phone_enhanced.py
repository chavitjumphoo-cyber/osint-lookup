"""Enhanced Phone Scanner with Thai carrier detection, GetContact, and fraud database integration"""

import re
import urllib.parse
from typing import Dict, List, Optional

import phonenumbers
from phonenumbers import carrier, geocoder, timezone


# Thai carrier prefixes (updated 2026)
THAI_CARRIERS = {
    "AIS": ["81", "82", "83", "84", "85", "86", "87", "88", "89", "90", "91", "92", "93", "94", "95", "96", "97", "98", "99", "63", "65"],
    "DTAC": ["62", "64", "66"],
    "TrueMove H": ["60", "61", "67"],
    "My by CAT": ["69"],
    "Penguin": ["59"],
}


def detect_thai_carrier(phone_e164: str) -> Optional[str]:
    """ตรวจสอบค่ายมือถือไทยจากเลขหมาย — แม่นยำกว่า phonenumbers library"""
    if not phone_e164.startswith("+66"):
        return None

    local = phone_e164[3:]  # ตัด +66 ออก
    if len(local) < 2:
        return None

    prefix = local[:2]

    for carrier_name, prefixes in THAI_CARRIERS.items():
        if prefix in prefixes:
            return carrier_name

    return None


def build_phone_footprints(phone_e164: str, country_iso: str = "") -> Dict[str, str]:
    """สร้าง footprint URLs รวม GetContact, Whoscall และ fraud databases"""
    clean_digits = re.sub(r"\D", "", phone_e164)
    local_format = phone_e164.replace("+", "")

    footprints = {
        # Social & Messaging
        "whatsapp": f"https://wa.me/{clean_digits}",
        "telegram": f"https://t.me/+{clean_digits}",
        "signal": f"https://signal.me/#p/+{clean_digits}",
        "line": f"https://line.me/ti/p/~{clean_digits}",

        # Caller ID Apps
        "truecaller": f"https://www.truecaller.com/search/{country_iso.lower()}/{clean_digits}" if country_iso else f"https://www.truecaller.com/search/th/{clean_digits}",
        "getcontact": f"https://www.getcontact.com/en/search?phone={phone_e164}",
        "whoscall": f"https://whoscall.com/search?phone={phone_e164}",
        "sync.me": f"https://sync.me/search/?phone={phone_e164}",

        # Search Engines
        "google_exact": f'https://www.google.com/search?q="{phone_e164}"',
        "google_variants": f'https://www.google.com/search?q={phone_e164.replace("+", "")}',
        "duckduckgo": f'https://duckduckgo.com/?q="{phone_e164}"',

        # Thai Fraud Databases
        "blacklist_seller": f"https://www.blacklistseller.com/search?q={clean_digits}",
        "thaifraud": f"https://www.thaifraud.com/search?phone={phone_e164}",
        "pantip_fraud": f"https://pantip.com/search?q={urllib.parse.quote(phone_e164)}",
        "กลุ่มเตือนภัย": f"https://www.facebook.com/search/top?q={urllib.parse.quote(phone_e164)}",
    }

    return footprints


def enhanced_phone_scan(phone_number: str, default_region: str = "TH") -> Dict:
    """สแกนเบอร์แบบเต็มรูปแบบ พร้อม Thai carrier detection และ fraud database links"""
    clean_input = phone_number.strip()

    try:
        parsed = phonenumbers.parse(clean_input, default_region)
    except Exception as exc:
        return {
            "error": f"รูปแบบเบอร์ไม่ถูกต้อง: {exc}",
            "raw_input": phone_number,
        }

    is_valid = phonenumbers.is_valid_number(parsed)
    if not is_valid:
        return {
            "error": "เบอร์ไม่ถูกต้องหรือยังไม่ได้จัดสรร",
            "raw_input": phone_number,
            "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        }

    # Basic info
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    country_code = parsed.country_code
    country_iso = phonenumbers.region_code_for_number(parsed) or ""
    country_name = geocoder.description_for_number(parsed, "th") or geocoder.description_for_number(parsed, "en") or "ไม่ทราบ"

    # Enhanced carrier detection
    carrier_name = carrier.name_for_number(parsed, "th") or carrier.name_for_number(parsed, "en")

    # ใช้ Thai carrier detection ที่แม่นยำกว่า
    if country_iso == "TH":
        thai_carrier = detect_thai_carrier(e164)
        if thai_carrier:
            carrier_name = thai_carrier
        elif not carrier_name:
            carrier_name = "ไม่ทราบค่าย (อาจเป็นเบอร์ใหม่หรือพิเศษ)"

    if not carrier_name:
        carrier_name = "ไม่ทราบ"

    # Line type
    line_type_code = phonenumbers.number_type(parsed)
    line_type_map = {
        phonenumbers.PhoneNumberType.MOBILE: "มือถือ",
        phonenumbers.PhoneNumberType.FIXED_LINE: "โทรศัพท์บ้าน",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "บ้านหรือมือถือ",
        phonenumbers.PhoneNumberType.TOLL_FREE: "หมายเลขฟรี",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "หมายเลขพิเศษ (คิดค่าบริการ)",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "หมายเลขส่วนตัว",
        phonenumbers.PhoneNumberType.PAGER: "เพจเจอร์",
        phonenumbers.PhoneNumberType.UAN: "Universal Access Number",
        phonenumbers.PhoneNumberType.VOICEMAIL: "Voice Mail",
    }
    line_type = line_type_map.get(line_type_code, "ไม่ทราบ")

    # Timezones
    timezones_list = list(timezone.time_zones_for_number(parsed))

    # Footprints (รวม GetContact + Fraud Databases)
    footprints = build_phone_footprints(e164, country_iso)

    return {
        "raw_input": phone_number,
        "e164": e164,
        "is_valid": True,
        "country_code": country_code,
        "country_iso": country_iso,
        "country_name": country_name,
        "carrier_name": carrier_name,
        "line_type": line_type,
        "timezones": timezones_list,
        "footprints": footprints,
        "fraud_check_available": country_iso == "TH",  # ระบุว่ามี fraud database หรือไม่
    }
