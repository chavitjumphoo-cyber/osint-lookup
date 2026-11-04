"""Orchestrator — lead-driven investigation

Normalize → hypotheses → search → rank → fetch → extract → leads → pivot → synthesize
ทุก artifact มี source/hash; รายงานสร้างจาก corpus ไม่ใช่รายการ evidence แบน
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vendor.synint.core.context import InvestigationContext
from vendor.synint.core.identity_resolution import IdentityResolver

from ..profiling import collectors, pivots, profile_resolver, relationships, synthesizer
from ..profiling import corpus as corpus_mod
from ..profiling import timeline as timeline_mod
from . import budget as budget_mod
from . import trust_anchor
from .store import RunStore

PROFILES = {"quick", "standard", "deep"}
LIMITS = {
    "quick": {"queries": 2, "fetch": 2, "leads": 2, "scan": True, "probe": False},
    "standard": {"queries": 5, "fetch": 4, "leads": 4, "scan": True, "probe": True},
    "deep": {"queries": 12, "fetch": 16, "leads": 20, "scan": True, "probe": True},
}


class RunNotFound(Exception):
    pass


@dataclass
class RunResult:
    run_id: str
    status: str
    findings: list[dict] = field(default_factory=list)
    error: str | None = None
    report: str | None = None


class Orchestrator:
    def __init__(self, store: RunStore | None = None):
        self.store = store or RunStore()

    # -- lifecycle --------------------------------------------------------

    def start(
        self,
        target: str,
        profile: str = "standard",
        trusted: list[str] | None = None,
        parent_run_id: str | None = None,
    ) -> str:
        if profile not in PROFILES:
            raise ValueError(f"profile ต้องเป็นหนึ่งใน {sorted(PROFILES)}")
        context = InvestigationContext.from_target(target)
        run_id = self.store.create_run(
            target, context.target_type, profile, trusted or [], parent_run_id
        )
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

    def _finding(self, run_id: str, tool: str, text: str, status: str = "ok", digest: str = "") -> None:
        self.store.add_finding(run_id, tool, text, status, digest)

    def _cancelled(self, run_id: str) -> bool:
        run = self.store.get_run(run_id)
        return bool(run and run["status"] == "cancelled")

    def _finish(self, run_id: str, status: str, error: str | None = None) -> RunResult:
        return RunResult(
            run_id, status, self.store.list_findings(run_id), error, self.store.get_report(run_id)
        )

    # -- run --------------------------------------------------------------

    def run(self, run_id: str) -> RunResult:
        run = self.store.get_run(run_id)
        if not run:
            raise RunNotFound(run_id)
        if run["status"] in {"done", "failed", "cancelled"}:
            return self._finish(run_id, run["status"], run.get("error"))

        context = InvestigationContext.from_target(run["target"])
        limits = LIMITS[run["profile"]]
        budget = budget_mod.RunBudget(
            {"quick": budget_mod.Budget.quick, "standard": budget_mod.Budget.standard, "deep": budget_mod.Budget.deep}[run["profile"]]()
        )
        corpus = corpus_mod.Corpus(self.store, run_id)
        self.store.set_status(run_id, "running")
        self._emit(run_id, "start", f"เริ่มสืบสวนแบบ lead-driven ({run['profile']})")

        from . import agent_engine

        if run["profile"] in {"standard", "deep"} and agent_engine.available():
            return self._run_agent(run, context, budget, corpus)

        try:
            trusted = self.store.trusted(run_id)
            anchor_names: list[str] = []
            if trusted and context.target_type == "username":
                result = trust_anchor.apply_trust(context.original_target, trusted)
                anchor_names = result.reference_names
                self._finding(run_id, "trusted_scan", result.summary())
                for profile in result.kept:
                    from ..profiling.artifacts import Artifact

                    corpus.add(
                        Artifact(
                            source_url=profile.url,
                            source_type="profile",
                            source_tool="trust_anchor",
                            platform=profile.network_name,
                            author=profile.username,
                            title=(profile.metadata or {}).get("name", ""),
                            content=profile.bio or "",
                            confidence="Confirmed",
                        )
                    )

            # 1) hypotheses
            queries = pivots.search_queries(context.original_target, context.target_type, anchor_names)
            self._emit(run_id, "plan", f"สมมติฐานคำค้น {min(len(queries), limits['queries'])} ชุด")

            for query in queries[: limits["queries"]]:
                if self._cancelled(run_id):
                    return self._finish(run_id, "cancelled")
                budget.step()
                budget.tool_call()
                self._emit(run_id, "search", query)
                try:
                    results = collectors.search(query, limit=8)
                except Exception as exc:  # noqa: BLE001
                    self._finding(run_id, "web_search", f"{query}: {type(exc).__name__}", "failed")
                    continue
                added = sum(1 for artifact in results if corpus.add(artifact))
                self._finding(run_id, "web_search", f"{query} → {added} ผลลัพธ์")
                self._emit(run_id, "result", f"{query} → {added} ผลลัพธ์")

            # 2) platform metadata
            if limits["scan"] and context.target_type in {"username", "email"}:
                username = context.original_target.split("@", 1)[0].lstrip("@")
                budget.step()
                self._emit(run_id, "tool", f"scan_profiles {username}")
                try:
                    profiles = collectors.scan_profiles(username)
                except Exception as exc:  # noqa: BLE001
                    profiles = []
                    self._finding(run_id, "scan_profiles", type(exc).__name__, "failed")
                added = sum(1 for artifact in profiles if corpus.add(artifact))
                self._finding(run_id, "scan_profiles", f"พบโปรไฟล์มีข้อมูล {added}")
                self._emit(run_id, "result", f"โปรไฟล์ที่มีข้อมูล {added}")

                if limits["probe"]:
                    budget.step()
                    self._emit(run_id, "tool", f"probe_platforms {username}")
                    for artifact in collectors.probe_platforms(username):
                        corpus.add(artifact)
                    self._finding(run_id, "probe_platforms", "ตรวจแพลตฟอร์มเพิ่มเติมแล้ว")

            # 3) rank and fetch
            fetched_urls = {
                a["source_url"] for a in corpus.artifacts() if a["source_type"] != "search_result"
            }
            search_results = [
                a for a in corpus.search_results() if a["source_url"] not in fetched_urls
            ]
            unread_profiles = [
                a
                for a in corpus.artifacts()
                if a.get("source_type") == "profile"
                and not a.get("content")
                and a["source_url"] not in fetched_urls
            ]
            pool = {a["source_url"]: a for a in search_results}
            for artifact in unread_profiles:
                pool.setdefault(artifact["source_url"], artifact)
            ranked = sorted(pool.values(), key=collectors.rank_result, reverse=True)
            for artifact in ranked[: limits["fetch"]]:
                if self._cancelled(run_id):
                    return self._finish(run_id, "cancelled")
                budget.step()
                budget.tool_call()
                self._emit(run_id, "tool", f"fetch {artifact['source_url']}")
                fetched = collectors.fetch(artifact["source_url"])
                corpus.add(fetched)
                self._finding(run_id, "fetch_page", f"[{fetched.status}] {fetched.source_url}", fetched.status, fetched.output_hash)
                self._emit(run_id, "result", f"[{fetched.status}] {fetched.source_url}")

            # 4) extract + profiles
            entities = profile_resolver.extract_entities(corpus.artifacts())
            profiles = profile_resolver.resolve_profiles(corpus.artifacts(), entities)

            # 5) leads wave
            leads = self._build_leads(corpus, profiles, context)
            self._emit(run_id, "plan", f"leads ใหม่ {leads.pending()}")
            processed = 0
            while processed < limits["leads"] and not self._cancelled(run_id):
                lead = leads.next()
                if not lead:
                    break
                processed += 1
                budget.step()
                budget.tool_call()
                self._emit(run_id, "tool", f"pivot {lead.type} → {lead.value}")
                if lead.type == "url":
                    artifact = collectors.fetch(lead.value)
                    corpus.add(artifact)
                else:
                    try:
                        for artifact in collectors.search(f'"{lead.value}"', limit=5):
                            corpus.add(artifact)
                    except Exception:  # noqa: BLE001
                        pass
                if lead.type in {"username", "name"}:
                    try:
                        for artifact in collectors.scan_profiles(lead.value):
                            corpus.add(artifact)
                    except Exception:  # noqa: BLE001
                        pass

            # refresh after pivots
            entities = profile_resolver.extract_entities(corpus.artifacts())
            profiles = profile_resolver.resolve_profiles(corpus.artifacts(), entities)

            # 6) specialists
            contradictions = synthesizer.contradictions(profiles, entities)
            rels = relationships.co_occurring_entities(corpus.artifacts(), entities)
            explicit = relationships.explicit_relations(profiles)
            events = timeline_mod.build(corpus.artifacts(), entities)
            self._identity_candidates(run_id, profiles)
            self._finding(run_id, "contradiction", "\n".join(
                f"- {c['kind']} {c['value']}: {', '.join(c['detail'])}" for c in contradictions
            ) or "ไม่พบความขัดแย้ง")

            # 7) synthesize
            data = synthesizer.synthesize(run, profiles, entities, corpus.artifacts(), rels, contradictions, events)
            data["explicit_relations"] = explicit
            data["limitations"] = [
                "รวบรวมจากข้อมูลสาธารณะเท่านั้น",
                "การไม่พบข้อมูลไม่ยืนยันว่าปลอดภัย",
                f"เปิดอ่านได้ {sum(1 for a in corpus.artifacts() if a['source_type'] != 'search_result')} หน้า",
            ]
            data["_artifacts"] = [
                {key: a.get(key) for key in ("artifact_id", "source_tool", "status", "source_url")}
                for a in corpus.artifacts()
            ]
            data = synthesizer.llm_synthesize(data, run)
            self.store.save_report(run_id, synthesizer.render_markdown(data, run))
            self.store.set_status(run_id, "done")
            self._emit(run_id, "report", f"รายงานพร้อม ({len(profiles)} โปรไฟล์)")
            self._emit(run_id, "done", "เสร็จสิ้น")
            return self._finish(run_id, "done")

        except budget_mod.BudgetExceeded as exc:
            self._emit(run_id, "budget", str(exc))
            self._safe_report(run_id, run)
            self.store.set_status(run_id, "done")
            self._emit(run_id, "done", "เสร็จสิ้นเพราะหมดเพดาน")
            return self._finish(run_id, "done")
        except Exception as exc:  # noqa: BLE001
            self._emit(run_id, "error", f"{type(exc).__name__}: {exc}")
            self._safe_report(run_id, run)
            self.store.set_status(run_id, "failed", f"{type(exc).__name__}: {exc}")
            return self._finish(run_id, "failed", str(exc))

    def _run_agent(self, run: dict, context, budget, corpus) -> RunResult:
        run_id = run["id"]
        from .agent_engine import AgentEngine, seed_queries, seed_state

        try:
            trusted = self.store.trusted(run_id)
            if trusted and context.target_type == "username":
                self._emit(run_id, "tool", "trusted_scan")
                result = trust_anchor.apply_trust(context.original_target, trusted)
                self._finding(run_id, "trusted_scan", result.summary())
            state = seed_state(self.store, run)
            for query in seed_queries(state):
                if self._cancelled(run_id):
                    return self._finish(run_id, "cancelled")
                self._emit(run_id, "search", query)
                try:
                    for artifact in collectors.search(query, limit=8):
                        state.add_artifact(artifact)
                except Exception as exc:  # noqa: BLE001
                    self._finding(run_id, "web_search", type(exc).__name__, "failed")
            engine = AgentEngine(self.store, run_id, on_event=lambda e: self._emit(run_id, e["kind"], e["text"]))
            engine.run(run, state, budget)
            self.store.set_status(run_id, "done")
            self._emit(run_id, "done", f"agent เสร็จสิ้น ({state.steps} ขั้น)")
            return self._finish(run_id, "done")
        except budget_mod.BudgetExceeded as exc:
            self._emit(run_id, "budget", str(exc))
            self._safe_report(run_id, run)
            self.store.set_status(run_id, "done")
            return self._finish(run_id, "done")
        except Exception as exc:  # noqa: BLE001
            self._emit(run_id, "error", f"{type(exc).__name__}: {exc}")
            self._safe_report(run_id, run)
            self.store.set_status(run_id, "failed", str(exc))
            return self._finish(run_id, "failed", str(exc))

    # -- specialists ------------------------------------------------------

    def _build_leads(self, corpus, profiles, context):
        from ..profiling.leads import LeadQueue

        queue = LeadQueue()
        for profile in profiles:
            for handle in profile["handles"]:
                queue.add(handle, "username", "handle ในbio", priority=0.8)
            for name in profile["display_names"]:
                queue.add(name, "name", "ชื่อที่แสดง", priority=0.6)
            if profile["url"]:
                queue.add(profile["url"], "url", "โปรไฟล์ที่ยังไม่อ่าน", priority=0.9)
        for artifact in corpus.artifacts("search_result"):
            if artifact.get("platform") and artifact["source_url"] not in corpus.urls():
                queue.add(artifact["source_url"], "url", "ผลค้นน่าสนใจ", priority=collectors.rank_result(artifact))
        return queue

    def _identity_candidates(self, run_id: str, profiles: list[dict]) -> None:
        from ..profiling.identity_score import score_pair

        entities = [profile_resolver.profile_entities(profile) for profile in profiles]
        candidates = IdentityResolver.create_candidates(entities)
        for candidate in candidates:
            self.store.add_candidate(run_id, candidate.to_dict())
        pairs = []
        for index, left in enumerate(profiles):
            for right in profiles[index + 1 :]:
                if left["key"] == right["key"]:
                    continue
                scored = score_pair(left, right)
                if scored["verdict"] != "Unverified":
                    pairs.append(
                        f"{left['platform']}:{left['username']} ↔ {right['platform']}:{right['username']} "
                        f"= {scored['verdict']} ({scored['score']}) signals={','.join(scored['signals']) or '-'}"
                    )
        if pairs:
            self._finding(run_id, "ownership_scores", "\n".join(pairs[:30]))
        self._emit(run_id, "candidate", f"identity candidates: {len(candidates)}, scored pairs: {len(pairs)}")

    def _safe_report(self, run_id: str, run: dict) -> None:
        try:
            corpus = corpus_mod.Corpus(self.store, run_id)
            entities = profile_resolver.extract_entities(corpus.artifacts())
            profiles = profile_resolver.resolve_profiles(corpus.artifacts(), entities)
            data = synthesizer.synthesize(run, profiles, entities, corpus.artifacts(), [], [], [])
            data["limitations"] = ["งานหยุดก่อนกำหนด — รายงานไม่สมบูรณ์"]
            data["_artifacts"] = [
                {key: a.get(key) for key in ("artifact_id", "source_tool", "status", "source_url")}
                for a in corpus.artifacts()
            ]
            self.store.save_report(run_id, synthesizer.render_markdown(data, run))
        except Exception:  # noqa: BLE001
            pass
