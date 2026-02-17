"""
Pytest configuration and shared fixtures.

Fixtures defined here are available to all test files without importing.
Reference: Amendment B Quick Win, Gate 0
"""
import pytest
from pathlib import Path
import os
from typing import Dict, Any
from textwrap import dedent


@pytest.fixture(autouse=True)
def set_disabled_validators(request, monkeypatch):
    marker = request.node.get_closest_marker("disable_validators")
    if not marker:
        return
    if os.getenv("PELE_DISABLED_VALIDATORS"):
        return
    validators = []
    for value in marker.args:
        if isinstance(value, (list, tuple)):
            validators.extend(value)
        else:
            validators.append(value)
    validators = [v for v in validators if v]
    if validators:
        monkeypatch.setenv("PELE_DISABLED_VALIDATORS", ",".join(validators))


def pytest_addoption(parser) -> None:
    group = parser.getgroup("pele-agent")
    group.addoption(
        "--unit",
        action="store_true",
        help="Run unit tests only (auto-marks tests/unit).",
    )
    group.addoption(
        "--integration",
        action="store_true",
        help="Run integration tests only (auto-marks tests/integration).",
    )
    group.addoption(
        "--quality",
        action="store_true",
        help="Run quality tests only (auto-marks tests/quality).",
    )
    group.addoption(
        "--llm-provider",
        dest="llm_provider",
        default=None,
        help="LLM provider override for integration/E2E runs (cborg, alcf, openai, etc.)",
    )
    group.addoption(
        "--llm-model",
        dest="llm_model",
        default=None,
        help="LLM model override for integration/E2E runs",
    )
    group.addoption(
        "--alcf-cluster",
        dest="alcf_cluster",
        default=None,
        help="ALCF cluster selector (sophia or metis)",
    )
    group.addoption(
        "--alcf-base-url",
        dest="alcf_base_url",
        default=None,
        help="ALCF base URL override",
    )
    group.addoption(
        "--pelelmex-remote",
        action="store_true",
        help="Enable PeleLMeX test-matrix remote targets",
    )


def pytest_configure(config) -> None:
    selections = [
        config.getoption("--unit"),
        config.getoption("--integration"),
        config.getoption("--quality"),
    ]
    if sum(bool(selection) for selection in selections) > 1:
        raise pytest.UsageError("Choose only one of --unit, --integration, or --quality.")


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        path = Path(str(item.fspath))
        if "tests" not in path.parts:
            continue
        if "unit" in path.parts:
            item.add_marker(pytest.mark.unit)
        elif "integration" in path.parts:
            item.add_marker(pytest.mark.integration)
        elif "quality" in path.parts:
            item.add_marker(pytest.mark.quality)

    if config.getoption("--unit"):
        selected = "unit"
    elif config.getoption("--integration"):
        selected = "integration"
    elif config.getoption("--quality"):
        selected = "quality"
    else:
        selected = None

    if selected:
        skip = pytest.mark.skip(reason=f"skipped by --{selected}")
        for item in items:
            if not item.get_closest_marker(selected):
                item.add_marker(skip)

    if not _explicit_e2e_selected(config):
        skip_e2e = pytest.mark.skip(
            reason=(
                "E2E smoke tests disabled by default; select tests/e2e or -m e2e to run."
            )
        )
        for item in items:
            if item.get_closest_marker("e2e"):
                item.add_marker(skip_e2e)

    for item in items:
        if item.get_closest_marker("use_real_services") and item.get_closest_marker("use_mock_services"):
            raise pytest.UsageError(
                "use_real_services and use_mock_services are mutually exclusive."
            )

        if item.get_closest_marker("use_real_services") and not _has_required_llm_key(config):
            item.add_marker(pytest.mark.skip(reason="Required LLM API key not available"))

        solver_marker = item.get_closest_marker("requires_solver")
        if solver_marker:
            solver_args = solver_marker.args
            if solver_args and not _repos_available(solver_args):
                item.add_marker(pytest.mark.skip(reason="Required solver repo(s) not available"))
            if solver_args and not _schemas_available(solver_args):
                item.add_marker(pytest.mark.skip(reason="Required solver schema(s) not available"))
            if solver_args:
                default_indices = _default_indices_for_item(item)
                if default_indices and not _indices_available(default_indices):
                    item.add_marker(pytest.mark.skip(reason="Required FAISS index files not available"))

        repo_marker = item.get_closest_marker("requires_repos")
        if repo_marker and not _repos_available(repo_marker.args):
            item.add_marker(pytest.mark.skip(reason="Required solver repo(s) not available"))

        schema_marker = item.get_closest_marker("requires_schema")
        if schema_marker and not _schemas_available(schema_marker.args):
            item.add_marker(pytest.mark.skip(reason="Required schema file(s) not available"))

        indices_marker = item.get_closest_marker("requires_indices")
        if indices_marker and not _indices_available(indices_marker.args):
            item.add_marker(pytest.mark.skip(reason="Required FAISS index files not available"))


