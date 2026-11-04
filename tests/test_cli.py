from osint_agent import cli
from osint_agent.services import orchestrator as orch


def test_doctor_runs(capsys):
    code = cli.main(["doctor"])
    assert code in (0, 1)
    assert "doctor" in capsys.readouterr().out


def test_scan_prints_findings(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(orch.collectors, "search", lambda q, limit=8: [])
    monkeypatch.setattr(orch.collectors, "scan_profiles", lambda u, timeout=45: [])
    db = str(tmp_path / "runs.sqlite")
    code = cli.main(["--db", db, "scan", "johndoe", "-p", "quick"])
    out = capsys.readouterr().out
    assert code == 0
    assert "web_search" in out or "scan_profiles" in out


def test_export_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(orch.collectors, "search", lambda q, limit=8: [])
    monkeypatch.setattr(orch.collectors, "scan_profiles", lambda u, timeout=45: [])
    db = str(tmp_path / "runs.sqlite")
    cli.main(["--db", db, "scan", "johndoe", "-p", "quick"])
    from osint_agent.services.store import RunStore

    run_id = RunStore(db).list_runs()[0]["id"]
    target = tmp_path / "out.json"
    assert cli.main(["--db", db, "export", run_id, "-o", str(target)]) == 0
    assert run_id in target.read_text()


def test_unknown_run_returns_error(tmp_path, capsys):
    db = str(tmp_path / "runs.sqlite")
    assert cli.main(["--db", db, "resume", "nope"]) == 1
    assert "ไม่พบ run" in capsys.readouterr().err
