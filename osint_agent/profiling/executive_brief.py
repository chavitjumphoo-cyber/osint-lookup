"""Executive Brief — คำตอบหน้าเดียวที่อ่านเข้าใจก่อนรายละเอียด

LLM เขียนได้ แต่ validator ตัด claim ที่ไม่มี artifact จริง และห้ามยกระดับความมั่นใจเกินหลักฐาน
"""

from __future__ import annotations

import json
import os
import re

CONF_ORDER = {"Confirmed": 4, "Probable": 3, "Possible": 2, "Unverified": 1, "Inferred": 1, "Speculative": 0}


def _valid(evidence: list[str], valid_ids: set[str]) -> list[str]:
    return [eid for eid in evidence if eid in valid_ids][:6]


def _profile_conf(profiles: list[dict]) -> str:
    opened = [p for p in profiles if p.get("evidence")]
    if not opened:
        return "Unverified"
    return max((p.get("confidence", "Unverified") for p in opened), key=lambda c: CONF_ORDER.get(c, 0))


def _facts(data: dict) -> list[dict]:
    identity = data["identity"]
    facts = []
    mapping = (
        ("ชื่อที่ปรากฏ", identity.get("names")),
        ("ชื่อเล่น/นามแฝง", identity.get("aliases")),
        ("นามสกุลที่ใช้เป็น pivot", identity.get("family_names")),
        ("แพลตฟอร์ม", sorted({p["platform"] for p in data.get("profiles_detail", [])})),
        ("อาชีพ/บทบาท", identity.get("organizations")),
        ("พื้นที่", identity.get("locations")),
        ("อีเมล", identity.get("emails")),
        ("เบอร์", identity.get("phones")),
    )
    for label, values in mapping:
        if values:
            facts.append({"label": label, "value": ", ".join(values[:5])})
    return facts


def build(data: dict, artifacts: list[dict]) -> dict:
    valid = {a["artifact_id"] for a in artifacts}
    profiles = data.get("profiles_detail") or []
    confidence = _profile_conf(profiles)
    name = (data["identity"].get("names") or [None])[0]
    platforms = sorted({p["platform"] for p in profiles})
    usernames = sorted({p["username"] for p in profiles if p.get("username")})[:5]
    locations = data["identity"].get("locations") or []
    orgs = data["identity"].get("organizations") or []
    relations = data.get("explicit_relations") or []
    cog = data.get("cognitive") or {}

    if name:
        headline = f"เป้าหมายมีความเป็นไปได้ว่าเป็น {name}"
        answer = (
            f"จากหลักฐานสาธารณะที่เปิดอ่านได้ เป้าหมายมีความเป็นไปได้ว่าเป็น **{name}**"
        )
        if usernames:
            answer += f" ซึ่งใช้ชื่อบัญชี {', '.join(f'`{u}`' for u in usernames)}"
        if platforms:
            answer += f" บน {', '.join(platforms[:4])}"
        answer += f" ระดับความมั่นใจโดยรวมคือ **{confidence}**"
        if confidence in {"Unverified", "Possible", "Speculative"}:
            answer += " และยังไม่ควรถือเป็นการยืนยันตัวบุคคล"
        answer += "."
    elif usernames:
        headline = "ยังไม่ทราบชื่อจริง แต่พบบัญชีที่น่าจะเกี่ยวข้อง"
        answer = (
            "ยังไม่พบชื่อจริงจากแหล่งที่ยืนยันได้ แต่พบชื่อบัญชี "
            + ", ".join(usernames)
            + f" ระดับความมั่นใจ **{confidence}**"
        )
    else:
        headline = "ยังไม่สามารถระบุตัวบุคคลได้จากข้อมูลที่เข้าถึง"
        answer = "หลักฐานที่พบยังไม่พอระบุชื่อหรือตัวตน ต้องเก็บข้อมูลเพิ่ม"

    assessment = []
    if orgs or data.get("interests"):
        assessment.append(
            "ร่องรอยที่พบชี้ไปทาง " + ", ".join((orgs + data.get("interests", []))[:5])
            + " แต่เป็นข้อมูลจากโปรไฟล์/โพสต์ที่ยังต้องยืนยัน"
        )
    if locations:
        assessment.append("พบการระบุพื้นที่สาธารณะ " + ", ".join(locations[:3]) + " โดยไม่ใช่ที่อยู่ปัจจุบัน")
    if not assessment:
        assessment.append("ยังไม่มีข้อมูลพอสรุปวิถีชีวิตหรืออาชีพ")

    rel_summary = "ยังไม่พบข้อความที่ระบุความสัมพันธ์โดยตรง"
    if relations:
        rel_summary = "; ".join(
            f"{r.get('relationship')}: {r.get('name')} ({r.get('snippet', '')[:80]})" for r in relations[:3]
        )
    elif data["identity"].get("family_names"):
        rel_summary = (
            "พบนามสกุล " + ", ".join(data["identity"]["family_names"][:3])
            + " ใช้เป็น pivot ได้ แต่ยังไม่ยืนยันความสัมพันธ์"
        )

    six_labels = {
        "identity": "อัตลักษณ์",
        "geo_temporal": "พื้นที่และเวลา",
        "psychological": "จิตวิทยา",
        "technical": "เทคนิค",
        "ideological": "อุดมการณ์",
        "opsec": "OpSec",
    }
    six_summary = "ยังประเมินไม่ได้ทุกมิติ"
    if cog:
        six_summary = "; ".join(
            f"{label}: {cog.get(key, {}).get('assessment', 'ประเมินไม่ได้')} "
            f"({cog.get(key, {}).get('confidence', 'Unverified')})"
            for key, label in six_labels.items()
        )

    confirmed = [
        f"{p['platform']}:{p.get('username')} — {', '.join(p['display_names'][:1]) or 'มีโปรไฟล์'}"
        for p in profiles if p.get("confidence") == "Confirmed"
    ][:6]
    probable = [f"{p['platform']}:{p.get('username')}" for p in profiles if p.get("confidence") == "Probable"][:6]
    contradictions = [
        f"{c['kind']} `{c['value']}`: {', '.join(c['detail'])}" for c in data.get("contradictions", [])[:6]
    ]
    unknowns = list(data.get("questions_unanswered") or [])[:8]
    if not unknowns:
        unknowns = ["ยังไม่ยืนยันชื่อจริงจากแหล่งทางการ"]

    evidence = sorted({eid for p in profiles for eid in p.get("evidence", [])})[:10]
    return {
        "headline": headline,
        "identity_answer": answer,
        "confidence": confidence,
        "quick_facts": _facts(data),
        "overall_assessment": " ".join(assessment),
        "relationships_summary": rel_summary,
        "six_d_summary": six_summary,
        "confirmed": confirmed,
        "probable": probable,
        "contradictions": contradictions,
        "unknowns": unknowns,
        "recommended_next_steps": list(data.get("next_pivots") or [])[:6],
        "evidence_ids": _valid(evidence, valid),
    }


