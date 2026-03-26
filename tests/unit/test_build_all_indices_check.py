import importlib
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = "database.scripts.build_all_indices"


def _write_manifest(path: Path, entries: list[dict]) -> None:
    path.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")


def test_check_contract_flags_and_provider_model_filtering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2: FAISS manifest provenance --check contract.
    Contract: handoff manifest flags (STALE, MODEL MISMATCH, MISSING).
    Graph state: N/A (CLI/database artifact validation path).
    """
    module = importlib.import_module(MODULE_PATH)

    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir(parents=True)
    manifest_path = faiss_root / "build_session_manifest.json"
    _write_manifest(
        manifest_path,
        [
            {
                "solver": "PeleC",
                "level": "all",
                "generated_at": "2026-03-12T00:00:00+00:00",
                "repo_commit": "sha-current-pelec",
                "dependencies_commit": "deps-1",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
            },
            {
                "solver": "PeleLMeX",
                "level": "all",
                "generated_at": "2026-03-12T00:00:00+00:00",
                "repo_commit": "sha-old-pelelmex",
                "dependencies_commit": "deps-2",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-large",
            },
            {
                "solver": "PeleLMeX",
                "level": "all",
                "generated_at": "2026-03-12T01:00:00+00:00",
                "repo_commit": "sha-current-pelelmex",
                "dependencies_commit": "deps-3",
                "embedding_provider": "cborg",
                "embedding_model": "text-embedding-3-small",
            },
        ],
    )

    class _Cfg:
        embedding_provider = "openai"
        faiss_embedding_model = "text-embedding-3-small"

    class _SolverCfg1:
        code_name = "PeleC"

    class _SolverCfg2:
        code_name = "PeleLMeX"

    monkeypatch.setattr(module, "discover_code_configs", lambda: [_SolverCfg1, _SolverCfg2])
    monkeypatch.setattr(module, "_resolve_repo_head_for_solver", lambda solver, config: {
        "PeleC": "sha-current-pelec",
        "PeleLMeX": "sha-current-pelelmex",
    }.get(solver, "MISSING"))

    exit_code, lines = module.run_manifest_provenance_check(faiss_root=faiss_root, config=_Cfg())

    output = "\n".join(lines)
    assert exit_code == 1
    assert "MODEL MISMATCH" in output
    assert "MISSING" in output
    assert "PeleC" in output and "PeleLMeX" in output
    assert "STALE" not in output


def test_check_mode_does_not_build_indices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2: --check must be verification-only.
    Contract: no Level0/1/2 build side effects during provenance checks.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)

    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir(parents=True)
    _write_manifest(
        faiss_root / "build_session_manifest.json",
        [
            {
                "solver": "PeleC",
                "level": "all",
                "generated_at": "2026-03-12T00:00:00+00:00",
                "repo_commit": "sha-current-pelec",
                "dependencies_commit": "deps-1",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
            }
        ],
    )

    class _Cfg:
        embedding_provider = "openai"
        faiss_embedding_model = "text-embedding-3-small"

    class _SolverCfg1:
        code_name = "PeleC"

    monkeypatch.setattr(module, "discover_code_configs", lambda: [_SolverCfg1])
    monkeypatch.setattr(module, "_resolve_repo_head_for_solver", lambda solver, config: "sha-current-pelec")
    monkeypatch.setattr(module, "_load_runtime_config", lambda: _Cfg())

    def _fail(*_args, **_kwargs):
        raise AssertionError("build should not run during --check")

    monkeypatch.setattr(module, "build_level0", _fail)
    monkeypatch.setattr(module, "build_level1", _fail)
    monkeypatch.setattr(module, "build_level2", _fail)

    monkeypatch.setattr(
        "sys.argv",
        ["build_all_indices.py", "--check", "--output", str(faiss_root)],
    )

    exit_code = module.main()
    assert exit_code == 0


def test_load_manifest_entries_validates_shapes(tmp_path: Path) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2: resilient manifest ingestion for check mode.
    Contract: build_session_manifest JSON accepts list/entries-list and rejects malformed entries.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir()

    with pytest.raises(FileNotFoundError):
        module._load_manifest_entries(faiss_root)

    (faiss_root / "build_session_manifest.json").write_text(
        json.dumps([{"solver": "PeleC"}, "bad"]),
        encoding="utf-8",
    )
    assert module._load_manifest_entries(faiss_root) == [{"solver": "PeleC"}]

    (faiss_root / "build_session_manifest.json").write_text(
        json.dumps({"entries": "bad"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        module._load_manifest_entries(faiss_root)


def test_resolve_repo_head_for_solver_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2: solver-level staleness detection source of truth.
    Contract: repo HEAD resolution returns concrete SHA or MISSING sentinel.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    repo = tmp_path / "repo"
    repo.mkdir()
    config = SimpleNamespace(repositories={"PeleC": repo})

    assert module._resolve_repo_head_for_solver("Unknown", config) == "MISSING"

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    assert module._resolve_repo_head_for_solver("PeleC", config) == "MISSING"

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=""),
    )
    assert module._resolve_repo_head_for_solver("PeleC", config) == "MISSING"

    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="abc123\n"),
    )
    assert module._resolve_repo_head_for_solver("PeleC", config) == "abc123"


def test_resolve_config_and_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2: solver registry/repo lookup routing for checks/builds.
    Contract: code-name and repo-name mapping consistency for CLI resolution.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)

    class _PeleC:
        code_name = "PeleC"
        github_repo = "pelec"

    class _ERF:
        code_name = "ERF"
        github_repo = "erf"

    monkeypatch.setattr(module, "discover_code_configs", lambda: [_PeleC, _ERF])

    assert module._resolve_config_class(code_name="pelec") is _PeleC
    assert module._resolve_config_class(repo_path=Path("/x/ERF")) is _ERF
    assert module._resolve_config_class(code_name="missing") is None

    direct_repo = tmp_path / "direct"
    direct_repo.mkdir()
    assert module._resolve_repo_root(direct_repo, None) == direct_repo

    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_a.mkdir()
    cfg = SimpleNamespace(repositories={"PeleC": repo_a, "ERF": repo_b})
    monkeypatch.setattr("src.services.config_service.ConfigService.initialize", lambda _self: cfg)
    assert module._resolve_repo_root(None, "pelec") == repo_a
    assert module._resolve_repo_root(None, None) == repo_a

    cfg_empty = SimpleNamespace(repositories={"PeleC": repo_b})
    monkeypatch.setattr("src.services.config_service.ConfigService.initialize", lambda _self: cfg_empty)
    assert module._resolve_repo_root(None, None) is None


def test_create_embedder_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 hardening (deterministic validation path in test mode).
    Contract: embedder factory supports mock mode and safe fallback behavior.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)

    mock_embedder = module.create_embedder(use_real=False)
    assert len(mock_embedder.embed_texts(["a"])) == 100

    class _Service:
        embeddings = object()

        def embed_texts(self, texts):
            return [[1.0] for _ in texts]

        def expand_documents(self, documents, metadata=None):
            return documents, metadata or []

    cfg = SimpleNamespace(embedding_provider="openai", faiss_embedding_model="text-embedding-3-small")
    monkeypatch.setattr("src.services.config_service.ConfigService.initialize", lambda _self: cfg)
    monkeypatch.setattr("src.services.embedding_service_factory.get_embedding_service", lambda _cfg: _Service())
    real = module.create_embedder(use_real=True)
    assert real.embed_texts(["x", "y"]) == [[1.0], [1.0]]
    assert real.expand_documents(["d"], [{"k": "v"}]) == (["d"], [{"k": "v"}])

    monkeypatch.setattr(
        "src.services.embedding_service_factory.get_embedding_service",
        lambda _cfg: SimpleNamespace(embeddings=None),
    )
    fallback = module.create_embedder(use_real=True)
    assert len(fallback.embed_texts(["a"])) == 100


def test_build_level_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 operational reliability context for index build orchestration.
    Contract: Level0/1/2 builders return predictable counts and handle missing repos.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)

    class _L0:
        def __init__(self, embedder):
            self.embedder = embedder

        def build(self, output_dir: Path):
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "router.faiss").write_bytes(b"x")

    monkeypatch.setattr(module, "Level0Builder", _L0)
    assert module.build_level0(tmp_path / "level0", object()) == 1

    missing_repo = tmp_path / "missing"
    assert module.build_level1(missing_repo, tmp_path / "l1_missing", object()) == 0
    assert module.build_level2(missing_repo, tmp_path / "l2_missing", object()) == 0

    class _Cfg:
        code_name = "PeleC"

    class _L1:
        def __init__(self, config, embedder):
            assert config.code_name == "PeleC"

        def build(self, source_dir: Path, output_dir: Path):
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "docs.faiss").write_bytes(b"x")

    class _L2:
        def __init__(self, config, embedder):
            assert config.code_name == "PeleC"

        def build(self, repo_root: Path, output_dir: Path):
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "cases.faiss").write_bytes(b"x")
            (output_dir / "cases_metadata.json").write_text('[{"a":1}]', encoding="utf-8")

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(module, "_resolve_config_class", lambda **_kwargs: _Cfg)
    monkeypatch.setattr(module, "Level1Builder", _L1)
    monkeypatch.setattr(module, "Level2Builder", _L2)
    assert module.build_level1(repo, tmp_path / "level1", object()) == 1
    assert module.build_level2(repo, tmp_path / "level2", object()) == 1


def test_manifest_check_stale_and_pass_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2: stale/non-stale provenance gate outcomes.
    Contract: exit non-zero on stale; exit zero on clean provenance.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    faiss_root = tmp_path / "faiss"
    faiss_root.mkdir()

    class _Cfg:
        embedding_provider = "openai"
        faiss_embedding_model = "text-embedding-3-small"

    class _SolverCfg:
        code_name = "PeleC"

    monkeypatch.setattr(module, "discover_code_configs", lambda: [_SolverCfg])

    _write_manifest(
        faiss_root / "build_session_manifest.json",
        [
            {
                "solver": "PeleC",
                "level": "all",
                "generated_at": "2026-03-12T00:00:00+00:00",
                "repo_commit": "old",
                "dependencies_commit": "deps",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
            }
        ],
    )
    monkeypatch.setattr(module, "_resolve_repo_head_for_solver", lambda solver, config: "new")
    stale_code, stale_lines = module.run_manifest_provenance_check(faiss_root=faiss_root, config=_Cfg())
    assert stale_code == 1
    assert "STALE" in "\n".join(stale_lines)

    _write_manifest(
        faiss_root / "build_session_manifest.json",
        [
            {
                "solver": "PeleC",
                "level": "all",
                "generated_at": "2026-03-12T00:00:00+00:00",
                "repo_commit": "new",
                "dependencies_commit": "deps",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
            }
        ],
    )
    ok_code, ok_lines = module.run_manifest_provenance_check(faiss_root=faiss_root, config=_Cfg())
    assert ok_code == 0
    assert ok_lines[-1] == "Result: PASS"


def test_main_cli_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2 CLI behavior coverage.
    Contract: check-mode error handling and parser fail-fast on unresolved repos.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    out = tmp_path / "out"

    monkeypatch.setattr(module, "run_manifest_provenance_check", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr("sys.argv", ["build_all_indices.py", "--check", "--output", str(out)])
    assert module.main() == 1

    calls = []
    monkeypatch.setattr(module, "create_embedder", lambda use_real: object())
    monkeypatch.setattr(module, "build_level0", lambda output_dir, embedder: calls.append("l0") or 1)
    monkeypatch.setattr(module, "build_level1", lambda repo_root, output_dir, embedder, config_class: calls.append("l1") or 1)
    monkeypatch.setattr(module, "build_level2", lambda repo_root, output_dir, embedder, config_class: calls.append("l2") or 1)
    monkeypatch.setattr("sys.argv", ["build_all_indices.py", "--level", "0", "--mock", "--output", str(out)])
    assert module.main() == 0
    assert calls == ["l0"]

    monkeypatch.setattr(module, "_resolve_repo_root", lambda args_repo, code_name: None)
    monkeypatch.setattr("sys.argv", ["build_all_indices.py", "--level", "1", "--mock", "--output", str(out)])
    with pytest.raises(SystemExit):
        module.main()


def test_provenance_git_and_dependency_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2 helper coverage.
    Contract: provenance metadata reads git/dependency commits with safe fallbacks.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)

    assert module._safe_git_rev_parse_head(None) is None
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="abc123\n"),
    )
    assert module._safe_git_rev_parse_head(tmp_path) == "abc123"

    def _raise(*_args, **_kwargs):
        raise FileNotFoundError("git missing")

    monkeypatch.setattr(module.subprocess, "run", _raise)
    assert module._safe_git_rev_parse_head(tmp_path) is None

    deps = tmp_path / ".dependencies.json"
    deps.write_text(json.dumps({"repos": {"pelec": {"commit": "dep-1"}}}), encoding="utf-8")
    assert module._load_dependencies_commit("PeleC", deps) == "dep-1"
    assert module._load_dependencies_commit("unknown", deps) is None
    assert module._load_dependencies_commit(None, deps) is None

    deps.write_text(json.dumps({"repos": {"pelec": {"commit": "  "}}}), encoding="utf-8")
    assert module._load_dependencies_commit("pelec", deps) is None
    deps.write_text("{bad json", encoding="utf-8")
    assert module._load_dependencies_commit("pelec", deps) is None


def test_extract_and_write_provenance_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2 provenance artifact generation.
    Contract: required manifest payload fields persisted deterministically.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)

    no_service_provider, no_service_model, no_service_dim = module._extract_embedding_metadata(object())
    assert (no_service_provider, no_service_model, no_service_dim) == (None, None, None)

    embedder = SimpleNamespace(
        service=SimpleNamespace(
            config=SimpleNamespace(
                embedding_provider="openai",
                faiss_embedding_model="text-embedding-3-small",
                embedding_dimension=1536,
            )
        )
    )
    provider, model, dim = module._extract_embedding_metadata(embedder)
    assert (provider, model, dim) == ("openai", "text-embedding-3-small", 1536)

    monkeypatch.setattr(module, "_iso_utc_now", lambda: "2026-03-12T00:00:00+00:00")
    monkeypatch.setattr(module, "_safe_git_rev_parse_head", lambda _source_dir: "repo-sha")
    monkeypatch.setattr(module, "_load_dependencies_commit", lambda _solver: "dep-sha")

    manifest_path, payload = module._write_provenance_file(
        output_dir=tmp_path / "level1",
        filename="pelec_faiss_provenance.json",
        embedder=embedder,
        solver="pelec",
        level="1",
        source_dir=tmp_path,
    )
    assert manifest_path.exists()
    assert payload["generated_at"] == "2026-03-12T00:00:00+00:00"
    assert payload["repo_commit"] == "repo-sha"
    assert payload["dependencies_commit"] == "dep-sha"
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["embedding_provider"] == "openai"


def test_session_manifest_merge_and_normalization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2 session manifest behavior.
    Contract: merge-by (level,solver) key with normalized entry filtering.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    session_path = tmp_path / "build_session_manifest.json"

    assert module._load_session_entries(session_path) == []
    session_path.write_text("{bad", encoding="utf-8")
    assert module._load_session_entries(session_path) == []
    session_path.write_text(json.dumps({"entries": "bad"}), encoding="utf-8")
    assert module._load_session_entries(session_path) == []
    session_path.write_text(json.dumps({"entries": [{"level": "1"}, "bad"]}), encoding="utf-8")
    assert module._load_session_entries(session_path) == [{"level": "1"}]

    session_path.write_text(
        json.dumps(
            {
                "entries": [
                    {"level": "1", "solver": "pelec", "manifest_path": "old.json", "repo_commit": "old"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_iso_utc_now", lambda: "2026-03-12T02:00:00+00:00")
    out = module._write_build_session_manifest(
        root_output_dir=tmp_path,
        new_entries=[
            {"level": "1", "solver": "pelec", "manifest_path": "new.json", "repo_commit": "new"},
            {"level": "2", "solver": "pelec", "manifest_path": "l2.json", "repo_commit": "new2"},
        ],
    )
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert merged["generated_at"] == "2026-03-12T02:00:00+00:00"
    assert len(merged["entries"]) == 2
    l1_entry = [e for e in merged["entries"] if e["level"] == "1"][0]
    assert l1_entry["manifest_path"] == "new.json"


def test_resolve_build_context_and_run_build_levels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 hardening appendix complexity/decomposition alignment.
    Contract: helper-extracted CLI context/build routing behaves predictably.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    parser = argparse.ArgumentParser()

    args_l0 = SimpleNamespace(level="0", repo=None, code=None)
    assert module._resolve_build_context(parser, args_l0) == (None, None, "N/A")

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(module, "_resolve_repo_root", lambda *_args, **_kwargs: repo)
    monkeypatch.setattr(module, "_resolve_config_class", lambda **_kwargs: None)
    args_l1 = SimpleNamespace(level="1", repo=None, code="pelec")
    repo_root, config_class, solver_name = module._resolve_build_context(parser, args_l1)
    assert repo_root == repo
    assert solver_name == "repo"
    assert config_class.code_name == "repo"

    calls = []
    monkeypatch.setattr(module, "build_level0", lambda *_args, **_kwargs: calls.append("l0") or 2)
    monkeypatch.setattr(module, "build_level1", lambda *_args, **_kwargs: calls.append("l1") or 3)
    monkeypatch.setattr(module, "build_level2", lambda *_args, **_kwargs: calls.append("l2") or 4)
    args_all = SimpleNamespace(level="all", output=tmp_path)
    total = module._run_build_levels(args=args_all, repo_root=repo, config_class=config_class, embedder=object())
    assert total == 9
    assert calls == ["l0", "l1", "l2"]


def test_run_cli_provenance_paths_for_levels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    PRD v26.05 Amendment B5.1 Phase 2 end-to-end CLI provenance wiring.
    Contract: level-specific provenance writes and conditional session manifest write.
    Graph state: N/A.
    """
    module = importlib.import_module(MODULE_PATH)
    parser = argparse.ArgumentParser()
    out = tmp_path / "out"
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(module, "_resolve_build_context", lambda _parser, _args: (repo, SimpleNamespace(code_name="PeleC"), "PeleC"))
    monkeypatch.setattr(module, "create_embedder", lambda use_real: object())
    monkeypatch.setattr(module, "build_level0", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(module, "build_level1", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(module, "build_level2", lambda *_args, **_kwargs: 1)

    calls = {"provenance": [], "session": 0}

    def _fake_write_provenance_file(**kwargs):
        calls["provenance"].append(kwargs["level"])
        level_dir = kwargs["output_dir"]
        level_dir.mkdir(parents=True, exist_ok=True)
        p = level_dir / kwargs["filename"]
        p.write_text("{}", encoding="utf-8")
        return p, {"level": kwargs["level"], "solver": kwargs["solver"], "generated_at": "now"}

    monkeypatch.setattr(module, "_write_provenance_file", _fake_write_provenance_file)
    monkeypatch.setattr(
        module,
        "_write_build_session_manifest",
        lambda **_kwargs: calls.__setitem__("session", calls["session"] + 1) or (out / "build_session_manifest.json"),
    )

    args = SimpleNamespace(check=False, level="all", output=out, mock=True, repo=None, code=None)
    assert module._run_cli(parser, args) == 0
    assert calls["provenance"] == ["1", "2"]
    assert calls["session"] == 1

    # No built indices -> no session manifest write
    monkeypatch.setattr(module, "build_level1", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(module, "build_level2", lambda *_args, **_kwargs: 0)
    calls = {"provenance": [], "session": 0}
    monkeypatch.setattr(module, "_write_provenance_file", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not write provenance")))
    monkeypatch.setattr(module, "_write_build_session_manifest", lambda **_kwargs: calls.__setitem__("session", 99))
    assert module._run_cli(parser, args) == 0
    assert calls["session"] == 0
