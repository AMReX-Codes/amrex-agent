"""
Unit tests for remap prompt selection logic.
"""

import sys
import types

import pytest
from pydantic import BaseModel, ConfigDict, Field


class DummyConfigService:
    llm_provider = "cborg"
    cborg_api_key = "test-key"
    cborg_base_url = "https://example.test"
    llm_model = "test-model"


class FakeClient:
    def __init__(self):
        self.chat = self
        self.completions = self
        self.last_messages = None

    def create(self, **kwargs):
        from src.services.config_model_factory import MappingExtraction
        self.last_messages = kwargs.get("messages")
        return MappingExtraction(mappings=[])


def _install_fake_instructor(monkeypatch):
    fake_client = FakeClient()

    instructor_module = types.SimpleNamespace(
        from_openai=lambda client: fake_client
    )
    openai_module = types.SimpleNamespace(
        OpenAI=lambda **kwargs: object()
    )

    monkeypatch.setitem(sys.modules, "instructor", instructor_module)
    monkeypatch.setitem(sys.modules, "openai", openai_module)

    return fake_client


@pytest.fixture
def sample_config_model():
    class SampleModel(BaseModel):
        model_config = ConfigDict(populate_by_name=True, extra="allow")
        prob_jet_rad: float = Field(default=1.0, alias="prob.jet_rad")

    return SampleModel()


def test_remap_prompt_uses_solver_override(monkeypatch, sample_config_model):
    from src.services.config_model_factory import ConfigModelFactory

    fake_client = _install_fake_instructor(monkeypatch)

    class SolverConfig:
        prompt_templates = {
            "remap": {
                "template": "X {failed_list} Y {schema_list} Z {format_hints}"
            }
        }

        @classmethod
        def get_prompt_templates(cls):
            return cls.prompt_templates

    failed_mods = [("jet_diameter", 2.0)]
    ConfigModelFactory.remap_failed_modifications(
        failed_mods,
        sample_config_model,
        DummyConfigService(),
        SolverConfig,
    )

    assert fake_client.last_messages is not None
    assert fake_client.last_messages[0]["content"] == (
        "X - jet_diameter: 2.0 Y - prob.jet_rad (<class 'float'>) Z None provided"
    )


def test_remap_prompt_falls_back_to_base(monkeypatch, sample_config_model):
    from database.configs.base_amrex_config import BaseAMReXConfig
    from src.services.config_model_factory import ConfigModelFactory

    fake_client = _install_fake_instructor(monkeypatch)

    failed_mods = [("jet_diameter", 2.0)]
    ConfigModelFactory.remap_failed_modifications(
        failed_mods,
        sample_config_model,
        DummyConfigService(),
        None,
    )

    expected = BaseAMReXConfig.get_prompt_templates()["remap"]["template"].format(
        failed_list="- jet_diameter: 2.0",
        schema_list="- prob.jet_rad (<class 'float'>)",
        format_hints="None provided",
    )

    assert fake_client.last_messages is not None
    assert fake_client.last_messages[0]["content"] == expected


pytestmark = pytest.mark.input_writer_config_model_factory
