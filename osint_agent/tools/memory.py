"""ค้นหลักฐานที่เก็บไว้ใน run ด้วย BM25"""

from .base import plain


def search_evidence_schema():
    return {
        "name": "search_evidence",
        "description": (
            "ค้นหลักฐานทั้งหมดที่เก็บมาใน run นี้ด้วย BM25 — ใช้เมื่อต้องหาว่าเคยพบ "
            "อีเมล/เบอร์/ชื่อ/URL นี้ที่ไหนมาก่อน score 0-1 อ่อน 1-3 ปานกลาง 3+ แรง "
            "ไม่ใช่เปอร์เซ็นต์"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "run_id": {"type": "string"},
                "query": {"type": "string"},
            },
            "required": ["run_id", "query"],
        },
    }


def run_search_evidence(run_id: str, query: str) -> dict:
    from ..services.evidence_memory import EvidenceMemory
    from ..services.store import RunStore

    evidence = RunStore().list_evidence(run_id)
    memory = EvidenceMemory()
    memory.index(evidence)
    hits = memory.search(query)
    if not hits:
        return plain(f"ไม่พบหลักฐานที่ตรงกับ '{query}'")
    lines = [f"ผลค้นหลักฐาน '{query}':"]
    for hit in hits:
        metadata = hit.get("metadata") or {}
        lines.append(
            f"- score {hit['score']:.2f} · {metadata.get('evidence_type')} · "
            f"{metadata.get('value')} · {metadata.get('source_agent')}"
        )
    return plain("\n".join(lines))
