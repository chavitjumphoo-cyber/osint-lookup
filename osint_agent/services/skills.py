"""เลือกและบังคับใช้ pivot playbook ตามชนิด target"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

PLAYBOOK_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "playbooks"
PROFILE_ORDER = {"quick": 0, "standard": 1, "deep": 2}


@dataclass
class PlaybookStep:
    tool: str
    why: str
    profiles: list[str] = field(default_factory=lambda: ["quick", "standard", "deep"])

    def allowed(self, profile: str) -> bool:
        return PROFILE_ORDER[profile] >= min(PROFILE_ORDER[p] for p in self.profiles)


@dataclass
class Playbook:
    id: str
    target_types: list[str]
    trigger: str
    max_steps: dict[str, int]
    required_tools: list[str]
    steps: list[PlaybookStep]
    outputs: list[str]
    anti_patterns: list[str]
    stop_conditions: list[str]

    def steps_for(self, profile: str) -> list[PlaybookStep]:
        return [step for step in self.steps if step.allowed(profile)][: self.max_steps[profile]]

    def prompt_block(self, profile: str) -> str:
        lines = [f"# Active playbook: {self.id}", f"Trigger: {self.trigger}", "Steps:"]
        for index, step in enumerate(self.steps_for(profile), start=1):
            lines.append(f"{index}. {step.tool} — {step.why}")
        lines.append("Anti-patterns:")
        lines += [f"- {item}" for item in self.anti_patterns]
        lines.append("Stop conditions:")
        lines += [f"- {item}" for item in self.stop_conditions]
        return "\n".join(lines)


def _load() -> dict[str, Playbook]:
    books = {}
    for path in PLAYBOOK_DIR.glob("*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        steps = [
            PlaybookStep(
                tool=str(raw["tool"]),
                why=str(raw.get("why", "")),
                profiles=[str(p) for p in raw.get("profiles", ["quick", "standard", "deep"])],
            )
            for raw in payload.get("steps", [])
        ]
        book = Playbook(
            id=str(payload["id"]),
            target_types=[str(t) for t in payload.get("target_types", [])],
            trigger=str(payload.get("trigger", "")),
            max_steps={k: int(v) for k, v in (payload.get("max_steps") or {}).items()},
            required_tools=[str(t) for t in payload.get("required_tools", [])],
            steps=steps,
            outputs=[str(o) for o in payload.get("outputs", [])],
            anti_patterns=[str(a) for a in payload.get("anti_patterns", [])],
            stop_conditions=[str(s) for s in payload.get("stop_conditions", [])],
        )
        for target_type in book.target_types:
            books[target_type] = book
    return books


PLAYBOOKS = _load()


class UnknownTargetType(Exception):
    pass


def select(target_type: str) -> Playbook:
    book = PLAYBOOKS.get(target_type)
    if book:
        return book
    if target_type in {"photo", "file"}:
        return PLAYBOOKS["photo"]
    raise UnknownTargetType(target_type)


def from_tools(tools: list[str]) -> list[str]:
    """คืนชื่อ tool ที่รู้จักใน playbook (กันพิมพ์ผิด)"""
    from ..tools import TOOLS

    return [tool for tool in tools if tool in TOOLS]
