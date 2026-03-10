"""SQLite-backed workflow/session store for MCP server."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SESSION_LIFECYCLE_STATES = ("creation", "active", "completed", "archived")
_COMPLETION_STATUSES = {"complete", "completed", "success", "succeeded", "done"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowSession:
    session_id: str
    state: dict[str, Any]
    created_at: str
    updated_at: str
    lifecycle_state: str


def _normalize_lifecycle_state(value: Any) -> str | None:
    if isinstance(value, str) and value in SESSION_LIFECYCLE_STATES:
        return value
    return None


def _is_completed_signal(state: dict[str, Any]) -> bool:
    if state.get("completed") is True:
        return True
    for key in ("status", "job_status"):
        value = state.get(key)
        if isinstance(value, str) and value.lower() in _COMPLETION_STATUSES:
            return True
    return False


def _is_archived_signal(state: dict[str, Any]) -> bool:
    if state.get("archived") is True:
        return True
    status = state.get("status")
    return isinstance(status, str) and status.lower() == "archived"


def _is_valid_transition(previous: str, target: str) -> bool:
    transitions = {
        "creation": {"creation", "active", "completed", "archived"},
        "active": {"active", "completed", "archived"},
        "completed": {"completed", "archived"},
        "archived": {"archived"},
    }
    return target in transitions[previous]


def _resolve_lifecycle_state(
    previous_state: dict[str, Any] | None,
    incoming_state: dict[str, Any],
    *,
    is_new: bool,
) -> str:
    if is_new:
        return "creation"

    previous_lifecycle = _normalize_lifecycle_state((previous_state or {}).get("session_lifecycle_state")) or "creation"
    requested_lifecycle = _normalize_lifecycle_state(incoming_state.get("session_lifecycle_state"))

    if previous_lifecycle == "archived":
        if requested_lifecycle and requested_lifecycle != "archived":
            raise ValueError("Invalid lifecycle transition: archived sessions are immutable")
        return "archived"

    lifecycle_state = requested_lifecycle
    if lifecycle_state is None:
        if _is_archived_signal(incoming_state):
            lifecycle_state = "archived"
        elif _is_completed_signal(incoming_state):
            lifecycle_state = "completed"
        elif previous_lifecycle == "creation":
            lifecycle_state = "active"
        else:
            lifecycle_state = previous_lifecycle

    if not _is_valid_transition(previous_lifecycle, lifecycle_state):
        raise ValueError(f"Invalid lifecycle transition: {previous_lifecycle} -> {lifecycle_state}")
    return lifecycle_state


def _enrich_lifecycle_metadata(
    previous_state: dict[str, Any] | None,
    incoming_state: dict[str, Any],
    lifecycle_state: str,
    now: str,
) -> dict[str, Any]:
    enriched = dict(incoming_state)
    previous = previous_state or {}
    previous_lifecycle = _normalize_lifecycle_state(previous.get("session_lifecycle_state")) or "creation"

    for marker in (
        "session_created_at",
        "session_active_at",
        "session_completed_at",
        "session_archived_at",
    ):
        if marker in previous and marker not in enriched:
            enriched[marker] = previous[marker]

    enriched.setdefault("session_created_at", now)
    if lifecycle_state == "active" and previous_lifecycle != "active" and "session_active_at" not in enriched:
        enriched["session_active_at"] = now
    if lifecycle_state == "completed" and previous_lifecycle != "completed" and "session_completed_at" not in enriched:
        enriched["session_completed_at"] = now
    if lifecycle_state == "archived" and previous_lifecycle != "archived" and "session_archived_at" not in enriched:
        enriched["session_archived_at"] = now

    enriched["session_lifecycle_state"] = lifecycle_state
    enriched["session_lifecycle_updated_at"] = now
    return enriched


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
        lifecycle_state = _normalize_lifecycle_state(state.get("session_lifecycle_state")) or "creation"
        return WorkflowSession(
            session_id=row["session_id"],
            state=state,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            lifecycle_state=lifecycle_state,
        )

    def upsert_session(self, session_id: str, state: dict[str, Any]) -> None:
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM workflow_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            previous_state = json.loads(row["state_json"]) if row else None
            lifecycle_state = _resolve_lifecycle_state(
                previous_state,
                state,
                is_new=row is None,
            )
            enriched_state = _enrich_lifecycle_metadata(
                previous_state,
                state,
                lifecycle_state,
                now,
            )
            payload = json.dumps(enriched_state, default=str)
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
