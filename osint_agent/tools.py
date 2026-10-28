"""
คลังเครื่องมือของ agent — client-side tools ที่โค้ดรันเอง (ต่างจาก web_search ที่ API รันให้)

execute_tool() คืน dict เสมอ: {"output": str, "images": [{"media_type", "data"}, ...]}
ภาพที่แนบมาจะถูกส่งเข้าโมเดลใน tool_result ทำให้ agent "เห็น" รูปในหน้าเว็บได้

Advanced Tools (inspired by osint-d2):
- scan_phone_advanced: WhatsApp status + multi-platform footprint
- compare_avatars: perceptual dHash matching
- correlate_stylometry: character n-gram writing style comparison
"""

import base64
import hashlib
import ipaddress
import random
import re
import shutil
import socket
import subprocess
import threading
import time
import asyncio
from urllib.parse import urljoin, urlparse, quote_plus

import requests
from bs4 import BeautifulSoup
from googlesearch import search as google_search_api

from . import advanced_tools  # import module ใหม่
from . import synint_agents  # SYNINT-inspired agents
from . import platform_scanner  # Multi-platform scanner
from . import identity_triangulation  # Identity triangulation

SHERLOCK_TIMEOUT = 180
FETCH_TIMEOUT = 15
IMAGE_TIMEOUT = 10
FETCH_MAX_CHARS = 12000
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 1_500_000
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Research/1.0"

IMAGE_MEDIA_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}

# ชื่อผู้ใช้ที่ยอมให้ส่งเข้า sherlock — กันการแทรก argument (เช่น "--json /etc/passwd")
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

DOMAIN_MIN_INTERVAL = 2.0
DOMAIN_JITTER = 1.5


class DomainRateLimiter:
    """เว้นระยะการเรียกโดเมนเดียวกันอย่างน้อย min_interval วินาที + หน่วงสุ่ม กันโดนบล็อก"""

    def __init__(self, min_interval: float, jitter: float):
        self.min_interval = min_interval
        self.jitter = jitter
        self._next_allowed: dict = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> float:
        host = (host or "").lower()
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next_allowed.get(host, 0.0))
            self._next_allowed[host] = start + self.min_interval + random.uniform(0, self.jitter)
        delay = start - now
        if delay > 0:
            time.sleep(delay)
        return delay


RATE_LIMITER = DomainRateLimiter(DOMAIN_MIN_INTERVAL, DOMAIN_JITTER)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Multi-Platform Scanner (30+ platforms)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def scan_platforms_schema():
    return {
        "name": "scan_platforms",
        "description": (
            "สแกน username ข้าม 30+ แพลตฟอร์มพร้อมกัน — เร็วกว่า sherlock และ real-time\n\n"
            "แพลตฟอร์มที่รองรับ:\n"
            "- Social: Facebook, Instagram, Twitter/X, TikTok, LinkedIn, YouTube, Snapchat, Telegram\n"
            "- Developer: GitHub, GitLab, Stack Overflow, HackerRank, LeetCode, Kaggle\n"
            "- Forums: Pantip, Medium, Reddit, DeviantArt, Behance\n"
            "- Gaming: Twitch, Steam, Xbox, PlayStation\n\n"
            "ใช้เมื่อต้องการค้นหา username แบบครอบคลุม"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username ที่ต้องการสแกน เช่น johndoe, testuser123",
                },
            },
            "required": ["username"],
        },
    }


