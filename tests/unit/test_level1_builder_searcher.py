"""
Unit tests for Level1Builder and Level1Searcher.
"""

from pathlib import Path
import json

import faiss
import numpy as np

from database.indexing.level1_builder import Level1Builder
from database.indexing.level1_searcher import Level1Searcher


class DummyConfig:
    code_name = "AMReX"
    documentation_map = {}


class DummyEmbedder:
    def embed_query(self, _query):
        return [0.0, 0.0, 0.0]


def test_chunk_document_with_sections():
    builder = Level1Builder(DummyConfig, embedder=None)
    content = "Intro section\n## SectionA\nBody A\n## SectionB\nBody B"
    chunks = builder._chunk_document(content, Path("dummy.md"))

    assert len(chunks) == 3
    assert chunks[0]["metadata"]["section"] == "header"
    assert chunks[1]["metadata"]["section"] == "SectionA"
    assert "SectionA" in chunks[1]["text"]
    assert chunks[2]["metadata"]["section"] == "SectionB"


def test_resolve_agent_path_points_to_repo_file():
    builder = Level1Builder(DummyConfig, embedder=None)
    resolved = builder._resolve_agent_path("database/configs/amrex_config.py")
    assert resolved is not None
    assert resolved.exists()


def test_level1_searcher_returns_results(tmp_path):
    # Build a small FAISS index and metadata
    index_dir = tmp_path / "level1"
    index_dir.mkdir()

    vectors = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], dtype=np.float32)
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    index_path = index_dir / "amrex_doc_solver_readme.faiss"
    faiss.write_index(index, str(index_path))

    metadata = [
        {"source": "README.md", "index_type": "solver_readme"},
        {"source": "guide.md", "index_type": "solver_readme"},
    ]
    (index_dir / "amrex_doc_solver_readme_metadata.json").write_text(
        json.dumps(metadata)
    )

    searcher = Level1Searcher("AMReX", index_dir, embedder=DummyEmbedder())
    results = searcher.search_all_docs("test", top_k=1)

    assert results
    assert results[0]["doc_type"] == "solver_readme"
    assert "metadata" in results[0]
