"""สังเคราะห์ Subject Intelligence Dossier จาก corpus

ค่าเริ่มต้น deterministic; ถ้ามี LLM จะให้เรียบเรียง JSON ตาม schema แล้ว render
"""

from __future__ import annotations

import json
import os
import re

from . import cognitive


def contradictions(profiles: list[dict], entities: list[dict]) -> list[dict]:
    found = []
    by_username: dict[str, list[dict]] = {}
    for profile in profiles:
        if profile["username"]:
            by_username.setdefault(profile["username"].lower(), []).append(profile)

    for username, group in by_username.items():
        names = {name.lower() for profile in group for name in profile["display_names"]}
        locations = {loc.lower() for profile in group for loc in profile["locations"]}
        if len(names) > 1:
            found.append({"kind": "display_name", "value": username, "detail": sorted(names)})
        if len(locations) > 1:
            found.append({"kind": "location", "value": username, "detail": sorted(locations)})

    multi = {}
    for entity in entities:
        multi.setdefault(entity["type"], set()).add(entity["value"].lower())
    for kind, values in multi.items():
        if kind in {"name", "location", "organization"} and len(values) > 3:
            found.append({"kind": f"many_{kind}", "value": "", "detail": sorted(values)[:10]})
    return found


def _profile_line(profile: dict) -> str:
    bits = [f"**{profile['platform']}**"]
    if profile["username"]:
        bits.append(f"`{profile['username']}`")
    if profile["display_names"]:
        bits.append(f"ชื่อที่แสดง: {', '.join(profile['display_names'][:2])}")
    if profile["bios"]:
        bits.append(f"bio: {profile['bios'][0][:180]}")
    if profile["locations"]:
        bits.append(f"พื้นที่: {', '.join(profile['locations'][:3])}")
    if profile["organizations"]:
        bits.append(f"องค์กร: {', '.join(profile['organizations'][:3])}")
    if profile["emails"]:
        bits.append(f"อีเมล: {', '.join(profile['emails'][:3])}")
    if profile["links"]:
        bits.append(f"ลิงก์: {', '.join(profile['links'][:2])}")
    bits.append(f"Confidence: {profile['confidence']}")
    bits.append(f"Evidence: {', '.join(profile['evidence'])}")
    return "- " + " · ".join(bits) + f"\n  URL: {profile['url']}"


def synthesize(
    run: dict,
    profiles: list[dict],
    entities: list[dict],
    artifacts: list[dict],
    relationships: list[dict],
    contradictions_list: list[dict],
    events: list[dict],
) -> dict:
    names = sorted({value for profile in profiles for value in profile["display_names"]})
    locations = sorted({entity["value"] for entity in entities if entity["type"] == "location"})
    orgs = sorted({value for profile in profiles for value in profile["organizations"]})
    interests = sorted({entity["value"] for entity in entities if entity["type"] == "interest"})
    emails = sorted({value for profile in profiles for value in profile["emails"]})
    phones = sorted({value for profile in profiles for value in profile["phones"]})

    lines_profiles = [{"platform": p["platform"], "username": p["username"], "url": p["url"],
                       "confidence": p["confidence"], "evidence": p["evidence"]} for p in profiles]

    summary = []
    likely = [p for p in profiles if p["confidence"] in {"Confirmed", "Probable"}]
    if likely:
        summary.append(
            "ตัวตนที่มีความเป็นไปได้สูงสุด: "
            + "; ".join(
                f"{p['platform']}:{p['username']} ({p['confidence']})" for p in likely[:5]
            )
        )
    if profiles:
        summary.append(f"พบโปรไฟล์ {len(profiles)} แห่งจาก {len({p['platform'] for p in profiles})} แพลตฟอร์ม")
    if names:
        summary.append(f"ชื่อที่แสดงซึ่งพบ: {', '.join(names[:5])}")
    if locations:
        summary.append(f"พื้นที่/สถานที่ซึ่งพบ: {', '.join(locations[:5])}")
    if not summary:
        summary.append("ยังไม่พบข้อมูลโปรไฟล์ที่ยืนยันได้จากแหล่งสาธารณะ")
    summary.append("แยกได้เป็น: ยืนยันได้ / เป็นไปได้ / ขัดแย้ง / ยังตอบไม่ได้ (ดูหัวข้อ 11 และ 15)")

    return {
        "executive_summary": summary,
        "identity": {
            "names": names,
            "locations": locations,
            "emails": emails,
            "phones": phones,
            "organizations": orgs,
        },
        "profiles": lines_profiles,
        "associates": relationships,
        "interests": interests,
        "cognitive": cognitive.evaluate(profiles, artifacts, entities),
        "geo_temporal": {"locations": locations, "events": events[:20]},
        "technical_profile": [i for i in interests if i in {"tech", "crypto", "trading"}],
        "fraud_history": [a for a in artifacts if a.get("platform") == "pantip"][:10],
        "opsec_exposure": {
            "emails": emails,
            "phones": phones,
            "leaked_profile_count": len(emails) + len(phones),
        },
        "contradictions": contradictions_list,
        "critical_pivots": [
            {"type": "username", "value": p["username"], "reason": f"พบบน {p['platform']}"}
            for p in profiles if p["username"]
        ][:10],
        "timeline": events[:30],
        "limitations": [],
        "findings": [
            {
                "statement": f"พบบัญชี {p['platform']} ของ {p['username'] or p['url']}",
                "confidence": p["confidence"],
                "evidence": p["evidence"],
                "source_url": p["url"],
            }
            for p in profiles
        ],
        "artifact_ids": [a["artifact_id"] for a in artifacts],
    }