def _run_scan_platforms(username: str) -> dict:
    """สแกน username ข้าม 30+ แพลตฟอร์ม"""
    try:
        results = platform_scanner.scan_username_advanced(username)
        output = platform_scanner.format_scan_results(results)
        return {"output": output, "images": []}
    except Exception as e:
        return {"output": f"เกิดข้อผิดพลาด: {str(e)}", "images": []}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Google Search (Real)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def google_search_schema():
    return {
        "name": "google_search",
        "description": (
            "ค้นหาข้อมูลจาก Google Search จริงๆ — รองรับ Google Dorks และเทคนิคค้นหาขั้นสูง\n\n"
            "Google Dorks (ตัวอย่าง):\n"
            '- "exact phrase" = ค้นหาวลีที่ตรงทุกตัว\n'
            '- site:facebook.com = จำกัดเฉพาะเว็บไซต์นั้น\n'
            '- inurl:profile = URL ต้องมีคำว่า profile\n'
            '- intitle:"john doe" = หัวข้อต้องมี john doe\n'
            '- filetype:pdf = เฉพาะไฟล์ PDF\n'
            '- * = wildcard สำหรับคำใดก็ได้\n'
            '- OR = หรือ (เช่น "john" OR "jane")\n'
            '- - = ไม่รวม (เช่น "john" -smith)\n'
            '- .. = ช่วงตัวเลข (เช่น 2020..2023)\n\n'
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


def _run_google_search(query: str, num_results: int = 10, lang: str = "th", region: str = "th") -> dict:
    """ค้นหา Google จริงๆ พร้อม Google Dorks support"""
    try:
        # จำกัด num_results ไม่เกิน 30
        num_results = min(num_results, 30)

        # ใช้ googlesearch-python แทน web_search API
        results = []
        count = 0

        # รองรับ Google Dorks โดยส่ง query ตรงๆ
        for url in google_search_api(
            query,
            num_results=num_results,
            lang=lang,
            region=region,
            sleep_interval=1.5,  # หน่วงเวลาเพื่อไม่ให้โดนบล็อก
            advanced=True
        ):
            count += 1
            results.append(f"{count}. {url}")
            if count >= num_results:
                break

        if not results:
            return {
                "output": f"ไม่พบผลลัพธ์สำหรับ: {query}\n\nคำแนะนำ:\n- ลองใช้คำค้นที่กว้างขึ้น\n- ลองใช้ Google Dorks เช่น site:facebook.com",
                "images": []
            }

        output = f"🔍 Google Search: \"{query}\"\n"
        output += f"📍 Region: {region.upper()} | Language: {lang.upper()}\n\n"
        output += "ผลลัพธ์:\n" + "\n".join(results)
        output += f"\n\n✓ พบทั้งหมด {len(results)} รายการ"

        # แนะนำ Google Dorks หากยังไม่ได้ใช้
        if "site:" not in query and "inurl:" not in query and "intitle:" not in query:
            output += "\n\n💡 เคล็ดลับ: ลองใช้ Google Dorks เช่น:\n"
            output += f'- "{query}" site:facebook.com\n'
            output += f'- "{query}" site:pantip.com\n'
            output += f'- inurl:profile "{query}"'

        return {"output": output, "images": []}

    except Exception as e:
        return {
            "output": f"เกิดข้อผิดพลาดในการค้นหา Google: {str(e)}\n\nคำแนะนำ:\n- ตรวจสอบว่าติดตั้ง googlesearch-python แล้ว\n- อาจโดนบล็อกจาก Google ชั่วคราว (ลองอีกครั้งในอีก 1-2 นาที)",
            "images": []
        }


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


def fetch_page_schema():
    return {
        "name": "fetch_page",
        "description": (
            "เปิดอ่านหน้าเว็บหนึ่งหน้า ดึงข้อความ (ตัดแท็ก HTML ออก) พร้อมแนบรูปภาพที่มีในหน้า "
            "ให้คุณมองเห็นได้สูงสุด 4 รูป ใช้เมื่อผลการค้นมีลิงก์ที่น่าจะมีรายละเอียดสำคัญ "
            "เช่น กระทู้ Pantip ที่เล่าเหตุการณ์ โพสต์เตือนภัย หน้าบริษัท หรือโปรไฟล์สาธารณะ "
            "รูปที่แนบมาช่วยยืนยันบริบทได้ (โลโก้สแกม ภาพสินค้า สลิปโอนเงิน ภาพหน้าจอแชท) "
            "แต่ห้ามใช้ระบุตัวบุคคลจากใบหน้าหรืออ่านป้ายทะเบียน/ป้ายชื่อ/ที่อยู่"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL เต็มที่ขึ้นต้นด้วย http:// หรือ https://"},
                "focus": {
                    "type": "string",
                    "description": "คำสำคัญที่ต้องการเน้น เช่น ชื่อเป้าหมาย — ระบบจะดึงย่อหน้าที่มีคำนี้ก่อน",
                },
            },
            "required": ["url"],
        },
    }


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


def _plain(text: str) -> dict:
    return {"output": text, "images": []}


def _run_sherlock(username: str) -> dict:
    if not USERNAME_RE.match(username):
        return _plain(
            f"ไม่สามารถรันได้: ชื่อผู้ใช้ '{username}' มีอักขระที่ไม่อนุญาต "
            "(รับเฉพาะ a-z A-Z 0-9 . _ - ยาวไม่เกิน 64)"
        )

    exe = shutil.which("sherlock")
    if not exe:
        return _plain("ไม่พบคำสั่ง sherlock ในเครื่อง — ตรวจสอบว่าติดตั้งไว้ใน PATH แล้ว")

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
        return _plain(f"Sherlock ใช้เวลานานเกิน {SHERLOCK_TIMEOUT} วินาที และถูกยกเลิก")
    except OSError as exc:
        return _plain(f"เรียก sherlock ไม่สำเร็จ: {exc}")

    found = []
    for line in (proc.stdout or "").splitlines():
        match = re.match(r"^\[\+\]\s*([^:]+):\s*(\S+)", line.strip())
        if match:
            found.append((match.group(1).strip(), match.group(2).strip()))

    if not found:
        detail = (proc.stderr or "").strip()[:300]
        return _plain(
            f"Sherlock ไม่พบบัญชีที่ใช้ชื่อ '{username}' บนแพลตฟอร์มใด (ตรวจทั้งหมดแล้ว)"
            + (f" — stderr: {detail}" if detail else "")
        )

    shown = found[:60]
    lines = [f"พบ {len(found)} แพลตฟอร์มที่ใช้ชื่อ '{username}':"]
    for site, url in shown:
        lines.append(f"- {site}: {url}")
    if len(found) > len(shown):
        lines.append(f"... และอีก {len(found) - len(shown)} แพลตฟอร์ม")
    return _plain("\n".join(lines))


def _is_public_host(host: str) -> bool:
    """กัน SSRF — ปฏิเสธ hostname ที่ชี้ไป loopback/private/reserved"""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


MAX_REDIRECTS = 5


class UnsafeURLError(Exception):
    pass


def _check_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("รองรับเฉพาะ http:// และ https://")
    host = parsed.hostname or ""
    if not _is_public_host(host):
        raise UnsafeURLError("ที่อยู่นี้ไม่ใช่เว็บสาธารณะ (ถูกบล็อกเพื่อความปลอดภัย)")
    return host


def safe_get(url: str, timeout: float, stream: bool = False, headers: dict | None = None):
    """GET ที่ตรวจ SSRF ทุก hop ของ redirect และเว้นระยะต่อโดเมน"""
    merged = {"User-Agent": USER_AGENT, "Accept-Language": "th,en;q=0.8", **(headers or {})}
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        host = _check_url(current)
        RATE_LIMITER.wait(host)
        response = requests.get(
            current, timeout=timeout, headers=merged, stream=stream, allow_redirects=False
        )
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise UnsafeURLError("redirect ไม่มีปลายทาง")
            current = urljoin(current, location)
            continue
        return response
    raise UnsafeURLError(f"redirect เกิน {MAX_REDIRECTS} ครั้ง")


def _download_image(url: str) -> dict | None:
    """ดาวน์โหลดรูปเดียว คืน content block ของ Anthropic หรือ None ถ้าใช้ไม่ได้"""
    try:
        response = safe_get(url, timeout=IMAGE_TIMEOUT, stream=True)
    except (requests.RequestException, UnsafeURLError):
        return None

    if response.status_code >= 400:
        return None

    media_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if media_type not in IMAGE_MEDIA_TYPES:
        return None

    chunks = []
    total = 0
    try:
        for chunk in response.iter_content(65536):
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:
                return None
            chunks.append(chunk)
    except requests.RequestException:
        return None
    finally:
        response.close()

    data = b"".join(chunks)
    if len(data) < 1024:
        return None

    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": IMAGE_MEDIA_TYPES[media_type],
            "data": base64.b64encode(data).decode("ascii"),
        },
    }


