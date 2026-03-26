import json
from pathlib import Path
from types import SimpleNamespace

from database.scripts import build_all_indices


def test_build_all_provenance_and_session_manifest_merge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    deps = tmp_path / ".dependencies.json"
    deps.write_text(
        json.dumps(
            {
                "repos": {
                    "erf": {"commit": "dep-erf"},
                    "pelec": {"commit": "dep-pelec"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        build_all_indices,
        "_project_root",
        lambda: tmp_path,
    )

    class _RunResult:
        stdout = "git-commit-all\n"

    monkeypatch.setattr(
        build_all_indices.subprocess,
        "run",
        lambda *args, **kwargs: _RunResult(),
    )

    embedder = SimpleNamespace(
        service=SimpleNamespace(
            config=SimpleNamespace(
                embedding_provider="cborg",
                faiss_embedding_model="lbl/nomic-embed-text",
                embedding_dimension=768,
            )
        )
    )

    level1_dir = tmp_path / "faiss" / "level1"
    manifest_path, payload = build_all_indices._write_provenance_file(
        output_dir=level1_dir,
        filename="erf_faiss_provenance.json",
        embedder=embedder,
        solver="erf",
        level="1",
        source_dir=tmp_path,
    )
    assert manifest_path.exists()
    assert payload["solver"] == "erf"
    assert payload["level"] == "1"
    assert payload["repo_commit"] == "git-commit-all"
    assert payload["dependencies_commit"] == "dep-erf"

    root_output = tmp_path / "faiss"
    session_a = build_all_indices._write_build_session_manifest(
        root_output_dir=root_output,
        new_entries=[
            {
                "manifest_path": manifest_path.relative_to(root_output).as_posix(),
                **payload,
            }
        ],
    )
    assert session_a.exists()

    _, payload_pelec = build_all_indices._write_provenance_file(
        output_dir=tmp_path / "faiss" / "level2",
        filename="pelec_faiss_provenance.json",
        embedder=embedder,
        solver="pelec",
        level="2",
        source_dir=tmp_path,
    )
    session_b = build_all_indices._write_build_session_manifest(
        root_output_dir=root_output,
        new_entries=[
            {
                "manifest_path": "level2/pelec_faiss_provenance.json",
                **payload_pelec,
            }
        ],
    )

    data = json.loads(session_b.read_text(encoding="utf-8"))
    entries = data["entries"]
    keys = {(entry["level"], entry["solver"]) for entry in entries}
    assert ("1", "erf") in keys
    assert ("2", "pelec") in keys


def test_session_manifest_keeps_distinct_embedding_configurations(tmp_path: Path) -> None:
    root_output = tmp_path / "faiss"
    session_path = build_all_indices._write_build_session_manifest(
        root_output_dir=root_output,
        new_entries=[
            {
                "level": "1",
                "solver": "erf",
                "embedding_provider": "cborg",
                "embedding_model": "lbl/nomic-embed-text",
                "manifest_path": "level1/erf_cborg_manifest.json",
            }
        ],
    )
    assert session_path.exists()

    build_all_indices._write_build_session_manifest(
        root_output_dir=root_output,
        new_entries=[
            {
                "level": "1",
                "solver": "erf",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-large",
                "manifest_path": "level1/erf_openai_manifest.json",
            }
        ],
    )

    data = json.loads(session_path.read_text(encoding="utf-8"))
    entries = data["entries"]
    matching = [
        entry
        for entry in entries
        if entry.get("level") == "1" and entry.get("solver") == "erf"
    ]
    providers_models = {
        (entry.get("embedding_provider"), entry.get("embedding_model"))
        for entry in matching
    }
    assert ("cborg", "lbl/nomic-embed-text") in providers_models
    assert ("openai", "text-embedding-3-large") in providers_models
