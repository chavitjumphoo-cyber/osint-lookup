"""สถานะกลางของ AgentEngine — LLM เห็นเฉพาะข้อมูลที่ผ่าน evidence core แล้ว"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1

from ..profiling import profile_resolver


@dataclass
class AgentState:
    run_id: str
    target: str
    target_type: str
    objective: str = "สร้าง Subject Intelligence Dossier จากหลักฐานสาธารณะ"
    artifacts: list[dict] = field(default_factory=list)
    profiles: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    leads: list[dict] = field(default_factory=list)
    pivots: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    steps: int = 0
    fetches: int = 0
    max_steps: int = 30
    max_fetches: int = 20
    store: object | None = None

    def refresh(self) -> None:
        self.entities = profile_resolver.extract_entities(self.artifacts)
        self.profiles = profile_resolver.resolve_profiles(self.artifacts, self.entities)
        seen = {f"{lead['type']}:{lead['value'].lower()}" for lead in self.leads}
        for profile in self.profiles:
            for handle in profile.get("handles", []):
                key = f"username:{handle.lower()}"
                if key not in seen:
                    self.leads.append({"type": "username", "value": handle, "reason": "handle ในโปรไฟล์"})
                    seen.add(key)
            for name in profile.get("display_names", []):
                key = f"name:{name.lower()}"
                if key not in seen:
                    self.leads.append({"type": "name", "value": name, "reason": "ชื่อที่แสดง"})
                    seen.add(key)

    def add_artifact(self, artifact) -> bool:
        if any(item["artifact_id"] == artifact.artifact_id for item in self.artifacts):
            return False
        payload = artifact.to_dict()
        self.artifacts.append(payload)
        if self.store is not None:
            self.store.add_artifact(self.run_id, payload)
        self.refresh()
        return True

    def next_lead(self) -> dict | None:
        if not self.leads:
            return None
        lead = self.leads.pop(0)
        self.pivots.append({**lead, "artifact": sha1(lead["value"].encode()).hexdigest()[:12]})
        return lead

    def snapshot(self, limit: int = 12) -> dict:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "objective": self.objective,
            "budget": {"steps": f"{self.steps}/{self.max_steps}", "fetches": f"{self.fetches}/{self.max_fetches}"},
            "counts": {
                "artifacts": len(self.artifacts),
                "profiles": len(self.profiles),
                "entities": len(self.entities),
                "leads": len(self.leads),
            },
            "profiles": [
                {
                    "platform": p["platform"],
                    "username": p["username"],
                    "names": p["display_names"][:3],
                    "bios": [b[:160] for b in p["bios"][:2]],
                    "locations": p["locations"][:3],
                    "evidence": p["evidence"][:4],
                }
                for p in self.profiles[:limit]
            ],
            "leads": self.leads[:limit],
            "recent_actions": self.actions[-8:],
        }

    def log_action(self, action: str, target: str, reason: str, expected: str, before: list[str], result: str) -> None:
        self.actions.append(
            {
                "step": self.steps,
                "action": action,
                "target": target,
                "reason": reason,
                "expected_value": expected,
                "evidence_before": before[:5],
                "result": result[:300],
            }
        )

    def exhausted(self) -> bool:
        return self.steps >= self.max_steps or self.fetches >= self.max_fetches
