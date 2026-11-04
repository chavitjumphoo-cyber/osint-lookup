"""ที่เก็บ run, event และ finding ระหว่างการสืบสวน (SQLite)

ใช้เป็น checkpoint ไปด้วย: step ที่ status = done จะถูกข้ามเมื่อ resume
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_PATH = os.path.join("audit", "runs.sqlite")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class RunStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("OSINT_DB") or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq)
                );
                CREATE TABLE IF NOT EXISTS steps (
                    run_id TEXT NOT NULL,
                    step_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, step_key)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    run_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decided_at TEXT,
                    PRIMARY KEY (run_id, candidate_id)
                );
                CREATE TABLE IF NOT EXISTS findings (
                    run_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    tool TEXT NOT NULL,
                    output TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ok',
                    output_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq)
                );
                CREATE TABLE IF NOT EXISTS reports (
                    run_id TEXT PRIMARY KEY,
                    markdown TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._migrate(connection)

    def _columns(self, connection: sqlite3.Connection, table: str) -> set[str]:
        return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}

    def _ensure_columns(
        self, connection: sqlite3.Connection, table: str, columns: dict[str, str]
    ) -> None:
        existing = self._columns(connection, table)
        for column, ddl in columns.items():
            if column not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _migrate(self, connection: sqlite3.Connection) -> None:
        """เติมคอลัมน์ที่เพิ่มภายหลังให้ฐานเดิม — CREATE IF NOT EXISTS ไม่ retro-fit"""
        self._ensure_columns(
            connection,
            "findings",
            {"status": "TEXT NOT NULL DEFAULT 'ok'", "output_hash": "TEXT NOT NULL DEFAULT ''"},
        )

    # -- runs -------------------------------------------------------------

    def create_run(
        self, target: str, target_type: str, profile: str, trusted: list[str] | None = None
    ) -> str:
        run_id = uuid.uuid4().hex[:12]
        now = _now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO runs (id, target, target_type, profile, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'queued', ?, ?)",
                (run_id, target, target_type, profile, now, now),
            )
            connection.execute(
                "INSERT OR REPLACE INTO events (run_id, seq, kind, text, created_at) VALUES (?, 0, 'meta', ?, ?)",
                (run_id, json.dumps({"trusted": trusted or []}, ensure_ascii=False), now),
            )
        return run_id

    def trusted(self, run_id: str) -> list[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT text FROM events WHERE run_id = ? AND seq = 0", (run_id,)
            ).fetchone()
        if not row:
            return []
        try:
            return json.loads(row["text"]).get("trusted") or []
        except ValueError:
            return []

    def set_status(self, run_id: str, status: str, error: str | None = None) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, error, _now(), run_id),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 50) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    # -- events -----------------------------------------------------------

    def add_event(self, run_id: str, kind: str, text: str) -> dict:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) AS seq FROM events WHERE run_id = ?", (run_id,)
            ).fetchone()
            seq = int(row["seq"]) + 1
            created = _now()
            connection.execute(
                "INSERT INTO events (run_id, seq, kind, text, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, seq, kind, text, created),
            )
        return {"seq": seq, "kind": kind, "text": text, "created_at": created}

    def list_events(self, run_id: str, after: int = 0) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT seq, kind, text, created_at FROM events WHERE run_id = ? AND seq > ? "
                "ORDER BY seq",
                (run_id, after),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- steps (checkpoint) ----------------------------------------------

    def step_status(self, run_id: str, step_key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM steps WHERE run_id = ? AND step_key = ?", (run_id, step_key)
            ).fetchone()
        return row["status"] if row else None

    def set_step(self, run_id: str, step_key: str, status: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO steps (run_id, step_key, status, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(run_id, step_key) DO UPDATE SET status = excluded.status, "
                "updated_at = excluded.updated_at",
                (run_id, step_key, status, _now()),
            )

    # -- findings ---------------------------------------------------------

    def add_finding(
        self, run_id: str, tool: str, output: str, status: str = "ok", output_hash: str = ""
    ) -> None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) AS seq FROM findings WHERE run_id = ?", (run_id,)
            ).fetchone()
            connection.execute(
                "INSERT INTO findings (run_id, seq, tool, output, status, output_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, int(row["seq"]) + 1, tool, output, status, output_hash, _now()),
            )

    # -- evidence ---------------------------------------------------------

    def add_evidence(self, run_id: str, item: dict) -> None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) AS seq FROM evidence WHERE run_id = ?", (run_id,)
            ).fetchone()
            connection.execute(
                "INSERT INTO evidence (run_id, seq, payload) VALUES (?, ?, ?)",
                (run_id, int(row["seq"]) + 1, json.dumps(item, ensure_ascii=False)),
            )

    def list_evidence(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM evidence WHERE run_id = ? ORDER BY seq", (run_id,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    # -- identity candidates ---------------------------------------------

    def add_candidate(self, run_id: str, candidate: dict) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO candidates (run_id, candidate_id, payload, status) "
                "VALUES (?, ?, ?, 'CANDIDATE')",
                (run_id, candidate["candidate_id"], json.dumps(candidate, ensure_ascii=False)),
            )

    def list_candidates(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload, status, decided_at FROM candidates WHERE run_id = ? "
                "ORDER BY candidate_id",
                (run_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = json.loads(row["payload"])
            item["status"] = row["status"]
            item["decided_at"] = row["decided_at"]
            result.append(item)
        return result

    def decide_candidate(self, run_id: str, candidate_id: str, action: str) -> dict | None:
        mapping = {"confirm": "CONFIRMED", "reject": "REJECTED", "reverse": "CANDIDATE"}
        status = mapping.get(action)
        if not status:
            return None
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE candidates SET status = ?, decided_at = ? WHERE run_id = ? AND candidate_id = ?",
                (status, _now(), run_id, candidate_id),
            )
        if cursor.rowcount == 0:
            return None
        return next(
            (c for c in self.list_candidates(run_id) if c["candidate_id"] == candidate_id), None
        )

    def save_report(self, run_id: str, markdown: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO reports (run_id, markdown, created_at) VALUES (?, ?, ?)",
                (run_id, markdown, _now()),
            )

    def get_report(self, run_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT markdown FROM reports WHERE run_id = ?", (run_id,)
            ).fetchone()
        return row["markdown"] if row else None

    def list_findings(self, run_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT seq, tool, output, status, output_hash, created_at FROM findings "
                "WHERE run_id = ? ORDER BY seq",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def to_dict(self, run_id: str) -> dict | None:
        run = self.get_run(run_id)
        if not run:
            return None
        run["events"] = self.list_events(run_id)
        run["findings"] = self.list_findings(run_id)
        run["evidence"] = self.list_evidence(run_id)
        run["candidates"] = self.list_candidates(run_id)
        run["report"] = self.get_report(run_id)
        return run

    def export_json(self, run_id: str) -> str:
        data = self.to_dict(run_id)
        return json.dumps(data, ensure_ascii=False, indent=2) if data else "{}"
