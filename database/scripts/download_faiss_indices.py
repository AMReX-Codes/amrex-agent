#!/usr/bin/env python3
"""Download published FAISS artifacts into local database/faiss."""

import argparse
import logging
import sys
from pathlib import Path

try:
    from src.services.faiss_artifacts import ensure_faiss_indices
except ModuleNotFoundError:
    ROOT_DIR = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(ROOT_DIR))
    from src.services.faiss_artifacts import ensure_faiss_indices

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Download FAISS artifacts from a published manifest.

    Returns
    -------
    None
        Downloads artifacts to the local FAISS directory.
    """
    parser = argparse.ArgumentParser(description="Download FAISS artifacts from a published manifest.")
    parser.add_argument("--faiss-root", type=Path, default=Path("database/faiss"), help="Local FAISS root directory")
    parser.add_argument("--base-url", help="Base URL for published artifacts (expects manifest.json)")
    parser.add_argument("--manifest-url", help="Full manifest URL (overrides base URL)")
    parser.add_argument("--expected-embedding-model", help="Expected embedding model for compatibility checks")
    args = parser.parse_args()

    if not args.base_url and not args.manifest_url:
        raise SystemExit("Provide --base-url or --manifest-url")

    downloaded = ensure_faiss_indices(
        faiss_root=args.faiss_root,
        base_url=args.base_url,
        manifest_url=args.manifest_url,
        expected_embedding_model=args.expected_embedding_model,
    )
    logger.info(f"Downloaded {downloaded} files")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
