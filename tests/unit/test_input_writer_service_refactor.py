import pytest
from pathlib import Path
from unittest.mock import Mock, patch


@pytest.fixture
def mock_config():
    config = Mock()
    config.amrex_cases_path = "/path/to/cases"
    return config


@pytest.fixture
def disable_embedding_service(monkeypatch):
    monkeypatch.setattr("src.services.embedding_service_factory.get_embedding_service", lambda _cfg: Mock())


@pytest.fixture
def sample_baseline_text():
    return """# Grid
amr.n_cell = 64 64 64
amr.max_level = 0

# Physics
amr.cfl = 0.9
"""


def _baseline(tmp_path):
    return {
        "code_name": "AMReX",
        "repo_path": str(tmp_path / "AMReX"),
        "case_path": "AMReX/Tests/Amr/Advection_AmrCore",
        "local_path": str(tmp_path / "missing"),
    }


class TestApplyPlanRefactor:
    def test_apply_plan_loads_baseline_as_text(
        self,
        mock_config,
        sample_baseline_text,
        tmp_path,
        monkeypatch,
        disable_embedding_service,
    ):
        from src.services.input_writer import InputWriterService

        mock_cases_service = Mock()
        mock_cases_service.get_case_files.return_value = {
            "inputs_text": sample_baseline_text
        }

        mock_factory = Mock()
        MockModelClass = type("AMReXModel", (), {})
        mock_model = Mock()
        mock_factory.create_from_schema.return_value = MockModelClass
        mock_factory.hydrate.return_value = mock_model
        mock_factory.apply_modifications.return_value = {
            "config": mock_model,
            "unresolved_parameters": [],
            "available_schema_params": [],
            "remap_success_count": 0,
            "suggested_params": {},
        }

        mock_rule_engine = Mock()
        mock_rule_engine.enforce.return_value = mock_model

        mock_writer = Mock()
        mock_writer.serialize.return_value = "output text with content"

        monkeypatch.setattr("src.services.input_writer.ConfigModelFactory", mock_factory)
        monkeypatch.setattr("src.services.input_writer.RuleEngine", mock_rule_engine)
        monkeypatch.setattr("src.services.input_writer.InputsFileWriter", mock_writer)

        service = InputWriterService(mock_config)
        service.cases_svc = mock_cases_service

        result = service.apply_plan(
            selected_case="AMReX/Tests/Amr/Advection_AmrCore",
            modifications=[("amr.n_cell", "128 128 128")],
            baseline=_baseline(tmp_path),
            reasoning="test",
            output_dir=tmp_path,
        )

        mock_cases_service.get_case_files.assert_called_once_with("AMReX/Tests/Amr/Advection_AmrCore")
        mock_factory.hydrate.assert_called_once()
        hydrated_text = mock_factory.hydrate.call_args[0][1]
        assert "amr.n_cell" in hydrated_text
        assert "64 64 64" in hydrated_text
        assert result["status"] == "success"

    def test_apply_plan_applies_modifications(
        self,
        mock_config,
        sample_baseline_text,
        tmp_path,
        disable_embedding_service,
    ):
        from src.services.input_writer import InputWriterService

        with patch("src.services.input_writer.AMReXCasesService") as mock_cases, \
             patch("src.services.input_writer.ConfigModelFactory") as mock_factory, \
             patch("src.services.input_writer.RuleEngine") as mock_rules, \
             patch("src.services.input_writer.InputsFileWriter") as mock_writer:

            mock_cases_instance = Mock()
            mock_cases_instance.get_case_files.return_value = {
                "inputs_text": sample_baseline_text
            }
            mock_cases.return_value = mock_cases_instance

            mock_model = Mock()
            mock_factory.create_from_schema.return_value = type("Model", (), {})
            mock_factory.hydrate.return_value = mock_model
            mock_factory.apply_modifications.return_value = {
                "config": mock_model,
                "unresolved_parameters": [],
                "available_schema_params": [],
                "remap_success_count": 0,
                "suggested_params": {},
            }
            mock_rules.enforce.return_value = mock_model
            mock_writer.serialize.return_value = "output"

            service = InputWriterService(mock_config)
            service.apply_plan(
                selected_case="AMReX/Tests/Amr/Advection_AmrCore",
                modifications=[("amr.n_cell", "128 128 128")],
                baseline=_baseline(tmp_path),
                reasoning="test",
                output_dir=tmp_path,
            )

            mock_factory.apply_modifications.assert_called_once()
            modifications = mock_factory.apply_modifications.call_args[0][1]
            assert modifications == [("amr.n_cell", "128 128 128")]

    def test_apply_plan_enforces_rules_after_modification(
        self,
        mock_config,
        sample_baseline_text,
        tmp_path,
        disable_embedding_service,
    ):
        from src.services.input_writer import InputWriterService

        call_order = []

        with patch("src.services.input_writer.AMReXCasesService") as mock_cases, \
             patch("src.services.input_writer.ConfigModelFactory") as mock_factory, \
             patch("src.services.input_writer.RuleEngine") as mock_rules, \
             patch("src.services.input_writer.InputsFileWriter") as mock_writer:

            mock_cases_instance = Mock()
            mock_cases_instance.get_case_files.return_value = {
                "inputs_text": sample_baseline_text
            }
            mock_cases.return_value = mock_cases_instance

            mock_model = Mock()
            mock_factory.create_from_schema.return_value = type("Model", (), {})
            mock_factory.hydrate.return_value = mock_model

            def track_modify(*_args, **_kwargs):
                call_order.append("modify")
                return {
                    "config": mock_model,
                    "unresolved_parameters": [],
                    "available_schema_params": [],
                    "remap_success_count": 0,
                    "suggested_params": {},
                }

            def track_enforce(*_args, **_kwargs):
                call_order.append("enforce")
                return mock_model

            mock_factory.apply_modifications.side_effect = track_modify
            mock_rules.enforce.side_effect = track_enforce
            mock_writer.serialize.return_value = "output"

            service = InputWriterService(mock_config)
            service.apply_plan(
                selected_case="AMReX/Tests/Amr/Advection_AmrCore",
                modifications=[("amr.n_cell", "128 128 128")],
                baseline=_baseline(tmp_path),
                reasoning="test",
                output_dir=tmp_path,
            )

            assert call_order == ["modify", "enforce"]

    def test_apply_plan_serializes_with_format_preservation(
        self,
        mock_config,
        sample_baseline_text,
        tmp_path,
        disable_embedding_service,
    ):
        from src.services.input_writer import InputWriterService

        with patch("src.services.input_writer.AMReXCasesService") as mock_cases, \
             patch("src.services.input_writer.ConfigModelFactory") as mock_factory, \
             patch("src.services.input_writer.RuleEngine") as mock_rules, \
             patch("src.services.input_writer.InputsFileWriter") as mock_writer:

            mock_cases_instance = Mock()
            mock_cases_instance.get_case_files.return_value = {
                "inputs_text": sample_baseline_text
            }
            mock_cases.return_value = mock_cases_instance

            mock_model = Mock()
            mock_factory.create_from_schema.return_value = type("Model", (), {})
            mock_factory.hydrate.return_value = mock_model
            mock_factory.apply_modifications.return_value = {
                "config": mock_model,
                "unresolved_parameters": [],
                "available_schema_params": [],
                "remap_success_count": 0,
                "suggested_params": {},
            }
            mock_rules.enforce.return_value = mock_model
            mock_writer.serialize.return_value = "# Grid\namr.n_cell = 128 128 128\n"

            service = InputWriterService(mock_config)
            result = service.apply_plan(
                selected_case="AMReX/Tests/Amr/Advection_AmrCore",
                modifications=[("amr.n_cell", "128 128 128")],
                baseline=_baseline(tmp_path),
                reasoning="test",
                output_dir=tmp_path,
            )

            mock_writer.serialize.assert_called_once()
            call_args = mock_writer.serialize.call_args
            assert "original_text" in call_args[1] or len(call_args[0]) > 1
            assert (Path(tmp_path) / "inputs").exists()
            assert result["status"] == "success"


pytestmark = pytest.mark.unit
