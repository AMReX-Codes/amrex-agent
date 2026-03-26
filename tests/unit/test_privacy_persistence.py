import json

from src.utils.metrics import MetricsCollector
from src.utils.privacy import sanitize_payload


class DummyConfig:
    def __init__(self, mode):
        self.privacy_mode = mode
        self.privacy_hash_salt = "salt"


def test_metrics_jsonl_scrubbed_shared(tmp_path):
    config = DummyConfig("shared")
    collector = MetricsCollector()
    collector.record_event(
        "prompt_event",
        {"prompt": "email me at user@example.com"},
        stage="workflow",
        node="main",
    )
    path = tmp_path / "metrics.jsonl"
    collector.write_jsonl(str(path), config=config)

    content = path.read_text()
    assert "user@example.com" not in content
    assert "[REDACTED:EMAIL]" in content


def test_workflow_history_scrubbed_strict(tmp_path):
    config = DummyConfig("strict")
    history = [
        {
            "node": "architect",
            "details": {
                "prompt": "email me at user@example.com",
            },
        }
    ]
    payload = sanitize_payload(history, config=config)
    path = tmp_path / "workflow_history.json"
    path.write_text(json.dumps(payload))

    content = path.read_text()
    assert "user@example.com" not in content
    assert "prompt" in content
