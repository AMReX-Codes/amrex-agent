"""Helpers for downloading published FAISS artifacts."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

logger = logging.getLogger(__name__)


def _sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_manifest_from_url(url: str) -> dict:
    with urlopen(url) as response:
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def _load_manifest_from_path(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text())


def ensure_faiss_indices(
    faiss_root: Path,
    base_url: str | None = None,
    manifest_url: str | None = None,
) -> int:
    """
    Download missing/changed FAISS files into faiss_root.

    Call context: Used by embedding setup to ensure local indices are present.

    Parameters
    ----------
    faiss_root : Path
        Root directory to populate with FAISS files.
    base_url : str or None, optional
        Base URL hosting FAISS artifacts.
    manifest_url : str or None, optional
        Explicit URL to a JSON manifest of artifacts.

    Returns
    -------
    int
        Count of downloaded files.
    """
    faiss_root.mkdir(parents=True, exist_ok=True)

    if manifest_url:
        manifest = _load_manifest_from_url(manifest_url)
    elif base_url:
        manifest = _load_manifest_from_url(urljoin(base_url.rstrip("/") + "/", "manifest.json"))
    else:
        raise RuntimeError("No manifest_url or base_url provided for FAISS download")

    files = manifest.get("files", [])
    if not isinstance(files, Iterable):
        raise RuntimeError("Invalid manifest: missing files list")

    downloaded = 0
    for entry in files:
        rel_path = entry.get("path")
        if not rel_path:
            continue
        target_path = faiss_root / rel_path
        expected_hash = entry.get("sha256")

        if target_path.exists() and expected_hash:
            current_hash = _sha256(target_path)
            if current_hash == expected_hash:
                continue

        download_url = entry.get("url")
        if not download_url:
            if not base_url:
                raise RuntimeError(f"Missing url for {rel_path} and no base_url provided")
            download_url = urljoin(base_url.rstrip("/") + "/", rel_path)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(download_url) as response:
            target_path.write_bytes(response.read())
        downloaded += 1
        logger.info(f"Downloaded {rel_path}")

    return downloaded


def faiss_indices_present(faiss_root: Path) -> bool:
    """
    Check whether FAISS index files exist under the root.

    Parameters
    ----------
    faiss_root : Path
        Root directory to scan for FAISS indices.

    Returns
    -------
    bool
        True if any index file is found.
    """
    return any(faiss_root.rglob("index.faiss"))
