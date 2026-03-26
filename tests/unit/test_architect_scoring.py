"""
Unit coverage for ArchitectService scoring helpers.
"""

import math
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.services.architect import ArchitectService


def test_score_kb_relevance_batch_uses_faiss_sources(tmp_path):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.faiss_semantic_weight = 0.0

    architect = ArchitectService(config, Mock())
    architect.code_configs = {}

    case_list = ["Exec/RegTests/PMF", "Exec/RegTests/Sedov"]
    architect._knowledge = Mock()
    architect._knowledge.query = Mock(return_value={
        "method": "faiss",
        "sources": [
            {"case": "Exec/RegTests/PMF", "score": 1.0},
        ]
    })

    scores = architect._score_kb_relevance_batch(
        case_list=case_list,
        user_prompt="premixed flame",
        requirements={"physics": "combustion", "grid": [64, 64]},
        code_name="PeleC",
    )

    assert scores["Exec/RegTests/PMF"] == pytest.approx(math.exp(-1.0))
    assert scores["Exec/RegTests/Sedov"] == 0.0


def test_score_kb_relevance_batch_llm_method_parses_json(tmp_path):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.get_code_registry = Mock(return_value=["PeleC"])

    architect = ArchitectService(config, Mock())
    architect.code_configs = {}
    architect._knowledge = Mock()
    architect._knowledge.query = Mock(return_value={
        "method": "llm",
        "answer": "{\"PMF\": 9, \"Sedov\": 1}",
    })

    case_list = ["Exec/RegTests/PMF", "Exec/RegTests/Sedov"]

    scores = architect._score_kb_relevance_batch(
        case_list=case_list,
        user_prompt="premixed flame",
        requirements={"physics": "combustion", "grid": [64, 64]},
        code_name="PeleC",
    )

    assert scores["Exec/RegTests/PMF"] > scores["Exec/RegTests/Sedov"]


def test_score_path_heuristics_regression_boost(tmp_path):
    config = Mock()
    config.faiss_db_path = tmp_path
    architect = ArchitectService(config, Mock())

    (tmp_path / "Exec" / "Production").mkdir(parents=True)

    code_def = SimpleNamespace(local_path=tmp_path)
    score, details = architect._score_path_heuristics(
        "Exec/RegTests/PMF/inputs.rt",
        code_def,
    )

    assert score == pytest.approx(0.95)
    assert details["type"] == "Exec/Regression"
    assert details["filename_boost"] == "regression_test"


def test_score_faiss_semantic_batch_combines_indices(tmp_path):
    config = Mock()
    config.faiss_db_path = tmp_path
    architect = ArchitectService(config, Mock())

    case_list = ["Exec/RegTests/PMF", "Exec/RegTests/Sedov"]

    class DummyEmbeddings:
        def indices_available(self):
            return True

        def retrieve_faiss(self, query, index_name, topk):
            if index_name.endswith("_case_names"):
                return {
                    "results": [
                        {
                            "metadata": {"case": "Exec/RegTests/PMF", "case_name": "PMF"},
                            "score": 0.0,
                        },
                        {
                            "metadata": {"case": "Exec/RegTests/Sedov", "case_name": "Sedov"},
                            "score": 1.0,
                        },
                    ]
                }
            if index_name.endswith("_case_structure"):
                return {
                    "results": [
                        {
                            "metadata": {"case": "Exec/RegTests/PMF", "case_name": "PMF"},
                            "score": 1.0,
                        },
                        {
                            "metadata": {"case": "Exec/RegTests/Sedov", "case_name": "Sedov"},
                            "score": 0.0,
                        },
                    ]
                }
            return {
                "results": [
                    {
                        "metadata": {"case": "Exec/RegTests/PMF", "case_name": "PMF"},
                        "score": 2.0,
                    },
                ]
            }

    architect.embeddings = DummyEmbeddings()

    scores = architect._score_faiss_semantic_batch(
        case_list=case_list,
        user_prompt="premixed flame",
        requirements={"physics": "combustion"},
        code_name="PeleC",
    )

    expected_pmf = (
        0.80 * math.exp(-0.0) +
        0.12 * math.exp(-1.0) +
        0.08 * math.exp(-2.0)
    )
    expected_sedov = (
        0.80 * math.exp(-1.0) +
        0.12 * math.exp(-0.0) +
        0.08 * 0.0
    )

    assert scores["Exec/RegTests/PMF"] == pytest.approx(expected_pmf, rel=1e-3)
    assert scores["Exec/RegTests/Sedov"] == pytest.approx(expected_sedov, rel=1e-3)


def test_score_faiss_semantic_batch_handles_partial_indices(tmp_path):
    config = Mock()
    config.faiss_db_path = tmp_path
    architect = ArchitectService(config, Mock())

    case_list = ["Exec/RegTests/PMF"]

    class DummyEmbeddings:
        def indices_available(self):
            return True

        def retrieve_faiss(self, query, index_name, topk):
            if index_name.endswith("_case_names"):
                return {
                    "results": [
                        {
                            "metadata": {"case": "Exec/RegTests/PMF", "case_name": "PMF"},
                            "score": 0.0,
                        },
                    ]
                }
            raise RuntimeError("missing index")

    architect.embeddings = DummyEmbeddings()

    scores = architect._score_faiss_semantic_batch(
        case_list=case_list,
        user_prompt="premixed flame",
        requirements={"physics": "combustion"},
        code_name="PeleC",
    )

    assert scores["Exec/RegTests/PMF"] == pytest.approx(0.80 * math.exp(-0.0))


def test_extract_requirements_defers_knowledge_init(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.repositories = {}
    config.get_code_registry = Mock(return_value=["PeleC"])

    architect = ArchitectService(config, Mock())
    architect.cases.get_code_names = Mock(return_value=["PeleC"])

    created = []

    class DummyKnowledge:
        def query(self, *_args, **_kwargs):
            return {"answer": "PeleC"}

    monkeypatch.setattr(
        "src.services.architect.PeleKnowledgeService",
        lambda _cfg: created.append(True) or DummyKnowledge(),
    )

    requirements = architect._extract_requirements("Use PeleC for this run")

    assert requirements["solver"] == "PeleC"
    assert architect._knowledge is None
    assert created == []


def test_extract_requirements_initializes_knowledge_when_needed(tmp_path, monkeypatch):
    config = Mock()
    config.faiss_db_path = tmp_path
    config.repositories = {}
    config.get_code_registry = Mock(return_value=["PeleC"])

    architect = ArchitectService(config, Mock())
    architect.cases.get_code_names = Mock(return_value=[])
    architect.level0_searcher = None

    created = []

    class DummyKnowledge:
        def query(self, *_args, **_kwargs):
            return {"answer": "PeleC"}

    monkeypatch.setattr(
        "src.services.architect.PeleKnowledgeService",
        lambda _cfg: created.append(True) or DummyKnowledge(),
    )

    requirements = architect._extract_requirements("Pick a solver for me")

    assert requirements["solver"] == "PeleC"
    assert architect._knowledge is not None
    assert created == [True]