def _collect_images(soup, page_url: str) -> list:
    """เลือกรูปจากหน้าเว็บ — เอารูปที่ใหญ่พอ (มี width/height ระบุ) ก่อน"""
    candidates = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        absolute = urljoin(page_url, src)

        width = img.get("width")
        height = img.get("height")
        try:
            score = int(width) * int(height) if width and height else 0
        except (TypeError, ValueError):
            score = 0
        if width and str(width).isdigit() and int(width) < 80:
            continue

        if absolute not in [c[0] for c in candidates]:
            candidates.append((absolute, score))

    candidates.sort(key=lambda item: item[1], reverse=True)

    images = []
    for url, _score in candidates[: MAX_IMAGES * 3]:
        if len(images) >= MAX_IMAGES:
            break
        block = _download_image(url)
        if block:
            images.append(block)
    return images


def _run_fetch(url: str, focus: str = "") -> dict:
    try:
        response = safe_get(url, timeout=FETCH_TIMEOUT)
    except UnsafeURLError as exc:
        return _plain(f"ไม่สามารถเปิดได้: {exc}")
    except requests.RequestException as exc:
        return _plain(f"เปิดหน้าเว็บไม่สำเร็จ: {type(exc).__name__}")

    if response.status_code >= 400:
        return _plain(
            f"หน้าเว็บตอบกลับ HTTP {response.status_code} — "
            "อาจต้องล็อกอินหรือถูกบล็อก bot จึงอ่านเนื้อหาไม่ได้"
        )

    content_type = (response.headers.get("Content-Type") or "").lower()
    if not content_type.startswith("text/html"):
        return _plain(f"หน้านี้ไม่ใช่ HTML (Content-Type: {content_type or 'ไม่ระบุ'}) อ่านข้อความไม่ได้")

    soup = BeautifulSoup(response.text, "html.parser")
    images = _collect_images(soup, response.url or url)

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))

    if focus:
        paragraphs = [p for p in text.split("\n\n") if focus.lower() in p.lower()]
        if paragraphs:
            text = "\n\n".join(paragraphs)

    if len(text) > FETCH_MAX_CHARS:
        text = text[:FETCH_MAX_CHARS] + "\n\n[... เนื้อหาถูกตัดตรงนี้ ...]"

    if not text.strip() and not images:
        return _plain(f"หน้าเว็บ '{title or url}' ไม่มีข้อความหรือรูปที่อ่านได้ (อาจเป็น JavaScript ล้วน)")

    caption = f"# {title or url}"
    if images:
        caption += f"\n\n[แนบรูปจากหน้าเว็บมาให้ {len(images)} รูป — ใช้เป็นบริบทประกอบ]"
    return {"output": f"{caption}\n{text}", "images": images}


