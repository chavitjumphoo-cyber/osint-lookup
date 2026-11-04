"""เครื่องมือ enrich เพิ่มเติม: DNS, RDAP/WHOIS, Wayback, GitHub, Gravatar"""

import hashlib
import json

from .base import plain
from .http import safe_get


def dns_lookup_schema():
    return {
        "name": "dns_lookup",
        "description": (
            "ตรวจระเบียน DNS ของโดเมนผ่าน Google Public DNS (A, AAAA, MX, NS, TXT, CNAME) "
            "ใช้ดูโครงสร้างพื้นฐานและสัญญาณ phishing เช่น MX ผิดปกติหรือ TXT แปลก"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string"}},
            "required": ["domain"],
        },
    }


def run_dns_lookup(domain: str) -> dict:
    records = {}
    for record_type in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"):
        try:
            response = safe_get(
                f"https://dns.google/resolve?name={domain}&type={record_type}", timeout=10
            )
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            records[record_type] = [f"error: {type(exc).__name__}"]
            continue
        answers = payload.get("Answer") or []
        records[record_type] = [str(item.get("data")) for item in answers] or ["-"]

    lines = [f"DNS ของ {domain}:"]
    for record_type, values in records.items():
        lines.append(f"- {record_type}: {', '.join(values)}")
    return plain("\n".join(lines))


def whois_lookup_schema():
    return {
        "name": "whois_lookup",
        "description": (
            "ดึงข้อมูลจดทะเบียนโดเมนผ่าน RDAP (registrar, วันที่สร้าง/หมดอายุ, nameserver, สถานะ) "
            "ใช้ประเมินอายุและเจ้าของโดเมนโดยไม่ต้องใช้ WHOIS port 43"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"domain": {"type": "string"}},
            "required": ["domain"],
        },
    }


def run_whois_lookup(domain: str) -> dict:
    try:
        response = safe_get(f"https://rdap.org/domain/{domain}", timeout=15)
    except Exception as exc:  # noqa: BLE001
        return plain(f"เรียก RDAP ไม่สำเร็จ: {type(exc).__name__}")
    if response.status_code >= 400:
        return plain(f"RDAP ตอบ HTTP {response.status_code}")

    data = response.json()
    lines = [f"ข้อมูลจดทะเบียน {domain}:"]
    for event in data.get("events") or []:
        lines.append(f"- {event.get('eventAction')}: {event.get('eventDate')}")
    for entity in data.get("entities") or []:
        roles = ", ".join(entity.get("roles") or [])
        name = None
        for item in entity.get("vcardArray", [[], []])[1]:
            if item and item[0] == "fn":
                name = item[3]
        if name:
            lines.append(f"- {roles}: {name}")
    for server in data.get("nameservers") or []:
        lines.append(f"- nameserver: {server.get('ldhName')}")
    lines.append(f"- status: {', '.join(data.get('status') or []) or '-'}")
    return plain("\n".join(lines))


def wayback_lookup_schema():
    return {
        "name": "wayback_lookup",
        "description": (
            "ค้น snapshot เก่าใน Wayback Machine (CDX API) — ใช้ดูหน้าที่ถูกลบ เปลี่ยน bio "
            "หรือเส้นทางที่เคยเปิดเผย"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}, "limit": {"type": "integer", "default": 10}},
            "required": ["url"],
        },
    }


def run_wayback_lookup(url: str, limit: int = 10) -> dict:
    limit = max(1, min(int(limit or 10), 30))
    query = (
        "https://web.archive.org/cdx/search/cdx?url="
        f"{url}&output=json&collapse=digest&limit={limit}&fl=timestamp,original,statuscode"
    )
    try:
        response = safe_get(query, timeout=20)
    except Exception as exc:  # noqa: BLE001
        return plain(f"เรียก Wayback ไม่สำเร็จ: {type(exc).__name__}")
    if response.status_code >= 400:
        return plain(f"Wayback ตอบ HTTP {response.status_code}")
    try:
        rows = response.json()
    except ValueError:
        return plain("Wayback ไม่ได้คืน JSON")

    if len(rows) <= 1:
        return plain(f"ไม่พบ snapshot ของ {url}")
    lines = [f"พบ snapshot {len(rows) - 1} รายการ:"]
    for row in rows[1:]:
        lines.append(f"- {row[0]} · HTTP {row[2]} · {row[1]}")
    return plain("\n".join(lines))


