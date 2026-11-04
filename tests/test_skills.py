import pytest

from osint_agent.services import skills


def test_select_by_target_type():
    assert skills.select("phone").id == "phone"
    assert skills.select("url").id == "domain"
    assert skills.select("file").id == "photo"


def test_unknown_target_type():
    with pytest.raises(skills.UnknownTargetType):
        skills.select("nonsense")


def test_quick_has_fewer_steps_than_deep():
    book = skills.select("domain")
    quick = [step.tool for step in book.steps_for("quick")]
    deep = [step.tool for step in book.steps_for("deep")]
    assert len(quick) < len(deep)
    assert "whois_lookup" in deep and "whois_lookup" not in quick


def test_prompt_block_contains_discipline():
    block = skills.select("phone").prompt_block("standard")
    assert "Anti-patterns" in block
    assert "Stop conditions" in block
    assert "phone_info" in block


def test_all_playbook_tools_exist():
    from osint_agent.tools import TOOLS

    for book in skills.PLAYBOOKS.values():
        for step in book.steps:
            assert step.tool in TOOLS, step.tool
