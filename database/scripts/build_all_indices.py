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
import sys
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


def main() -> None:
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

    args = parser.parse_args()

    requires_repo = args.level in ['1', '2', 'all']
    repo_root = None
    config_class = None
    solver_name = "N/A"
    if requires_repo:
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
        solver_name = config_class.code_name

    # Create embedder
    embedder = create_embedder(use_real=not args.mock)

    # Create output directories
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

    # Build requested levels
    total_indices = 0

    if args.level in ['0', 'all']:
        total_indices += build_level0(args.output / 'level0', embedder)

    if args.level in ['1', 'all']:
        total_indices += build_level1(repo_root, args.output / 'level1', embedder, config_class)

    if args.level in ['2', 'all']:
        total_indices += build_level2(repo_root, args.output / 'level2', embedder, config_class)

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


if __name__ == '__main__':
    main()
