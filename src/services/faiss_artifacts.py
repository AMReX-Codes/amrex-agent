"""Helpers for downloading published FAISS artifacts."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from datetime import datetime
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
    manifest = json.loads(payload.decode("utf-8"))
    _validate_manifest_metadata(manifest)
    return manifest


def _load_manifest_from_path(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    _validate_manifest_metadata(manifest)
    return manifest


def _is_iso8601_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _parse_major_version(version: str) -> int | None:
    try:
        return int(version.strip().split(".", 1)[0])
    except (TypeError, ValueError):
        return None


def _validate_manifest_metadata(manifest: dict) -> None:
    version = manifest.get("version")
    if version is None:
        logger.warning(
            "FAISS manifest missing version metadata; accepting legacy format."
        )
        return
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("Invalid manifest: missing version")

    timestamp = manifest.get("generated_at") or manifest.get("timestamp")
    if not isinstance(timestamp, str) or not _is_iso8601_timestamp(timestamp):
        raise RuntimeError("Invalid manifest: missing valid generated_at/timestamp")

    major = _parse_major_version(version)
    embedding_model = manifest.get("embedding_model")
    if major is not None and major >= 2:
        if not isinstance(embedding_model, str) or not embedding_model.strip():
            raise RuntimeError("Invalid manifest: missing embedding_model for version >= 2")
    elif embedding_model is None:
        logger.warning(
            "FAISS manifest missing embedding_model metadata; compatibility checks are limited."
        )


def _validate_manifest_embedding_compatibility(
    manifest: dict,
    expected_embedding_model: str | None = None,
) -> None:
    if not expected_embedding_model:
        return

    manifest_embedding_model = manifest.get("embedding_model")
    if not isinstance(manifest_embedding_model, str) or not manifest_embedding_model.strip():
        logger.warning(
            "FAISS manifest has no embedding_model; cannot verify compatibility with configured model %s.",
            expected_embedding_model,
        )
        return

    if manifest_embedding_model != expected_embedding_model:
        version = manifest.get("version")
        major = _parse_major_version(version) if isinstance(version, str) else None
        message = (
            "FAISS manifest embedding_model '%s' does not match configured model '%s'."
            % (manifest_embedding_model, expected_embedding_model)
        )
        if major is not None and major >= 2:
            raise RuntimeError(message)
        logger.warning("%s Accepting legacy manifest.", message)


def ensure_faiss_indices(
    faiss_root: Path,
    base_url: str | None = None,
    manifest_url: str | None = None,
    expected_embedding_model: str | None = None,
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

    _validate_manifest_embedding_compatibility(
        manifest=manifest,
        expected_embedding_model=expected_embedding_model,
    )

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
        logger.debug(f"Downloaded {rel_path}")

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