def github_intel_schema():
    return {
        "name": "github_intel",
        "description": (
            "ดึงข้อมูลสาธารณะจาก GitHub API (ชื่อที่แสดง, bio, บริษัท, เมือง, เว็บ, วันที่สร้างบัญชี) "
            "ใช้ยืนยันตัวตนจาก username โดยไม่ต้อง scrape หน้าเว็บ"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"username": {"type": "string"}},
            "required": ["username"],
        },
    }


def run_github_intel(username: str) -> dict:
    try:
        response = safe_get(
            f"https://api.github.com/users/{username}",
            timeout=10,
            headers={"Accept": "application/vnd.github+json"},
        )
    except Exception as exc:  # noqa: BLE001
        return plain(f"เรียก GitHub ไม่สำเร็จ: {type(exc).__name__}")
    if response.status_code == 404:
        return plain(f"ไม่พบบัญชี GitHub '{username}'")
    if response.status_code >= 400:
        return plain(f"GitHub ตอบ HTTP {response.status_code}")
    data = response.json()
    lines = [f"GitHub @{data.get('login')}:"]
    for key, label in (
        ("name", "ชื่อ"),
        ("bio", "bio"),
        ("company", "บริษัท"),
        ("location", "เมือง"),
        ("blog", "เว็บ"),
        ("twitter_username", "twitter"),
        ("created_at", "สร้างบัญชี"),
        ("public_repos", "repo สาธารณะ"),
        ("followers", "ผู้ติดตาม"),
    ):
        if data.get(key):
            lines.append(f"- {label}: {data[key]}")
    return plain("\n".join(lines))


def gravatar_lookup_schema():
    return {
        "name": "gravatar_lookup",
        "description": (
            "ตรวจว่าอีเมลมีโปรไฟล์ Gravatar หรือไม่ และดึงชื่อที่แสดง/บัญชีที่ผูกไว้ "
            "ใช้เป็นจุด pivot ไปยัง username อื่น"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    }


def run_gravatar_lookup(email: str) -> dict:
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
    try:
        response = safe_get(f"https://gravatar.com/{digest}.json", timeout=10)
    except Exception as exc:  # noqa: BLE001
        return plain(f"เรียก Gravatar ไม่สำเร็จ: {type(exc).__name__}")
    if response.status_code == 404:
        return plain(f"ไม่พบโปรไฟล์ Gravatar ของ {email}")
    if response.status_code >= 400:
        return plain(f"Gravatar ตอบ HTTP {response.status_code}")

    try:
        entries = response.json().get("entry") or []
    except ValueError:
        return plain("Gravatar ไม่ได้คืน JSON")
    if not entries:
        return plain(f"ไม่พบโปรไฟล์ Gravatar ของ {email}")

    entry = entries[0]
    lines = ["พบโปรไฟล์ Gravatar:"]
    for key, label in (
        ("displayName", "ชื่อที่แสดง"),
        ("preferredUsername", "username"),
        ("aboutMe", "เกี่ยวกับ"),
        ("currentLocation", "สถานที่"),
        ("thumbnailUrl", "รูป"),
    ):
        if entry.get(key):
            lines.append(f"- {label}: {entry[key]}")
    for account in entry.get("accounts") or []:
        lines.append(f"- บัญชีที่ผูก: {account.get('shortname')} → {account.get('url')}")
    return plain("\n".join(lines))


def json_dumps(data) -> str:
    return json.dumps(data, ensure_ascii=False)
