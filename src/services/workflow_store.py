"""SQLite-backed workflow/session store for MCP server."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowSession:
    session_id: str
    state: dict[str, Any]
    created_at: str
    updated_at: str


class WorkflowStore:
    """Persist workflow session state in SQLite (WAL)."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
                """
            )

    def get_session(self, session_id: str) -> WorkflowSession | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        state = json.loads(row["state_json"])
        return WorkflowSession(
            session_id=row["session_id"],
            state=state,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert_session(self, session_id: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, default=str)
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workflow_sessions (session_id, created_at, updated_at, state_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    state_json = excluded.state_json
                """,
                (session_id, now, now, payload),
            )