def validate(brief: dict, artifacts: list[dict], profiles: list[dict]) -> dict:
    valid = {a["artifact_id"] for a in artifacts}
    cleaned = dict(brief)
    cleaned["evidence_ids"] = _valid(cleaned.get("evidence_ids") or [], valid)
    if not cleaned["evidence_ids"]:
        cleaned["confidence"] = "Unverified"
        cleaned["identity_answer"] = (
            cleaned.get("identity_answer", "") + " (ยังไม่มีหลักฐานที่อ้างอิงได้โดยตรง)"
        )
    if cleaned.get("confidence") == "Confirmed":
        if len({p.get("platform") for p in profiles if p.get("evidence")}) < 2:
            cleaned["confidence"] = "Probable"
    return cleaned


def llm_build(data: dict, artifacts: list[dict]) -> dict:
    if os.environ.get("OSINT_LLM_REPORT", "1") == "0":
        return build(data, artifacts)
    try:
        from vendor._compat import complete_text

        schema = {
            "headline": "", "identity_answer": "", "confidence": "", "quick_facts": [],
            "overall_assessment": "", "relationships_summary": "", "six_d_summary": "",
            "confirmed": [], "probable": [], "contradictions": [], "unknowns": [],
            "recommended_next_steps": [], "evidence_ids": [],
        }
        payload = {
            "schema": schema,
            "data": {k: v for k, v in data.items() if not k.startswith("_")},
            "artifact_ids": [a["artifact_id"] for a in artifacts][:120],
        }
        raw = complete_text(
            "เขียน Executive Brief ภาษาไทย 1 หน้า: เริ่มด้วยคำตอบว่าเป้าหมายน่าจะเป็นใคร "
            "เป็นร้อยแก้ว ไม่ใช่รายการ URL; ใช้เฉพาะข้อมูลใน data; ทุก claim สำคัญต้องมี evidence_ids; "
            "ห้ามสรุปครอบครัวจากนามสกุลซ้ำ; ถ้าไม่พอให้เขียนว่ายังยืนยันไม่ได้; ตอบ JSON เท่านั้น",
            [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)[:16000]}],
            max_tokens=2600,
        )
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return build(data, artifacts)
        return validate({**build(data, artifacts), **json.loads(match.group(0))}, artifacts, data.get("profiles_detail") or [])
    except Exception:  # noqa: BLE001
        return build(data, artifacts)


def render(brief: dict) -> str:
    out = ["## สรุปหน้าเดียว", "", f"### {brief.get('headline', '')}", "", brief.get("identity_answer", ""), ""]
    if brief.get("quick_facts"):
        out += ["| รายการ | ค่า |", "|---|---|"]
        out += [f"| {item['label']} | {item['value']} |" for item in brief["quick_facts"]]
        out.append("")
    out += ["**ภาพรวม**", brief.get("overall_assessment", ""), ""]
    out += ["**ความสัมพันธ์**", brief.get("relationships_summary", ""), ""]
    out += ["**สรุป 6D**", brief.get("six_d_summary", ""), ""]
    for key, title in (
        ("confirmed", "ยืนยันได้"),
        ("probable", "มีความเป็นไปได้"),
        ("contradictions", "ขัดแย้ง"),
        ("unknowns", "ยังตอบไม่ได้"),
        ("recommended_next_steps", "จุดที่ควรสืบต่อ"),
    ):
        if brief.get(key):
            out += [f"**{title}**"] + [f"- {item}" for item in brief[key]] + [""]
    out += ["*รายละเอียดเชิงเทคนิค หลักฐาน และ 6D อยู่ในส่วนถัดไป*", ""]
    return "\n".join(out)
