"""สถานะกลางของ AgentEngine — LLM ต้องเห็นหลักฐานสำคัญ ไม่ใช่แค่จำนวน"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..profiling import profile_resolver
from . import information_gain, question_manager


@dataclass
class Coverage:
    search_queries: int = 0
    pages_opened: int = 0
    profiles_read: int = 0
    identifiers_extracted: int = 0
    cross_checks: int = 0
    contradictions_checked: bool = False
    six_d_computed: bool = False

    def to_dict(self) -> dict:
        return {
            "search_queries": self.search_queries,
            "pages_opened": self.pages_opened,
            "profiles_read": self.profiles_read,
            "identifiers_extracted": self.identifiers_extracted,
            "cross_checks": self.cross_checks,
            "contradictions_checked": self.contradictions_checked,
            "six_d_computed": self.six_d_computed,
        }


@dataclass
class AgentState:
    run_id: str
    target: str
    target_type: str
    objective: str = "ระบุตัวตนดิจิทัลและสร้าง profile ภาพรวมของเป้าหมาย"
    artifacts: list[dict] = field(default_factory=list)
    profiles: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    leads: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    steps: int = 0
    fetches: int = 0
    max_steps: int = 30
    max_fetches: int = 20
    store: object | None = None
    coverage: Coverage = field(default_factory=Coverage)
    questions: list[dict] = field(default_factory=list)

    def refresh(self) -> None:
        self.entities = profile_resolver.extract_entities(self.artifacts)
        self.profiles = profile_resolver.resolve_profiles(self.artifacts, self.entities)
        self.coverage.identifiers_extracted = len(self.entities)
        if self.entities:
            question_manager.answer(self.questions, "ตัวระบุ", [e["source_artifact"] for e in self.entities[:5]], partial=True)
        if any(p.get("display_names") for p in self.profiles):
            question_manager.answer(self.questions, "ชื่อที่ปรากฏ", self._name_evidence())
        if any(p.get("locations") for p in self.profiles):
            question_manager.answer(self.questions, "พื้นที่สาธารณะ", self._flat("locations"))
        if any(p.get("emails") or p.get("phones") for p in self.profiles):
            question_manager.answer(self.questions, "อีเมล", self._flat("emails") + self._flat("phones"))
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
            for site in profile.get("links", [])[:2]:
                key = f"url:{site.lower()}"
                if key not in seen:
                    self.leads.append({"type": "url", "value": site, "reason": "ลิงก์ในโปรไฟล์"})
                    seen.add(key)
            for family in profile.get("family_names", []):
                key = f"family_name:{family.lower()}"
                if key not in seen:
                    self.leads.append({"type": "family_name", "value": family, "reason": "นามสกุลที่พบ"})
                    seen.add(key)

    def _flat(self, field: str) -> list[str]:
        return [eid for p in self.profiles for eid in p.get("evidence", []) if p.get(field)][:5]

    def _name_evidence(self) -> list[str]:
        return [eid for p in self.profiles if p.get("display_names") for eid in p.get("evidence", [])][:5]

    def add_artifact(self, artifact) -> bool:
        if any(item["artifact_id"] == artifact.artifact_id for item in self.artifacts):
            return False
        payload = artifact.to_dict()
        self.artifacts.append(payload)
        if artifact.source_type in {"profile", "post", "page"}:
            self.coverage.pages_opened += 1
            if artifact.source_type == "profile":
                self.coverage.profiles_read += 1
        if self.store is not None:
            self.store.add_artifact(self.run_id, payload)
        self.refresh()
        return True

    def next_lead(self) -> dict | None:
        if not self.leads:
            return None
        return self.leads.pop(0)

    def _important(self, limit: int = 10) -> list[dict]:
        def score(a):
            s = 0
            if a.get("source_type") == "profile":
                s += 5
            if a.get("title"):
                s += 2
            if len(a.get("content", "")) > 80:
                s += 2
            if a.get("platform") in {"github", "linkedin", "facebook", "pantip"}:
                s += 2
            if a.get("source_type") == "search_result":
                s -= 2
            return s

        ranked = sorted(self.artifacts, key=score, reverse=True)[:limit]
        return [
            {
                "artifact_id": a["artifact_id"],
                "url": a.get("source_url"),
                "type": a.get("source_type"),
                "platform": a.get("platform"),
                "status": a.get("status"),
                "title": a.get("title"),
                "excerpt": (a.get("content") or "")[:900],
                "confidence": a.get("confidence"),
            }
            for a in ranked
        ]

    def snapshot(self, limit: int = 10) -> dict:
        return {
            "target": self.target,
            "target_type": self.target_type,
            "objective": self.objective,
            "budget": {"steps": f"{self.steps}/{self.max_steps}", "fetches": f"{self.fetches}/{self.max_fetches}"},
            "coverage": self.coverage.to_dict(),
            "profiles": [
                {
                    "key": p["key"],
                    "platform": p["platform"],
                    "username": p["username"],
                    "names": p["display_names"][:3],
                    "bios": [b[:220] for b in p["bios"][:2]],
                    "locations": p["locations"][:3],
                    "organizations": p["organizations"][:3],
                    "links": p["links"][:3],
                    "family_names": p["family_names"][:3],
                    "confidence": p["confidence"],
                    "evidence": p["evidence"][:5],
                }
                for p in self.profiles[:limit]
            ],
            "leads": information_gain.rank(self.leads[:24], {a.get("source_url", "") for a in self.artifacts})[:12],
            "important_artifacts": self._important(),
            "questions": {
                "coverage": question_manager.coverage(self.questions),
                "unanswered": question_manager.remaining(self.questions)[:8],
            },
            "recent_actions": self.actions[-6:],
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

    def ready_to_finalize(self, profile: str) -> tuple[bool, list[str]]:
        minimum = {
            "standard": {"search_queries": 3, "pages_opened": 3, "profiles_read": 2},
            "deep": {"search_queries": 6, "pages_opened": 8, "profiles_read": 4},
        }[profile]
        missing = [
            f"{key} {getattr(self.coverage, key)}/{value}"
            for key, value in minimum.items()
            if getattr(self.coverage, key) < value
        ]
        unanswered = question_manager.remaining(self.questions)
        if len(unanswered) > 3:
            missing.append(f"ยังตอบคำถามไม่ได้ {len(unanswered)} ข้อ")
        return not missing, missing
