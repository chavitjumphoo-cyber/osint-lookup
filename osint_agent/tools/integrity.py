"""ตรวจว่า payload ที่อ้างว่ามาจาก tool ตรงกับ hash จริงหรือไม่"""

import json

from ..core.evidence import verify_hash
from .base import plain


def verify_output_integrity_schema():
    return {
        "name": "verify_output_integrity",
        "description": (
            "ตรวจ output_hash ของผล tool ว่าตรงกับ payload จริง — ใช้ตรวจว่าข้อมูลที่อ้าง "
            "ในรายงานถูกผลิตโดย tool call นั้นจริง ไม่ถูกแต่งขึ้นภายหลัง"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string"},
                "endpoint": {"type": "string"},
                "status": {"type": "string"},
                "result": {"type": "string"},
                "output_hash": {"type": "string"},
            },
            "required": ["tool", "endpoint", "status", "result", "output_hash"],
        },
    }


def run_verify_output_integrity(
    tool: str, endpoint: str, status: str, result: str, output_hash: str
) -> dict:
    return plain(json.dumps(verify_hash(tool, endpoint, status, result, output_hash), ensure_ascii=False))
