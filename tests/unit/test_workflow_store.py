from pathlib import Path

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

