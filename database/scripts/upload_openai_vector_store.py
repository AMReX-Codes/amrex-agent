#!/usr/bin/env python3
"""
Upload FAISS source documents to an OpenAI hosted vector store.

This reuses the same document construction logic as build_index.py so
hosted retrieval matches local FAISS content.
"""

import argparse
import logging
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from database.configs import BaseAMReXConfig, discover_code_configs
    from database.scripts.build_index import (
        build_case_details_documents,
        build_case_names_documents,
        build_case_structure_documents,
        build_chemistry_documents,
        build_input_templates_documents,
    )

    from src.services.config_service import ConfigService
    from src.services.embedding_factory import _resolve_api_key
except ModuleNotFoundError:
    PELE_AGENT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PELE_AGENT_ROOT))
    from database.configs import BaseAMReXConfig, discover_code_configs
    from database.scripts.build_index import (
        build_case_details_documents,
        build_case_names_documents,
        build_case_structure_documents,
        build_chemistry_documents,
        build_input_templates_documents,
    )

    from src.services.config_service import ConfigService
    from src.services.embedding_factory import _resolve_api_key

DOCUMENT_BUILDERS = {
    "case_structure": build_case_structure_documents,
    "case_details": build_case_details_documents,
    "input_templates": build_input_templates_documents,
    "case_names": build_case_names_documents,
    "chemistry": build_chemistry_documents,
}


def _resolve_config_map():
    config_map = {cfg.code_name.lower(): cfg for cfg in discover_code_configs()}
    config_map.setdefault("amrex", BaseAMReXConfig)
    return config_map


def _resolve_store_id(args, config) -> str:
    store_id = args.vector_store_id or getattr(config, "openai_vector_store_id", None) or os.getenv("OPENAI_VECTOR_STORE_ID")
    if not store_id:
        raise RuntimeError("OpenAI vector store ID not configured")
    return store_id


def _write_documents_file(output_dir: Path, index_name: str, code_name: str, doc_type: str, documents: list) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{index_name}.txt"

    header = [
        f"# index_name: {index_name}",
        f"# code: {code_name}",
        f"# type: {doc_type}",
        "",
    ]

    parts = header + [doc.page_content for doc in documents]
    file_path.write_text("\n\n---\n\n".join(parts))
    return file_path


def _append_store_record(root_dir: Path, name: str, store_id: str) -> None:
    stores_path = root_dir / "demo" / "vector_store" / "STORES.md"
    stores_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"- Name: {name}\n- ID: {store_id}\n"
    if stores_path.exists():
        content = stores_path.read_text()
    else:
        content = "# Hosted Vector Store IDs\n\nRecord the vector store IDs created for demos/releases.\n\n## Auto-added\n"
    content += f"\n{line}"
    stores_path.write_text(content)


def _upload_file(client, store_id: str, file_path: Path) -> str:
    with open(file_path, "rb") as handle:
        uploaded = client.files.create(file=handle, purpose="assistants")
    client.vector_stores.files.create(vector_store_id=store_id, file_id=uploaded.id)
    return uploaded.id


def _get_openai_client(config):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc

    api_key = _resolve_api_key("openai", config)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    base_url = getattr(config, "openai_base_url", None) or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def _resolve_source_dir(config, code_config, explicit_source: Path | None):
    if explicit_source:
        return explicit_source
    source_dir = config.repositories.get(code_config.code_name)
    if not source_dir or not source_dir.exists():
        raise RuntimeError(f"Source directory not found for {code_config.code_name}")
    return source_dir


def _iter_configs(config_name: str) -> Iterable:
    config_map = _resolve_config_map()
    if config_name == "all":
        return list(config_map.values())
    return [config_map[config_name]]


