import json
from pathlib import Path

from src.services import faiss_artifacts


class DummyResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ensure_faiss_indices_returns_existing_paths(monkeypatch, tmp_path):
    target_path = tmp_path / "index.faiss"
    target_path.write_bytes(b"seed")
    expected_hash = faiss_artifacts._sha256(target_path)

    manifest = {
        "files": [
            {"path": "index.faiss", "sha256": expected_hash},
        ]
    }

    def fake_urlopen(url):
        if url.endswith("manifest.json"):
            return DummyResponse(json.dumps(manifest).encode("utf-8"))
        raise AssertionError(f"Unexpected download attempt: {url}")

    monkeypatch.setattr(faiss_artifacts, "urlopen", fake_urlopen)

    downloaded = faiss_artifacts.ensure_faiss_indices(
        tmp_path,
        manifest_url="https://example.com/manifest.json",
    )

    assert downloaded == 0
    assert target_path.exists()


def test_ensure_faiss_indices_downloads_missing(monkeypatch, tmp_path):
    manifest = {
        "files": [
            {
                "path": "level1/index.faiss",
                "url": "https://example.com/level1/index.faiss",
            }
        ]
    }

    def fake_urlopen(url):
        if url.endswith("manifest.json"):
            return DummyResponse(json.dumps(manifest).encode("utf-8"))
        if url.endswith("index.faiss"):
            return DummyResponse(b"payload")
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(faiss_artifacts, "urlopen", fake_urlopen)

    downloaded = faiss_artifacts.ensure_faiss_indices(
        tmp_path,
        manifest_url="https://example.com/manifest.json",
    )

    assert downloaded == 1
    assert (tmp_path / "level1" / "index.faiss").read_bytes() == b"payload"


def test_validate_manifest_metadata_accepts_legacy_without_version(caplog):
    manifest = {"files": [{"path": "index.faiss"}]}

    faiss_artifacts._validate_manifest_metadata(manifest)

    assert "missing version metadata" in caplog.text


def test_validate_manifest_metadata_requires_timestamp_for_versioned_manifest():
    manifest = {"version": "1.0.0", "files": [{"path": "index.faiss"}]}

    try:
        faiss_artifacts._validate_manifest_metadata(manifest)
    except RuntimeError as exc:
        assert "missing valid generated_at/timestamp" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing timestamp")


def test_validate_manifest_metadata_requires_embedding_model_for_v2():
    manifest = {
        "version": "2.0",
        "generated_at": "2026-03-10T00:00:00Z",
        "files": [{"path": "index.faiss"}],
    }

    try:
        faiss_artifacts._validate_manifest_metadata(manifest)
    except RuntimeError as exc:
        assert "missing embedding_model" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing embedding_model")


def test_validate_manifest_embedding_compatibility_rejects_v2_mismatch():
    manifest = {
        "version": "2.0",
        "generated_at": "2026-03-10T00:00:00Z",
        "embedding_model": "model-a",
        "files": [{"path": "index.faiss"}],
    }

    try:
        faiss_artifacts._validate_manifest_embedding_compatibility(
            manifest,
            expected_embedding_model="model-b",
        )
    except RuntimeError as exc:
        assert "does not match configured model" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for versioned manifest model mismatch")


def test_validate_manifest_embedding_compatibility_warns_on_legacy_mismatch(caplog):
    manifest = {
        "version": "1.0",
        "generated_at": "2026-03-10T00:00:00Z",
        "embedding_model": "model-a",
        "files": [{"path": "index.faiss"}],
    }

    faiss_artifacts._validate_manifest_embedding_compatibility(
        manifest,
        expected_embedding_model="model-b",
    )

    assert "Accepting legacy manifest." in caplog.text
