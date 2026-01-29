from pathlib import Path

from src.services.knowledge import PeleKnowledgeService


class DummyEmbeddingService:
    def __init__(self, results=None, available=True, raise_on=None):
        self._results = results or {}
        self._available = available
        self._raise_on = raise_on or set()
        self.embeddings = object()

    def indices_available(self):
        return self._available

    def retrieve_faiss(self, index_name, _query, topk=5):
        if index_name in self._raise_on:
            raise FileNotFoundError(index_name)
        return self._results.get(index_name, {"results": []})


class DummyConfig:
    def __init__(self, knowledge_base_path: Path):
        self.knowledge_base_path = knowledge_base_path
        self.default_solver = "PeleC"
        self.faiss_fallback_to_llm = True
        self.llm_model = "test-model"


def test_query_faiss_missing_index_graceful(monkeypatch, tmp_path):
    dummy_embeddings = DummyEmbeddingService(
        results={},
        raise_on={"pelec_case_details"},
    )
    monkeypatch.setattr(
        "src.services.embedding_service_factory.get_embedding_service",
        lambda _config: dummy_embeddings,
    )
    monkeypatch.setattr(
        PeleKnowledgeService,
        "_get_knowledge_tools",
        lambda _self, _solver: {},
    )

    service = PeleKnowledgeService(DummyConfig(tmp_path / "kb"))

    assert service._query_faiss("Find cases") is None


def test_query_faiss_empty_input_returns_none(monkeypatch, tmp_path):
    dummy_embeddings = DummyEmbeddingService(
        results={"pelec_case_details": {"results": []}},
    )
    monkeypatch.setattr(
        "src.services.embedding_service_factory.get_embedding_service",
        lambda _config: dummy_embeddings,
    )
    monkeypatch.setattr(
        PeleKnowledgeService,
        "_get_knowledge_tools",
        lambda _self, _solver: {},
    )

    service = PeleKnowledgeService(DummyConfig(tmp_path / "kb"))

    assert service._query_faiss("") is None
