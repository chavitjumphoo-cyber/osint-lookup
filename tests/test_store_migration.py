import sqlite3

from osint_agent.services.store import RunStore

OLD_FINDINGS = """
CREATE TABLE findings (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    tool TEXT NOT NULL,
    output TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
)
"""


def test_migrates_old_findings_table(tmp_path):
    path = tmp_path / "old.sqlite"
    connection = sqlite3.connect(path)
    connection.execute(OLD_FINDINGS)
    connection.commit()
    connection.close()

    store = RunStore(path)
    with store._connect() as connection:
        columns = store._columns(connection, "findings")
    assert {"status", "output_hash"} <= columns

    run_id = store.create_run("target", "text", "quick")
    store.add_finding(run_id, "tool", "output")
    finding = store.list_findings(run_id)[0]
    assert finding["status"] == "ok"
    assert finding["output_hash"] == ""


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "old.sqlite"
    store = RunStore(path)
    store._init()
    store._init()
    with store._connect() as connection:
        columns = store._columns(connection, "findings")
    assert {"status", "output_hash"} <= columns