PHONE_RE = re.compile(r"(?<!\d)(?:\+66|0)[\d\-\s]{8,12}\d(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_.]{3,30}")
ACCOUNT_RE = re.compile(r"(?<!\d)\d{3}[-\s]?\d[-\s]?\d{5}[-\s]?\d(?!\d)")


def _run_extract_entities(text: str) -> dict:
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
    return _plain("\n".join(lines))


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


def _run_phone_info(number: str) -> dict:
    import phonenumbers
    from phonenumbers import carrier, geocoder

    raw = re.sub(r"[\s\-()]", "", number)
    if not raw:
        return _plain("ไม่ได้ระบุเบอร์โทร")

    try:
        parsed = phonenumbers.parse(raw, "TH")
    except phonenumbers.NumberParseException as exc:
        return _plain(f"แยกรูปแบบเบอร์ไม่ได้: {exc}")

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
    return _plain("\n".join(lines))


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


def _run_verify_official(value: str, claimed: str = "") -> dict:
    raw = value.strip()
    if not raw:
        return _plain("ไม่ได้ระบุค่าที่ต้องการตรวจ")

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
        return _plain("\n".join(lines))

    domain = _normalize_domain(raw)
    if not domain:
        return _plain(f"แยกโดเมนจาก '{raw}' ไม่ได้")
    lines.append(f"โดเมนที่ตรวจ: {domain}")

    for name, info in OFFICIAL_ENTITIES.items():
        for official in info["domains"]:
            if domain == official or domain.endswith("." + official):
                if info.get("verified"):
                    lines.append(f"ผล: เป็นโดเมนทางการของ {name} ({official}) — ยืนยันจากหน้าเว็บทางการ {info['verified_on']}")
                else:
                    lines.append(f"ผล: ตรงกับโดเมนของ {name} ในรายการอ้างอิง ({official}) — รายการยังไม่ได้ยืนยันกับเว็บทางการ")
                return _plain("\n".join(lines))

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
    return _plain("\n".join(lines))


# ------------------------------------------------------------- breach check

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


EMAIL_ONLY_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def _hibp_api_key() -> str:
    import os

    from .agent import read_config

    return read_config().get("HIBP_API_KEY") or os.environ.get("HIBP_API_KEY", "")


