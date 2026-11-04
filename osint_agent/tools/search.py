"""เครื่องมือค้นหา: Google (พร้อม dorks), Sherlock และการสกัด entity"""

import re
import shutil
import subprocess

from .base import (
    ACCOUNT_RE,
    EMAIL_RE,
    HANDLE_RE,
    PHONE_RE,
    SHERLOCK_TIMEOUT,
    URL_RE,
    USERNAME_RE,
    plain,
)


def web_search_schema():
    return {
        "name": "web_search",
        "description": (
            "ค้นหาเว็บแบบหลายเครื่องยนต์ (DuckDuckGo, Yahoo, Brave, Bing, Yandex) "
            "ผ่าน headless browser — ไม่ต้องใช้ API key รองรับ Google Dorks\n\n"
            "Google Dorks (ตัวอย่าง):\n"
            '- "exact phrase" = ค้นหาวลีที่ตรงทุกตัว\n'
            "- site:facebook.com = จำกัดเฉพาะเว็บไซต์นั้น\n"
            "- inurl:profile = URL ต้องมีคำว่า profile\n"
            '- intitle:"john doe" = หัวข้อต้องมี john doe\n'
            "- filetype:pdf = เฉพาะไฟล์ PDF\n"
            "- * = wildcard สำหรับคำใดก็ได้\n"
            '- OR = หรือ (เช่น "john" OR "jane")\n'
            '- - = ไม่รวม (เช่น "john" -smith)\n'
            "- .. = ช่วงตัวเลข (เช่น 2020..2023)\n\n"
            "ตัวอย่างคำค้นขั้นสูง:\n"
            '- "วงศ์ยศ เกิดศรี" site:facebook.com\n'
            '- "0812345678" (site:facebook.com OR site:twitter.com)\n'
            '- intext:"วงศ์ยศ" site:pantip.com\n'
            '- "john doe" filetype:pdf\n'
            '- intitle:"resume" "john doe" filetype:pdf'
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "คำค้นหา รองรับ Google Dorks เช่น:\n"
                        '- "วงศ์ยศ เกิดศรี" site:facebook.com\n'
                        '- inurl:profile "john doe"\n'
                        '- "0812345678" (pantip OR facebook)'
                    ),
                },
                "num_results": {
                    "type": "integer",
                    "description": "จำนวนผลลัพธ์ที่ต้องการ (default: 10, max: 30)",
                    "default": 10,
                },
                "lang": {
                    "type": "string",
                    "description": "ภาษา เช่น 'th' สำหรับไทย, 'en' สำหรับอังกฤษ (default: th)",
                    "default": "th",
                },
                "region": {
                    "type": "string",
                    "description": "ภูมิภาค เช่น 'th' สำหรับไทย, 'us' สำหรับสหรัฐฯ (default: th)",
                    "default": "th",
                },
            },
            "required": ["query"],
        },
    }


def run_web_search(
    query: str, num_results: int = 10, lang: str = "th", region: str = "th"
) -> dict:
    """ค้นหาหลาย engine พร้อม attribution และสถานะต่อ engine"""
    from ..services import search_engines

    try:
        payload = search_engines.search(query, num_results, lang, region)
    except Exception as exc:  # noqa: BLE001
        return plain(f"เกิดข้อผิดพลาดในการค้นหา: {type(exc).__name__}: {exc}")

    engines = payload["engines"]
    results = payload["results"]

    output = f'🔎 Web Search: "{query}"\n'
    output += "🧭 Engines: " + (", ".join(f"{e['engine']}={e['status']}" for e in engines) or "ไม่มี") + "\n\n"

    if not results:
        output += "ไม่พบผลลัพธ์\n"
        blocked = [e for e in engines if e["status"] in {"blocked", "failed"}]
        if blocked:
            output += "\nหมายเหตุ: engine ที่ล้มเหลว — " + ", ".join(
                f"{e['engine']} ({e['detail'] or e['status']})" for e in blocked
            )
        return plain(output)

    current = None
    for index, item in enumerate(results, start=1):
        if item["engine"] != current:
            current = item["engine"]
            output += f"\n[{item.get('label') or current}]\n"
        output += f"{index}. {item['title']}\n   {item['url']}\n"
        if item.get("snippet"):
            output += f"   {item['snippet'][:200]}\n"

    output += f"\n✓ รวม {len(results)} รายการ (dedupe แล้ว)"
    if "site:" not in query and "inurl:" not in query and "intitle:" not in query:
        output += "\n\n💡 ลอง Google Dorks: " + f'"{query}" site:facebook.com'
    return plain(output)


# alias เดิม — โค้ด/agent รุ่นก่อนยังเรียกชื่อนี้ได้
run_google_search = run_web_search


