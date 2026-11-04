import pytest

from osint_agent.services.budget import Budget, BudgetExceeded, RunBudget


def test_step_limit():
    budget = RunBudget(Budget(max_steps=2))
    budget.step()
    budget.step()
    with pytest.raises(BudgetExceeded):
        budget.step()


def test_tool_call_limit():
    budget = RunBudget(Budget(max_tool_calls=1))
    budget.tool_call()
    with pytest.raises(BudgetExceeded):
        budget.tool_call()


def test_time_limit(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr("osint_agent.services.budget.time.monotonic", lambda: clock["now"])
    budget = RunBudget(Budget(max_seconds=1))
    clock["now"] = 2.0
    with pytest.raises(BudgetExceeded):
        budget.step()


def test_trim_caps_output():
    budget = RunBudget(Budget(max_result_chars=10))
    assert len(budget.trim("x" * 50)) < 50
    assert "ถูกตัด" in budget.trim("x" * 50)


def test_profiles_have_expected_limits():
    assert Budget.quick().max_steps < Budget.standard().max_steps < Budget.deep().max_steps
