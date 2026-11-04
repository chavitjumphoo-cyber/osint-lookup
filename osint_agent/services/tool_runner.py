"""รัน tool แล้วแปลงผลเป็น ToolOutcome ตามสัญญากลาง"""

from __future__ import annotations

from ..core.evidence import ToolOutcome, build_outcome
from ..tools import execute_tool


def run_tool(tool: str, args: dict, max_chars: int | None = None) -> ToolOutcome:
    raw = execute_tool(tool, args)
    output = raw.get("output", "") if isinstance(raw, dict) else str(raw)
    images = raw.get("images", []) if isinstance(raw, dict) else []
    if max_chars and len(output) > max_chars:
        output = output[:max_chars] + "\n[... ผลลัพธ์ยาวเกิน ถูกตัด ...]"
    return build_outcome(tool, f"tool:{tool}", output, images)
