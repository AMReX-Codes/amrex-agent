import json
from pathlib import Path

from src.services.file_generation import FileGenerationService


class FakeSolver:
    code_name = "MockSolver"

    @classmethod
    def resolve_executable_path(cls, app_config):
        return None

    @classmethod
    def get_slurm_metadata(cls):
        return {"job_name": "mock_job", "display_name": "MockSolver"}

    @classmethod
    def get_readme_title(cls):
        return "MockSolver Simulation"

    @classmethod
    def get_readme_summary_lines(cls, config):
        return ["Dimensions: 3D", "Grid: 4 4 4", "AMR Levels: 0"]

    @classmethod
    def get_readme_solver_lines(cls, config):
        return ["Model: unit-test"]

    @classmethod
    def estimate_resources(cls, config, system="perlmutter"):
        return {
            "recommended_nodes": 2,
            "estimated_walltime_hours": 1.5,
            "total_cores": 256,
            "base_cells": 64,
            "max_cells": 128,
            "memory_gb": 10.0,
            "cells_per_core": 2,
            "cost_node_hours": 3.0,
        }


class FakeConfig:
    def get_code_registry(self):
        return {"MockSolver": FakeSolver}


def test_write_simulation_files(tmp_path):
    service = FileGenerationService(config=FakeConfig())
    output_dir = tmp_path / "run"

    config = {
        "amr": {"n_cell": "4 4 4", "max_level": 0},
        "_metadata": {
            "timestamp": "2025-01-01T00:00:00Z",
            "user_intent": "unit test",
            "baseline": "tests/inputs",
            "selected_solver": "MockSolver",
        },
    }

    result = service.write_simulation_files(
        config_json=json.dumps(config),
        output_dir=output_dir,
        selected_solver="MockSolver",
        executable_path="/path/to/solver.ex",
        system="perlmutter",
    )

    assert Path(result["inputs"]).exists()
    assert Path(result["submit_script"]).exists()
    assert Path(result["readme"]).exists()

    readme = Path(result["readme"]).read_text()
    assert "MockSolver Simulation" in readme
    assert "**Generated:** 2025-01-01T00:00:00Z" in readme
    assert "Resource Estimates" in readme


def test_generate_slurm_script_includes_directives(monkeypatch):
    service = FileGenerationService(config=FakeConfig())

    monkeypatch.setenv("NERSC_HOST", "perlmutter")
    monkeypatch.setenv("SBATCH_ACCOUNT", "testacct")

    resources = FakeSolver.estimate_resources({})

    script = service._generate_slurm_script(
        solver_config=FakeSolver,
        resources=resources,
        executable_path="/path/to/solver.ex",
    )

    assert "#SBATCH -A testacct" in script
    assert "#SBATCH -N 2" in script
    assert "#SBATCH -q regular" in script
    assert "srun -n 256" in script


def test_generate_readme_includes_summary():
    service = FileGenerationService(config=FakeConfig())

    config = {
        "amr": {"n_cell": "4 4 4", "max_level": 0},
        "_metadata": {
            "timestamp": "2025-01-01T00:00:00Z",
            "user_intent": "unit test",
            "baseline": "tests/inputs",
        },
    }
    resources = FakeSolver.estimate_resources(config)

    readme = service._generate_readme(
        solver_config=FakeSolver,
        config=config,
        resources=resources,
        executable_path="/path/to/solver.ex",
    )

    assert "Configuration Summary" in readme
    assert "Dimensions" in readme
    assert "Resource Estimates" in readme
