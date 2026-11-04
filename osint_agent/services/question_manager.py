"""คำถามที่การสืบสวนต้องตอบ — ใช้เป็น coverage gate และ critic"""

from __future__ import annotations

QUESTIONS = {
    "person": [
        "ชื่อที่ปรากฏคืออะไร",
        "username หลักคืออะไร",
        "โปรไฟล์ใดน่าจะเป็นบุคคลเดียวกัน",
        "อาชีพ องค์กร หรือการศึกษาคืออะไร",
        "มีพื้นที่สาธารณะที่ระบุเองหรือไม่",
        "มีอีเมล เบอร์ หรือเว็บไซต์ใด",
        "มีความสัมพันธ์ที่แหล่งระบุโดยตรงหรือไม่",
        "มีประวัติ scam หรือไม่",
        "มี contradictions อะไร",
        "ข้อมูลใดที่ยังตอบไม่ได้",
    ],
    "generic": [
        "ตัวระบุที่พบมีอะไรบ้าง",
        "แหล่งใดยืนยันตัวระบุนั้น",
        "มีข้อมูลเพิ่มจากหน้าเว็บหรือไม่",
        "มี contradictions อะไร",
        "ข้อมูลใดที่ยังตอบไม่ได้",
    ],
}


def for_target(target_type: str) -> list[dict]:
    key = "person" if target_type in {"name", "username", "email", "phone"} else "generic"
    return [{"question": text, "status": "open", "evidence": []} for text in QUESTIONS[key]]


def answer(questions: list[dict], keyword: str, evidence: list[str], partial: bool = False) -> list[str]:
    """ทำเครื่องหมายคำถามที่เกี่ยวข้องว่าตอบแล้ว/บางส่วน"""
    changed = []
    for item in questions:
        if item["status"] != "open":
            continue
        if keyword and keyword in item["question"]:
            item["status"] = "partial" if partial else "answered"
            item["evidence"] = evidence[:5]
            changed.append(item["question"])
    return changed


def remaining(questions: list[dict]) -> list[str]:
    return [item["question"] for item in questions if item["status"] == "open"]


def coverage(questions: list[dict]) -> dict:
    total = len(questions) or 1
    answered = sum(1 for item in questions if item["status"] in {"answered", "partial"})
    return {"answered": answered, "total": total, "ratio": round(answered / total, 2)}