def main() -> None:
    """
    Upload FAISS source documents to an OpenAI vector store.

    Returns
    -------
    None
        Uploads documents to the configured vector store.
    """
    parser = argparse.ArgumentParser(description="Upload FAISS source documents to OpenAI vector store.")
    parser.add_argument(
        "--config",
        default="all",
        choices=sorted(_resolve_config_map().keys()) + ["all"],
        help="Code configuration to upload (default: all)",
    )
    parser.add_argument(
        "--type",
        default="all",
        choices=sorted(DOCUMENT_BUILDERS.keys()) + ["all"],
        help="Document type to upload (default: all)",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Source directory to scan (required for case_* and input_templates when config is not configured)",
    )
    parser.add_argument(
        "--vector-store-id",
        help="OpenAI vector store ID (defaults to OPENAI_VECTOR_STORE_ID or config)",
    )
    parser.add_argument(
        "--create-store",
        action="store_true",
        help="Create a new vector store before uploading",
    )
    parser.add_argument(
        "--create-per-code",
        action="store_true",
        help="Create and upload one vector store per code",
    )
    parser.add_argument(
        "--store-name",
        default="amrex-agent-docs",
        help="Vector store name (used with --create-store)",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="Embedding model for the new vector store (used with --create-store)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to write intermediate files (defaults to a temp dir)",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        help="Maximum number of cases to process (for testing)",
    )
    parser.add_argument(
        "--tokenize",
        action="store_true",
        help="Enable foam-agent style tokenization",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate files only; do not upload",
    )

    args = parser.parse_args()

    config = ConfigService().initialize()
    client = None if args.dry_run else _get_openai_client(config)

    if args.create_store and args.create_per_code:
        raise SystemExit("--create-store cannot be combined with --create-per-code")

    store_id = None
    if args.create_store:
        if args.dry_run:
            raise SystemExit("--create-store requires live API access (remove --dry-run)")
        try:
            created = client.vector_stores.create(
                name=args.store_name,
                embedding_model=args.embedding_model,
            )
        except TypeError:
            created = client.vector_stores.create(name=args.store_name)
            logger.info("[WARN] Vector store created without embedding_model (SDK mismatch).")
        store_id = created.id
        logger.info(f"[OK] Created vector store: {store_id}")
        _append_store_record(PELE_AGENT_ROOT, args.store_name, store_id)
    elif not args.create_per_code:
        store_id = _resolve_store_id(args, config)

    if args.config == "all" and args.source:
        raise SystemExit("--source cannot be used with --config all")

    output_dir = args.output_dir or Path(tempfile.mkdtemp(prefix="openai-vector-store-"))

    types = DOCUMENT_BUILDERS.keys() if args.type == "all" else [args.type]

    for code_config in _iter_configs(args.config):
        source_dir = _resolve_source_dir(config, code_config, args.source)
        code_name = code_config.code_name

        active_store_id = store_id
        if args.create_per_code:
            if args.dry_run:
                raise SystemExit("--create-per-code requires live API access (remove --dry-run)")
            per_code_name = f"{args.store_name}-{code_name.lower()}"
            try:
                created = client.vector_stores.create(
                    name=per_code_name,
                    embedding_model=args.embedding_model,
                )
            except TypeError:
                created = client.vector_stores.create(name=per_code_name)
                logger.info("[WARN] Vector store created without embedding_model (SDK mismatch).")
            active_store_id = created.id
            logger.info(f"[OK] Created vector store for {code_name}: {active_store_id}")
            _append_store_record(PELE_AGENT_ROOT, per_code_name, active_store_id)

        for doc_type in types:
            builder = DOCUMENT_BUILDERS[doc_type]
            if doc_type == "chemistry":
                documents = builder(code_config, skip_tokenize=not args.tokenize)
            else:
                documents = builder(
                    code_config,
                    source_dir,
                    max_cases=args.max_cases,
                    skip_tokenize=not args.tokenize,
                )

            if not documents:
                logger.info(f"[SKIP] No documents for {code_name} {doc_type}")
                continue

            index_name = f"{code_name.lower()}_{doc_type}"
            file_path = _write_documents_file(output_dir, index_name, code_name, doc_type, documents)
            logger.info(f"[OK] Wrote {len(documents)} docs to {file_path}")

            if args.dry_run:
                continue

            file_id = _upload_file(client, active_store_id, file_path)
            logger.info(f"[OK] Uploaded {file_path.name} -> file {file_id}")

    logger.info("[DONE] Upload complete")
    if args.dry_run:
        logger.info(f"[DRY-RUN] Files at: {output_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
