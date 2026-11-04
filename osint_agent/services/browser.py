"""เบราว์เซอร์สำหรับ agent — ใช้ Moli ก่อน แล้ว fallback เป็น requests

Moli: https://github.com/lexmount/moli (headless browser, Apache-2.0)
เรียกด้วย arg list ไม่ผ่าน shell, จำกัดเวลาและขนาดผล, บล็อก private network
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..tools.base import USER_AGENT

MOLI_TIMEOUT_MS = 15_000
MAX_HTML_CHARS = 2_000_000
FALLBACK_PATHS = (Path.home() / ".local" / "bin" / "moli", Path("/usr/local/bin/moli"))


class BrowserError(Exception):
    pass


@dataclass
class Page:
    url: str
    final_url: str
    status: int
    html: str
    title: str = ""
    engine: str = "moli"


def resolve_binary() -> str | None:
    candidate = os.environ.get("MOLI_BIN")
    if candidate and Path(candidate).exists():
        return candidate
    found = shutil.which("moli")
    if found:
        return found
    for path in FALLBACK_PATHS:
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return None


def available() -> bool:
    return resolve_binary() is not None


def _run(args: list[str], timeout: float) -> str:
    binary = resolve_binary()
    if not binary:
        raise BrowserError("ไม่พบคำสั่ง moli")
    try:
        proc = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise BrowserError(f"moli ใช้เวลาเกิน {timeout:.0f} วินาที") from exc
    except OSError as exc:
        raise BrowserError(f"เรียก moli ไม่สำเร็จ: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        raise BrowserError(detail[-1] if detail else f"moli exit {proc.returncode}")
    return proc.stdout or ""


def fetch_json(url: str, timeout: float = 20.0) -> Page:
    payload = _run(
        [
            "fetch",
            "--block-private-networks",
            "--timeout",
            str(MOLI_TIMEOUT_MS),
            "--dump",
            "json",
            "--wait",
            "done",
            url,
        ],
        timeout,
    )
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise BrowserError("moli ไม่ได้คืน JSON") from exc
    return Page(
        url=url,
        final_url=str(data.get("final_url") or url),
        status=int(data.get("status") or 0),
        html=str(data.get("html") or "")[:MAX_HTML_CHARS],
        title=str(data.get("title") or ""),
    )


def fetch_markdown(url: str, timeout: float = 20.0) -> str:
    return _run(
        [
            "fetch",
            "--block-private-networks",
            "--timeout",
            str(MOLI_TIMEOUT_MS),
            "--dump",
            "markdown",
            "--wait",
            "done",
            url,
        ],
        timeout,
    )


def fetch_eval(url: str, expression: str, timeout: float = 20.0) -> str:
    """รัน JS บนหน้าแล้วคืนค่าที่ serialize เป็น JSON/text"""
    return _run(
        [
            "fetch",
            "--block-private-networks",
            "--timeout",
            str(MOLI_TIMEOUT_MS),
            "--wait",
            "done",
            "--eval",
            expression,
            url,
        ],
        timeout,
    )


def fetch_fallback(url: str, timeout: float = 15.0) -> Page:
    """fallback ด้วย requests + SSRF guard เดิม"""
    from ..tools.http import safe_get

    response = safe_get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    content_type = (response.headers.get("Content-Type") or "").lower()
    html = response.text if content_type.startswith("text/html") else ""
    return Page(
        url=url,
        final_url=response.url or url,
        status=response.status_code,
        html=html[:MAX_HTML_CHARS],
        engine="requests-fallback",
    )
