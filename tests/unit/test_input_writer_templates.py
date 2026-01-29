from src.services.input_writer import InputWriterService


class DummyConfig:
    def __init__(self):
        self.repositories = {}

    def get_code_registry(self):
        return {}


class DummyEmbeddings:
    def __init__(self, results=None):
        self.embeddings = True
        self._results = results

    def indices_available(self):
        return True

    def retrieve_faiss(self, index_name, query, topk=50):
        return {"results": self._results or []}


def test_retrieve_similar_templates_returns_results(monkeypatch):
    from src.services import embedding_service_factory

    mock_results = [
        {
            "metadata": {
                "case_name": "PMF",
                "case_path": "Exec/RegTests/PMF",
                "mechanism": "gri30",
                "fuel": "CH4",
            },
            "score": 0.12,
            "content": "input preview",
        }
    ]

    monkeypatch.setattr(
        embedding_service_factory,
        "get_embedding_service",
        lambda config: DummyEmbeddings(results=mock_results),
    )

    service = InputWriterService(DummyConfig())

    plan = {
        "prompt": "Premixed methane flame",
        "requirements": {"fuel": "CH4", "mechanism": "gri30", "grid": [64, 64, 64]},
        "baseline": {"code": "PeleC"},
    }

    templates = service._retrieve_similar_templates(plan)

    assert templates
    assert templates[0]["case_name"] == "PMF"
    assert templates[0]["mechanism"] == "gri30"
    assert templates[0]["fuel"] == "CH4"


def test_retrieve_similar_templates_handles_empty(monkeypatch):
    from src.services import embedding_service_factory

    monkeypatch.setattr(
        embedding_service_factory,
        "get_embedding_service",
        lambda config: DummyEmbeddings(results=[]),
    )

    service = InputWriterService(DummyConfig())

    plan = {
        "prompt": "Premixed methane flame",
        "requirements": {"grid": [64, 64, 64]},
        "baseline": {"code": "PeleC"},
    }

    assert service._retrieve_similar_templates(plan) is None
