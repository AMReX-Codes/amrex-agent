#!/usr/bin/env python3
"""
Config-Driven FAISS Index Builder for AMReX Codes.

Generic index builder that works with any AMReX code (PeleC, PeleLMeX, ERF, WarpX, incflo, etc.)
by using code configuration classes.

Usage:
    # Build PeleC case structure index
    python build_index.py --config pelec --type case_structure --source ~/amrex-repos/PeleC

    # Build PeleLMeX case details index
    python build_index.py --config pelelmex --type case_details --source ~/amrex-repos/PeleLMeX

    # Build with custom embedding provider
    python build_index.py --config pelec --type case_structure --source ~/amrex-repos/PeleC --embedding openai

Index Types:
    - case_structure: High-level case organization (hierarchical level 1)
    - case_details: Detailed parameter documentation (hierarchical level 2)
    - input_templates: Input file patterns and templates
    - chemistry: Chemistry mechanism and fuel mappings

Pattern: Inspired by foam-agent's index building scripts but generalized for any AMReX code.
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

try:
    # Import database config system (relative to project root)
    from database.configs import BaseAMReXConfig, discover_code_configs
    from database.scripts.utils import (
        extract_directory_structure,
        extract_input_file_content,
        extract_readme_content,
        find_case_directories,
        format_case_document,
        tokenize,
    )

    from src.services.config_service import ConfigService
except ModuleNotFoundError:
    # Add paths for imports when running as a standalone script
    PELE_AGENT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PELE_AGENT_ROOT))
    from database.configs import BaseAMReXConfig, discover_code_configs
    from database.scripts.utils import (
        extract_directory_structure,
        extract_input_file_content,
        extract_readme_content,
        find_case_directories,
        format_case_document,
        tokenize,
    )

    from src.services.config_service import ConfigService


# Map config names to classes
def _build_config_map():
    return {cfg.code_name.lower(): cfg for cfg in discover_code_configs()}


CONFIG_MAP = _build_config_map()
CONFIG_MAP.setdefault("amrex", BaseAMReXConfig)

# Initialize logger first
logger = logging.getLogger(__name__)

# Load config for API keys
try:
    AGENT_CONFIG = ConfigService().initialize()
    key = AGENT_CONFIG.cborg_api_key
    logger.debug(f"[DEBUG] Config has cborg_api_key: {bool(key)}, type: {type(key)}")
except Exception as e:
    logger.debug(f"[DEBUG] Config loading FAILED: {e}")
    import traceback
    traceback.print_exc()
    AGENT_CONFIG = None

def get_embedding_model(
    provider: str = "openai",
    model_name: str = "lbl/nomic-embed-text",
) -> Any:
    """
    Get an embeddings client for a provider/model.

    Parameters
    ----------
    provider : str, optional
        Embeddings provider identifier.
    model_name : str, optional
        Model name for the provider.

    Returns
    -------
    Any
        Embeddings client instance.
    """
    from src.services.embedding_factory import create_embeddings

    embeddings = create_embeddings(
        provider=provider,
        model_name=model_name,
        config=AGENT_CONFIG,
    )
    if embeddings is None:
        raise RuntimeError(f"Failed to initialize {provider} embeddings")

    class EmbeddingAdapter:
        def __init__(self, embeddings_obj, config):
            self.embeddings = embeddings_obj
            self.config = config

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self.embeddings.embed_documents(texts)

        def embed_query(self, text: str) -> list[float]:
            if hasattr(self.embeddings, "embed_query"):
                return self.embeddings.embed_query(text)
            raise RuntimeError("Embedding provider does not support embed_query")

        def expand_documents(
            self,
            documents: list[str],
            metadata: list[dict[str, Any]] | None = None,
        ) -> tuple[list[str], list[dict[str, Any]]]:
            chunk_size = 0
            if self.config is not None:
                chunk_size = getattr(self.config, "embedding_chunk_size_chars", 0) or 0
            if chunk_size <= 0 or not documents:
                return documents, metadata or []

            chunked_docs = []
            parent_indices = []
            for idx, text in enumerate(documents):
                if len(text) <= chunk_size:
                    chunked_docs.append(text)
                    parent_indices.append(idx)
                    continue
                start = 0
                text_len = len(text)
                while start < text_len:
                    end = min(start + chunk_size, text_len)
                    chunked_docs.append(text[start:end])
                    parent_indices.append(idx)
                    if end >= text_len:
                        break
                    start = end

            if not parent_indices:
                return documents, metadata or []

            base_meta = metadata or [{} for _ in documents]
            expanded_meta = []
            for chunk_idx, parent_idx in enumerate(parent_indices):
                parent = base_meta[parent_idx] if parent_idx < len(base_meta) else {}
                meta = dict(parent) if isinstance(parent, dict) else {}
                meta["chunk_parent"] = parent_idx
                meta["chunk_index"] = chunk_idx
                expanded_meta.append(meta)
            return chunked_docs, expanded_meta

    return EmbeddingAdapter(embeddings, AGENT_CONFIG)


def _maybe_chunk_documents(documents: list[Document], embedding_model) -> list[Document]:
    if not hasattr(embedding_model, "expand_documents"):
        return documents
    texts = [doc.page_content for doc in documents]
    metas = [doc.metadata for doc in documents]
    chunked_texts, chunked_metas = embedding_model.expand_documents(texts, metas)
    if not chunked_texts:
        return documents
    return [
        Document(page_content=text, metadata=meta)
        for text, meta in zip(chunked_texts, chunked_metas, strict=False)
    ]


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


def _load_dependencies_commit(solver: str, dependencies_path: Path | None = None) -> str | None:
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


def _extract_embedding_metadata(
    embedding_model: Any,
    embedding_provider_arg: str | None,
    embedding_model_arg: str | None,
) -> tuple[str | None, str | None, int | None]:
    config = getattr(embedding_model, "config", None)
    inner_embedding = getattr(embedding_model, "embeddings", embedding_model)

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

    for attr in ("provider", "embedding_provider"):
        value = getattr(inner_embedding, attr, None)
        if isinstance(value, str) and value.strip():
            provider = value
            break

    for attr in ("model", "model_name"):
        value = getattr(inner_embedding, attr, None)
        if isinstance(value, str) and value.strip():
            model_name = value
            break

    for attr in ("embedding_dimension", "dimension", "dimensions"):
        value = getattr(inner_embedding, attr, None)
        if isinstance(value, int):
            dimension = value
            break

    if provider is None and embedding_provider_arg:
        provider = embedding_provider_arg
    if model_name is None and embedding_model_arg:
        model_name = embedding_model_arg

    return provider, model_name, dimension


def _resolve_effective_provider(
    provider_arg: str | None,
    embedding_arg: str | None,
    config_provider: str | None,
) -> str:
    for candidate in (provider_arg, embedding_arg, config_provider):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()
    raise ValueError(
        "Unable to determine embedding provider. Pass --provider or --embedding."
    )


def _resolve_output_dir(
    output_arg: Path | None,
    effective_provider: str,
    code_name: str,
    index_type: str,
) -> Path:
    if output_arg:
        base_dir = output_arg / effective_provider
    else:
        base_dir = Path(__file__).parent.parent / "faiss" / effective_provider
    return base_dir / f"{code_name}_{index_type}"


def write_faiss_provenance_manifest(
    *,
    output_dir: Path,
    embedding_model: Any,
    solver: str | None,
    level: str | None,
    source_dir: Path | None,
    embedding_provider_arg: str | None,
    embedding_model_arg: str | None,
    build_script: str = "build_index.py",
    dependencies_path: Path | None = None,
    manifest_name: str = "faiss_provenance.json",
) -> Path:
    provider, model_name, dimension = _extract_embedding_metadata(
        embedding_model=embedding_model,
        embedding_provider_arg=embedding_provider_arg,
        embedding_model_arg=embedding_model_arg,
    )
    payload = {
        "version": "1",
        "generated_at": _iso_utc_now(),
        "embedding_model": model_name,
        "embedding_provider": provider,
        "embedding_dimension": dimension,
        "solver": solver,
        "level": level,
        "repo_commit": _safe_git_rev_parse_head(source_dir),
        "build_script": build_script,
        "dependencies_commit": _load_dependencies_commit(
            solver=solver or "",
            dependencies_path=dependencies_path,
        )
        if solver
        else None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / manifest_name
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path



def build_case_structure_documents(
        code_config: type[BaseAMReXConfig],
        source_dir: Path,
        max_cases: int = None,
        skip_tokenize: bool = True
) -> list[Document]:
    """
    Build case structure documents (hierarchical level 1).

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    max_cases : int, optional
        Maximum number of cases to include.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    List[Document]
        Generated case structure documents.
    """
    logger.debug(f"\nBuilding case structure documents for {code_config.code_name}")
    logger.debug(f"Source: {source_dir}")

    case_paths, case_dirs = find_case_directories(source_dir)
    logger.debug(f"Found {len(case_paths)} case directories")

    if max_cases:
        case_paths = case_paths[:max_cases]
        case_dirs = case_dirs[:max_cases]
        logger.debug(f"Processing first {max_cases} cases")

    documents = []

    for i, (_case_path, case_dir) in enumerate(zip(case_paths, case_dirs, strict=False)):
        if (i + 1) % 10 == 0:
            logger.debug(f"Processing case {i + 1}/{len(case_paths)}: {case_dir.name}")

        metadata = code_config.extract_metadata(case_dir)
        details = {
            'structure': extract_directory_structure(case_dir, max_depth=2),
        }

        doc_text = format_case_document(metadata, details)
        doc_text_final = doc_text if skip_tokenize else tokenize(doc_text)

        documents.append(Document(page_content=doc_text_final, metadata=metadata))

    logger.debug(f"\nCreated {len(documents)} documents")
    return documents


def build_case_structure_index(
        code_config: type[BaseAMReXConfig],
        source_dir: Path,
        output_dir: Path,
        embedding_model: Any,
        max_cases: int = None,
        skip_tokenize: bool = True
) -> None:
    """
    Build case structure index (hierarchical level 1).

    Focuses on high-level case organization and directory structure.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    output_dir : Path
        Output directory for FAISS index.
    embedding_model : Any
        Embeddings client instance.
    max_cases : int, optional
        Maximum number of cases to process.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    None
        Writes a FAISS index to disk.
    """
    logger.debug(f"\nBuilding case structure index for {code_config.code_name}")
    logger.debug(f"Source: {source_dir}")
    logger.debug(f"Output: {output_dir}")

    documents = build_case_structure_documents(
        code_config,
        source_dir,
        max_cases=max_cases,
        skip_tokenize=skip_tokenize
    )

    documents = _maybe_chunk_documents(documents, embedding_model)
    # Build FAISS index
    logger.debug("Generating embeddings and building FAISS index...")
    vectordb = FAISS.from_documents(documents, embedding_model)

    # Save index
    from database.scripts.index_utils import save_faiss_index
    save_faiss_index(vectordb, output_dir)

    logger.debug(f"[OK] Index saved to {output_dir}")

def build_case_details_documents(
        code_config: type[BaseAMReXConfig],
        source_dir: Path,
        max_cases: int = None,
        skip_tokenize: bool = True
) -> list[Document]:
    """
    Build case details documents (hierarchical level 2).

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    max_cases : int, optional
        Maximum number of cases to include.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    List[Document]
        Generated case details documents.
    """
    logger.debug(f"\nBuilding case details documents for {code_config.code_name}")
    logger.debug(f"Source: {source_dir}")

    case_paths, case_dirs = find_case_directories(source_dir)
    logger.debug(f"Found {len(case_paths)} case directories")

    if max_cases:
        case_paths = case_paths[:max_cases]
        case_dirs = case_dirs[:max_cases]
        logger.debug(f"Processing first {max_cases} cases")

    documents = []

    for i, (_case_path, case_dir) in enumerate(zip(case_paths, case_dirs, strict=False)):
        if (i + 1) % 10 == 0:
            logger.debug(f"Processing case {i + 1}/{len(case_paths)}: {case_dir.name}")

        metadata = code_config.extract_metadata(case_dir)
        readme = extract_readme_content(case_dir)
        inputs = extract_input_file_content(case_dir, max_lines=50)

        details = {}
        if readme:
            details['parameters'] = f"README:\n{readme}"
        if inputs:
            if 'parameters' in details:
                details['parameters'] += f"\n\nInputs file:\n{inputs}"
            else:
                details['parameters'] = f"Inputs file:\n{inputs}"

        if not details:
            continue

        doc_text = format_case_document(metadata, details)
        doc_text_final = doc_text if skip_tokenize else tokenize(doc_text)
        documents.append(Document(page_content=doc_text_final, metadata=metadata))

    logger.debug(f"\nCreated {len(documents)} documents")
    return documents


def build_case_details_index(
        code_config: type[BaseAMReXConfig],
        source_dir: Path,
        output_dir: Path,
        embedding_model: Any,
        max_cases: int = None,
        skip_tokenize: bool = True
) -> None:
    """
    Build case details index (hierarchical level 2).

    Focuses on detailed parameter documentation and README content.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    output_dir : Path
        Output directory for FAISS index.
    embedding_model : Any
        Embeddings client instance.
    max_cases : int, optional
        Maximum number of cases to process.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    None
        Writes a FAISS index to disk.
    """
    logger.debug(f"\nBuilding case details index for {code_config.code_name}")
    logger.debug(f"Source: {source_dir}")
    logger.debug(f"Output: {output_dir}")

    documents = build_case_details_documents(
        code_config,
        source_dir,
        max_cases=max_cases,
        skip_tokenize=skip_tokenize
    )

    documents = _maybe_chunk_documents(documents, embedding_model)
    # Build FAISS index
    logger.debug("Generating embeddings and building FAISS index...")
    vectordb = FAISS.from_documents(documents, embedding_model)

    # Save index
    from database.scripts.index_utils import save_faiss_index
    save_faiss_index(vectordb, output_dir)

    logger.debug(f"[OK] Index saved to {output_dir}")

def build_input_templates_documents(
        code_config: type[BaseAMReXConfig],
        source_dir: Path,
        max_cases: int = None,
        skip_tokenize: bool = True
) -> list[Document]:
    """
    Build input template documents from inputs files.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    max_cases : int, optional
        Maximum number of cases to include.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    List[Document]
        Generated input template documents.
    """
    logger.debug(f"\nBuilding input templates documents for {code_config.code_name}")
    logger.debug(f"Source: {source_dir}")

    case_paths, case_dirs = find_case_directories(source_dir)
    logger.debug(f"Found {len(case_paths)} case directories")

    if max_cases:
        case_paths = case_paths[:max_cases]
        case_dirs = case_dirs[:max_cases]

    documents = []

    for i, (_case_path, case_dir) in enumerate(zip(case_paths, case_dirs, strict=False)):
        if (i + 1) % 10 == 0:
            logger.debug(f"Processing case {i + 1}/{len(case_paths)}: {case_dir.name}")

        metadata = code_config.extract_metadata(case_dir)
        inputs = extract_input_file_content(case_dir, max_lines=200)

        if not inputs:
            continue

        details = {
            'parameters': f"Input file template:\n{inputs}"
        }

        doc_text = format_case_document(metadata, details)
        doc_text_final = doc_text if skip_tokenize else tokenize(doc_text)
        documents.append(Document(page_content=doc_text_final, metadata=metadata))

    logger.debug(f"\nCreated {len(documents)} documents")
    return documents


def build_input_templates_index(
        code_config: type[BaseAMReXConfig],
        source_dir: Path,
        output_dir: Path,
        embedding_model: Any,
        max_cases: int = None,
        skip_tokenize: bool = True
) -> None:
    """
    Build input templates index.

    Focuses on input file patterns and parameter configurations.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    output_dir : Path
        Output directory for FAISS index.
    embedding_model : Any
        Embeddings client instance.
    max_cases : int, optional
        Maximum number of cases to process.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    None
        Writes a FAISS index to disk.
    """
    logger.debug(f"\nBuilding input templates index for {code_config.code_name}")
    logger.debug(f"Source: {source_dir}")
    logger.debug(f"Output: {output_dir}")

    documents = build_input_templates_documents(
        code_config,
        source_dir,
        max_cases=max_cases,
        skip_tokenize=skip_tokenize
    )

    documents = _maybe_chunk_documents(documents, embedding_model)
    # Build FAISS index
    logger.debug("Generating embeddings and building FAISS index...")
    vectordb = FAISS.from_documents(documents, embedding_model)

    # Save index
    from database.scripts.index_utils import save_faiss_index
    save_faiss_index(vectordb, output_dir)

    logger.debug(f"[OK] Index saved to {output_dir}")

def build_case_names_documents(
    code_config: type[BaseAMReXConfig],
    source_dir: Path,
    max_cases: int = None,
    skip_tokenize: bool = True
) -> list[Document]:
    """
    Build lightweight case name/directory documents.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    max_cases : int, optional
        Maximum number of cases to include.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    List[Document]
        Generated case name documents.
    """
    logger.debug("\n=== Building Case Names Documents ===")
    logger.debug(f"Source: {source_dir}")

    code_name = code_config.__name__.replace('Config', '')
    logger.debug(f"Code: {code_name}")

    case_paths, case_dirs = find_case_directories(source_dir)
    logger.debug(f"Found {len(case_paths)} test cases")

    if max_cases:
        case_paths = case_paths[:max_cases]
        case_dirs = case_dirs[:max_cases]

    documents = []

    for i, (case_path, case_dir) in enumerate(zip(case_paths, case_dirs, strict=False)):
        case_name = case_dir.name

        path_parts = Path(case_path).parts
        if len(path_parts) > 1:
            case_type = path_parts[1] if path_parts[0] == 'Exec' else path_parts[0]
        else:
            case_type = "unknown"

        content_parts = [
            "<case_name_index>",
            f"case_name: {case_name}",
            f"directory: {case_path}",
            f"case_type: {case_type}",
        ]

        readme = case_dir / 'README.md'
        if readme.exists():
            try:
                with open(readme, encoding='utf-8') as f:
                    import re
                    headers = re.findall(r'^#{1,2}\s+(.+)$', f.read(), re.MULTILINE)
                    if headers:
                        content_parts.append("headers:")
                        content_parts.extend([f"  - {h.strip()}" for h in headers[:5]])
            except Exception:
                pass

        content_parts.append("</case_name_index>")

        metadata = {
            'case_name': case_name,
            'case': case_path,
            'case_type': case_type,
            'local_path': str(case_dir),
            'code': code_name,
        }

        documents.append(Document(page_content='\n'.join(content_parts), metadata=metadata))

        if (i + 1) % 20 == 0:
            logger.debug(f"  Processed {i + 1}/{len(case_paths)} cases...", end='\r')

    logger.debug(f"\n  Processed {len(documents)}/{len(case_paths)} cases")
    return documents


def build_case_names_index(
    code_config: type[BaseAMReXConfig],
    source_dir: Path,
    output_dir: Path,
    embedding_model: Any,
    max_cases: int = None,
    skip_tokenize: bool = True
) -> None:
    """
    Build lightweight case name/directory index.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    source_dir : Path
        Repository root to scan.
    output_dir : Path
        Output directory for FAISS index.
    embedding_model : Any
        Embeddings client instance.
    max_cases : int, optional
        Maximum number of cases to process.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    None
        Writes a FAISS index to disk.
    """
    logger.debug("\n=== Building Case Names Index ===")
    logger.debug(f"Source: {source_dir}")
    logger.debug(f"Output: {output_dir}")

    documents = build_case_names_documents(
        code_config,
        source_dir,
        max_cases=max_cases,
        skip_tokenize=skip_tokenize
    )

    if not documents:
        logger.debug("ERROR: No documents created!")
        return

    documents = _maybe_chunk_documents(documents, embedding_model)
    logger.debug("Building FAISS index...")
    vectordb = FAISS.from_documents(documents, embedding_model)

    output_dir.mkdir(parents=True, exist_ok=True)
    vectordb.save_local(str(output_dir))

    logger.debug(f"[OK] Saved {len(documents)} case names to {output_dir}")

    index_file = output_dir / 'index.faiss'
    if index_file.exists():
        logger.debug(f"  Index size: {index_file.stat().st_size / 1024:.1f} KB")

    logger.debug("\nSample entries:")
    for doc in documents[:3]:
        logger.debug(f"  - {doc.metadata['case_name']} ({doc.metadata['case']})")

def build_chemistry_documents(
        code_config: type[BaseAMReXConfig],
        skip_tokenize: bool = True
) -> list[Document]:
    """
    Build chemistry/domain knowledge documents.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    List[Document]
        Generated chemistry documents.
    """
    logger.debug(f"\nBuilding chemistry documents for {code_config.code_name}")

    domain_data = code_config.get_domain_data()
    mechanisms = domain_data.get('mechanisms', {})

    if not mechanisms:
        logger.debug("Warning: No chemistry mechanisms found in config. Skipping.")
        return []

    logger.debug(f"Found {len(mechanisms)} chemistry mechanisms")

    documents = []

    for mechanism, fuels in mechanisms.items():
        metadata = {
            'code': code_config.code_name,
            'mechanism': mechanism,
            'fuels': ', '.join(fuels) if fuels else 'unknown',
            'type': 'chemistry'
        }

        fuel_list = ', '.join(fuels) if fuels else 'unknown fuels'
        doc_text = f"""Chemistry mechanism: {mechanism}
