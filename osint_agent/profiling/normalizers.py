"""ทำความสะอาดข้อความก่อนสกัด"""

from __future__ import annotations

import html
import re


def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def snippet(text: str, limit: int = 300) -> str:
    text = clean(text)
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"
