from types import SimpleNamespace

from src.services.embedding_factory import _resolve_api_key, _resolve_model_name


def test_resolve_api_key_prefers_config(monkeypatch) -> None:
    monkeypatch.setenv("CBORG_API_KEY", "env-key")
    config = SimpleNamespace(cborg_api_key="config-key")
    assert _resolve_api_key("cborg", config) == "config-key"


def test_resolve_api_key_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    config = SimpleNamespace(openai_api_key=None)
    assert _resolve_api_key("openai", config) == "env-key"


def test_resolve_api_key_normalizes_provider_case(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    config = SimpleNamespace(openai_api_key="config-key")
    assert _resolve_api_key("OpenAI", config) == "config-key"


def test_resolve_model_name_prefers_explicit_override() -> None:
    config = SimpleNamespace(faiss_embedding_model="text-embedding-3-small")
    assert (
        _resolve_model_name("openai", model_name="text-embedding-3-large", config=config)
        == "text-embedding-3-large"
    )


def test_resolve_model_name_uses_config_default() -> None:
    config = SimpleNamespace(faiss_embedding_model="text-embedding-3-large")
    assert _resolve_model_name("openai", model_name=None, config=config) == "text-embedding-3-large"


def test_resolve_model_name_falls_back_to_builtin_default() -> None:
    config = SimpleNamespace(faiss_embedding_model=None)
    assert _resolve_model_name("openai", model_name=None, config=config) == "text-embedding-3-small"
