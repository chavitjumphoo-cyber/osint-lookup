"""ชั้น HTTP: SSRF guard, rate limiter, ดาวน์โหลดรูป และ fetch_page"""

import base64
import ipaddress
import random
import re
import socket
import threading
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import (
    FETCH_MAX_CHARS,
    FETCH_TIMEOUT,
    IMAGE_MEDIA_TYPES,
    IMAGE_TIMEOUT,
    MAX_IMAGE_BYTES,
    MAX_IMAGES,
    USER_AGENT,
    plain,
)

DOMAIN_MIN_INTERVAL = 2.0
DOMAIN_JITTER = 1.5
MAX_REDIRECTS = 5


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


class UnsafeURLError(Exception):
    pass


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


def run_fetch(url: str, focus: str = "") -> dict:
    from ..services import browser

    try:
        _check_url(url)
    except UnsafeURLError as exc:
        return plain(f"ไม่สามารถเปิดได้: {exc}")

    page = None
    engine_note = ""
    if browser.available():
        try:
            page = browser.fetch_json(url, timeout=FETCH_TIMEOUT + 10)
        except browser.BrowserError as exc:
            engine_note = f"[moli ใช้ไม่ได้: {exc} — ลองใหม่ด้วย requests]\n"
    if page is None:
        try:
            page = browser.fetch_fallback(url, timeout=FETCH_TIMEOUT)
        except UnsafeURLError as exc:
            return plain(f"ไม่สามารถเปิดได้: {exc}")
        except requests.RequestException as exc:
            return plain(f"เปิดหน้าเว็บไม่สำเร็จ: {type(exc).__name__}")

    if page.status >= 400:
        return plain(
            f"หน้าเว็บตอบกลับ HTTP {page.status} — "
            "อาจต้องล็อกอินหรือถูกบล็อก bot จึงอ่านเนื้อหาไม่ได้"
        )
    if not page.html:
        return plain(f"หน้านี้ไม่ใช่ HTML (engine: {page.engine}) อ่านข้อความไม่ได้")

    soup = BeautifulSoup(page.html, "html.parser")
    images = _collect_images(soup, page.final_url or url)

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    title = page.title.strip() or (soup.title.string or "").strip() if soup.title else page.title
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))

    if focus:
        paragraphs = [p for p in text.split("\n\n") if focus.lower() in p.lower()]
        if paragraphs:
            text = "\n\n".join(paragraphs)

    if len(text) > FETCH_MAX_CHARS:
        text = text[:FETCH_MAX_CHARS] + "\n\n[... เนื้อหาถูกตัดตรงนี้ ...]"

    if not text.strip() and not images:
        return plain(f"หน้าเว็บ '{title or url}' ไม่มีข้อความหรือรูปที่อ่านได้ (อาจเป็น JavaScript ล้วน)")

    caption = f"# {title or url}\n[engine: {page.engine}]"
    if images:
        caption += f"\n\n[แนบรูปจากหน้าเว็บมาให้ {len(images)} รูป — ใช้เป็นบริบทประกอบ]"
    return {"output": f"{engine_note}{caption}\n{text}", "images": images}
