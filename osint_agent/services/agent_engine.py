"""AgentEngine — LLM planner + deterministic evidence core"""

from __future__ import annotations

import json
import os

from ..profiling import pivots, profile_resolver, relationships, synthesizer
from ..profiling import timeline as timeline_mod
from . import agent_prompts, agent_tools
from . import budget as budget_mod
from .agent_state import AgentState

MAX_RESULT_CHARS = 6000


class AgentUnavailable(Exception):
    pass


def available() -> bool:
    if os.environ.get("OSINT_AGENT", "1") == "0":
        return False
    try:
        from osint_agent.agent import read_config

        config = read_config()
        return bool(
            config.get("MAXPLUS_API_KEY")
            or config.get("MAXPLUS_BASE_URL")
            or config.get("ANTHROPIC_API_KEY")
            or config.get("ANTHROPIC_BASE_URL")
        )
    except Exception:  # noqa: BLE001
        return False


class AgentEngine:
    def __init__(self, store, run_id: str, client=None, on_event=None):
        self.store = store
        self.run_id = run_id
        self.client = client
        self.emit = on_event or (lambda *_a, **_k: None)

    def _client(self):
        if self.client is not None:
            return self.client
        from ..agent import _build_client

        return _build_client()

    def _trim(self, payload: dict) -> str:
        text = agent_tools.dumps(payload)
        return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + "…"

    def run(self, run: dict, state: AgentState, budget: budget_mod.RunBudget) -> dict:
        from ..agent import STEP_MAX_TOKENS, model_name

        client = self._client()
        self.state = state
        messages = [{"role": "user", "content": agent_prompts.state_message(state.snapshot())}]
        finalize = False

        while not finalize and not state.exhausted():
            state.steps += 1
            budget.step()
            response = client.messages.create(
                model=model_name(),
                max_tokens=STEP_MAX_TOKENS,
                system=agent_prompts.AGENT_SYSTEM,
                messages=messages,
                tools=agent_tools.TOOL_SCHEMAS,
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if not tool_blocks:
                break

            results = []
            for block in tool_blocks:
                name = block.name
                args = block.input or {}
                before = [a["artifact_id"] for a in state.artifacts[-3:]]
                self.emit({"kind": "agent_action", "text": f"{name} {json.dumps(args, ensure_ascii=False)[:160]}"})
                if name == "finalize_report":
                    finalize = True
                try:
                    payload = agent_tools.execute(name, args, self)
                except Exception as exc:  # noqa: BLE001
                    payload = {"error": f"{type(exc).__name__}: {exc}"}
                if name in {"fetch_profile", "fetch_page", "search_web"}:
                    budget.tool_call()
                state.log_action(name, args.get("url") or args.get("query") or args.get("value") or "", args.get("reason", ""), name, before, self._trim(payload))
                self.store.add_finding(run["id"], f"agent:{name}", self._trim(payload), "ok", "")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": [{"type": "text", "text": self._trim(payload)}],
                    }
                )
                if name == "finalize_report":
                    break

            messages.append({"role": "user", "content": results})
            messages = messages[-14:]
            messages[0] = {"role": "user", "content": agent_prompts.state_message(state.snapshot())}

        return self._finalize(run, state)

    def _finalize(self, run: dict, state: AgentState) -> dict:
        contradictions = synthesizer.contradictions(state.profiles, state.entities)
        rels = relationships.co_occurring_entities(state.artifacts, state.entities)
        explicit = relationships.explicit_relations(state.profiles)
        events = timeline_mod.build(state.artifacts, state.entities)
        self._candidates(state)
        self._ownership(state)
        data = synthesizer.synthesize(
            run, state.profiles, state.entities, state.artifacts, rels, contradictions, events
        )
        data["explicit_relations"] = explicit
        data["actions"] = state.actions
        data["limitations"] = [
            "รวบรวมจากข้อมูลสาธารณะเท่านั้น",
            "การไม่พบข้อมูลไม่ยืนยันว่าปลอดภัย",
            f"agent ใช้ {state.steps} ขั้น เปิดอ่าน {state.fetches} หน้า",
        ]
        data["_artifacts"] = [
            {k: a.get(k) for k in ("artifact_id", "source_tool", "status", "source_url")}
            for a in state.artifacts
        ]
        data = synthesizer.llm_synthesize(data, run)
        self.store.save_report(run["id"], synthesizer.render_markdown(data, run))
        return data

    def _ownership(self, state: AgentState) -> None:
        from ..profiling.identity_score import score_pair

        pairs = []
        for index, left in enumerate(state.profiles):
            for right in state.profiles[index + 1 :]:
                scored = score_pair(left, right)
                if scored["verdict"] != "Unverified":
                    pairs.append(f"{left['key']} ↔ {right['key']} = {scored['verdict']} ({scored['score']})")
        if pairs:
            self.store.add_finding(state.run_id, "ownership_scores", "\n".join(pairs[:30]))

    def _candidates(self, state: AgentState) -> None:
        from vendor.synint.core.identity_resolution import IdentityResolver

        entities = [profile_resolver.profile_entities(p) for p in state.profiles]
        for candidate in IdentityResolver.create_candidates(entities):
            self.store.add_candidate(state.run_id, candidate.to_dict())


def seed_state(store, run: dict) -> AgentState:
    from .budget import Budget

    profile = run["profile"]
    limits = {
        "standard": (24, 12, Budget.standard()),
        "deep": (40, 30, Budget.deep()),
    }[profile]
    state = AgentState(
        run_id=run["id"],
        target=run["target"],
        target_type=run["target_type"],
        max_steps=limits[0],
        max_fetches=limits[1],
        store=store,
    )
    existing = store.list_artifacts(run["id"])
    state.artifacts = existing
    state.refresh()
    return state


def seed_queries(state: AgentState) -> list[str]:
    queries = pivots.search_queries(state.target, state.target_type)
    if state.target_type == "name":
        from ..profiling.thai_identity import parse_name, surname_queries

        parsed = parse_name(state.target)
        if parsed:
            queries = [f'"{state.target}"'] + surname_queries(parsed["family_name"])[:3] + queries
    return list(dict.fromkeys(queries))[:4]