def sherlock_schema():
    return {
        "name": "sherlock_username",
        "description": (
            "ตรวจว่าชื่อผู้ใช้ (username) หนึ่งชื่อถูกใช้บนแพลตฟอร์มออนไลน์ใดบ้าง "
            "โดยรันเครื่องมือ Sherlock ที่ติดตั้งในเครื่อง ใช้เมื่อมี username หรือ "
            "ชื่อบัญชีจากลิงก์โซเชียลมีเดียที่พบ และต้องการรู้ว่าชื่อเดียวกันไปปรากฏที่อื่นหรือไม่ "
            "ใช้เวลาราว 30-60 วินาที ผลลัพธ์คือรายชื่อแพลตฟอร์ม + URL ของโปรไฟล์ที่พบ"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "ชื่อผู้ใช้ เช่น somchai_99 (ห้ามมีช่องว่างหรือ http://)",
                }
            },
            "required": ["username"],
        },
    }


def run_sherlock(username: str) -> dict:
    if not USERNAME_RE.match(username):
        return plain(
            f"ไม่สามารถรันได้: ชื่อผู้ใช้ '{username}' มีอักขระที่ไม่อนุญาต "
            "(รับเฉพาะ a-z A-Z 0-9 . _ - ยาวไม่เกิน 64)"
        )

    exe = shutil.which("sherlock")
    if not exe:
        return plain("ไม่พบคำสั่ง sherlock ในเครื่อง — ตรวจสอบว่าติดตั้งไว้ใน PATH แล้ว")

    try:
        proc = subprocess.run(
            [exe, username, "--print-found", "--no-color", "--no-txt", "--timeout", "5"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SHERLOCK_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return plain(f"Sherlock ใช้เวลานานเกิน {SHERLOCK_TIMEOUT} วินาที และถูกยกเลิก")
    except OSError as exc:
        return plain(f"เรียก sherlock ไม่สำเร็จ: {exc}")

    found = []
    for line in (proc.stdout or "").splitlines():
        match = re.match(r"^\[\+\]\s*([^:]+):\s*(\S+)", line.strip())
        if match:
            found.append((match.group(1).strip(), match.group(2).strip()))

    if not found:
        detail = (proc.stderr or "").strip()[:300]
        return plain(
            f"Sherlock ไม่พบบัญชีที่ใช้ชื่อ '{username}' บนแพลตฟอร์มใด (ตรวจทั้งหมดแล้ว)"
            + (f" — stderr: {detail}" if detail else "")
        )

    shown = found[:60]
    lines = [f"พบ {len(found)} แพลตฟอร์มที่ใช้ชื่อ '{username}':"]
    for site, url in shown:
        lines.append(f"- {site}: {url}")
    if len(found) > len(shown):
        lines.append(f"... และอีก {len(found) - len(shown)} แพลตฟอร์ม")
    return plain("\n".join(lines))


def extract_entities_schema():
    return {
        "name": "extract_entities",
        "description": (
            "สกัดข้อมูลที่ระบุตัวตนได้จากข้อความ (เบอร์โทร อีเมล ลิงก์ ชื่อผู้ใช้ @handle เลขบัญชี) "
            "ใช้เมื่อมีข้อความยาวจากหน้าเว็บหรือผลค้น และต้องการดึงเฉพาะตัวเลข/ที่อยู่ที่นำไปต่อยอดค้นได้ "
            "ใช้ tool นี้ก่อนวางแผนค้นรอบถัดไปเสมอ"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "ข้อความดิบที่ต้องการสกัด"}},
            "required": ["text"],
        },
    }


def run_extract_entities(text: str) -> dict:
    phones = sorted({re.sub(r"[\s-]", "", m.group(0)) for m in PHONE_RE.finditer(text)})
    emails = sorted({m.group(0).lower() for m in EMAIL_RE.finditer(text)})
    urls = sorted({m.group(0) for m in URL_RE.finditer(text)})
    handles = sorted({m.group(0) for m in HANDLE_RE.finditer(text)})
    accounts = sorted({re.sub(r"[\s-]", "", m.group(0)) for m in ACCOUNT_RE.finditer(text)})

    lines = ["สิ่งที่สกัดได้จากข้อความ:"]
    lines.append(f"- เบอร์โทร ({len(phones)}): {', '.join(phones) if phones else '-'}")
    lines.append(f"- อีเมล ({len(emails)}): {', '.join(emails) if emails else '-'}")
    lines.append(f"- ลิงก์ ({len(urls)}): {', '.join(urls[:20]) if urls else '-'}")
    lines.append(f"- handle (@) ({len(handles)}): {', '.join(handles) if handles else '-'}")
    lines.append(f"- เลขที่คล้ายเลขบัญชี ({len(accounts)}): {', '.join(accounts) if accounts else '-'}")

    if not any([phones, emails, urls, handles, accounts]):
        lines.append("\nไม่พบข้อมูลที่ระบุตัวตนได้ในข้อความนี้")
    return plain("\n".join(lines))
