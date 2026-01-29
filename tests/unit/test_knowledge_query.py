from pathlib import Path

import pytest

from src.services.knowledge import PeleKnowledgeService


class DummyEmbeddingService:
    def __init__(self, results=None, available=True):
        self._results = results or {}
        self._available = available
        self.embeddings = object()

    def indices_available(self):
        return self._available

    def retrieve_faiss(self, index_name, _query, topk=5):
        return self._results.get(index_name, {"results": []})


class DummyConfig:
    def __init__(self, knowledge_base_path: Path):
        self.knowledge_base_path = knowledge_base_path
        self.default_solver = "PeleC"
        self.faiss_fallback_to_llm = True
        self.llm_model = "test-model"


def test_query_combines_faiss_and_llm(monkeypatch, tmp_path):
    faiss_results = {
        "pelec_case_details": {
            "results": [
                {
                    "score": 0.5,
                    "content": "Case details content",
                    "metadata": {"case_name": "CaseA", "case": "Exec/CaseA"},
                }
            ]
        }
    }
    dummy_embeddings = DummyEmbeddingService(results=faiss_results)
    monkeypatch.setattr(
        "src.services.embedding_service_factory.get_embedding_service",
        lambda _config: dummy_embeddings,
    )
    def _ask(question):
        return {
            "answer": "LLM answer",
            "sources": [{"case": "Exec/CaseA"}],
            "confidence": 0.6,
        }
    monkeypatch.setattr(
        PeleKnowledgeService,
        "_get_knowledge_tools",
        lambda _self, _solver: {
            "ask": _ask,
        },
    )

    service = PeleKnowledgeService(DummyConfig(tmp_path / "kb"))

    result = service.query("Describe the case setup")

    assert result["method"] == "hybrid"
    assert "Based on case database" in result["answer"]
    assert "LLM analysis" in result["answer"]
    assert result["confidence"] > 0
    assert len(result["sources"]) == 1
    assert result["sources"][0]["case"] == "Exec/CaseA"


def test_combine_results_dedupes_sources(monkeypatch, tmp_path):
    dummy_embeddings = DummyEmbeddingService(results={})
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

    faiss_result = {
        "answer": "FAISS answer",
        "sources": [{"case": "Exec/CaseA"}, {"case": "Exec/CaseB"}],
        "confidence": 0.5,
    }
    llm_result = {
        "answer": "LLM answer",
        "sources": [{"case": "Exec/CaseB"}, {"case": "Exec/CaseC"}],
        "confidence": 0.5,
    }

    combined = service._combine_results(faiss_result, llm_result)

    assert combined["sources"] == [
        {"case": "Exec/CaseA"},
        {"case": "Exec/CaseB"},
        {"case": "Exec/CaseC"},
    ]
