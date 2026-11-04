"""Orchestrator — วางแผนตาม playbook, เก็บ evidence + hash, checkpoint และให้ specialist ตรวจ

Phase 5: ใช้ playbook เป็นแผน, มี specialist (identity/contradiction/scoring/timeline)
และบังคับ emit_report ท้ายงาน
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1

from vendor.synint.core.context import InvestigationContext
from vendor.synint.core.identity_resolution import IdentityResolver
from vendor.synint.core.schemas import EvidenceItem

from . import report_builder, skills, trust_anchor
from .budget import Budget, BudgetExceeded, RunBudget
from .store import RunStore

PROFILES = {"quick", "standard", "deep"}
SPECIALISTS = ("trusted_scan", "identity_candidate", "contradiction", "evidence_scoring", "timeline", "emit_report")


class RunNotFound(Exception):
    pass


@dataclass
class RunResult:
    run_id: str
    status: str
    findings: list[dict] = field(default_factory=list)
    error: str | None = None
    report: str | None = None


def _q(value: str) -> str:
    return f'"{value}"'


def _args(tool: str, context: InvestigationContext, run_id: str) -> dict:
    target = context.original_target
    kind = context.target_type
    if tool in {"phone_info"}:
        return {"number": target}
    if tool == "scan_phone_advanced":
        return {"phone_number": target}
    if tool == "verify_official":
        return {"value": target}
    if tool in {"scan_platforms", "sherlock_username", "github_intel"}:
        return {"username": target}
    if tool in {"breach_check", "gravatar_lookup"}:
        return {"email": target}
    if tool == "fetch_page":
        return {"url": target if kind == "url" else f"https://{target}"}
    if tool in {"dns_lookup", "whois_lookup"}:
        return {"domain": target}
    if tool == "wayback_lookup":
        return {"url": target if kind == "url" else f"https://{target}"}
    if tool == "extract_entities":
        return {"text": target}
    if tool == "search_evidence":
        return {"run_id": run_id, "query": target}
    if tool in {"web_search", "google_search"}:
        return {"query": _q(target)}
    return {}


class Orchestrator:
    def __init__(self, store: RunStore | None = None):
        self.store = store or RunStore()

    # -- lifecycle --------------------------------------------------------

    def start(self, target: str, profile: str = "standard", trusted: list[str] | None = None) -> str:
        if profile not in PROFILES:
            raise ValueError(f"profile ต้องเป็นหนึ่งใน {sorted(PROFILES)}")
        context = InvestigationContext.from_target(target)
        try:
            skills.select(context.target_type)
        except skills.UnknownTargetType:
            pass
        run_id = self.store.create_run(target, context.target_type, profile, trusted or [])
        self._emit(run_id, "queued", f"รับงาน: {context.target_type} = {target}")
        return run_id

    def cancel(self, run_id: str) -> bool:
        run = self.store.get_run(run_id)
        if not run or run["status"] in {"done", "failed", "cancelled"}:
            return False
        self.store.set_status(run_id, "cancelled")
        return True

    # -- helpers ----------------------------------------------------------

    def _emit(self, run_id: str, kind: str, text: str) -> None:
        self.store.add_event(run_id, kind, text)

    def _store_outcome(self, run_id: str, outcome) -> None:
        self.store.add_finding(run_id, outcome.tool, outcome.result, outcome.status, outcome.output_hash)
        if outcome.status in {"ok", "unknown", "empty"}:
            for item in outcome.evidence:
                item.setdefault("supporting_context", {})["output_hash"] = outcome.output_hash
                self.store.add_evidence(run_id, item)

    def _registry(self, run_id: str):
        from vendor.synint.core.registries import EvidenceRegistry

        registry = EvidenceRegistry()
        for item in self.store.list_evidence(run_id):
            registry.add(EvidenceItem.from_dict(item))
        return registry

    # -- run --------------------------------------------------------------

    def run(self, run_id: str) -> RunResult:
        run = self.store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        if run["status"] in {"done", "failed", "cancelled"}:
            return RunResult(run_id, run["status"], self.store.list_findings(run_id), run.get("error"))

        context = InvestigationContext.from_target(run["target"])
        budget = RunBudget(
            {"quick": Budget.quick, "standard": Budget.standard, "deep": Budget.deep}[run["profile"]]()
        )
        try:
            playbook = skills.select(context.target_type)
        except skills.UnknownTargetType:
            playbook = skills.PLAYBOOKS["text"]

        self.store.set_status(run_id, "running")
        self._emit(run_id, "start", f"เริ่มสืบสวน ({run['profile']}) ตาม playbook {playbook.id}")
        self._emit(run_id, "playbook", playbook.prompt_block(run["profile"]))

        try:
            steps = playbook.steps_for(run["profile"])
            trusted = self.store.trusted(run_id)
            if trusted and context.target_type == "username":
                steps.insert(0, skills.PlaybookStep("trusted_scan", "ตัด namesake ด้วย anchor", ["quick", "standard", "deep"]))

            for step in steps:
                if self.store.get_run(run_id)["status"] == "cancelled":
                    self._emit(run_id, "cancelled", "ผู้ใช้ยกเลิกงาน")
                    return self._finish(run_id, "cancelled")

                if self.store.step_status(run_id, step.tool) == "done":
                    self._emit(run_id, "skip", f"ข้ามขั้นที่ทำแล้ว: {step.tool}")
                    continue

                budget.step()
                self.store.set_step(run_id, step.tool, "running")
                self._emit(run_id, "tool", f"{step.tool} — {step.why}")

                if step.tool == "trusted_scan":
                    self._trusted_scan(run_id, context.original_target, trusted)
                else:
                    budget.tool_call()
                    from .tool_runner import run_tool

                    outcome = run_tool(step.tool, _args(step.tool, context, run_id), budget.budget.max_result_chars)
                    self._store_outcome(run_id, outcome)
                    self._emit(run_id, "result", f"[{outcome.status}] {outcome.result[:240]}".replace("\n", " "))

                self.store.set_step(run_id, step.tool, "done")

            for specialist in ("identity_candidate", "contradiction", "evidence_scoring", "timeline"):
                self._specialist(run_id, specialist)
            self._emit_report(run_id)

            if self.store.get_run(run_id)["status"] == "cancelled":
                return self._finish(run_id, "cancelled")
            self.store.set_status(run_id, "done")
            self._emit(run_id, "done", "เสร็จสิ้น")
            return self._finish(run_id, "done")

        except BudgetExceeded as exc:
            self._emit(run_id, "budget", str(exc))
            self._specialist(run_id, "evidence_scoring")
            self._emit_report(run_id)
            self.store.set_status(run_id, "done")
            self._emit(run_id, "done", "เสร็จสิ้นเพราะหมดเพดาน")
            return self._finish(run_id, "done")

        except Exception as exc:  # noqa: BLE001
            message = f"{type(exc).__name__}: {exc}"
            try:
                self._emit_report(run_id)
            except Exception:  # noqa: BLE001
                pass
            self.store.set_status(run_id, "failed", message)
            self._emit(run_id, "error", message)
            return self._finish(run_id, "failed", message)

    def _finish(self, run_id: str, status: str, error: str | None = None) -> RunResult:
        return RunResult(
            run_id, status, self.store.list_findings(run_id), error, self.store.get_report(run_id)
        )

    # -- specialists ------------------------------------------------------

    def _trusted_scan(self, run_id: str, target: str, anchors: list[str]) -> None:
        result = trust_anchor.apply_trust(target, anchors)
        text = result.summary()
        if result.reference_names:
            text = f"ชื่ออ้างอิงจาก anchor: {', '.join(result.reference_names)}\n" + text
        self.store.add_finding(run_id, "trusted_scan", text, "ok", "")
        for profile in result.kept:
            self.store.add_evidence(
                run_id,
                EvidenceItem(
                    source_agent="trusted_scan",
                    evidence_type="url",
                    value=profile.url,
                    normalized_value=profile.url.lower(),
                    confidence=0.9,
                    source_reference="trust_anchor",
                    evidence_tier="direct",
                    supporting_context={"verified_by": "trust_anchor"},
                ).to_dict(),
            )
        self._emit(run_id, "result", text.replace("\n", " ")[:240])

    def _specialist(self, run_id: str, name: str) -> None:
        evidence = self.store.list_evidence(run_id)
        if name == "identity_candidate":
            entities: dict[tuple, dict] = {}
            for item in evidence:
                key = (item["evidence_type"], item["value"].lower())
                entity = entities.setdefault(
                    key,
                    {"entity_id": "ent_" + sha1(f"{key[0]}|{key[1]}".encode()).hexdigest()[:12]},
                )
                bucket = {"email": "emails", "phone": "phones", "username": "usernames"}.get(key[0])
                if bucket:
                    entity.setdefault(bucket, []).append(key[1])
            candidates = IdentityResolver.create_candidates(entities.values())
            for candidate in candidates:
                self.store.add_candidate(run_id, candidate.to_dict())
            self._emit(run_id, "candidate", f"identity candidates: {len(candidates)}")

        elif name == "contradiction":
            counts: dict[str, set[str]] = {}
            for item in evidence:
                counts.setdefault(item["evidence_type"], set()).add(item["value"].lower())
            conflicts = {kind: sorted(values) for kind, values in counts.items() if len(values) > 1}
            text = "ไม่พบความขัดแย้ง" if not conflicts else "\n".join(
                f"- {kind}: {', '.join(values)}" for kind, values in conflicts.items()
            )
            self.store.add_finding(run_id, "contradiction", text, "ok", "")
            self._emit(run_id, "result", text.replace("\n", " ")[:240])

        elif name == "evidence_scoring":
            tiers: dict[str, int] = {}
            for item in evidence:
                tiers[item.get("evidence_tier", "enrichment")] = tiers.get(item.get("evidence_tier", "enrichment"), 0) + 1
            text = "การให้ระดับหลักฐาน: " + (", ".join(f"{k}={v}" for k, v in sorted(tiers.items())) or "ไม่มีหลักฐาน")
            self.store.add_finding(run_id, "evidence_scoring", text, "ok", "")
            self._emit(run_id, "result", text)

        elif name == "timeline":
            lines = [
                f"- {item.get('supporting_context', {}).get('output_hash', '')[:16]} "
                f"{item['evidence_type']}={item['value']} ({item['source_agent']})"
                for item in evidence
            ]
            self.store.add_finding(run_id, "timeline", "\n".join(lines) or "ไม่มีหลักฐาน", "ok", "")
            self._emit(run_id, "result", f"timeline: {len(evidence)} รายการ")

    def _emit_report(self, run_id: str) -> None:
        run = self.store.get_run(run_id)
        evidence = self.store.list_evidence(run_id)
        findings = self.store.list_findings(run_id)
        candidates = self.store.list_candidates(run_id)
        markdown = report_builder.build_report(run, evidence, findings, candidates)
        self.store.save_report(run_id, markdown)
        self._emit(run_id, "report", f"รายงานพร้อม ({len(evidence)} หลักฐาน)")
