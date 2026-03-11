import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from database.scripts import build_index


def _parse_iso8601(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def test_write_faiss_provenance_manifest_populates_required_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    deps = tmp_path / ".dependencies.json"
    deps.write_text(
        json.dumps({"repos": {"erf": {"commit": "dep-commit-123"}}}),
        encoding="utf-8",
    )
    source_dir = tmp_path / "ERF"
    source_dir.mkdir(parents=True)

    class _RunResult:
        stdout = "git-commit-abc\n"

    monkeypatch.setattr(build_index.subprocess, "run", lambda *args, **kwargs: _RunResult())

    embedding_model = SimpleNamespace(
        config=SimpleNamespace(
            embedding_provider="cborg",
            faiss_embedding_model="lbl/nomic-embed-text",
            embedding_dimension=768,
        ),
        embeddings=SimpleNamespace(model="lbl/nomic-embed-text"),
    )

    manifest_path = build_index.write_faiss_provenance_manifest(
        output_dir=tmp_path / "out",
        embedding_model=embedding_model,
        solver="erf",
        level="case_details",
        source_dir=source_dir,
        embedding_provider_arg="openai",
        embedding_model_arg="text-embedding-3-small",
        dependencies_path=deps,
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_keys = {
        "version",
        "generated_at",
        "embedding_model",
        "embedding_provider",
        "embedding_dimension",
        "solver",
        "level",
        "repo_commit",
        "build_script",
        "dependencies_commit",
    }
    assert set(payload.keys()) == expected_keys
    assert payload["version"] == "1"
    assert isinstance(payload["generated_at"], str)
    _parse_iso8601(payload["generated_at"])
    assert payload["embedding_model"] == "lbl/nomic-embed-text"
    assert payload["embedding_provider"] == "cborg"
    assert payload["embedding_dimension"] == 768
    assert payload["solver"] == "erf"
    assert payload["level"] == "case_details"
    assert payload["repo_commit"] == "git-commit-abc"
    assert payload["build_script"] == "build_index.py"
    assert payload["dependencies_commit"] == "dep-commit-123"


def test_write_faiss_provenance_manifest_uses_nulls_when_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def _raise_git(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(build_index.subprocess, "run", _raise_git)

    embedding_model = SimpleNamespace(
        config=SimpleNamespace(),
        embeddings=SimpleNamespace(),
    )

    manifest_path = build_index.write_faiss_provenance_manifest(
        output_dir=tmp_path / "out",
        embedding_model=embedding_model,
        solver="erf",
        level="case_structure",
        source_dir=tmp_path / "missing_repo",
        embedding_provider_arg=None,
        embedding_model_arg=None,
        dependencies_path=tmp_path / "missing.dependencies.json",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["embedding_model"] is None
    assert payload["embedding_provider"] is None
    assert payload["embedding_dimension"] is None
    assert payload["repo_commit"] is None
    assert payload["dependencies_commit"] is None
