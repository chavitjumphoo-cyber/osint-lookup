"""Lead queue — ต่อยอดเฉพาะสิ่งที่พบใหม่ และไม่ค้นซ้ำโดยไม่มีเหตุผล"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(order=True)
class Lead:
    priority: float
    value: str = field(compare=False)
    type: str = field(default="text", compare=False)
    reason: str = field(default="", compare=False)
    source_artifact: str = field(default="", compare=False)
    status: str = field(default="queued", compare=False)


class LeadQueue:
    def __init__(self):
        self._leads: list[Lead] = []
        self._seen: set[tuple[str, str]] = set()

    def add(
        self, value: str, lead_type: str, reason: str, source_artifact: str = "", priority: float = 0.5
    ) -> bool:
        value = value.strip()
        if not value:
            return False
        key = (lead_type, value.lower())
        if key in self._seen:
            return False
        self._seen.add(key)
        self._leads.append(
            Lead(min(1.0, max(0.0, priority)), value, lead_type, reason, source_artifact)
        )
        self._leads.sort(reverse=True)
        return True

    def next(self) -> Lead | None:
        while self._leads:
            lead = self._leads.pop(0)
            if lead.status == "queued":
                lead.status = "running"
                return lead
        return None

    def pending(self) -> int:
        return sum(1 for lead in self._leads if lead.status == "queued")

    def all(self) -> list[Lead]:
        return list(self._leads)
