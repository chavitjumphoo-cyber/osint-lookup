"""BM25 memory เหนือหลักฐานที่เก็บมา — ใช้ค้นข้ามหลักฐานระหว่างสืบสวน"""

from __future__ import annotations

from vendor.osint_d2.adapters.vector_store import VectorStore


class EvidenceMemory:
    def __init__(self) -> None:
        self._store = VectorStore()
        self._seen: set[str] = set()

    def index(self, evidence: list[dict]) -> None:
        for item in evidence:
            evidence_id = item.get("id") or ""
            if not evidence_id or evidence_id in self._seen:
                continue
            self._seen.add(evidence_id)
            text = " ".join(
                str(item.get(key) or "")
                for key in ("evidence_type", "value", "source_agent", "source_reference")
            )
            self._store.add_document(evidence_id, item.get("source_agent", "evidence"), text, item)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        return self._store.search_semantic(query, limit=limit)