def render_markdown(data: dict, run: dict) -> str:
    out = ["# Subject Intelligence Dossier", ""]
    out += [f"- **เป้าหมาย**: `{run['target']}` ({run['target_type']})", f"- **Run**: `{run['id']}`", ""]

    def section(title: str, items: list[str]) -> None:
        out.append(f"## {title}")
        out.append("")
        out.extend(items or ["- ไม่พบข้อมูล"])
        out.append("")

    section("1. บทสรุปผู้บริหาร", [f"- {line}" for line in data["executive_summary"]])

    identity = data["identity"]
    section(
        "2. Identity & Digital Identifiers",
        [f"- **{label}**: {', '.join(values)}" for label, values in {
            "ชื่อที่แสดง": identity["names"],
            "พื้นที่": identity["locations"],
            "อีเมล": identity["emails"],
            "เบอร์": identity["phones"],
            "องค์กร": identity["organizations"],
        }.items() if values],
    )

    out.append("## 3. Social Profiles")
    out.append("")
    for profile in data["profiles"]:
        out.append(f"- **{profile['platform']}** · `{profile['username']}` · {profile['confidence']}")
        out.append(f"  {profile['url']} · evidence: {', '.join(profile['evidence'])}")
    if not data["profiles"]:
        out.append("- ไม่พบโปรไฟล์")
    out.append("")

    section("4. Associates & Relationships", [
        f"- {item['name']} ↔ {item['handle']} (พบร่วม {item['strength']} ครั้ง)" for item in data["associates"]
    ])
    section("5. Lifestyle & Interests", [f"- {item}" for item in data["interests"]])
    section("6. Geo-temporal Signals", [f"- {item['date']}: {item['title']}" for item in data["geo_temporal"]["events"]])
    section("7. Technical Profile", [f"- {item}" for item in data["technical_profile"]])

    out.append("## 8. 6D Cognitive Profiling")
    out.append("")
    labels = {
        "identity": "8.1 Identity",
        "geo_temporal": "8.2 Geo-temporal",
        "psychological": "8.3 Psychological (OCEAN)",
        "technical": "8.4 Technical",
        "ideological": "8.5 Ideological",
        "opsec": "8.6 OpSec / Attack Surface",
    }
    for key, label in labels.items():
        item = data["cognitive"].get(key) or {}
        out.append(f"### {label}")
        out.append(f"- **{item.get('confidence', 'Unverified')}** — {item.get('assessment', 'ประเมินไม่ได้')}")
        if item.get("rationale"):
            out.append(f"- เหตุผล: {item['rationale']}")
        if item.get("evidence"):
            out.append(f"- Evidence: {', '.join(item['evidence'][:8])}")
        if item.get("metrics"):
            out.append(f"- ตัวชี้วัด: {json.dumps(item['metrics'], ensure_ascii=False)}")
        out.append("")
    out.append("*OCEAN เป็นสมมติฐานจากสถิติข้อความ ไม่ใช่แบบประเมินจิตวิทยา*")
    out.append("")

    section("9. Fraud / Scam History", [
        f"- {item.get('title') or item.get('source_url')} ({item.get('platform')})" for item in data["fraud_history"]
    ])
    section("10. OpSec Exposure", [
        f"- {key}: {', '.join(value) if isinstance(value, list) else value}"
        for key, value in data["opsec_exposure"].items()
    ])
    section("11. Contradictions", [
        f"- {item['kind']} `{item['value']}`: {', '.join(item['detail'])}" for item in data["contradictions"]
    ])
    section("12. Critical Pivot Points", [
        f"- {item['type']} `{item['value']}` — {item['reason']}" for item in data["critical_pivots"]
    ])
    section("13. Timeline", [f"- {item['date']} · {item['title']}" for item in data["timeline"]])
    section("14. Evidence Sources", [
        f"- `{item['artifact_id']}` · {item.get('source_tool')} · {item.get('status')} · {item.get('source_url')}"
        for item in data.get("_artifacts", [])
    ])
    if data.get("actions"):
        section("14B. Agent Actions", [
            f"- step {item.get('step')}: {item.get('action')} {item.get('target')} — {item.get('reason') or '-'}"
            for item in data["actions"][:40]
        ])
    section("15. Confidence Assessment & ข้อจำกัด (Limitations)", [
        f"- {line}" for line in data["limitations"]
    ] or ["- ต้องตรวจด้วยมนุษย์ก่อนใช้ตัดสินใจ"])
    out.append("---")
    out.append("*Confidence: Confirmed / Probable / Unverified / Inferred / Speculative*")
    return "\n".join(out)


def llm_synthesize(data: dict, run: dict) -> dict:
    if os.environ.get("OSINT_LLM_REPORT", "1") == "0":
        return data
    try:
        from vendor._compat import complete_text

        prompt = {
            "target": run["target"],
            "type": run["target_type"],
            "data": {key: value for key, value in data.items() if not key.startswith("_")},
        }
        raw = complete_text(
            "เขียนบทสรุป profiling ภาษาไทยเป็น JSON ตาม schema เดิม ห้ามเพิ่ม identifier ที่ไม่มี "
            "และคง evidence id ไว้ทุก finding",
            [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)[:12000]}],
            max_tokens=3000,
        )
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            return data
        parsed = json.loads(match.group(0))
        merged = {**data, **{key: value for key, value in parsed.items() if key in data}}
        merged["findings"] = _validate_findings(merged.get("findings") or [], data)
        return merged
    except Exception:  # noqa: BLE001
        return data


def _validate_findings(findings: list[dict], data: dict) -> list[dict]:
    """ตัด finding ที่อ้าง evidence id ไม่มีจริง"""
    valid = {item for item in data.get("artifact_ids", [])}
    kept = []
    for finding in findings:
        evidence = [eid for eid in (finding.get("evidence") or []) if eid in valid]
        if evidence:
            kept.append({**finding, "evidence": evidence})
    return kept