def _explicit_e2e_selected(config) -> bool:
    markexpr = config.option.markexpr or ""
    if "not e2e" in markexpr:
        return False
    if "e2e" in markexpr:
        return True
    for arg in config.args:
        try:
            parts = Path(arg).parts
        except TypeError:
            continue
        if "tests" in parts and "e2e" in parts:
            return True
    return False


def _selected_llm_provider(config) -> str | None:
    return (config.getoption("llm_provider") or "").strip().lower() or None


def _has_required_llm_key(config) -> bool:
    provider = _selected_llm_provider(config)
    provider_env = {
        "alcf": "ALCF_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "pnnl": "LLM_API_KEY",
        "litellm": "LLM_API_KEY",
    }
    env_var = provider_env.get(provider)
    if env_var:
        return bool(os.getenv(env_var))
    if provider == "alcf":
        return bool(os.getenv("ALCF_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider:
        return bool(os.getenv("LLM_API_KEY"))
    return _has_cborg_key()


def _has_cborg_key() -> bool:
    if os.getenv("CBORG_API_KEY"):
        return True
    return (Path.home() / ".nersc" / "cborg_api_key.txt").is_file()


def _repos_available(repo_names: tuple) -> bool:
    if not repo_names:
        return True
    for repo_name in repo_names:
        env_var, repo_dir = _repo_env_and_dir(repo_name)
        if env_var is None:
            return False
        if _resolve_repo_path(env_var, repo_dir) is None:
            return False
    return True


def _schemas_available(repo_names: tuple) -> bool:
    if not repo_names:
        return True
    from database.configs import discover_code_configs

    repo_root = Path(__file__).resolve().parents[1]
    schema_root = repo_root / "database" / "schemas"
    configs = {cfg.code_name: cfg for cfg in discover_code_configs()}
    for repo_name in repo_names:
        config = configs.get(repo_name)
        if not config:
            return False
        pattern = getattr(config, "schema_pattern", "amrex_schema_*.json")
        if not list(schema_root.glob(pattern)):
            return False
    return True


def _indices_available(index_names: tuple) -> bool:
    if not index_names:
        return True
    from src.config import AMReXAgentConfig
    from src.services.faiss_artifacts import faiss_indices_present

    faiss_root = AMReXAgentConfig().faiss_db_path
    if not faiss_root.exists():
        return False
    for index_name in index_names:
        normalized = str(index_name).strip().lower()
        if not normalized:
            continue
        if normalized in {"faiss", "any", "all"}:
            if not faiss_indices_present(faiss_root):
                return False
            continue
        if normalized in {"level0", "l0"}:
            if not _faiss_dir_has_indices(faiss_root / "level0"):
                return False
            continue
        if normalized in {"level1", "l1"}:
            if not _faiss_dir_has_indices(faiss_root / "level1"):
                return False
            continue
        if normalized in {"level2", "l2"}:
            if not _faiss_dir_has_indices(faiss_root / "level2"):
                return False
            continue
        if not _faiss_dir_has_indices(faiss_root / normalized):
            return False
    return True


def _default_indices_for_item(item) -> tuple[str, ...]:
    if item.get_closest_marker("indexing_hierarchical"):
        return ("level0", "level1", "level2")
    return ("faiss",)


def _faiss_dir_has_indices(directory: Path) -> bool:
    if not directory.exists():
        return False
    return any(directory.rglob("*.faiss"))


def _repo_env_and_dir(repo_name: str) -> tuple[str | None, str | None]:
    repo_map = {
        "PeleC": ("PELEC_REPO_PATH", "PeleC"),
        "PeleLMeX": ("PELELMEX_REPO_PATH", "PeleLMeX"),
        "ERF": ("ERF_REPO_PATH", "ERF"),
        "AMReX": ("AMREX_REPO_PATH", "amrex"),
        "REMORA": ("REMORA_REPO_PATH", "REMORA"),
    }
    return repo_map.get(repo_name, (None, None))


def _resolve_repo_path(env_var: str, repo_name: str) -> Path | None:
    env_path = os.getenv(env_var)
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate
        return None
    repo_root = Path(__file__).resolve().parents[1]
    candidate = repo_root.parent / repo_name
    if candidate.exists():
        return candidate
    candidate = repo_root / repo_name
    if candidate.exists():
        return candidate
    return None


@pytest.fixture
def config() -> Dict[str, Any]:
    """
    Mock configuration object for testing.
    
    Returns a minimal valid config that can be used across tests
    without requiring actual FAISS indices or API keys.
    
    Usage:
        def test_something(config):
            service = MyService(config)
            assert service.config == config
    """
    return {
        "faiss_index_path": "/tmp/test_indices",
        "faiss_embedding_model": "nomic-embed-text-v1",
        "llm_model": "claude-sonnet-4-20250514",
        "llm_provider": "cborg",
        "llm_temperature": 0.1,
        "llm_max_tokens": 4000,
        "cborg_api_key": "test-key",
        "nersc_token": "test-token",
    }


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """
    Temporary git repository for testing.
    
    Creates a temporary directory that mimics an AMReX repository structure.
    Automatically cleaned up after test completes.
    
    Args:
        tmp_path: pytest's built-in temporary directory fixture
    
    Returns:
        Path to temporary repository root
    
    Usage:
        def test_case_discovery(temp_repo):
            cases = find_cases(temp_repo)
            assert len(cases) > 0
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    # Create minimal AMReX repo structure
    (repo_dir / "Exec").mkdir()
    (repo_dir / "Exec" / "RegTests").mkdir()
    (repo_dir / "Exec" / "Production").mkdir()
    
    # Create a dummy case
    case_dir = repo_dir / "Exec" / "RegTests" / "TestCase"
    case_dir.mkdir()
    
    # Create a dummy inputs file
    inputs_file = case_dir / "inputs"
    inputs_file.write_text("""# Test inputs file
amr.max_level = 2
amr.n_cell = 64 64 64
geometry.prob_lo = 0.0 0.0 0.0
geometry.prob_hi = 1.0 1.0 1.0
geometry.is_periodic = 1 1 1
""")
    
    # Create dummy README
    readme = case_dir / "README.md"
    readme.write_text("# Test Case\n\nThis is a test case for unit tests.")
    
    return repo_dir


@pytest.fixture
def mock_embeddings():
    """
    Mock embedding service to avoid real API calls in tests.
    
    Returns a simple mock that generates fake 768-dim embeddings.
    This prevents tests from requiring CBORG API access.
    
    Usage:
        def test_semantic_search(mock_embeddings):
            embedding = mock_embeddings.embed("test query")
            assert len(embedding) == 768
    """
    class MockEmbeddings:
        def embed(self, text: str) -> list[float]:
            """Return fake 768-dim vector."""
            # Use hash of text for deterministic fake embeddings
            seed = hash(text) % 1000
            return [float(seed + i) / 1000 for i in range(768)]
        
        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            """Return batch of fake embeddings."""
            return [self.embed(text) for text in texts]
        
        def indices_available(self) -> bool:
            """Mock: Always return False (no real indices in tests)."""
            return False
    
    return MockEmbeddings()


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """
    Temporary configuration file for testing config loading.
    
    Creates a valid YAML config file in a temporary directory.
    
    Usage:
        def test_load_config(temp_config_file):
            config = load_config(temp_config_file)
            assert config['llm_provider'] == 'cborg'
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text("""llm_provider: cborg
llm_model: claude-sonnet-4-20250514
faiss_index_path: /tmp/test_indices
faiss_embedding_model: nomic-embed-text-v1
""")
    return config_path


@pytest.fixture
def mock_llm_client():
    """
    Mock LLM client to avoid real API calls in tests.

    Returns a simple mock that generates deterministic responses.

    Usage:
        def test_architect(mock_llm_client):
            response = mock_llm_client.generate("test prompt")
            assert "mock" in response.lower()
    """
    class MockLLMClient:
        def generate(self, prompt: str, **kwargs) -> str:
            """Return mock response."""
            return f"Mock response to: {prompt[:50]}..."

        def generate_json(self, prompt: str, **kwargs) -> dict:
            """Return mock JSON response."""
            return {
                "requirements": ["requirement1", "requirement2"],
                "code": "AMReX",
                "reasoning": "Mock reasoning"
            }

    return MockLLMClient()


@pytest.fixture
def use_real_services(request) -> bool:
    """
    Detect if test is marked with @pytest.mark.use_real_services.

    Conditional mocking fixture that checks for pytest markers to control
    whether tests use real services or mocked ones.

    Returns:
        True if test has @pytest.mark.use_real_services
        False otherwise (default to mocked services)

    Usage:
        @pytest.mark.use_real_services
        def test_with_real_service(use_real_services):
            assert use_real_services is True
    """
    return request.node.get_closest_marker("use_real_services") is not None


@pytest.fixture
def indexing_strategy(request) -> str:
    """
    Detect indexing strategy from pytest markers.

    Allows tests to control which indexing approach is used:
    - "simple": development's proven single FAISS approach
    - "hierarchical": integration_ladder's L0/L1/L2 approach

    Returns:
        Indexing strategy name from config or marker
        Defaults to "simple" if no marker specified

    Usage:
        @pytest.mark.indexing_hierarchical
        def test_hierarchical_indexing(indexing_strategy):
            assert indexing_strategy == "hierarchical"
    """
    if request.node.get_closest_marker("indexing_hierarchical"):
        return "hierarchical"
    elif request.node.get_closest_marker("indexing_simple"):
        return "simple"
    else:
        return "simple"  # Default


@pytest.fixture
def pele_config(config, indexing_strategy) -> "AMReXAgentConfig":
    """
    Create AMReXAgentConfig with strategy from markers.

    Constructs a full AMReXAgentConfig object (not dict) with:
    - All necessary defaults
    - indexing_strategy set from pytest markers

    Returns:
        AMReXAgentConfig instance configured for test

    Usage:
        def test_architect_planning(pele_config):
            assert pele_config.indexing_strategy == "simple"
    """
    from src.config import AMReXAgentConfig

    cfg = AMReXAgentConfig()
    cfg.indexing_strategy = indexing_strategy
    return cfg


@pytest.fixture
def sample_plan() -> Dict[str, Any]:
    """
    Sample architect plan for testing input writer.
    
    Returns a minimal valid plan structure.
    
    Usage:
        def test_apply_plan(sample_plan):
            result = writer.apply_plan(sample_plan)
            assert result['inputs_path'].exists()
    """
    return {
        "baseline": {
            "code": "AMReX",
            "path": "Tests/Amr/Advection_AmrCore",
            "name": "AMReX/Tests/Amr/Advection_AmrCore",
        },
        "modifications": [
            {
                "section": "amr",
                "parameter": "max_level",
                "value": "3",
                "reason": "Increase refinement"
            }
        ],
        "requirements": {
            "grid_resolution": "128x128x128",
            "max_refinement": 3,
        }
    }


@pytest.fixture
def schema_with_eb_dependency() -> Dict[str, Any]:
    """
    Mock schema with EB-dependent parameters.
    
    Used by build flag filtering tests.
    """
    return {
        "amr.cfl": {
            "type": "Real",
            "default": 0.5,
            "required": False,
            "build_flags": [],
        },
        "eb.sphere_radius": {
            "type": "Real",
            "default": 1.0,
            "required": False,
            "build_flags": ["USE_EB"],
        },
        "eb.sphere_center": {
            "type": "Vector<Real>",
            "default": [0.0, 0.0, 0.0],
            "required": False,
            "build_flags": ["USE_EB"],
        },
    }


@pytest.fixture
def schema_with_complex_deps() -> Dict[str, Any]:
    """
    Mock schema with complex dependencies.
    
    Tests AND/OR logic and negation.
    """
    return {
        "amr.cfl": {
            "type": "Real",
            "default": 0.5,
            "build_flags": [],
        },
        "eb.sphere_radius": {
            "type": "Real",
            "default": 1.0,
            "build_flags": ["USE_EB"],
            "dependencies": ["DIM==3"],
        },
        "prob.num_bubbles": {
            "type": "int",
            "default": 1,
            "build_flags": ["USE_EB"],
            "dependencies": ["!USE_PARTICLES"],
        },
    }


# ============================================================================
# Reviewer Service: Reviewer Orchestrator: Reviewer Orchestrator Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock config for Reviewer tests."""
    from unittest.mock import Mock
    config = Mock()
    config.max_iterations = 3
    config.disabled_validators = []
    return config

@pytest.fixture
def sample_plan():
    """Sample execution plan for validation tests."""
    return {"amr.n_cell": "64 64 64", "amr.cfl": "0.5"}

@pytest.fixture
def sample_violation():
    """Standard error-level violation."""
    from src.services.rules.base import RuleViolation
    return RuleViolation(
        rule_name="TestRule",
        severity="error",
        message="Something is wrong"
    )

@pytest.fixture
def critical_violation():
    """Critical violation for short-circuit testing."""
    from src.services.rules.base import RuleViolation
    return RuleViolation(
        rule_name="CriticalRule",
        severity="critical",
        message="File not found"
    )


# ============================================================================
# Integration Ladder Fixtures (Integration Ladder)
# ============================================================================

from tests.integration.fixtures.sample_graph_states import (
    get_l1_state, 
    get_l2_state, 
    get_l3_state,
    get_l4_state
)
from tests.integration.fixtures.mock_simulation_outputs import (
    create_mock_run_directory,
    create_failed_simulation
)

@pytest.fixture
def integration_level(request):
    '''
    Detects the integration level from the test marker.
    Returns: int (1-4) or 0 if no marker.
    '''
    for marker in request.node.iter_markers():
        if marker.name.startswith("integration_l"):
            try:
                return int(marker.name.split("_l")[1])
            except (ValueError, IndexError):
                continue
    return 0


@pytest.fixture
def ladder_state(integration_level, tmp_path):
    '''Returns the appropriate starting GraphState for the integration level.'''
    if integration_level == 1:
        return get_l1_state()
    elif integration_level == 2:
        return get_l2_state(tmp_path)
    elif integration_level == 3:
        run_dir = create_mock_run_directory(tmp_path / "sim_run", status="success")
        return get_l3_state(run_dir)
    elif integration_level == 4:
        return get_l4_state(tmp_path)
    return get_l1_state()


@pytest.fixture
def architect_node(integration_level):
    '''Real or mocked Architect node based on level.'''
    if integration_level >= 1:
        from src.nodes.architect_node import architect_node
        return architect_node
    else:
        def mock_node(state):
            return {
                **state,
                "plan": {"baseline": {"code": "AMReX"}, "modifications": []},
                "baseline": {"code": "AMReX", "path": "Tests/Amr/Advection_AmrCore"}
            }
        return mock_node


@pytest.fixture
def reviewer_node(integration_level):
    '''Real or mocked Reviewer node.'''
    if integration_level >= 1:
        from src.nodes.reviewer_node import reviewer_node
        return reviewer_node
    else:
        def mock_node(state):
            return {
                **state,
                "review_analysis": {"status": "approved", "issues": []},
                "mode": "initial"
            }
        return mock_node


@pytest.fixture
def input_writer_node(integration_level, tmp_path):
    '''Real or mocked InputWriter node.'''
    if integration_level >= 2:
        from src.nodes.input_writer_node import input_writer_node

        def wrapped_node(state):
            state["config"].output_dir = str(tmp_path)
            return input_writer_node(state)

        return wrapped_node
    else:
        def mock_node(state):
            return {
                **state,
                "inputs_path": "/fake/inputs",
                "config_dict": {"amr.n_cell": "64 64 64"},
                "run_dir": "/fake/run_dir"
            }
        return mock_node


@pytest.fixture
def runner_node(integration_level):
    '''Real or mocked Runner node.'''
    if integration_level >= 4:
        from src.nodes.runner_node import runner_node
        return runner_node
    else:
        def mock_node(state):
            return {
                **state,
                "run_dir": state.get("run_dir", "/fake/run_dir"),
                "job_id": "MOCK_JOB_123",
                "executable": "/fake/AMReX.ex"
            }
        return mock_node


@pytest.fixture
def analysis_node(integration_level):
    '''Real or mocked Analysis node.'''
    if integration_level >= 3:
        from src.nodes.analysis_node import analysis_node
        return analysis_node
    else:
        def mock_node(state):
            return {
                **state,
                "analysis_report": {
                    "status": "success",
                    "timesteps": 100,
                    "cfl_history": [0.5, 0.5, 0.5]
                }
            }
        return mock_node


@pytest.fixture
def visualization_node(integration_level):
    '''Real or mocked Visualization node.'''
    if integration_level >= 3:
        from src.nodes.visualization_node import visualization_node
        return visualization_node
    else:
        def mock_node(state):
            return {
                **state,
                "visualization_images": ["/fake/plot1.png"],
                "visualization_status": "success"
            }
        return mock_node


@pytest.fixture
def sample_simulation_output(tmp_path):
    '''Creates a complete mock simulation output directory.'''
    return create_mock_run_directory(tmp_path / "mock_sim", status="success")


@pytest.fixture
def failed_simulation_output(tmp_path):
    '''Creates a failed simulation output for error testing.'''
    return create_failed_simulation(tmp_path / "failed_sim")


# ============================================================================
# Level 4 Fixtures: Shim Executable
# ============================================================================

@pytest.fixture
def shim_executable(tmp_path):
    """
    Creates a Python script that mimics AMReX executable behavior.

    Accepts arguments to control behavior:
    - --sleep N: Sleep for N seconds (for timeout tests)
    - --fail: Exit with code 1 (simulation failure)
    - --crash: Exit with code 139 (segfault simulation)

    Writes minimal log files to satisfy Analysis node.
    """
    shim_content = """#!/usr/bin/env python3
import sys
import time
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="?", help="Inputs file")
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep time")
    parser.add_argument("--fail", action="store_true", help="Exit with error")
    parser.add_argument("--crash", action="store_true", help="Segfault simulation")
    args = parser.parse_args()

    print(f"Shim AMReX.ex running with args: {sys.argv}")

    # Simulate runtime
    if args.sleep > 0:
        print(f"Sleeping for {args.sleep} seconds...")
        time.sleep(args.sleep)

    # Simulate log file output
    with open("run.log", "w") as f:
        f.write("AMReX: run starting...\\n")
        f.write("STEP = 0  TIME = 0.0000000e+00  DT = 1.000000e-06\\n")
        f.write("STEP = 10 TIME = 1.0000000e-05  DT = 1.000000e-06\\n")

        if args.fail:
            f.write("Error: CFL violation detected\\n")
        elif args.crash:
            f.write("Error: Segmentation fault\\n")
        else:
            f.write("AMReX: run completed successfully.\\n")
            f.write("AMReX finalized\\n")

    # Simulate plotfile directory
    plt_dir = Path("plt00010")
    plt_dir.mkdir(exist_ok=True)
    (plt_dir / "Header").write_text("HyperCLaw-V1.1\\n")

    # Exit with appropriate code
    if args.fail:
        sys.exit(1)
    if args.crash:
        sys.exit(139)

    print("Shim execution complete")

if __name__ == "__main__":
    main()
"""
    shim_path = tmp_path / "AMReX.ex"
    shim_path.write_text(dedent(shim_content))
    shim_path.chmod(0o755)
    return shim_path


@pytest.fixture
def mock_baseline_dir(tmp_path, shim_executable):
    """
    Creates a mock baseline directory with shim executable.

    Mimics structure of AMReX/Tests/Amr/Advection_AmrCore with:
    - AMReX.ex (shim)
    - inputs file
    - README

    Returns path to baseline directory.
    """
    baseline = tmp_path / "MockAMReX" / "Tests" / "Amr" / "Advection_AmrCore"
    baseline.mkdir(parents=True)

    # Place shim as AMReX.ex
    import shutil
    shutil.copy(shim_executable, baseline / "AMReX.ex")

    # Create inputs file
    (baseline / "inputs").write_text(dedent("""
        # Mock inputs file
        amr.n_cell = 64 64 64
        amr.max_level = 0
        """))

    # Create README
    (baseline / "README.md").write_text("Mock PMF case for testing")

    return baseline
