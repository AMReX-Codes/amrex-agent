from types import SimpleNamespace

from src.benchmark_runner import _write_jsonl


def test_benchmark_jsonl_scrubs_prompt(tmp_path):
    config = SimpleNamespace(
        privacy_mode="shared",
        privacy_scrubber="builtin",
        privacy_hash_salt="salt",
    )
    path = tmp_path / "bench.jsonl"
    _write_jsonl(path, {"prompt_excerpt": "email user@example.com"}, config=config)
    content = path.read_text()
    assert "user@example.com" not in content
    assert "[REDACTED:EMAIL]" in content
