#!/usr/bin/env python3
"""
Build All FAISS Indices.

Production CLI tool for building the complete 3-level hierarchical index.
Orchestrates Level0Builder, Level1Builder, and Level2Builder.

Usage:
    # Quick test (mock embedder, no API calls)
    python database/scripts/build_all_indices.py --mock --output ./test_indices

    # Production build
    export OPENAI_API_KEY=sk-...
    python database/scripts/build_all_indices.py --repo ~/codes/PeleC --output ./prod_indices

    # Overnight batch job
    nohup python database/scripts/build_all_indices.py --output ./indices > build.log 2>&1 &

Design:
    Based on validated test patterns from Components 5a, 5b, 5c.
    Uses same mock patterns for fast testing without API calls.

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""
import argparse
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.configs import BaseAMReXConfig, discover_code_configs
from database.indexing.level0_builder import Level0Builder
from database.indexing.level1_builder import Level1Builder
from database.indexing.level2_builder import Level2Builder

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _iso_utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_git_rev_parse_head(source_dir: Path | None) -> str | None:
    if source_dir is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _load_dependencies_commit(solver: str | None, dependencies_path: Path | None = None) -> str | None:
    if not solver:
        return None
    dep_path = dependencies_path or (_project_root() / ".dependencies.json")
    try:
        payload = json.loads(dep_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    repos = payload.get("repos")
    if not isinstance(repos, dict):
        return None
    entry = repos.get(solver) or repos.get(solver.lower())
    if not isinstance(entry, dict):
        return None
    commit = entry.get("commit")
    return commit if isinstance(commit, str) and commit.strip() else None


def _extract_embedding_metadata(embedder: Any) -> tuple[str | None, str | None, int | None]:
    config = None
    if hasattr(embedder, "service"):
        config = getattr(embedder.service, "config", None)

    provider: str | None = None
    model_name: str | None = None
    dimension: int | None = None
    if config is not None:
        provider = getattr(config, "embedding_provider", None) or provider
        model_name = getattr(config, "faiss_embedding_model", None) or model_name
        raw_dim = (
            getattr(config, "embedding_dimension", None)
            or getattr(config, "faiss_embedding_dimension", None)
        )
        if isinstance(raw_dim, int):
            dimension = raw_dim

    return provider, model_name, dimension


def _write_provenance_file(
    *,
    output_dir: Path,
    filename: str,
    embedder: Any,
    solver: str | None,
    level: str,
    source_dir: Path | None,
) -> tuple[Path, dict[str, Any]]:
    provider, model_name, dimension = _extract_embedding_metadata(embedder)
    payload = {
        "version": "1",
        "generated_at": _iso_utc_now(),
        "embedding_model": model_name,
        "embedding_provider": provider,
        "embedding_dimension": dimension,
        "solver": solver,
        "level": level,
        "repo_commit": _safe_git_rev_parse_head(source_dir),
        "build_script": "build_all_indices.py",
        "dependencies_commit": _load_dependencies_commit(solver),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / filename
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path, payload


def _session_key(level: str | None, solver: str | None) -> str:
    return f"{level or ''}::{solver or '__global__'}"


def _load_session_entries(session_manifest_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(session_manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict):
            normalized.append(entry)
    return normalized


def _write_build_session_manifest(
    *,
    root_output_dir: Path,
    new_entries: list[dict[str, Any]],
) -> Path:
    manifest_path = root_output_dir / "build_session_manifest.json"
    existing_entries = _load_session_entries(manifest_path)

    merged: dict[str, dict[str, Any]] = {}
    for entry in existing_entries:
        key = _session_key(entry.get("level"), entry.get("solver"))
        merged[key] = entry
    for entry in new_entries:
        key = _session_key(entry.get("level"), entry.get("solver"))
        merged[key] = entry

    final_entries = sorted(
        merged.values(),
        key=lambda item: (
            str(item.get("level") or ""),
            str(item.get("solver") or ""),
            str(item.get("manifest_path") or ""),
        ),
    )

    payload = {
        "version": "1",
        "generated_at": _iso_utc_now(),
        "build_script": "build_all_indices.py",
        "entries": final_entries,
    }
    root_output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path

def _load_runtime_config():
    from src.services.config_service import ConfigService

    return ConfigService().initialize()


def _load_manifest_entries(faiss_root: Path) -> list[dict[str, Any]]:
    manifest_path = faiss_root / "build_session_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]

    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("Manifest is invalid: expected top-level list or entries list")
    return [entry for entry in entries if isinstance(entry, dict)]


def _resolve_repo_head_for_solver(solver: str, config: Any) -> str:
    repo_path = getattr(config, "repositories", {}).get(solver)
    if repo_path is None:
        return "MISSING"
    if not repo_path.exists():
        return "MISSING"

    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "MISSING"
    sha = result.stdout.strip()
    return sha if sha else "MISSING"


def _format_check_row(entry: dict[str, Any], flags: list[str]) -> str:
    return (
        f"solver={entry.get('solver', '-')}; "
        f"level={entry.get('level', '-')}; "
        f"generated_at={entry.get('generated_at', '-')}; "
        f"repo_commit={entry.get('repo_commit', '-')}; "
        f"dependencies_commit={entry.get('dependencies_commit', '-')}; "
        f"embedding_model={entry.get('embedding_model', '-')}; "
        f"embedding_provider={entry.get('embedding_provider', '-')}; "
        f"flags={','.join(flags) if flags else 'OK'}"
    )


def _evaluate_manifest_entry(
    entry: dict[str, Any],
    *,
    active_provider: str,
    active_model: str,
    config: Any,
) -> tuple[str, list[str]]:
    solver = str(entry.get("solver", "")).strip()
    provider = str(entry.get("embedding_provider", "")).strip().lower()
    model = str(entry.get("embedding_model", "")).strip()
    repo_commit = str(entry.get("repo_commit", "")).strip()

    if provider != active_provider or model != active_model:
        return solver, ["MODEL MISMATCH"]

    current_head = _resolve_repo_head_for_solver(solver, config)
    if repo_commit != current_head:
        return solver, ["STALE"]
    return solver, []


def _append_missing_solver_rows(
    *,
    lines: list[str],
    registry: list[str],
    matched_solvers: set[str],
    active_provider: str,
    active_model: str,
) -> bool:
    found_missing = False
    for solver in registry:
        if solver in matched_solvers:
            continue
        found_missing = True
        lines.append(
            _format_check_row(
                {
                    "solver": solver,
                    "level": "-",
                    "generated_at": "-",
                    "repo_commit": "-",
                    "dependencies_commit": "-",
                    "embedding_model": active_model,
                    "embedding_provider": active_provider,
                },
                ["MISSING"],
            )
        )
    return found_missing


def run_manifest_provenance_check(
    faiss_root: Path,
    config: Any | None = None,
) -> tuple[int, list[str]]:
    config = config or _load_runtime_config()
    active_provider = str(getattr(config, "embedding_provider", "")).strip().lower()
    active_model = str(getattr(config, "faiss_embedding_model", "")).strip()
    manifest_entries = _load_manifest_entries(faiss_root)
    registry = [cfg.code_name for cfg in discover_code_configs()]

    has_failures = False
    matched_solvers: set[str] = set()
    lines: list[str] = [
        "Manifest provenance check:",
        f"  faiss_root={faiss_root}",
        f"  active_embedding_provider={active_provider}",
        f"  active_embedding_model={active_model}",
    ]

    for entry in manifest_entries:
        solver, flags = _evaluate_manifest_entry(
            entry,
            active_provider=active_provider,
            active_model=active_model,
            config=config,
        )
        if not flags:
            matched_solvers.add(solver)
        has_failures = has_failures or bool(flags)
        lines.append(_format_check_row(entry, flags))

    has_failures = _append_missing_solver_rows(
        lines=lines,
        registry=registry,
        matched_solvers=matched_solvers,
        active_provider=active_provider,
        active_model=active_model,
    ) or has_failures

    lines.append("Result: FAIL" if has_failures else "Result: PASS")
    return (1 if has_failures else 0), lines

def _resolve_config_class(repo_path: Path | None = None, code_name: str | None = None):
    configs = list(discover_code_configs())

    if code_name:
        target = code_name.lower()
        for cfg in configs:
            if cfg.code_name.lower() == target or getattr(cfg, "github_repo", "").lower() == target:
                return cfg

    if repo_path:
        repo_name = repo_path.name.lower()
        for cfg in configs:
            if cfg.code_name.lower() == repo_name or getattr(cfg, "github_repo", "").lower() == repo_name:
                return cfg

    return None


def _resolve_repo_root(args_repo: Path | None, code_name: str | None):
    if args_repo:
        return args_repo

    from src.services.config_service import ConfigService
    config = ConfigService().initialize()

    if code_name:
        config_cls = _resolve_config_class(code_name=code_name)
        if config_cls:
            return config.repositories.get(config_cls.code_name)
        return None

    for repo_path in config.repositories.values():
        if repo_path and repo_path.exists():
            return repo_path

    return None


def create_embedder(use_real: bool = True) -> Any:
    """
    Create a real or mock embedder for indexing.

    Parameters
    ----------
    use_real : bool, optional
        Whether to use the configured embeddings service.

    Returns
    -------
    object
        Embedder with an ``embed_texts`` method.
    """
    if not use_real:
        mock = Mock()
        mock.embed_texts.return_value = [[0.1] * 384] * 100
        logger.debug("[LIST] Using mock embedder (test mode, no API calls)")
        return mock

    try:
        from src.services.config_service import ConfigService
        from src.services.embedding_service_factory import get_embedding_service

        config = ConfigService().initialize()
        embedder = get_embedding_service(config)

        class EmbedderAdapter:
            def __init__(self, service):
                self.service = service

            def embed_texts(self, texts: list[str]) -> list[list[float]]:
                """
                Embed a list of texts using the configured service.

                Parameters
                ----------
                texts : list
                    Texts to embed.

                Returns
                -------
                list
                    Embedding vectors.
                """
                return self.service.embed_texts(texts)

            def expand_documents(
                self,
                documents: list[str],
                metadata: list[dict[str, Any]] | None = None,
            ) -> tuple[list[str], list[dict[str, Any]]]:
                return self.service.expand_documents(documents, metadata)

        if embedder.embeddings is None:
            raise RuntimeError("Embedding service loaded without embeddings")

        logger.info(f"[PASS] Using real embedder: {config.embedding_provider}/{config.faiss_embedding_model}")
        return EmbedderAdapter(embedder)

    except Exception as e:
        logger.warning(f"[WARN]  Could not initialize real embedder: {e}")
        logger.debug("   Falling back to mock (no API calls)")
        import traceback
        traceback.print_exc()
        return create_embedder(use_real=False)

def build_level0(output_dir: Path, embedder: Any) -> int:
    """
    Build Level 0 indices (solver routing).

    Parameters
    ----------
    output_dir : Path
        Output directory for indices.
    embedder : object
        Embedder with an ``embed_texts`` method.

    Returns
    -------
    int
        Number of indices built.
    """
    logger.debug("\n" + "=" * 70)
    logger.debug("LEVEL 0: Multi-Solver Router")
    logger.debug("=" * 70)

    builder = Level0Builder(embedder=embedder)
    builder.build(output_dir=output_dir)

    # Verify
    indices = list(output_dir.glob("*.faiss"))
    logger.debug(f"\n[PASS] Built {len(indices)} Level 0 indices:")
    for idx in sorted(indices):
        size_mb = idx.stat().st_size / 1024 / 1024
        logger.debug(f"   • {idx.name:40s} ({size_mb:.2f} MB)")

    return len(indices)


def build_level1(
    repo_root: Path,
    output_dir: Path,
    embedder: Any,
    config_class: type[BaseAMReXConfig] | None = None,
) -> int:
    """
    Build Level 1 indices (documentation).

    Parameters
    ----------
    repo_root : Path
        Solver repository root.
    output_dir : Path
        Output directory for indices.
    embedder : object
        Embedder with an ``embed_texts`` method.
    config_class : object, optional
        Solver configuration class.

    Returns
    -------
    int
        Number of indices built.
    """
    if config_class is None:
        config_class = _resolve_config_class(repo_path=repo_root)

    if not config_class:
        config_class = type(
            "GenericAMReXConfig",
            (BaseAMReXConfig,),
            {"code_name": repo_root.name},
        )

    solver_name = config_class.code_name

    logger.debug("\n" + "=" * 70)
    logger.debug(f"LEVEL 1: {solver_name} Documentation")
    logger.debug("=" * 70)

    if not repo_root or not repo_root.exists():
        logger.error(f"[ERROR] Repository not found: {repo_root}")
        logger.debug("   Set --repo /path/to/{solver_name} or provide a code-specific repo path")
        return 0

    builder = Level1Builder(config=config_class, embedder=embedder)
    builder.build(source_dir=repo_root, output_dir=output_dir)

    # Verify
    indices = list(output_dir.glob("*.faiss"))
    logger.debug(f"\n[PASS] Built {len(indices)} Level 1 indices:")
    for idx in sorted(indices):
        size_mb = idx.stat().st_size / 1024 / 1024
        logger.debug(f"   • {idx.name:40s} ({size_mb:.2f} MB)")

    return len(indices)


def build_level2(
    repo_root: Path,
    output_dir: Path,
    embedder: Any,
    config_class: type[BaseAMReXConfig] | None = None,
) -> int:
    """
    Build Level 2 indices (case metadata).

    Parameters
    ----------
    repo_root : Path
        Solver repository root.
    output_dir : Path
        Output directory for indices.
    embedder : object
        Embedder with an ``embed_texts`` method.
    config_class : object, optional
        Solver configuration class.

    Returns
    -------
    int
        Number of indices built.
    """
    if config_class is None:
        config_class = _resolve_config_class(repo_path=repo_root)

    if not config_class:
        config_class = type(
            "GenericAMReXConfig",
            (BaseAMReXConfig,),
            {"code_name": repo_root.name},
        )

    solver_name = config_class.code_name

    logger.debug("\n" + "=" * 70)
    logger.debug(f"LEVEL 2: {solver_name} Case Metadata")
    logger.debug("=" * 70)

    if not repo_root or not repo_root.exists():
        logger.error(f"[ERROR] Repository not found: {repo_root}")
        return 0

    builder = Level2Builder(config=config_class, embedder=embedder)
    builder.build(repo_root=repo_root, output_dir=output_dir)

    # Verify
    indices = list(output_dir.glob("*.faiss"))
    logger.debug(f"\n[PASS] Built {len(indices)} Level 2 indices:")
    for idx in sorted(indices):
        size_mb = idx.stat().st_size / 1024 / 1024
        logger.debug(f"   • {idx.name:40s} ({size_mb:.2f} MB)")

    # Check metadata
    metadata_files = list(output_dir.glob("*_metadata.json"))
    if metadata_files:
        with open(metadata_files[0]) as f:
            sample = json.load(f)
        logger.debug(f"\n[STATS] Metadata: {len(metadata_files)} files, {len(sample)} entries in sample")

    return len(indices)


def main() -> int:
    """
    Run the multi-level index build CLI.

    Returns
    -------
    None
        Executes the CLI workflow.
    """
    parser = argparse.ArgumentParser(
        description="Build FAISS indices for hierarchical RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with mock embedder
  python database/scripts/build_all_indices.py --mock --output ./test

  # Production build
  export OPENAI_API_KEY=sk-...
  python database/scripts/build_all_indices.py --repo ~/codes/PeleC --output ./indices

  # Overnight batch
  nohup python database/scripts/build_all_indices.py --output ./prod > build.log 2>&1 &
        """
    )
    parser.add_argument(
        '--level',
        choices=['0', '1', '2', 'all'],
        default='all',
        help='Which level to build (default: all)'
    )
    parser.add_argument(
        '--code',
        help='Solver code name (e.g., pelec, pelelmex, erf) to resolve repo/config'
    )
    parser.add_argument(
        '--repo',
        type=Path,
        help='Path to solver repository root (overrides --code)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('./faiss_indices'),
        help='Output directory (default: ./faiss_indices)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock embedder (fast, no API calls)'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check build_session_manifest.json provenance only (no index build)',
    )

    args = parser.parse_args()
    return _run_cli(parser, args)


