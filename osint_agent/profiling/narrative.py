"""Narrative Intelligence Summary — ร้อยแก้วที่มีหลักฐานกำกับ

LLM เขียนได้ แต่ validator บังคับให้ทุกย่อหน้าอ้าง artifact ที่มีจริง
"""

from __future__ import annotations

import json
import os
import re

CONF_ORDER = {"Confirmed": 4, "Probable": 3, "Possible": 2, "Unverified": 1, "Inferred": 1, "Speculative": 0}


def _ids(profiles: list[dict], predicate=None) -> list[str]:
    ids = []
    for profile in profiles:
        if predicate and not predicate(profile):
            continue
        ids.extend(profile.get("evidence", [])[:3])
    return sorted(set(ids))[:8]


def _name(profiles: list[dict]) -> str | None:
    for profile in profiles:
        if profile.get("display_names"):
            return profile["display_names"][0]
    return None


def _best(profiles: list[dict]) -> str:
    if not profiles:
        return "Unverified"
    return max((p.get("confidence", "Unverified") for p in profiles), key=lambda c: CONF_ORDER.get(c, 0))


def build(data: dict, artifacts: list[dict]) -> dict:
    profiles = data.get("profiles_detail") or []
    identity = data["identity"]
    family = identity.get("family_names") or []
    explicit = data.get("explicit_relations") or []
    valid = {a["artifact_id"] for a in artifacts}
    name = (identity.get("names") or [None])[0]
    confidence = _best(profiles)
    platforms = sorted({p["platform"] for p in profiles if p.get("evidence")})
    usernames = sorted({p["username"] for p in profiles if p.get("username")})[:4]
    locations = identity.get("locations") or []
    orgs = identity.get("organizations") or []
    interests = data.get("interests") or []
    cog = data.get("cognitive") or {}

    if name:
        opening = (
            f"จากหลักฐานสาธารณะที่ตรวจสอบได้ เป้าหมายมีความเป็นไปได้ว่าเกี่ยวข้องกับบุคคลชื่อ **{name}**"
        )
        if usernames:
            opening += f" ซึ่งใช้ชื่อผู้ใช้ {', '.join(f'`{u}`' for u in usernames)}"
        if platforms:
            opening += f" บน {', '.join(platforms[:4])}"
        opening += f" ระดับความมั่นใจโดยรวมอยู่ที่ **{confidence}**"
        if confidence in {"Unverified", "Speculative"}:
            opening += " และยังไม่ถือเป็นการยืนยันตัวบุคคล"
        opening += "."
    else:
        opening = (
            "ยังไม่พบหลักฐานที่เพียงพอจะระบุชื่อหรือตัวตนของเป้าหมายได้ "
            f"ข้อมูลที่พบอยู่ในระดับ **{confidence}**"
        )

    digital = "ยังไม่พบตัวระบุดิจิทัลที่เชื่อมโยงกัน"
    if usernames or identity.get("emails") or identity.get("phones"):
        bits = []
        if usernames:
            bits.append("username " + ", ".join(usernames))
        if identity.get("emails"):
            bits.append("อีเมล " + ", ".join(identity["emails"][:3]))
        if identity.get("phones"):
            bits.append("เบอร์ " + ", ".join(identity["phones"][:3]))
        digital = "พบตัวระบุที่เกี่ยวข้อง ได้แก่ " + "; ".join(bits) + " แต่ username ซ้ำเพียงอย่างเดียวไม่ยืนยันว่าเป็นคนเดียวกัน"

    work = "ยังไม่พบหลักฐานด้านอาชีพหรือการศึกษา"
    if orgs or interests:
        parts = []
        if orgs:
            parts.append("องค์กรที่ปรากฏ: " + ", ".join(orgs[:3]))
        if interests:
            parts.append("หัวข้อที่พบซ้ำ: " + ", ".join(interests[:4]))
        work = "; ".join(parts) + " — เป็นข้อมูลจากโปรไฟล์/โพสต์ ยังต้องยืนยันด้วยแหล่งอิสระ"

    geo = "ยังไม่พบสถานที่สาธารณะที่ยืนยันได้"
    if locations:
        geo = "พบการระบุพื้นที่สาธารณะ " + ", ".join(locations[:3]) + " แต่ไม่ใช่ที่อยู่ปัจจุบัน"

    fam = "ยังไม่พบข้อความที่ระบุความสัมพันธ์ครอบครัวโดยตรง"
    if explicit:
        lines = [
            f"{item.get('relationship')}: {item.get('name')} ({item.get('snippet', '')[:100]})"
            for item in explicit[:3]
        ]
        fam = "; ".join(lines)
    elif family:
        fam = "พบนามสกุล " + ", ".join(family[:3]) + " ซึ่งใช้เป็น pivot ได้ แต่ยังไม่ยืนยันความสัมพันธ์"

    six = {}
    for key, _label in (
        ("identity", "Identity"),
        ("geo_temporal", "Geo-temporal"),
        ("psychological", "Psychological/OCEAN"),
        ("technical", "Technical"),
        ("ideological", "Ideological"),
        ("opsec", "OpSec"),
    ):
        item = cog.get(key) or {}
        six[key] = {
            "narrative": item.get("assessment", "ประเมินไม่ได้"),
            "confidence": item.get("confidence", "Unverified"),
            "evidence": [eid for eid in item.get("evidence", []) if eid in valid][:6],
        }

    contradictions = [
        f"{c['kind']} `{c['value']}`: {', '.join(c['detail'])}" for c in data.get("contradictions", [])[:5]
    ]

    claims = {
        "identity_answer": {"narrative": opening, "confidence": confidence, "evidence": _ids(profiles)[:6]},
        "digital_identity": {"narrative": digital, "evidence": _ids(profiles)[:6]},
        "work_education": {"narrative": work, "evidence": _ids(profiles, lambda p: bool(p.get("organizations") or p.get("languages")))[:6]},
        "geo_temporal": {"narrative": geo, "evidence": _ids(profiles, lambda p: bool(p.get("locations")))[:6]},
        "family": {"narrative": fam, "evidence": [i.get("artifact_id") for i in explicit if i.get("artifact_id")][:6]},
        "lifestyle": {"narrative": "ความสนใจที่พบ: " + ", ".join(interests[:5]) if interests else "ยังไม่พบความสนใจที่ชัดเจน", "evidence": []},
        "six_d": six,
        "contradictions": contradictions,
        "limitations": data.get("limitations", []),
    }
    return claims


