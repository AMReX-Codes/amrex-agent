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