def _run_check_mode(output: Path) -> int:
    try:
        exit_code, lines = run_manifest_provenance_check(faiss_root=output)
    except Exception as exc:
        print(f"Manifest provenance check failed: {exc}")
        return 1
    for line in lines:
        print(line)
    return exit_code


def _resolve_build_context(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[Any, Any, str]:
    requires_repo = args.level in ['1', '2', 'all']
    if not requires_repo:
        return None, None, "N/A"

    repo_root = _resolve_repo_root(args.repo, args.code)
    if not repo_root:
        parser.error("Could not resolve repository. Provide --repo or --code with a configured repo path.")

    config_class = _resolve_config_class(repo_path=repo_root, code_name=args.code)
    if not config_class:
        config_class = type(
            "GenericAMReXConfig",
            (BaseAMReXConfig,),
            {"code_name": repo_root.name},
        )
    return repo_root, config_class, config_class.code_name


def _run_build_levels(
    *,
    args: argparse.Namespace,
    repo_root: Path | None,
    config_class: type[BaseAMReXConfig] | None,
    embedder: Any,
) -> int:
    total_indices = 0
    if args.level in ['0', 'all']:
        total_indices += build_level0(args.output / 'level0', embedder)
    if args.level in ['1', 'all']:
        total_indices += build_level1(repo_root, args.output / 'level1', embedder, config_class)
    if args.level in ['2', 'all']:
        total_indices += build_level2(repo_root, args.output / 'level2', embedder, config_class)
    return total_indices


def _selected_build_tasks(
    *,
    level: str,
    output_root: Path,
    repo_root: Path | None,
    config_class: type[BaseAMReXConfig] | None,
    solver_name: str,
) -> list[dict[str, Any]]:
    solver_slug = str(solver_name).lower()
    tasks: list[dict[str, Any]] = [
        {
            "level": "0",
            "enabled": level in ["0", "all"],
            "output_dir": output_root / "level0",
            "builder": lambda embedder: build_level0(output_root / "level0", embedder),
            "filename": "faiss_provenance.json",
            "solver": None,
            "source_dir": None,
        },
        {
            "level": "1",
            "enabled": level in ["1", "all"],
            "output_dir": output_root / "level1",
            "builder": lambda embedder: build_level1(repo_root, output_root / "level1", embedder, config_class),
            "filename": f"{solver_slug}_faiss_provenance.json",
            "solver": solver_slug,
            "source_dir": repo_root,
        },
        {
            "level": "2",
            "enabled": level in ["2", "all"],
            "output_dir": output_root / "level2",
            "builder": lambda embedder: build_level2(repo_root, output_root / "level2", embedder, config_class),
            "filename": f"{solver_slug}_faiss_provenance.json",
            "solver": solver_slug,
            "source_dir": repo_root,
        },
    ]
    return tasks


def _build_and_collect_provenance(
    *,
    tasks: list[dict[str, Any]],
    embedder: Any,
    output_root: Path,
) -> tuple[int, list[dict[str, Any]]]:
    total_indices = 0
    session_entries: list[dict[str, Any]] = []

    for task in tasks:
        if not task["enabled"]:
            continue

        built = task["builder"](embedder)
        total_indices += built
        if built <= 0:
            continue

        manifest_path, payload = _write_provenance_file(
            output_dir=task["output_dir"],
            filename=task["filename"],
            embedder=embedder,
            solver=task["solver"],
            level=task["level"],
            source_dir=task["source_dir"],
        )
        logger.debug(f"Provenance manifest written to: {manifest_path}")
        session_entries.append(
            {
                "manifest_path": manifest_path.relative_to(output_root).as_posix(),
                **payload,
            }
        )

    return total_indices, session_entries


def _run_cli(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.check:
        return _run_check_mode(args.output)

    repo_root, config_class, solver_name = _resolve_build_context(parser, args)
    embedder = create_embedder(use_real=not args.mock)
    args.output.mkdir(parents=True, exist_ok=True)

    logger.debug(f"""
╔══════════════════════════════════════════════════════════════════════╗
║              FAISS Index Builder - Hierarchical RAG System           ║
╚══════════════════════════════════════════════════════════════════════╝

Configuration:
  Solver:     {solver_name}
  Repository: {repo_root if repo_root else 'N/A'}
  Output:     {args.output.absolute()}
  Level:      {args.level}
  Embedder:   {'Mock (test mode)' if args.mock else 'Real (OpenAI API)'}
""")
    tasks = _selected_build_tasks(
        level=args.level,
        output_root=args.output,
        repo_root=repo_root,
        config_class=config_class,
        solver_name=solver_name,
    )
    total_indices, session_entries = _build_and_collect_provenance(
        tasks=tasks,
        embedder=embedder,
        output_root=args.output,
    )

    if session_entries:
        session_manifest = _write_build_session_manifest(
            root_output_dir=args.output,
            new_entries=session_entries,
        )
        logger.debug(f"Build session manifest written to: {session_manifest}")

    logger.debug(f"""
╔══════════════════════════════════════════════════════════════════════╗
║                         BUILD COMPLETE                               ║
╚══════════════════════════════════════════════════════════════════════╝

Total Indices: {total_indices}
Output: {args.output.absolute()}

Next Steps:
  1. Verify: ls -lh {args.output}/*/*.faiss
  2. Test search (Architect Service: Solver Selection)
  3. Use in production
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
