import json
import hashlib
from pathlib import Path

import numpy as np

from database.indexing.level0_builder import Level0Builder
from database.indexing.level0_searcher import Level0Searcher


class DeterministicEmbedder:
    """Deterministic hash-based embedder for offline Level-0 tests."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def expand_documents(self, documents, metadata):
        return documents, metadata

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self.dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    def embed_texts(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str):
        return self._embed(text)


def _load_suite() -> list[dict]:
    data_file = Path(__file__).resolve().parent.parent / "data" / "level0_ab_prompts.json"
    return json.loads(data_file.read_text())


def test_level0_24_prompt_suite_regression(tmp_path):
    """
    Deterministic regression gate for Level-0 routing using a 24-prompt suite.
    """
    embedder = DeterministicEmbedder()
    index_dir = tmp_path / "level0"
    Level0Builder(embedder=embedder).build(output_dir=index_dir)
    searcher = Level0Searcher(index_dir=index_dir, embedder=embedder)

    prompts = _load_suite()
    misses = []
    explicit_misses = []
    for item in prompts:
        result = searcher.search(item["prompt"], top_k=1)
        assert result, f"No result for prompt {item['id']}"
        got = result[0]["code"]
        if got != item["expected_solver"]:
            misses.append((item["id"], item["expected_solver"], got))
            if item.get("class") == "explicit":
                explicit_misses.append((item["id"], item["expected_solver"], got))

    # Explicit solver mentions should never regress.
    assert not explicit_misses, f"Explicit routing misses: {explicit_misses}"

    # Keep the full suite in pytest as a deterministic guard with a realistic
    # floor for hash-based offline embeddings.
    accuracy = 1.0 - (len(misses) / max(1, len(prompts)))
    assert accuracy >= 0.75, f"Level0 suite accuracy {accuracy:.3f} below 0.75; misses={misses}"


def test_level0_cross_cutting_neutral_fallback(tmp_path):
    """
    If no KB reports and no per-solver guidance exist, builder should synthesize
    neutral config-derived fallback guidance (not Pele-biased text).
    """
    embedder = DeterministicEmbedder()
    builder = Level0Builder(embedder=embedder, knowledge_base_path=tmp_path / "missing_kb")

    class FakeA:
        code_name = "SolverA"
        description = "Solver A description"
        selection_keywords = ["alpha", "beta"]
        level0_physics_regimes = [{"family": "F1", "description": "D1", "aliases": []}]
        level0_capabilities = ["cap a"]
        level0_lineage = {"description": "lineage a"}
        level0_cross_cutting_guidance = []

    class FakeB:
        code_name = "SolverB"
        description = "Solver B description"
        selection_keywords = ["gamma"]
        level0_physics_regimes = [{"family": "F2", "description": "D2", "aliases": []}]
        level0_capabilities = ["cap b"]
        level0_lineage = {"description": "lineage b"}
        level0_cross_cutting_guidance = []

    builder.configs = [FakeA, FakeB]
    out = tmp_path / "level0"
    builder.build(output_dir=out)

    meta = json.loads((out / "cross_cutting_guidance_metadata.json").read_text())
    assert meta, "Expected synthesized fallback guidance entries"
    assert all(m.get("guidance_type") == "neutral_synthesized" for m in meta)
    assert all(m.get("source") == "config" for m in meta)
    assert len(meta) == 2