def validate(claims: dict, artifacts: list[dict]) -> dict:
    valid = {a["artifact_id"] for a in artifacts}
    cleaned = {}
    for key, value in claims.items():
        if key in {"six_d", "contradictions", "limitations"}:
            cleaned[key] = value
            continue
        if not isinstance(value, dict):
            continue
        evidence = [eid for eid in (value.get("evidence") or []) if eid in valid]
        cleaned[key] = {**value, "evidence": evidence}
    six = {}
    for key, value in (claims.get("six_d") or {}).items():
        six[key] = {**value, "evidence": [eid for eid in (value.get("evidence") or []) if eid in valid]}
    cleaned["six_d"] = six
    return cleaned


def llm_build(data: dict, artifacts: list[dict]) -> dict:
    if os.environ.get("OSINT_LLM_REPORT", "1") == "0":
        return build(data, artifacts)
    try:
        from vendor._compat import complete_text

        schema = {
            "identity_answer": {"narrative": "", "confidence": "", "evidence": []},
            "digital_identity": {"narrative": "", "evidence": []},
            "work_education": {"narrative": "", "evidence": []},
            "geo_temporal": {"narrative": "", "evidence": []},
            "family": {"narrative": "", "evidence": []},
            "lifestyle": {"narrative": "", "evidence": []},
            "six_d": {k: {"narrative": "", "confidence": "", "evidence": []} for k in
                      ("identity", "geo_temporal", "psychological", "technical", "ideological", "opsec")},
            "contradictions": [],
            "limitations": [],
        }
        payload = {
            "schema": schema,
            "data": {k: v for k, v in data.items() if not k.startswith("_")},
            "artifact_ids": [a["artifact_id"] for a in artifacts][:120],
        }
        raw = complete_text(
            "คุณเป็นนักวิเคราะห์ OSINT ภาษาไทย เขียนบทสรุปร้อยแก้วสั้น ๆ ว่าบุคคลนี้น่าจะเป็นใคร "
            "ตอบ JSON ตาม schema เท่านั้น ทุกย่อหน้าต้องมี evidence id จาก artifact_ids "
            "ห้ามแต่ง identifier; ใช้คำว่า 'มีความเป็นไปได้ว่า' และแยกสิ่งที่ยืนยันไม่ได้",
            [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)[:16000]}],
            max_tokens=3000,
        )
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return build(data, artifacts)
        return validate(json.loads(match.group(0)), artifacts)
    except Exception:  # noqa: BLE001
        return build(data, artifacts)


def render(claims: dict) -> str:
    out = ["## บุคคลนี้น่าจะเป็นใคร", "", claims.get("identity_answer", {}).get("narrative", "ยังไม่สามารถระบุได้"), ""]
    for key, title in (
        ("digital_identity", "อัตลักษณ์ดิจิทัล"),
        ("work_education", "อาชีพ/การศึกษา/องค์กร"),
        ("geo_temporal", "พื้นที่และเวลา"),
        ("family", "ครอบครัว/บุคคลแวดล้อม"),
        ("lifestyle", "ความสนใจ"),
    ):
        out += [f"### {title}", "", claims.get(key, {}).get("narrative", "ยังไม่พบข้อมูล"), ""]
    out += ["### 6D", ""]
    labels = {"identity": "Identity", "geo_temporal": "Geo-temporal", "psychological": "Psychological/OCEAN",
              "technical": "Technical", "ideological": "Ideological", "opsec": "OpSec"}
    for key, label in labels.items():
        item = claims.get("six_d", {}).get(key, {})
        out.append(f"- **{label}** ({item.get('confidence', 'Unverified')}): {item.get('narrative', 'ประเมินไม่ได้')}")
    out.append("")
    if claims.get("contradictions"):
        out += ["### สิ่งที่ขัดแย้ง", ""] + [f"- {c}" for c in claims["contradictions"]] + [""]
    if claims.get("limitations"):
        out += ["### ข้อจำกัด", ""] + [f"- {c}" for c in claims["limitations"]] + [""]
    return "\n".join(out)