def _run_breach_check(email: str) -> dict:
    email = email.strip().lower()
    if not EMAIL_ONLY_RE.match(email):
        return _plain(f"'{email}' ไม่ใช่รูปแบบอีเมลที่ถูกต้อง")

    api_key = _hibp_api_key()
    if not api_key:
        return _plain(
            "ยังไม่ได้ตั้งค่า HIBP_API_KEY ใน .env จึงตรวจประวัติข้อมูลรั่วไม่ได้ "
            "(สมัครได้ที่ haveibeenpwned.com/API/Key)"
        )

    from urllib.parse import quote

    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}?truncateResponse=false"
    RATE_LIMITER.wait("haveibeenpwned.com")
    try:
        response = requests.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={"hibp-api-key": api_key, "User-Agent": "OSINT-Lookup-Research"},
        )
    except requests.RequestException as exc:
        return _plain(f"เรียก HIBP ไม่สำเร็จ: {type(exc).__name__}")

    if response.status_code == 404:
        return _plain(
            f"ไม่พบ {email} ในเหตุข้อมูลรั่วที่ HIBP รู้จัก\n"
            "ข้อสังเกต: อีเมลที่ใช้มานานมักเคยรั่วอย่างน้อยหนึ่งครั้ง การไม่พบเลยอาจหมายถึงอีเมลเพิ่งสร้าง "
            "แต่ไม่ใช่หลักฐานยืนยันว่าเป็นอีเมลมิจฉาชีพ"
        )
    if response.status_code == 401:
        return _plain("HIBP_API_KEY ไม่ถูกต้อง")
    if response.status_code == 429:
        return _plain("HIBP จำกัดอัตราการเรียก ลองใหม่ภายหลัง")
    if response.status_code >= 400:
        return _plain(f"HIBP ตอบกลับ HTTP {response.status_code}")

    try:
        breaches = response.json()
    except ValueError:
        return _plain("อ่านผลจาก HIBP ไม่ได้")

    breaches = sorted(breaches, key=lambda b: b.get("BreachDate", ""))
    lines = [f"{email} อยู่ในเหตุข้อมูลรั่ว {len(breaches)} ครั้ง:"]
    for b in breaches[:25]:
        lines.append(f"- {b.get('Title') or b.get('Name')} ({(b.get('BreachDate') or '')[:4]})")
    if breaches:
        lines.append(f"ครั้งแรกที่พบ: {(breaches[0].get('BreachDate') or '')[:4]} — บ่งชี้ว่าอีเมลนี้มีอายุอย่างน้อยถึงปีนั้น")
    return _plain("\n".join(lines))


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


