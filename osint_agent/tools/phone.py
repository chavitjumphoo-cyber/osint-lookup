"""เครื่องมือเกี่ยวกับเบอร์โทรและการยืนยันช่องทางราชการ/ธนาคาร"""

import asyncio
import re
from urllib.parse import urlparse

from .base import plain

PHONE_TYPE_TH = {
    0: "เบอร์บ้าน/สำนักงาน",
    1: "มือถือ",
    2: "บ้านหรือมือถือ (แยกไม่ได้)",
    3: "โทรฟรี",
    4: "เบอร์เก็บค่าบริการพิเศษ",
    5: "แบ่งค่าใช้จ่าย",
    6: "VoIP (โทรผ่านอินเทอร์เน็ต)",
    7: "เบอร์ส่วนตัวแบบย้ายได้",
    8: "เพจเจอร์",
    9: "UAN",
    10: "วอยซ์เมล",
    99: "ไม่ทราบประเภท",
}


def phone_info_schema():
    return {
        "name": "phone_info",
        "description": (
            "ตรวจข้อมูลพื้นฐานของเบอร์โทรจากแผนเลขหมาย (ไม่ได้ค้นอินเทอร์เน็ต): "
            "รูปแบบถูกต้องไหม, ประเภท (มือถือ/บ้าน/VoIP/โทรฟรี), ค่ายเดิมที่ได้รับเลขหมาย, ประเทศ "
            "ใช้ตรวจเบอร์ที่อ้างว่าเป็นหน่วยงาน เช่น ธนาคารจริงใช้เบอร์ call center สั้น ไม่ใช่มือถือ "
            "หมายเหตุ: ค่ายอาจเปลี่ยนแล้วถ้าผู้ใช้ย้ายค่ายแบบคงเบอร์เดิม"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "number": {"type": "string", "description": "เบอร์โทร เช่น 0812345678 หรือ +66812345678"}
            },
            "required": ["number"],
        },
    }


def run_phone_info(number: str) -> dict:
    import phonenumbers
    from phonenumbers import carrier, geocoder

    raw = re.sub(r"[\s\-()]", "", number)
    if not raw:
        return plain("ไม่ได้ระบุเบอร์โทร")

    try:
        parsed = phonenumbers.parse(raw, "TH")
    except phonenumbers.NumberParseException as exc:
        return plain(f"แยกรูปแบบเบอร์ไม่ได้: {exc}")

    valid = phonenumbers.is_valid_number(parsed)
    number_type = phonenumbers.number_type(parsed)
    lines = [
        f"เบอร์: {raw}",
        f"รูปแบบสากล: {phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)}",
        f"รูปแบบถูกต้องตามแผนเลขหมาย: {'ใช่' if valid else 'ไม่ใช่'}",
        f"ประเภท: {PHONE_TYPE_TH.get(number_type, 'ไม่ทราบ')}",
        f"ค่ายเดิมที่ได้รับเลขหมาย: {carrier.name_for_number(parsed, 'th') or 'ไม่ทราบ'}",
        f"ประเทศ/พื้นที่: {geocoder.description_for_number(parsed, 'th') or 'ไม่ทราบ'}",
    ]
    if not valid:
        lines.append("ข้อสังเกต: เบอร์นี้ไม่ตรงแผนเลขหมาย อาจพิมพ์ผิดหรือเป็นเบอร์ปลอมแปลง (spoofed)")
    lines.append("หมายเหตุ: ค่ายอาจไม่ตรงปัจจุบันถ้าผู้ใช้ย้ายค่ายแบบคงเบอร์เดิม")
    return plain("\n".join(lines))


# --------------------------------------------------------- trust anchors

