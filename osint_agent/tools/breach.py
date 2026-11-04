"""ตรวจประวัติอีเมลในเหตุข้อมูลรั่ว (Have I Been Pwned)"""

import os
from urllib.parse import quote

import requests

from .base import EMAIL_ONLY_RE, FETCH_TIMEOUT, plain
from .http import RATE_LIMITER


def breach_check_schema():
    return {
        "name": "breach_check",
        "description": (
            "ตรวจว่าอีเมลเคยอยู่ในเหตุข้อมูลรั่วที่เปิดเผยต่อสาธารณะหรือไม่ (Have I Been Pwned) "
            "คืนเฉพาะชื่อเหตุการณ์และปี ไม่คืนรหัสผ่านหรือข้อมูลที่รั่ว "
            "อีเมลที่ไม่มีประวัติรั่วเลยอาจเป็นอีเมลเพิ่งสร้าง/ใช้ทิ้ง ซึ่งพบบ่อยในบัญชีมิจฉาชีพ "
            "ต้องตั้งค่า HIBP_API_KEY ใน .env ก่อน"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"email": {"type": "string", "description": "อีเมลที่ต้องการตรวจ"}},
            "required": ["email"],
        },
    }


def _hibp_api_key() -> str:
    from ..agent import read_config

    return read_config().get("HIBP_API_KEY") or os.environ.get("HIBP_API_KEY", "")


def run_breach_check(email: str) -> dict:
    email = email.strip().lower()
    if not EMAIL_ONLY_RE.match(email):
        return plain(f"'{email}' ไม่ใช่รูปแบบอีเมลที่ถูกต้อง")

    api_key = _hibp_api_key()
    if not api_key:
        return plain(
            "ยังไม่ได้ตั้งค่า HIBP_API_KEY ใน .env จึงตรวจประวัติข้อมูลรั่วไม่ได้ "
            "(สมัครได้ที่ haveibeenpwned.com/API/Key)"
        )

    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}?truncateResponse=false"
    RATE_LIMITER.wait("haveibeenpwned.com")
    try:
        response = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={"hibp-api-key": api_key, "User-Agent": "OSINT-Lookup-Research"},
        )
    except requests.RequestException as exc:
        return plain(f"เรียก HIBP ไม่สำเร็จ: {type(exc).__name__}")

    if response.status_code == 404:
        return plain(
            f"ไม่พบ {email} ในเหตุข้อมูลรั่วที่ HIBP รู้จัก\n"
            "ข้อสังเกต: อีเมลที่ใช้มานานมักเคยรั่วอย่างน้อยหนึ่งครั้ง การไม่พบเลยอาจหมายถึงอีเมลเพิ่งสร้าง "
            "แต่ไม่ใช่หลักฐานยืนยันว่าเป็นอีเมลมิจฉาชีพ"
        )
    if response.status_code == 401:
        return plain("HIBP_API_KEY ไม่ถูกต้อง")
    if response.status_code == 429:
        return plain("HIBP จำกัดอัตราการเรียก ลองใหม่ภายหลัง")
    if response.status_code >= 400:
        return plain(f"HIBP ตอบกลับ HTTP {response.status_code}")

    try:
        breaches = response.json()
    except ValueError:
        return plain("อ่านผลจาก HIBP ไม่ได้")

    breaches = sorted(breaches, key=lambda b: b.get("BreachDate", ""))
    lines = [f"{email} อยู่ในเหตุข้อมูลรั่ว {len(breaches)} ครั้ง:"]
    for b in breaches[:25]:
        lines.append(f"- {b.get('Title') or b.get('Name')} ({(b.get('BreachDate') or '')[:4]})")
    if breaches:
        lines.append(f"ครั้งแรกที่พบ: {(breaches[0].get('BreachDate') or '')[:4]} — บ่งชี้ว่าอีเมลนี้มีอายุอย่างน้อยถึงปีนั้น")
    return plain("\n".join(lines))
