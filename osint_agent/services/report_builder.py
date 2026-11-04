"""สร้างรายงานสืบสวนจากหลักฐาน — deterministic เป็นค่าเริ่มต้น, LLM ช่วยเรียบเรียงถ้ามี key"""

from __future__ import annotations

import os
from collections import Counter

from ..core.evidence import wrap_untrusted

CONFIDENCE_BY_TIER = {
    "direct": "Probable",
    "derived": "Unverified",
    "inferred": "Inferred",
    "enrichment": "Speculative",
}


def _confidence(evidence: list[dict], evidence_type: str) -> str:
    tiers = {item.get("evidence_tier") for item in evidence if item.get("evidence_type") == evidence_type}
    sources = {
        item.get("source_agent") for item in evidence if item.get("evidence_type") == evidence_type
    }
    if "direct" in tiers and len(sources) >= 2:
        return "Confirmed"
    for tier in ("direct", "derived", "inferred", "enrichment"):
        if tier in tiers:
            return CONFIDENCE_BY_TIER[tier]
    return "Speculative"


def _limitations(run: dict, evidence: list[dict], findings: list[dict]) -> list[str]:
    blocked = sum(1 for item in findings if item.get("status") == "blocked")
    failed = sum(1 for item in findings if item.get("status") == "failed")
    notes = [
        "รวบรวมจากข้อมูลสาธารณะเท่านั้น ไม่ได้ bypass การล็อกอินหรือเจาะระบบ",
        "การไม่พบข้อมูลไม่ยืนยันว่าปลอดภัย — บัญชีม้า/เว็บใหม่มักยังไม่มีใครรายงาน",
    ]
    if blocked:
        notes.append(f"มี {blocked} แหล่งที่ถูกบล็อกหรือต้องล็อกอิน จึงยืนยันไม่ได้")
    if failed:
        notes.append(f"มี {failed} เครื่องมือที่เรียกไม่สำเร็จ")
    if not evidence:
        notes.append("ไม่พบหลักฐานที่สกัดเป็น identifier ได้")
    return notes


def build_report(run: dict, evidence: list[dict], findings: list[dict], candidates: list[dict]) -> str:
    by_type = Counter(item.get("evidence_type") for item in evidence)
    sources = sorted({item.get("source_agent") for item in evidence if item.get("source_agent")})

    lines = ["# แฟ้มข่าวกรอง (Subject Intelligence Dossier)", ""]
    lines += [
        f"- **เป้าหมาย**: `{run['target']}` ({run['target_type']})",
        f"- **โปรไฟล์**: {run['profile']}",
        f"- **Run**: `{run['id']}`",
        f"- **สถานะ**: {run['status']}",
        "",
        "## 1. บทสรุปผู้บริหาร",
        "",
        (
            f"พบหลักฐาน {len(evidence)} ชิ้นจาก {len(sources)} แหล่ง "
            f"(ประเภท: {', '.join(f'{k}={v}' for k, v in sorted(by_type.items())) or 'ไม่มี'})"
        ),
    ]
    direct = [item for item in evidence if item.get("evidence_tier") == "direct"]
    if direct:
        lines.append(f"หลักฐานตรง (direct) {len(direct)} ชิ้น: " + ", ".join(
            f"{item['evidence_type']}={item['value']}" for item in direct[:8]
        ))
    lines.append("")

    lines += ["## 2. ระเบียบวิธี", ""]
    lines.append(f"ใช้ playbook `{run['target_type']}` และเครื่องมือ: {', '.join(sources) or '-'}")
    lines.append("ทุกผล tool ถูก hash ด้วย sha256 เพื่อตรวจสอบย้อนกลับได้")
    lines.append("")

    lines += ["## 3. ข้อค้นพบ", ""]
    for index, item in enumerate(evidence, start=1):
        confidence = _confidence(evidence, item["evidence_type"])
        lines += [
            f"### Finding {index}: {item['evidence_type']} = `{item['value']}`",
            f"- Confidence: **{confidence}**",
            f"- Source: `{item.get('source_agent')}` / `{item.get('source_reference')}`",
            f"- Evidence id: `{item.get('id')}`",
        ]
        context = item.get("supporting_context") or {}
        if context.get("output_hash"):
            lines.append(f"- Output hash: `{context['output_hash']}`")
        lines.append("")

    if candidates:
        lines += ["## 4. Identity candidates (ต้องมีมนุษย์ยืนยัน)", ""]
        for candidate in candidates:
            lines.append(
                f"- `{candidate['candidate_id']}` · {candidate.get('status')} · "
                f"entities: {', '.join(candidate.get('entity_ids', []))}"
            )
        lines.append("")

    lines += ["## 5. หลักฐานดิบ (untrusted)", ""]
    for finding in findings[:20]:
        lines += [
            f"<details><summary>{finding['tool']} · {finding.get('status')} · "
            f"{finding.get('output_hash', '')[:23]}…</summary>",
            "",
            wrap_untrusted((finding.get("output") or "")[:2000]),
            "",
            "</details>",
            "",
        ]

    lines += ["## 6. ข้อจำกัดของรายงานนี้", ""]
    lines += [f"- {note}" for note in _limitations(run, evidence, findings)]
    lines += ["", "---", ""]
    lines.append("*Confidence scale: Confirmed / Probable / Unverified / Inferred / Speculative*")
    return "\n".join(lines)


def llm_polish(report: str, evidence: list[dict]) -> str:
    if os.environ.get("OSINT_LLM_REPORT", "1") == "0":
        return report
    try:
        from vendor._compat import complete_text

        facts = "\n".join(
            f"- {item['evidence_type']}={item['value']} [{item['evidence_tier']}]" for item in evidence[:40]
        )
        return complete_text(
            "คุณเป็นนักวิเคราะห์ OSINT เรียบเรียงรายงานภาษาไทยจากรายงานร่างและข้อเท็จจริง "
            "ห้ามเพิ่ม identifier ที่ไม่มีในร่าง ห้ามเปลี่ยนระดับ confidence",
            [{"role": "user", "content": f"รายงานร่าง:\n{report}\n\nข้อเท็จจริง:\n{facts}"}],
            max_tokens=4096,
        ) or report
    except Exception:  # noqa: BLE001 — LLM ล้มต้องยังได้รายงาน
        return report
