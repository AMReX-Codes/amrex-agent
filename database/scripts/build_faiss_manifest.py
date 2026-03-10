#!/usr/bin/env python3
"""
Build a manifest for published FAISS artifacts.

Generates manifest.json with file paths + hashes for download clients.
"""

import argparse
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _collect_files(root: Path, exclude_path: Path | None = None) -> list[dict]:
    files = []
    exclude_resolved = exclude_path.resolve() if exclude_path else None
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if exclude_resolved and path.resolve() == exclude_resolved:
            continue
        rel_path = path.relative_to(root).as_posix()
        files.append(
            {
                "path": rel_path,
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return files


def _parse_major_version(version: str) -> int | None:
    try:
        return int(version.strip().split(".", 1)[0])
    except (TypeError, ValueError):
        return None


def main() -> None:
    """
    Build and write a FAISS manifest JSON file.

    Returns
    -------
    None
        Writes the manifest to disk.
    """
    parser = argparse.ArgumentParser(description="Build manifest for FAISS artifacts.")
    parser.add_argument("--faiss-root", type=Path, default=Path("database/faiss"), help="FAISS root directory")
    parser.add_argument("--output", type=Path, default=Path("database/faiss/manifest.json"), help="Manifest output path")
    parser.add_argument("--base-url", help="Optional base URL to include per-file download URLs")
    parser.add_argument("--version", default="2.0", help="Manifest schema version (default: 2.0)")
    parser.add_argument("--embedding-provider", help="Embedding provider used to build indices")
    parser.add_argument("--embedding-model", help="Embedding model used to build indices")
    parser.add_argument("--embedding-dimension", type=int, help="Embedding vector dimension")
    args = parser.parse_args()

    faiss_root = args.faiss_root
    if not faiss_root.exists():
        raise SystemExit(f"FAISS root not found: {faiss_root}")

    files = _collect_files(faiss_root, exclude_path=args.output)
    if args.base_url:
        base = args.base_url.rstrip("/") + "/"
        for entry in files:
            entry["url"] = base + entry["path"]

    version_major = _parse_major_version(args.version)
    if version_major is None:
        raise SystemExit(f"Invalid --version value: {args.version}")
    if version_major >= 2 and not args.embedding_model:
        raise SystemExit("--embedding-model is required for manifest version >= 2")

    manifest = {
        "version": args.version,
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(faiss_root),
        "files": files,
    }
    if args.embedding_provider:
        manifest["embedding_provider"] = args.embedding_provider
    if args.embedding_model:
        manifest["embedding_model"] = args.embedding_model
    if args.embedding_dimension is not None:
        manifest["embedding_dimension"] = args.embedding_dimension

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2))
    logger.info(f"Wrote manifest with {len(files)} files to {args.output}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