Fuels: {fuel_list}
Code: {code_config.code_name}

This mechanism ({mechanism}) is used for {fuel_list} combustion simulations.
"""

        doc_text_final = doc_text if skip_tokenize else tokenize(doc_text)
        documents.append(Document(page_content=doc_text_final, metadata=metadata))

    logger.debug(f"\nCreated {len(documents)} documents")
    return documents


def build_chemistry_index(
        code_config: type[BaseAMReXConfig],
        output_dir: Path,
        embedding_model: Any,
        skip_tokenize: bool = True
) -> None:
    """
    Build chemistry/domain knowledge index.

    Indexes mechanism-to-fuel mappings and domain-specific knowledge.

    Parameters
    ----------
    code_config : Type[BaseAMReXConfig]
        Solver configuration class.
    output_dir : Path
        Output directory for FAISS index.
    embedding_model : Any
        Embeddings client instance.
    skip_tokenize : bool, optional
        Whether to skip tokenization of document text.

    Returns
    -------
    None
        Writes a FAISS index to disk.
    """
    logger.debug(f"\nBuilding chemistry index for {code_config.code_name}")
    logger.debug(f"Output: {output_dir}")

    documents = build_chemistry_documents(code_config, skip_tokenize=skip_tokenize)
    if not documents:
        return

    documents = _maybe_chunk_documents(documents, embedding_model)
    # Build FAISS index
    logger.debug("Generating embeddings and building FAISS index...")
    vectordb = FAISS.from_documents(documents, embedding_model)

    # Save index
    from database.scripts.index_utils import save_faiss_index
    save_faiss_index(vectordb, output_dir)

    logger.debug(f"[OK] Index saved to {output_dir}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build FAISS indices for AMReX codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--config',
        required=True,
        choices=list(CONFIG_MAP.keys()),
        help='Code configuration to use (pelec, pelelmex, amrex)',
    )
    parser.add_argument(
        '--type',
        required=True,
        choices=['case_structure', 'case_details', 'input_templates', 'chemistry', 'case_names'],
        help='Type of index to build',
    )
    parser.add_argument(
        '--source',
        type=Path,
        help='Source directory to scan (required for case_* and input_templates types)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output directory for FAISS index (default: auto-generated from config and type)',
    )
    parser.add_argument(
        '--embedding',
        default='openai',
        choices=['openai', 'huggingface', 'cborg'],
        help='Embedding provider (default: openai)',
    )
    parser.add_argument(
        '--embedding-model',
        default='lbl/nomic-embed-text',
        help='Embedding model name (default: lbl/nomic-embed-text for OpenAI)',
    )
    parser.add_argument(
        '--provider',
        help='Provider namespace for FAISS output layout (e.g., cborg, amsc)',
    )
    parser.add_argument(
        '--max-cases',
        type=int,
        help='Maximum number of cases to process (for testing)',
    )
    parser.add_argument(
        '--tokenize',
        action='store_true',
        help=(
            'Enable foam-agent style tokenization (not recommended for modern semantic '
            'embeddings like nomic-embed-text)'
        ),
    )
    return parser


def _resolve_source_dir(
    args: argparse.Namespace,
    code_config: type[BaseAMReXConfig],
    config: Any,
    agent_root: Path,
) -> Path:
    if args.source:
        logger.info(f" Using source from argument: {args.source}")
        return args.source

    source_dir = config.repositories.get(code_config.code_name)
    if source_dir and source_dir.exists():
        logger.info(f" Using source from config: {source_dir}")
        return source_dir

    logger.debug(f"\n[ERROR] Source directory not found for {args.config}")
    logger.debug(f"  Config path: {source_dir}")
    logger.debug("\nOptions:")
    logger.debug(f"  1. Provide --source /path/to/{args.config}")
    logger.debug(f"  2. Set environment: export {args.config.upper()}_REPO_PATH=/path/to/repo")
    logger.debug(f"  3. Clone repo to: {agent_root.parent / args.config}")
    raise SystemExit(1)


def _validate_case_source(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.type not in ['case_structure', 'case_details', 'input_templates']:
        return
    if not args.source:
        parser.error(f"--source is required for index type '{args.type}'")
    if not args.source.exists():
        parser.error(f"Source directory does not exist: {args.source}")


def _run_index_builder(
    *,
    args: argparse.Namespace,
    code_config: type[BaseAMReXConfig],
    source_dir: Path,
    output_dir: Path,
    embedding_model: Any,
    skip_tokenize: bool,
) -> None:
    builders = {
        'case_structure': lambda: build_case_structure_index(
            code_config,
            source_dir,
            output_dir,
            embedding_model,
            max_cases=args.max_cases,
            skip_tokenize=skip_tokenize,
        ),
        'case_details': lambda: build_case_details_index(
            code_config,
            source_dir,
            output_dir,
            embedding_model,
            max_cases=args.max_cases,
            skip_tokenize=skip_tokenize,
        ),
        'input_templates': lambda: build_input_templates_index(
            code_config,
            source_dir,
            output_dir,
            embedding_model,
            max_cases=args.max_cases,
            skip_tokenize=skip_tokenize,
        ),
        'case_names': lambda: build_case_names_index(
            code_config,
            source_dir,
            output_dir,
            embedding_model,
            max_cases=args.max_cases,
            skip_tokenize=skip_tokenize,
        ),
        'chemistry': lambda: build_chemistry_index(
            code_config,
            output_dir,
            embedding_model,
            skip_tokenize=skip_tokenize,
        ),
    }
    builders[args.type]()


def main() -> None:
    """
    Run the FAISS index builder CLI.

    Returns
    -------
    None
        Parses CLI arguments and writes indices.
    """
    # === STEP 1: Load config and set up environment ===
    agent_root = Path(__file__).parent.parent

    # Load config - this sets up PELE_AGENT_ROOT and environment variables
    from src.config import load_config
    config = load_config()

    logger.debug(f"\n[INFO] Agent root: {agent_root}")
    logger.info(f" Environment: {config.environment}")

    # === STEP 2: Parse arguments ===
    parser = _build_parser()
    args = parser.parse_args()

    # === STEP 3: Determine source directory ===
    code_config = CONFIG_MAP[args.config]
    source_dir = _resolve_source_dir(args, code_config, config, agent_root)

    skip_tokenize = not args.tokenize

    # Get code config
    code_config = CONFIG_MAP[args.config]

    effective_provider = _resolve_effective_provider(
        provider_arg=args.provider,
        embedding_arg=args.embedding,
        config_provider=getattr(config, "embedding_provider", None),
    )
    output_dir = _resolve_output_dir(
        output_arg=args.output,
        effective_provider=effective_provider,
        code_name=code_config.code_name.lower(),
        index_type=args.type,
    )

    # Validate source for case-based indices
    _validate_case_source(args, parser)

    # Get embedding model
    embedding_provider = effective_provider
    embedding_model = get_embedding_model(args.embedding, args.embedding_model)

    _run_index_builder(
        args=args,
        code_config=code_config,
        source_dir=source_dir,
        output_dir=output_dir,
        embedding_model=embedding_model,
        skip_tokenize=skip_tokenize,
    )

    manifest_path = write_faiss_provenance_manifest(
        output_dir=output_dir,
        embedding_model=embedding_model,
        solver=args.config,
        level=args.type,
        source_dir=source_dir,
        embedding_provider_arg=embedding_provider,
        embedding_model_arg=args.embedding_model,
        build_script="build_index.py",
    )
    logger.debug(f"Provenance manifest written to: {manifest_path}")

    logger.debug("\n[OK] Index building complete!")
    logger.debug(f"Index location: {output_dir}")
    logger.debug("\nTo use this index, ensure it's in your FAISS database path:")
    logger.debug(f"  faiss_db_path: {output_dir.parent}")


if __name__ == '__main__':
    main()