# แหล่งอ้างอิงทางการของหน่วยงานที่มิจฉาชีพมักแอบอ้าง — ใช้เทียบว่าเว็บ/เบอร์ที่พบเป็นของจริงไหม
# "verified": True = ยืนยันกับหน้าเว็บทางการโดยตรงแล้ว (ระบุวันที่ใน verified_on)
# "verified": False = ยังไม่ได้ยืนยัน — เครื่องมือจะรายงานว่า "ตรงกับรายการอ้างอิง" ไม่ใช่ "ของจริง"
# รายการตรวจสอบล่าสุด: 2026-10-28 (ตรวจได้เฉพาะ SCB และ ttb ที่หน้าเว็บโหลดได้)
OFFICIAL_ENTITIES = {
    "ธนาคารไทยพาณิชย์ (SCB)": {
        "domains": ["scb.co.th"],
        "phones": ["027777777"],
        "verified": True,
        "verified_on": "2026-10-28",
        "source": "https://www.scb.co.th/th/personal-banking/contact-us.html (ยืนยันแล้ว: 0 2777 7777)",
    },
    "ทีทีบี (ttb)": {
        "domains": ["ttbbank.com"],
        "phones": ["1428", "020101428", "020201428"],
        "verified": True,
        "verified_on": "2026-10-28",
        "source": "https://www.ttbbank.com/th/contact (ยืนยันแล้ว: 0 2010 1428 / 1428)",
    },
    "ธนาคารกสิกรไทย (KBank)": {
        "domains": ["kasikornbank.com", "kbank.com"],
        "phones": [],
        "verified": False,
        "source": "ยังไม่ยืนยัน (เว็บตอบ HTTP 403 ต่อการดึงอัตโนมัติ)",
    },
    "ธนาคารกรุงเทพ (BBL)": {"domains": ["bangkokbank.com"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "ธนาคารกรุงไทย (KTB)": {"domains": ["krungthai.com", "ktb.co.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "ธนาคารกรุงศรีอยุธยา (Krungsri)": {"domains": ["krungsri.com"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "ธนาคารออมสิน (GSB)": {"domains": ["gsb.or.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "ธ.ก.ส. (BAAC)": {"domains": ["baac.or.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "ธนาคารแห่งประเทศไทย (BOT)": {"domains": ["bot.or.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "สำนักงานตำรวจแห่งชาติ / ศูนย์ AOC": {
        "domains": ["royalthaipolice.go.th", "thaipoliceonline.go.th"],
        "phones": [],
        "verified": False,
        "source": "ยังไม่ยืนยัน",
    },
    "กรมสรรพากร": {"domains": ["rd.go.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "การไฟฟ้านครหลวง (MEA)": {"domains": ["mea.or.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "การไฟฟ้าส่วนภูมิภาค (PEA)": {"domains": ["pea.co.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "กรมที่ดิน": {"domains": ["dol.go.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "ไปรษณีย์ไทย": {"domains": ["thailandpost.co.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "Kerry / KEX Express": {"domains": ["th.kex-express.com", "kex-express.com"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "Flash Express": {"domains": ["flashexpress.co.th", "flashexpress.com"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
    "สำนักงาน ก.ล.ต. (SEC)": {"domains": ["sec.or.th"], "phones": [], "verified": False, "source": "ยังไม่ยืนยัน"},
}


def verify_official_schema():
    return {
        "name": "verify_official",
        "description": (
            "เทียบโดเมนเว็บหรือเบอร์โทรกับรายชื่อช่องทางทางการของหน่วยงานที่มิจฉาชีพมักแอบอ้าง "
            "(ธนาคาร, ตำรวจ, สรรพากร, การไฟฟ้า, ขนส่ง, ก.ล.ต.) เพื่อบอกว่าเป็นของจริง "
            "หรือเป็นโดเมน/เบอร์ที่หน้าตาคล้ายแต่ไม่ใช่ทางการ (typosquatting) "
            "ใช้ทุกครั้งที่เป้าหมายอ้างว่าเป็นหน่วยงาน หรือเจอลิงก์ที่อ้างชื่อหน่วยงาน"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "URL/โดเมน หรือเบอร์โทรที่ต้องการตรวจ"},
                "claimed_entity": {"type": "string", "description": "หน่วยงานที่อีกฝ่ายอ้างว่าเป็น (ถ้ามี)"},
            },
            "required": ["value"],
        },
    }


def _normalize_domain(value: str) -> str:
    value = value.strip().lower()
    if "://" not in value:
        value = "http://" + value
    host = urlparse(value).hostname or ""
    return host[4:] if host.startswith("www.") else host


def _similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio()


def run_verify_official(value: str, claimed: str = "") -> dict:
    raw = value.strip()
    if not raw:
        return plain("ไม่ได้ระบุค่าที่ต้องการตรวจ")

    digits = re.sub(r"[^\d]", "", raw)
    is_phone = digits and len(digits) == len(re.sub(r"[\s\-+()]", "", raw)) and 3 <= len(digits) <= 12

    lines = []
    if is_phone:
        if digits.startswith("66") and len(digits) > 9:
            digits = "0" + digits[2:]
        matched = [
            (name, info) for name, info in OFFICIAL_ENTITIES.items() if digits in info["phones"]
        ]
        lines.append(f"เบอร์ที่ตรวจ: {digits}")
        if matched:
            name, info = matched[0]
            if info.get("verified"):
                lines.append(f"ผล: ตรงกับเบอร์ทางการของ {name} — ยืนยันจากหน้าเว็บทางการ {info['verified_on']}")
            else:
                lines.append(f"ผล: ตรงกับรายการอ้างอิงของ {name} (รายการนี้ยังไม่ได้ยืนยันกับเว็บทางการ)")
            lines.append("ข้อควรระวัง: มิจฉาชีพปลอมเบอร์โชว์ (caller ID spoofing) ได้ ให้วางสายแล้วโทรกลับเบอร์นี้เอง")
        else:
            lines.append("ผล: ไม่ตรงกับเบอร์ทางการในรายการอ้างอิง")
            if claimed:
                for name, info in OFFICIAL_ENTITIES.items():
                    if _similarity(claimed.lower(), name.lower()) > 0.35 or claimed.lower() in name.lower():
                        if info["phones"]:
                            mark = "" if info.get("verified") else " (ยังไม่ยืนยัน)"
                            lines.append(f"เบอร์ทางการของ {name}{mark}: {', '.join(info['phones'])}")
                        else:
                            lines.append(f"เบอร์ทางการของ {name}: ยังไม่มีในฐานข้อมูล — ให้ตรวจจากเว็บทางการของหน่วยงานเอง")
            if len(digits) >= 9 and digits.startswith("0"):
                lines.append(
                    "ข้อสังเกต: หน่วยงานราชการ/ธนาคารมักใช้เบอร์สั้น (4 หลัก) หรือเบอร์สำนักงาน "
                    "ไม่ค่อยโทรจากเบอร์มือถือส่วนตัวเพื่อขอข้อมูลหรือให้โอนเงิน"
                )
        return plain("\n".join(lines))

    domain = _normalize_domain(raw)
    if not domain:
        return plain(f"แยกโดเมนจาก '{raw}' ไม่ได้")
    lines.append(f"โดเมนที่ตรวจ: {domain}")

    for name, info in OFFICIAL_ENTITIES.items():
        for official in info["domains"]:
            if domain == official or domain.endswith("." + official):
                if info.get("verified"):
                    lines.append(f"ผล: เป็นโดเมนทางการของ {name} ({official}) — ยืนยันจากหน้าเว็บทางการ {info['verified_on']}")
                else:
                    lines.append(f"ผล: ตรงกับโดเมนของ {name} ในรายการอ้างอิง ({official}) — รายการยังไม่ได้ยืนยันกับเว็บทางการ")
                return plain("\n".join(lines))

    lookalikes = []
    for name, info in OFFICIAL_ENTITIES.items():
        for official in info["domains"]:
            brand = official.split(".")[0]
            score = _similarity(domain, official)
            if score >= 0.7 or (len(brand) >= 4 and brand in domain):
                lookalikes.append((score, name, official))
    lookalikes.sort(reverse=True)

    if lookalikes:
        lines.append("ผล: ⚠️ ไม่ใช่โดเมนทางการ แต่คล้ายหรือแอบใช้ชื่อหน่วยงาน — สัญญาณเว็บปลอม (phishing) สูง")
        for score, name, official in lookalikes[:3]:
            lines.append(f"- คล้าย {official} ของ {name} (ความคล้าย {score:.0%})")
    else:
        lines.append("ผล: ไม่ใช่โดเมนทางการของหน่วยงานในรายการ และไม่คล้ายโดเมนใดในรายการ")
    lines.append("หมายเหตุ: รายการอ้างอิงครอบคลุมเฉพาะหน่วยงานที่ถูกแอบอ้างบ่อย ไม่ใช่ทุกหน่วยงาน")
    return plain("\n".join(lines))


# ------------------------------------------------------------- scan_phone_advanced

def scan_phone_advanced_schema():
    return {
        "name": "scan_phone_advanced",
        "description": (
            "สแกนเบอร์โทรศัพท์แบบขั้นสูง — ตรวจสอบ WhatsApp active status, สร้าง footprint URLs "
            "(Telegram, Truecaller, Google dorks), ค้นหาชื่อที่เกี่ยวข้อง และให้ข้อมูล carrier/country/timezone "
            "ใช้แทน phone_info เมื่อต้องการข้อมูลเชิงลึก"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "phone_number": {
                    "type": "string",
                    "description": "เบอร์โทรศัพท์ (รูปแบบใดก็ได้ เช่น 0812345678, +66812345678)",
                }
            },
            "required": ["phone_number"],
        },
    }


def run_scan_phone_advanced(phone_number: str) -> dict:
    """รัน scan_phone แบบ async"""
    from .. import advanced_tools

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(advanced_tools.scan_phone(phone_number))
    finally:
        loop.close()

    if result.error:
        return plain(f"ข้อผิดพลาด: {result.error}")

    lines = [f"📱 เบอร์: {result.e164}"]
    lines.append(f"ประเทศ: {result.country_name} ({result.country_iso})")
    lines.append(f"ประเภท: {result.line_type}")
    if result.carrier_name:
        lines.append(f"ผู้ให้บริการ: {result.carrier_name}")
    if result.timezones:
        lines.append(f"เขตเวลา: {', '.join(result.timezones)}")

    if result.whatsapp_active is not None:
        status = "✅ ใช้งาน WhatsApp" if result.whatsapp_active else "❌ ไม่ได้ใช้ WhatsApp"
        lines.append(f"\nWhatsApp: {status}")
        if result.whatsapp_url:
            lines.append(f"URL: {result.whatsapp_url}")

    if result.associated_names:
        lines.append("\n🔍 ชื่อที่เกี่ยวข้อง (จากการค้น):")
        for name in result.associated_names:
            lines.append(f"- {name}")

    lines.append("\n🔗 Footprint URLs:")
    for platform, url in result.footprint_urls.items():
        lines.append(f"- {platform}: {url}")

    return plain("\n".join(lines))
