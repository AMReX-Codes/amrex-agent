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
import logging
import sys
from pathlib import Path

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
    PELE_CONFIG = ConfigService().initialize()
    key = PELE_CONFIG.cborg_api_key
    logger.debug(f"[DEBUG] Config has cborg_api_key: {bool(key)}, type: {type(key)}")
except Exception as e:
    logger.debug(f"[DEBUG] Config loading FAILED: {e}")
    import traceback
    traceback.print_exc()
    PELE_CONFIG = None

def get_embedding_model(provider: str = "openai", model_name: str = "text-embedding-3-small"):
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
    from src.services.embedding_service_factory import get_embedding_service

    service = get_embedding_service(PELE_CONFIG)
    if service.embeddings is None:
        raise RuntimeError(f"Failed to initialize {provider} embeddings")

    class EmbeddingAdapter:
        def __init__(self, embedding_service):
            self.service = embedding_service

        def embed_documents(self, texts):
            return self.service.embed_texts(texts)

        def embed_query(self, text):
            if hasattr(self.service.embeddings, "embed_query"):
                return self.service.embeddings.embed_query(text)
            raise RuntimeError("Embedding provider does not support embed_query")

        def expand_documents(self, documents, metadata=None):
            return self.service.expand_documents(documents, metadata)

    return EmbeddingAdapter(service)


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
        embedding_model,
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
        embedding_model,
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
        embedding_model,
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
    embedding_model,
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
        embedding_model,
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


def main():
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
    parser = argparse.ArgumentParser(
        description="Build FAISS indices for AMReX codes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--config',
        required=True,
        choices=list(CONFIG_MAP.keys()),
        help='Code configuration to use (pelec, pelelmex, amrex)'
    )

    parser.add_argument(
        '--type',
        required=True,
        choices=['case_structure', 'case_details', 'input_templates', 'chemistry', 'case_names'],
        help='Type of index to build'
    )

    parser.add_argument(
        '--source',
        type=Path,
        help='Source directory to scan (required for case_* and input_templates types)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        help='Output directory for FAISS index (default: auto-generated from config and type)'
    )

    parser.add_argument(
        '--embedding',
        default='openai',
        choices=['openai', 'huggingface', 'cborg'],
        help='Embedding provider (default: openai)'
    )

    parser.add_argument(
        '--embedding-model',
        default='text-embedding-3-small',
        help='Embedding model name (default: text-embedding-3-small for OpenAI)'
    )

    parser.add_argument(
        '--max-cases',
        type=int,
        help='Maximum number of cases to process (for testing)'
    )

    parser.add_argument(
    '--tokenize',
    action='store_true',
    help='Enable foam-agent style tokenization (not recommended for modern semantic embeddings like nomic-embed-text)'
)

    args = parser.parse_args()

    # === STEP 3: Determine source directory ===
    code_config = CONFIG_MAP[args.config]

    if args.source:
        source_dir = args.source
        logger.info(f" Using source from argument: {source_dir}")
    else:
        source_dir = config.repositories.get(code_config.code_name)

        if not source_dir or not source_dir.exists():
            logger.debug(f"\n[ERROR] Source directory not found for {args.config}")
            logger.debug(f"  Config path: {source_dir}")
            logger.debug("\nOptions:")
            logger.debug(f"  1. Provide --source /path/to/{args.config}")
            logger.debug(f"  2. Set environment: export {args.config.upper()}_REPO_PATH=/path/to/repo")
            logger.debug(f"  3. Clone repo to: {agent_root.parent / args.config}")
            sys.exit(1)

        logger.info(f" Using source from config: {source_dir}")

    skip_tokenize = not args.tokenize

    # Get code config
    code_config = CONFIG_MAP[args.config]

    # Determine output directory
    if args.output:
        output_dir = args.output
    else:
        # Auto-generate: database/faiss/{code}_{type}
        base_dir = Path(__file__).parent.parent / 'faiss'
        output_dir = base_dir / f"{code_config.code_name.lower()}_{args.type}"

    # Validate source for case-based indices
    if args.type in ['case_structure', 'case_details', 'input_templates']:
        if not args.source:
            parser.error(f"--source is required for index type '{args.type}'")
        if not args.source.exists():
            parser.error(f"Source directory does not exist: {args.source}")

    # Get embedding model
    embedding_model = get_embedding_model(args.embedding, args.embedding_model)

    # Build index based on type
    if args.type == 'case_structure':
        build_case_structure_index(
            code_config, source_dir, output_dir, embedding_model, max_cases=args.max_cases,
            skip_tokenize=skip_tokenize
        )

    elif args.type == 'case_details':
        build_case_details_index(
            code_config, source_dir, output_dir, embedding_model, max_cases=args.max_cases,
            skip_tokenize=skip_tokenize
        )

    elif args.type == 'input_templates':
        build_input_templates_index(
            code_config, source_dir, output_dir, embedding_model, max_cases=args.max_cases,
            skip_tokenize=skip_tokenize
        )
    elif args.type == 'case_names':
        build_case_names_index(
            code_config,
            source_dir,
            output_dir,
            embedding_model,
            max_cases=args.max_cases,
            skip_tokenize=skip_tokenize
        )
    elif args.type == 'chemistry':
        build_chemistry_index(code_config, output_dir, embedding_model, skip_tokenize=skip_tokenize)

    logger.debug("\n[OK] Index building complete!")
    logger.debug(f"Index location: {output_dir}")
    logger.debug("\nTo use this index, ensure it's in your FAISS database path:")
    logger.debug(f"  faiss_db_path: {output_dir.parent}")


if __name__ == '__main__':
    main()
