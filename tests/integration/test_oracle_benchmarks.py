import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from database.configs import discover_code_configs
from database.indexing.level0_builder import Level0Builder
from database.indexing.level0_searcher import Level0Searcher
from src.benchmark_runner import run_model_benchmark, validate_case_files


class DeterministicEmbedder:
    """Deterministic hash-based embedder for offline Level-0 routing tests."""

    def __init__(self, dim: int = 256) -> None:
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


def _load_level0_oracle_cases() -> list[dict]:
    data_file = Path(__file__).resolve().parents[1] / "data" / "level0_ab_prompts.json"
    return json.loads(data_file.read_text(encoding="utf-8"))


def _build_level0_searcher(tmp_path: Path) -> Level0Searcher:
    embedder = DeterministicEmbedder()
    index_dir = tmp_path / "level0"
    Level0Builder(embedder=embedder).build(output_dir=index_dir)
    return Level0Searcher(index_dir=index_dir, embedder=embedder)


def _config_for_solver(code_name: str):
    for config in discover_code_configs():
        if getattr(config, "code_name", None) == code_name:
            return config
    raise AssertionError(f"No config class found for solver code '{code_name}'")


@pytest.mark.integration
def test_squall_line_routes_to_erf(tmp_path: Path) -> None:
    """
    Given: Squall line prompt
    When:  Level-0 solver selection runs
    Then:  Routes to ERF solver family

    Go/no-go gate: if this fails, a routing bug exists and must be fixed
    before Wave 2 starts.
    """
    searcher = _build_level0_searcher(tmp_path)
    prompt = "Run a moist squall-line convection case for weather simulation."

    result = searcher.search(prompt, top_k=1)

    assert result, "No Level-0 selection result returned for squall-line prompt"
    assert result[0]["code"] == "ERF"


@pytest.mark.integration
def test_squall_line_schema_valid(tmp_path: Path) -> None:
    """Generated inputs file passes schema validation"""
    schema_path = Path("benchmark/specs/case_schema.yaml")
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    squall_suite = {
        "schema_version": "1.0",
        "suite_id": "oracle_squall_line_gate",
        "solver": "ERF",
        "cases": [
            {
                "id": "erf_squall_line_oracle",
                "solver": "ERF",
                "case_name": "SquallLineWarmBubble",
                "case_dir": "Exec/Convection/SquallLine",
                "inputs": "inputs_squall_line",
                "description": (
                    "Mesoscale squall line convection in ERF with warm-bubble "
                    "triggering and cloud microphysics."
                ),
                "dimension": 3,
                "physics": ["mesoscale", "convection", "warm_bubble", "microphysics"],
                "difficulty_tier": "hard",
                "prompt_length_band": "medium",
                "concept_density": "high",
                "specialized_knowledge": True,
                "novelty_tier": "config-extension",
                "scaling": {
                    "type": "strong",
                    "sizes": [
                        {
                            "label": "S",
                            "grid": "128x128x64",
                            "amr_levels": 0,
                        }
                    ],
                },
                "tags": ["oracle", "squall_line", "erf"],
                "status": "ready",
            }
        ],
    }

    suite_path = cases_dir / "erf_squall_line.yaml"
    suite_path.write_text(yaml.safe_dump(squall_suite, sort_keys=False), encoding="utf-8")

    errors = validate_case_files(schema_path=schema_path, cases_dir=cases_dir)

    assert errors == []


@pytest.mark.integration
def test_squall_line_jsonl_fields_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B3a fields present in benchmark output for squall line case"""

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "job_status": "ok",
                    "selected_case": "erf_squall_line_oracle",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.benchmark_runner.subprocess.run", fake_run)

    config = {
        "prompts": [
            {
                "id": "squall_line",
                "prompt": "Run an ERF squall line case with warm bubble and cloud microphysics.",
                "solver": "ERF",
                "case_id": "erf_squall_line_oracle",
            }
        ],
        "models": [
            {
                "id": "gate_model",
                "overrides": {
                    "llm_provider": "cborg",
                    "llm_model": "mock",
                },
            }
        ],
        "run_args": {"dry_run": True},
    }
    config_path = tmp_path / "bench.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = run_model_benchmark(config_path=config_path, output_dir=tmp_path, run_name="squall_gate")

    jsonl_path = Path(result["run_dir"]) / "benchmark_runs.jsonl"
    record = json.loads(jsonl_path.read_text(encoding="utf-8").splitlines()[0])

    required_fields = {
        "model_id",
        "prompt_id",
        "job_status",
        "analysis_status",
        "analysis_performance",
        "analysis_issues",
        "run_directory",
        "selected_case",
        "started_at",
        "ended_at",
        "duration_seconds",
        "exit_code",
        "error",
        "stderr_excerpt",
    }
    assert required_fields.issubset(record.keys())
    assert record["prompt_id"] == "squall_line"
    assert record["selected_case"] == "erf_squall_line_oracle"


@pytest.mark.integration
def test_squall_line_no_level0_regression(tmp_path: Path) -> None:
    """All existing oracle cases still route correctly after squall line case added"""
    searcher = _build_level0_searcher(tmp_path)
    prompts = _load_level0_oracle_cases()

    misses: list[tuple[str, str, str]] = []
    for item in prompts:
        result = searcher.search(item["prompt"], top_k=1)
        assert result, f"No Level-0 result for oracle case {item['id']}"
        got = result[0]["code"]
        expected = item["expected_solver"]
        if got != expected:
            misses.append((item["id"], expected, got))

    assert not misses, f"Level-0 oracle regressions detected: {misses}"


@pytest.mark.integration
def test_squall_line_routes_to_erf_directory(tmp_path: Path) -> None:
    """Squall line prompt resolves to the ERF squall-line case directory."""
    searcher = _build_level0_searcher(tmp_path)
    prompt = "Run a moist squall-line convection case for weather simulation."

    result = searcher.search(prompt, top_k=1)

    assert result, "No Level-0 selection result returned for squall-line prompt"
    assert result[0]["code"] == "ERF"
    config = _config_for_solver(result[0]["code"])
    assert "Exec/MoistRegTests/SquallLine_2D" in config.priority_cases
    assert config.priority_cases[0] == "Exec/MoistRegTests/SquallLine_2D"


@pytest.mark.integration
def test_remora_04_routes_to_remora_directory(tmp_path: Path) -> None:
    """remora_04 prompt resolves to REMORA solver directory defaults."""
    searcher = _build_level0_searcher(tmp_path)
    prompt = (
        "Regional ocean boundary-layer dynamics in a coastal channel using "
        "ROMS-derived REMORA physics with sigma terrain-following vertical "
        "coordinates and tidal forcing."
    )

    result = searcher.search(prompt, top_k=1)

    assert result, "No Level-0 selection result returned for remora_04 prompt"
    assert result[0]["code"] == "REMORA"
    config = _config_for_solver(result[0]["code"])
    assert config.default_exec_repo_path == "Exec/Seamount"
