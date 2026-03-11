from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import sqlite3

from src.services.workflow_store import WorkflowStore


def test_workflow_store_roundtrip(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "session-123"
    state = {"prompt": "test", "status": "ok"}
    store.upsert_session(session_id, state)

    loaded = store.get_session(session_id)
    assert loaded is not None
    assert loaded.session_id == session_id
    assert loaded.state == state


def test_sweep_state_persists_after_disconnect(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "sess-1"
    sweep_state = {
        "sweep_id": "sweep-1",
        "session_id": session_id,
        "status": "running",
    }
    store.upsert_session(session_id, {"sweep": sweep_state})

    reconnected = WorkflowStore(db_path)
    loaded = reconnected.get_session(session_id)

    assert loaded is not None
    assert loaded.state["sweep"]["sweep_id"] == "sweep-1"
    assert loaded.state["sweep"]["session_id"] == session_id
    assert loaded.state["sweep"]["status"] == "running"


def test_sweep_metadata_json_schema(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "sess-2"
    store.upsert_session(
        session_id,
        {
            "sweep_metadata": {
                "sweep_id": "sweep-2",
                "session_id": session_id,
                "status": "complete",
                "created_at": "2026-03-10T00:00:00Z",
            }
        },
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT state_json FROM workflow_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    assert row is not None
    state = json.loads(row[0])
    metadata = state["sweep_metadata"]
    assert metadata["sweep_id"] == "sweep-2"
    assert metadata["session_id"] == session_id
    assert metadata["status"] == "complete"
    assert metadata["created_at"]


def test_concurrent_sweep_writes_do_not_corrupt(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "sess-3"
    state = {"sweeps": {}}
    state["sweeps"]["sweep-a"] = {"sweep_id": "sweep-a", "status": "running"}
    store.upsert_session(session_id, state)

    state["sweeps"]["sweep-b"] = {"sweep_id": "sweep-b", "status": "complete"}
    store.upsert_session(session_id, state)

    loaded = store.get_session(session_id)
    assert loaded is not None
    assert loaded.state["sweeps"]["sweep-a"]["sweep_id"] == "sweep-a"
    assert loaded.state["sweeps"]["sweep-a"]["status"] == "running"
    assert loaded.state["sweeps"]["sweep-b"]["sweep_id"] == "sweep-b"
    assert loaded.state["sweeps"]["sweep-b"]["status"] == "complete"


def test_five_concurrent_users_write_without_session_collisions(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)
    user_count = 5
    writes_per_user = 20

    def write_user_state(user_index: int) -> None:
        session_id = f"user-session-{user_index}"
        for write_index in range(writes_per_user):
            store.upsert_session(
                session_id,
                {
                    "user_id": f"user-{user_index}",
                    "session_id": session_id,
                    "write_index": write_index,
                },
            )

    with ThreadPoolExecutor(max_workers=user_count) as pool:
        futures = [pool.submit(write_user_state, user_index) for user_index in range(user_count)]
        for future in futures:
            future.result()

    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM workflow_sessions").fetchone()[0]
    assert row_count == user_count

    for user_index in range(user_count):
        session_id = f"user-session-{user_index}"
        loaded = store.get_session(session_id)
        assert loaded is not None
        assert loaded.session_id == session_id
        assert loaded.state["session_id"] == session_id
        assert loaded.state["user_id"] == f"user-{user_index}"
        assert loaded.state["write_index"] == writes_per_user - 1
