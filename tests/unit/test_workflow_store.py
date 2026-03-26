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
    assert loaded.state["prompt"] == "test"
    assert loaded.state["status"] == "ok"
    assert loaded.lifecycle_state == "creation"


def test_session_lifecycle_starts_in_creation_state(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "lifecycle-create"
    store.upsert_session(session_id, {"prompt": "new session"})

    loaded = store.get_session(session_id)
    assert loaded is not None
    assert loaded.lifecycle_state == "creation"
    assert loaded.state["session_lifecycle_state"] == "creation"
    assert loaded.state["session_created_at"]
    assert loaded.state["session_lifecycle_updated_at"]


def test_session_lifecycle_transitions_active_completed_archived(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "lifecycle-transitions"
    store.upsert_session(session_id, {"status": "queued"})
    store.upsert_session(session_id, {"status": "running"})
    loaded_active = store.get_session(session_id)
    assert loaded_active is not None
    assert loaded_active.lifecycle_state == "active"
    assert loaded_active.state["session_active_at"]

    store.upsert_session(session_id, {"status": "completed"})
    loaded_completed = store.get_session(session_id)
    assert loaded_completed is not None
    assert loaded_completed.lifecycle_state == "completed"
    assert loaded_completed.state["session_completed_at"]

    store.upsert_session(session_id, {"archived": True})
    loaded_archived = store.get_session(session_id)
    assert loaded_archived is not None
    assert loaded_archived.lifecycle_state == "archived"
    assert loaded_archived.state["session_archived_at"]


def test_session_lifecycle_rejects_invalid_regression(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "lifecycle-invalid"
    store.upsert_session(session_id, {"status": "queued"})
    store.upsert_session(session_id, {"status": "running"})
    store.upsert_session(session_id, {"status": "completed"})

    try:
        store.upsert_session(session_id, {"session_lifecycle_state": "active"})
    except ValueError as exc:
        assert "Invalid lifecycle transition" in str(exc)
    else:
        raise AssertionError("Expected ValueError for completed -> active transition")


def test_archived_session_is_immutable(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "lifecycle-archived"
    store.upsert_session(session_id, {"status": "queued"})
    store.upsert_session(session_id, {"archived": True})

    try:
        store.upsert_session(session_id, {"session_lifecycle_state": "completed"})
    except ValueError as exc:
        assert "archived sessions are immutable" in str(exc)
    else:
        raise AssertionError("Expected ValueError for archived -> completed transition")


def test_archived_session_rejects_non_noop_update(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "lifecycle-archived-non-noop"
    store.upsert_session(session_id, {"status": "queued"})
    store.upsert_session(session_id, {"archived": True})

    try:
        store.upsert_session(session_id, {"status": "archived", "new_field": "unexpected"})
    except ValueError as exc:
        assert "archived sessions are immutable" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-noop update on archived session")


def test_archived_session_allows_noop_replay(tmp_path: Path):
    db_path = tmp_path / "workflow_store.db"
    store = WorkflowStore(db_path)

    session_id = "lifecycle-archived-noop"
    store.upsert_session(session_id, {"status": "queued"})
    store.upsert_session(session_id, {"archived": True})

    store.upsert_session(session_id, {"archived": True})
    loaded = store.get_session(session_id)
    assert loaded is not None
    assert loaded.lifecycle_state == "archived"


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
