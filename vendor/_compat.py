"""สะพานเชื่อมระหว่างโปรเจกต์กับโค้ดที่ vendor มา

- osint-d2 ออกแบบมาสำหรับ OpenAI-compatible API แต่โปรเจกต์นี้ใช้ Anthropic/MaxPlus
- osint-d2 อ่าน config จากตัวแปร OSINT_D2_* แต่โปรเจกต์นี้อ่าน .env ของตัวเอง
- ไฟล์นี้แปลงทั้งสองอย่างโดยไม่ต้องแก้โค้ด vendor กระจัดกระจาย
"""

from __future__ import annotations

import os
from typing import Any

from .osint_d2.core.config import AppSettings

DEFAULT_MODEL = "claude-sonnet-5"


def _project_config() -> dict:
    from osint_agent.agent import read_config

    return read_config()


def settings_from_project() -> AppSettings:
    """สร้าง AppSettings ของ vendor จาก .env ของโปรเจกต์"""
    config = _project_config()
    base_url = config.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
    api_key = config.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    model = config.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
    hibp = config.get("HIBP_API_KEY") or os.environ.get("HIBP_API_KEY")

    overrides: dict[str, Any] = {
        "ai_provider": "openai",
        "ai_model": model,
    }
    if base_url:
        overrides["ai_base_url"] = base_url
    if api_key:
        overrides["ai_api_key"] = api_key
    if hibp:
        overrides["hibp_api_key"] = hibp
    return AppSettings(**overrides)


def anthropic_client(api_key_override: str | None = None):
    """คืน Anthropic client ตัวเดียวกับที่ agent ใช้"""
    from osint_agent.agent import _build_client

    return _build_client(api_key_override=api_key_override)


def complete_text(
    system: str,
    messages: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    client=None,
) -> str:
    """เรียกโมเดลแบบข้อความล้วน แล้วคืนเฉพาะ text — ใช้โดย vendor ที่ไม่ส่ง tool"""
    client = client or anthropic_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()
