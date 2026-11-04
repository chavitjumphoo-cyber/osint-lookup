"""เพดานการใช้ทรัพยากรต่อการสืบสวนหนึ่งครั้ง"""

from __future__ import annotations

import time
from dataclasses import dataclass


class BudgetExceeded(Exception):
    def __init__(self, limit: str):
        self.limit = limit
        super().__init__(f"เกินเพดาน: {limit}")


@dataclass
class Budget:
    max_steps: int = 16
    max_tool_calls: int = 20
    max_seconds: float = 300.0
    max_result_chars: int = 12_000

    @classmethod
    def quick(cls) -> Budget:
        return cls(max_steps=5, max_tool_calls=6, max_seconds=90.0)

    @classmethod
    def standard(cls) -> Budget:
        return cls()

    @classmethod
    def deep(cls) -> Budget:
        return cls(max_steps=40, max_tool_calls=60, max_seconds=900.0, max_result_chars=20_000)


class RunBudget:
    def __init__(self, budget: Budget):
        self.budget = budget
        self.steps = 0
        self.tool_calls = 0
        self.started = time.monotonic()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def _check_time(self) -> None:
        if self.elapsed > self.budget.max_seconds:
            raise BudgetExceeded("max_seconds")

    def step(self) -> None:
        self._check_time()
        if self.steps >= self.budget.max_steps:
            raise BudgetExceeded("max_steps")
        self.steps += 1

    def tool_call(self) -> None:
        self._check_time()
        if self.tool_calls >= self.budget.max_tool_calls:
            raise BudgetExceeded("max_tool_calls")
        self.tool_calls += 1

    def trim(self, text: str) -> str:
        limit = self.budget.max_result_chars
        return text if len(text) <= limit else text[:limit] + "\n[... ผลลัพธ์ยาวเกิน ถูกตัด ...]"

    def remaining_seconds(self) -> float:
        return max(0.0, self.budget.max_seconds - self.elapsed)
