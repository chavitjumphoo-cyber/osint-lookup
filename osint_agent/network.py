"""Shared HTTP safeguards and bounded image downloads for OSINT tools."""

import ipaddress
import random
import socket
import threading
import time
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Research/1.0"
MAX_IMAGE_BYTES = 1_500_000
IMAGE_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

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


def _is_public_host(host: str) -> bool:
    """กัน SSRF — ปฏิเสธ hostname ที่ชี้ไป loopback/private/reserved"""
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not ip.is_global or ip.is_multicast:
            return False
    return True


MAX_REDIRECTS = 5


class UnsafeURLError(Exception):
    pass


def _check_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        parsed.port  # Validate malformed ports before issuing a request.
    except ValueError as exc:
        raise UnsafeURLError("รูปแบบ URL ไม่ถูกต้อง") from exc
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("รองรับเฉพาะ http:// และ https://")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURLError("ไม่รองรับ URL ที่ฝังข้อมูลเข้าสู่ระบบ")
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


def download_image(url: str, timeout: float = 10, max_bytes: int = MAX_IMAGE_BYTES) -> tuple[bytes, str]:
    """Download a public image, validating every redirect and limiting memory use."""
    response = safe_get(url, timeout=timeout, stream=True)
    try:
        response.raise_for_status()
        media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if media_type not in IMAGE_MEDIA_TYPES:
            raise ValueError("URL ไม่ได้ส่งกลับรูปภาพที่รองรับ")
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("รูปภาพมีขนาดใหญ่เกินที่กำหนด")
            chunks.append(chunk)
        return b"".join(chunks), media_type
    finally:
        response.close()
