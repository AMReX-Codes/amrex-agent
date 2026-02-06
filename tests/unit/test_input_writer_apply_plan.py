from pathlib import Path

import pytest

from src.services import input_writer as input_writer_module
from src.services.input_writer import InputWriterService


class DummyConfig:
    def __init__(self):
        self.repositories = {}
        self.inputs_file_strategy = "newest"

    def get_code_registry(self):
        return {}


class DummyEmbeddings:
    def __init__(self):
        self.embeddings = True


def test_apply_plan_writes_inputs(tmp_path, mock_baseline_dir, monkeypatch):
    from src.services import embedding_service_factory
    import database.configs as configs_module
    monkeypatch.setattr(
        embedding_service_factory,
        "get_embedding_service",
        lambda config: DummyEmbeddings(),
    )
    class StubConfig:
        @classmethod
        def find_inputs_files(cls, case_dir):
            return [Path(case_dir) / "inputs"]

    monkeypatch.setattr(
        configs_module,
        "get_config_for_path",
        lambda path: StubConfig,
    )

    monkeypatch.setattr(
        input_writer_module.ConfigModelFactory,
        "create_from_schema",
        lambda schema, build_config: dict,
    )
    monkeypatch.setattr(
        input_writer_module.ConfigModelFactory,
        "hydrate",
        lambda model_class, baseline_text: {"baseline_text": baseline_text},
    )
    monkeypatch.setattr(
        input_writer_module.ConfigModelFactory,
        "apply_modifications",
        lambda *args, **kwargs: {
            "config": {"amr": {"n_cell": "64 64 64"}},
            "unresolved_parameters": [],
            "available_schema_params": [],
            "remap_success_count": 0,
            "suggested_params": {},
        },
    )
    monkeypatch.setattr(
        input_writer_module.RuleEngine,
        "enforce",
        lambda config_model, solver_config, build_config: config_model,
    )
    monkeypatch.setattr(
        input_writer_module.InputsFileWriter,
        "serialize",
        lambda config_model, original_text, modified_keys=None: "amr.n_cell = 64 64 64\n",
    )

    service = InputWriterService(DummyConfig())
    output_dir = tmp_path / "run"
    baseline = {
        "code": "AMReX",
        "local_path": str(mock_baseline_dir),
        "case_path": "Tests/Amr/Advection_AmrCore",
        "repo_path": str(Path(mock_baseline_dir).parents[3]),
    }

    result = service.apply_plan(
        selected_case="Tests/Amr/Advection_AmrCore",
        modifications=[("amr.n_cell", "64 64 64"), ("amr.max_level", "1")],
        baseline=baseline,
        reasoning="unit test",
        output_dir=output_dir,
    )

    inputs_path = Path(result["inputs_path"])
    assert result["status"] == "success"
    assert inputs_path.exists()
    assert inputs_path.read_text() == "amr.n_cell = 64 64 64\n"
    assert result["modifications_applied"] == 2
    assert result["requires_parameter_resolution"] is False


def test_apply_plan_requires_baseline(tmp_path, monkeypatch):
    from src.services import embedding_service_factory
    monkeypatch.setattr(
        embedding_service_factory,
        "get_embedding_service",
        lambda config: DummyEmbeddings(),
    )

    service = InputWriterService(DummyConfig())

    with pytest.raises(ValueError, match="Incomplete baseline metadata"):
        service.apply_plan(
            selected_case="Tests/Amr/Advection_AmrCore",
            modifications=[],
            baseline={},
            output_dir=tmp_path / "run",
        )