def _run_scan_phone_advanced(phone_number: str) -> dict:
    """รัน scan_phone แบบ async"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(advanced_tools.scan_phone(phone_number))
    finally:
        loop.close()

    if result.error:
        return _plain(f"ข้อผิดพลาด: {result.error}")

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
        lines.append(f"\n🔍 ชื่อที่เกี่ยวข้อง (จากการค้น):")
        for name in result.associated_names:
            lines.append(f"- {name}")

    lines.append("\n🔗 Footprint URLs:")
    for platform, url in result.footprint_urls.items():
        lines.append(f"- {platform}: {url}")

    return _plain("\n".join(lines))


# ------------------------------------------------------------- compare_avatars

def compare_avatars_schema():
    return {
        "name": "compare_avatars",
        "description": (
            "เปรียบเทียบ 2 รูปโปรไฟล์ด้วย perceptual dHash — ตรวจจับว่าเป็นรูปเดียวกันหรือไม่ "
            "แม้จะ resize/recompress/crop เล็กน้อย ใช้ระบุว่าบัญชีหลายบัญชีเป็นคนเดียวกัน"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "avatar_url_1": {
                    "type": "string",
                    "description": "URL รูปที่ 1 (หรือ path ในเครื่อง)",
                },
                "avatar_url_2": {
                    "type": "string",
                    "description": "URL รูปที่ 2 (หรือ path ในเครื่อง)",
                },
            },
            "required": ["avatar_url_1", "avatar_url_2"],
        },
    }


def _run_compare_avatars(url1: str, url2: str) -> dict:
    try:
        result = advanced_tools.compare_avatars(url1, url2)
        if result.get("error"):
            return _plain(f"ข้อผิดพลาด: {result['error']}")

        lines = [f"🖼️ เปรียบเทียบรูปโปรไฟล์"]
        lines.append(f"รูปที่ 1: {url1}")
        lines.append(f"รูปที่ 2: {url2}")
        lines.append("")
        lines.append(f"ผลลัพธ์: {'✅ ตรงกัน (รูปเดียวกัน)' if result['matched'] else '❌ ไม่ตรงกัน'}")
        lines.append(f"ความคล้าย: {result['similarity_percentage']}%")
        lines.append(f"Hamming distance: {result['hamming_distance']} bits")
        lines.append(f"Hash 1: {result['hash1']}")
        lines.append(f"Hash 2: {result['hash2']}")

        return _plain("\n".join(lines))
    except Exception as exc:
        return _plain(f"เกิดข้อผิดพลาด: {type(exc).__name__}: {exc}")


# ------------------------------------------------------------- correlate_stylometry

def correlate_stylometry_schema():
    return {
        "name": "correlate_stylometry",
        "description": (
            "วิเคราะห์ลายมือเขียน (stylometry) ด้วย character n-gram — เทียบว่า 2 ข้อความ "
            "เขียนโดยคนเดียวกันหรือไม่ ใช้ระบุบัญชีนิรนามหลายบัญชีที่เป็นคนเดียวกัน "
            "ข้อความต้องยาวอย่างน้อย 40 ตัวอักษร"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text1": {
                    "type": "string",
                    "description": "ข้อความที่ 1 (เช่น โพสต์/คอมเมนต์จากบัญชีที่รู้จัก)",
                },
                "text2": {
                    "type": "string",
                    "description": "ข้อความที่ 2 (เช่น โพสต์/คอมเมนต์จากบัญชีนิรนาม)",
                },
            },
            "required": ["text1", "text2"],
        },
    }


def _run_correlate_stylometry(text1: str, text2: str) -> dict:
    result = advanced_tools.correlate_stylometry(text1, text2)

    lines = ["✍️ การวิเคราะห์ลายมือเขียน (Stylometry)"]
    if result.get("warning"):
        lines.append(f"⚠️ {result['warning']}")
    else:
        lines.append(f"ความคล้าย: {result['similarity']:.2%}")
        lines.append(f"ประเมิน: {result['interpretation']}")
        lines.append("")
        lines.append("คำแนะนำการแปลผล:")
        lines.append("- > 0.85: เขียนโดยคนเดียวกันมาก")
        lines.append("- 0.70-0.85: เขียนโดยคนเดียวกันได้")
        lines.append("- 0.50-0.70: คล้ายกันปานกลาง")
        lines.append("- < 0.50: แตกต่างกัน")

    return _plain("\n".join(lines))


# ------------------------------------------------------------- username_correlation

def username_correlation_schema():
    return {
        "name": "username_correlation",
        "description": (
            "สร้าง username variants และหาความเชื่อมโยงใน corpus ที่เก็บมา — "
            "จาก username หนึ่งสร้าง variants หลายรูปแบบ (john.doe → johndoe, j.doe, jdoe) "
            "แล้วเช็คว่ามีปรากฏในข้อความที่เก็บมาหรือไม่"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "Username seed (เช่น john.doe, @johndoe, https://twitter.com/johndoe)",
                },
                "collected_text": {
                    "type": "string",
                    "description": "ข้อความทั้งหมดที่เก็บมาจาก web_search, fetch_page, sherlock",
                },
            },
            "required": ["username", "collected_text"],
        },
    }


def _run_username_correlation(username: str, collected_text: str) -> dict:
    result = synint_agents.username_correlation_agent(username, collected_text)

    lines = ["🔗 Username Correlation Analysis"]
    lines.append(f"Seed: {result['seed']}")
    lines.append(f"Generated variants: {len(result['generated_variants'])} รูปแบบ")
    lines.append(f"Matched variants: {len(result['matched_variants'])} รูปแบบ")
    lines.append(f"Confidence: {result['confidence_score']:.0%}")
    lines.append("")

    if result["matched_variants"]:
        lines.append("✅ พบ variants เหล่านี้ใน corpus:")
        for v in result["matched_variants"][:10]:
            lines.append(f"- {v}")
        if len(result["matched_variants"]) > 10:
            lines.append(f"... และอีก {len(result['matched_variants']) - 10} รูปแบบ")
    else:
        lines.append("❌ ไม่พบ variants ใน corpus")

    if result["clusters"]:
        lines.append("")
        lines.append("🔍 Reuse Clusters:")
        for cluster in result["clusters"]:
            lines.append(f"- {cluster['cluster_id']}: {len(cluster['variants'])} variants")

    lines.append("")
    lines.append("⚠️ หมายเหตุ:")
    for note in result["confidence_notes"]:
        lines.append(f"- {note}")

    return _plain("\n".join(lines))


# ------------------------------------------------------------- email_harvest

def email_harvest_schema():
    return {
        "name": "email_harvest",
        "description": (
            "สร้างรูปแบบอีเมลที่เป็นไปได้จากโดเมน — สร้าง role accounts (admin@, info@, support@) "
            "และ person patterns (first.last@, flast@) เป็น hypothesis เท่านั้น ไม่ได้ยืนยันว่ามีจริง"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "โดเมน (เช่น example.com)",
                },
                "first_name": {
                    "type": "string",
                    "description": "ชื่อตัวอย่าง (ถ้ารู้จัก) — default: john",
                },
                "last_name": {
                    "type": "string",
                    "description": "นามสกุลตัวอย่าง (ถ้ารู้จัก) — default: doe",
                },
            },
            "required": ["domain"],
        },
    }


def _run_email_harvest(domain: str, first_name: str = "john", last_name: str = "doe") -> dict:
    result = synint_agents.email_harvest_agent(domain, first_name, last_name)

    lines = ["📧 Email Pattern Generation"]
    lines.append(f"Domain: {result['domain']}")
    lines.append(f"Generated: {result['generated_count']} addresses")
    lines.append("")
    lines.append("🎯 Role Accounts:")
    for addr in result["generated_addresses"][:12]:
        if any(role in addr for role in ["admin", "info", "support", "sales", "security", "contact"]):
            lines.append(f"- {addr}")
    lines.append("")
    lines.append("👤 Person Patterns:")
    for addr in result["generated_addresses"][:12]:
        if not any(role in addr for role in ["admin", "info", "support", "sales", "security", "contact"]):
            lines.append(f"- {addr}")

    lines.append("")
    lines.append(f"⚠️ {result['confidence_note']}")

    return _plain("\n".join(lines))


# ------------------------------------------------------------- identity_candidate

def identity_candidate_schema():
    return {
        "name": "identity_candidate",
        "description": (
            "วิเคราะห์ identity candidates — หาว่า entities หลายตัวเป็นคนเดียวกันหรือไม่ "
            "จับคู่ตาม email, username, phone ที่ตรงกัน ต้องมี human reviewer ยืนยัน"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entities_json": {
                    "type": "string",
                    "description": 'JSON array ของ entities เช่น [{"name":"John","email":"j@ex.com"},{"name":"J.Doe","email":"j@ex.com"}]',
                },
            },
            "required": ["entities_json"],
        },
    }


def _run_identity_candidate(entities_json: str) -> dict:
    import json

    try:
        entities = json.loads(entities_json)
    except json.JSONDecodeError:
        return _plain("❌ entities_json ไม่ใช่ JSON ที่ถูกต้อง")

    if not isinstance(entities, list):
        return _plain("❌ entities_json ต้องเป็น array")

    result = synint_agents.identity_candidate_agent(entities)

    lines = ["🔍 Identity Candidate Analysis"]
    lines.append(f"Input entities: {len(entities)}")
    lines.append(f"Candidates found: {result['candidate_count']}")
    lines.append("")

    if result.get("reason"):
        lines.append(f"⚠️ {result['reason']}")
    elif result["identity_candidates"]:
        lines.append("🎯 Identity Matches:")
        for candidate in result["identity_candidates"]:
            lines.append(f"\n- Match Type: {candidate['match_type']}")
            lines.append(f"  Signal: {candidate['signal']}")
            lines.append(f"  Entities: {', '.join(candidate['entities'])}")
            lines.append(f"  Confidence: {candidate['confidence']}")
            lines.append(f"  Sources: {candidate['source_count']}")

        lines.append("")
        lines.append(f"⚠️ {result['confirmation_policy']}")

    return _plain("\n".join(lines))


# ------------------------------------------------------------- darkweb_monitor

def darkweb_monitor_schema():
    return {
        "name": "darkweb_monitor",
        "description": (
            "Dark web monitoring scaffold — เตรียม hooks สำหรับค้นข้อมูลรั่วไหล "
            "คำนวณ entropy และระบุ matching patterns (ยังไม่ได้ integrate กับ breach database จริง)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Email, username, หรือ domain ที่ต้องการค้น",
                },
            },
            "required": ["target"],
        },
    }


def _run_darkweb_monitor(target: str) -> dict:
    result = synint_agents.darkweb_monitor_agent(target)

    lines = ["🕵️ Dark Web Monitor (Scaffold)"]
    lines.append(f"Target: {result['search_target']}")
    lines.append(f"Entropy: {result['target_entropy']}")
    lines.append(f"Classification: {result['agent_classification']}")
    lines.append("")
    lines.append("📚 Supported Local Sources:")
    for source in result["local_sources_supported"]:
        lines.append(f"- {source}")
    lines.append("")
    lines.append("🔍 Matching Hooks:")
    for hook, enabled in result["matching_hooks"].items():
        status = "✅" if enabled else "❌"
        lines.append(f"{status} {hook}")
    lines.append("")
    lines.append(f"⚠️ {result['note']}")

    return _plain("\n".join(lines))


TOOL_SCHEMAS = {
    "google_search": google_search_schema,
    "scan_platforms": scan_platforms_schema,
    "sherlock_username": sherlock_schema,
    "fetch_page": fetch_page_schema,
    "extract_entities": extract_entities_schema,
    "phone_info": phone_info_schema,
    "verify_official": verify_official_schema,
    "breach_check": breach_check_schema,
    "scan_phone_advanced": scan_phone_advanced_schema,
    "compare_avatars": compare_avatars_schema,
    "correlate_stylometry": correlate_stylometry_schema,
    "username_correlation": username_correlation_schema,
    "email_harvest": email_harvest_schema,
    "identity_candidate": identity_candidate_schema,
    "darkweb_monitor": darkweb_monitor_schema,
}


def build_tool_list():
    return [factory() for factory in TOOL_SCHEMAS.values()]


def execute_tool(name: str, tool_input: dict) -> dict:
    """คืน {"output": str, "images": [...]} — ต้องไม่ raise"""
    try:
        if name == "google_search":
            return _run_google_search(
                str(tool_input.get("query", "")).strip(),
                int(tool_input.get("num_results", 10)),
                str(tool_input.get("lang", "th")),
                str(tool_input.get("region", "th"))
            )
        if name == "scan_platforms":
            return _run_scan_platforms(str(tool_input.get("username", "")).strip())
        if name == "sherlock_username":
            return _run_sherlock(str(tool_input.get("username", "")).strip())
        if name == "fetch_page":
            return _run_fetch(
                str(tool_input.get("url", "")).strip(),
                str(tool_input.get("focus", "") or ""),
            )
        if name == "extract_entities":
            return _run_extract_entities(str(tool_input.get("text", "")))
        if name == "phone_info":
            return _run_phone_info(str(tool_input.get("number", "")))
        if name == "verify_official":
            return _run_verify_official(
                str(tool_input.get("value", "")), str(tool_input.get("claimed_entity", "") or "")
            )
        if name == "breach_check":
            return _run_breach_check(str(tool_input.get("email", "")))
        if name == "scan_phone_advanced":
            return _run_scan_phone_advanced(str(tool_input.get("phone_number", "")))
        if name == "compare_avatars":
            return _run_compare_avatars(
                str(tool_input.get("avatar_url_1", "")),
                str(tool_input.get("avatar_url_2", "")),
            )
        if name == "correlate_stylometry":
            return _run_correlate_stylometry(
                str(tool_input.get("text1", "")),
                str(tool_input.get("text2", "")),
            )
        if name == "username_correlation":
            return _run_username_correlation(
                str(tool_input.get("username", "")),
                str(tool_input.get("collected_text", "")),
            )
        if name == "email_harvest":
            return _run_email_harvest(
                str(tool_input.get("domain", "")),
                str(tool_input.get("first_name", "") or "john"),
                str(tool_input.get("last_name", "") or "doe"),
            )
        if name == "identity_candidate":
            return _run_identity_candidate(str(tool_input.get("entities_json", "")))
        if name == "darkweb_monitor":
            return _run_darkweb_monitor(str(tool_input.get("target", "")))
        return _plain(f"ไม่รู้จักเครื่องมือชื่อ '{name}'")
    except Exception as exc:  # noqa: BLE001 — tool ต้องไม่ทำให้ agent ล้ม
        return _plain(f"เครื่องมือ '{name}' เกิดข้อผิดพลาด: {type(exc).__name__}: {exc}")
