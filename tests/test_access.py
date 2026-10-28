import json

import pytest

from osint_agent import access

ACTOR = {"name": "user"}


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(access, "AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(access, "AUDIT_FILE", str(tmp_path / "audit" / "audit.jsonl"))


def _lines():
    with open(access.AUDIT_FILE, encoding="utf-8") as fh:
        return fh.readlines()


def _write(lines):
    with open(access.AUDIT_FILE, "w", encoding="utf-8") as fh:
        fh.writelines(lines)


def test_empty_log_ok():
    assert access.verify_audit_chain()[0]


def test_chain_verifies():
    access.audit("login", ACTOR)
    access.audit("search", ACTOR, target_value="0812345678")
    ok, count, _ = access.verify_audit_chain()
    assert ok and count == 2


def test_detects_edit():
    access.audit("search", ACTOR, target_value="0811111111")
    access.audit("search", ACTOR, target_value="0822222222")
    lines = _lines()
    entry = json.loads(lines[0])
    entry["target_value"] = "0899999999"
    lines[0] = json.dumps(entry, ensure_ascii=False) + "\n"
    _write(lines)
    ok, line_no, _ = access.verify_audit_chain()
    assert not ok and line_no == 1


def test_detects_deletion():
    for i in range(3):
        access.audit("search", ACTOR, target_value=str(i))
    lines = _lines()
    _write([lines[0], lines[2]])
    ok, line_no, _ = access.verify_audit_chain()
    assert not ok and line_no == 2
