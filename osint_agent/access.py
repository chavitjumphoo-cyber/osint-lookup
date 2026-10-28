"""
บันทึกการใช้งานแบบต่อท้ายเท่านั้น — แต่ละบรรทัดผูก hash ของบรรทัดก่อน แก้หรือลบย้อนหลังแล้วตรวจจับได้
"""

import hashlib
import json
import os
import threading
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(ROOT, "audit")
AUDIT_FILE = os.path.join(AUDIT_DIR, "audit.jsonl")

_lock = threading.Lock()


def _last_hash() -> str:
    if not os.path.exists(AUDIT_FILE):
        return "0" * 64
    with open(AUDIT_FILE, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        fh.seek(max(0, fh.tell() - 8192))
        lines = fh.read().decode("utf-8", errors="replace").strip().splitlines()
    if not lines:
        return "0" * 64
    try:
        return json.loads(lines[-1])["hash"]
    except (ValueError, KeyError):
        return "corrupt"


def audit(event: str, actor: dict, **details) -> dict:
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with _lock:
        entry = {
            "time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "event": event,
            "actor": actor.get("name"),
            **details,
            "prev": _last_hash(),
        }
        payload = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        entry["hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with open(AUDIT_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify_audit_chain() -> tuple[bool, int, str]:
    """คืน (ok, จำนวนบรรทัดหรือบรรทัดที่พัง, ข้อความ)"""
    if not os.path.exists(AUDIT_FILE):
        return True, 0, "ยังไม่มีบันทึก"
    prev = "0" * 64
    count = 0
    with open(AUDIT_FILE, "r", encoding="utf-8") as fh:
        for count, line in enumerate(fh, start=1):
            entry = json.loads(line)
            stored = entry.pop("hash", None)
            if entry.get("prev") != prev:
                return False, count, f"บรรทัด {count}: ห่วงโซ่ขาด (มีการลบหรือแทรกบรรทัด)"
            payload = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != stored:
                return False, count, f"บรรทัด {count}: เนื้อหาถูกแก้ไข"
            prev = stored
    return True, count, f"ตรวจครบ {count} บรรทัด ไม่พบการแก้ไข"


if __name__ == "__main__":
    ok, _, message = verify_audit_chain()
    print(("OK  " if ok else "FAIL ") + message)
