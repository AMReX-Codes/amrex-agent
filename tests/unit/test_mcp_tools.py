import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def mcp_server_module(monkeypatch, tmp_path_factory):
    home_dir = tmp_path_factory.mktemp("mcp_home")
    monkeypatch.setenv("HOME", str(home_dir))
    if "mcp_server" in sys.modules:
        del sys.modules["mcp_server"]
    return importlib.import_module("mcp_server")


def _write_inputs_file(tmp_path: Path) -> Path:
    inputs_path = tmp_path / "inputs"
    inputs_path.write_text("amr.max_level = 1\n")
    return inputs_path


def _write_executable(tmp_path: Path) -> Path:
    exe_path = tmp_path / "solver.MPI.CUDA.ex"
    exe_path.write_text("binary")
    exe_path.chmod(0o755)
    return exe_path


def test_mcp_query_knowledge_maps_response(mcp_server_module, monkeypatch):
    def fake_query(self, question, context=None):
        return {
            "answer": "ok",
            "sources": ["doc1"],
            "confidence": 0.7,
            "method": "mock",
        }

    monkeypatch.setattr(mcp_server_module.PeleKnowledgeService, "query", fake_query)

    result = mcp_server_module.mcp_query_knowledge(
        {"question": "What is CFL?", "code": "PeleC"}
    )

    assert result["answer"] == "ok"
    assert result["sources"] == ["doc1"]
    assert result["confidence"] == 0.7
    assert result["method"] == "mock"


def test_mcp_query_knowledge_requires_question(mcp_server_module):
    with pytest.raises(KeyError):
        mcp_server_module.mcp_query_knowledge({})


def test_mcp_create_simulation_plan_returns_writer_output(mcp_server_module, monkeypatch):
    plan = SimpleNamespace(
        selected_case="Exec/RegTests/PMF",
        modifications=[["amr.max_level", "2"]],
        reasoning="baseline selection",
        baseline={"code_name": "PeleC"},
        indexing_strategy="simple",
    )

    def fake_execute_planning(self, user_prompt, baseline_override=None, strategy=None):
        return plan

    def fake_apply_plan(
        self,
        selected_case,
        modifications,
        baseline,
        reasoning,
        output_dir,
    ):
        return {
            "run_dir": str(Path(output_dir) / "run_001"),
            "inputs_path": str(Path(output_dir) / "run_001" / "inputs"),
            "modifications_applied": len(modifications),
            "status": "ok",
            "requires_parameter_resolution": False,
            "unresolved_parameters": [],
            "available_schema_params": [],
            "suggested_params": {},
            "resolution_guidance": "",
        }

    monkeypatch.setattr(
        mcp_server_module.ArchitectService, "execute_planning", fake_execute_planning
    )
    monkeypatch.setattr(
        mcp_server_module.InputWriterService, "apply_plan", fake_apply_plan
    )

    result = mcp_server_module.mcp_create_simulation_plan(
        {"prompt": "2D flame", "output_dir": "./output"}
    )

    assert result["selected_case"] == plan.selected_case
    assert result["modifications"] == plan.modifications
    assert result["reasoning"] == plan.reasoning
    assert result["baseline"] == plan.baseline
    assert result["indexing_strategy"] == plan.indexing_strategy
    assert result["inputs_file_path"].endswith("inputs")
    assert result["status"] == "ok"


def test_mcp_create_simulation_plan_requires_prompt(mcp_server_module):
    with pytest.raises(KeyError):
        mcp_server_module.mcp_create_simulation_plan({})


def test_mcp_execute_workflow_defaults_steps(mcp_server_module, monkeypatch):
    calls = []

    def _stub(step_name, payload):
        calls.append(step_name)
        result = {f"{step_name}_result": True}
        if step_name == "run_simulation":
            result["run_directory"] = "/tmp/fake_run"
        return result

    monkeypatch.setattr(
        mcp_server_module,
        "mcp_create_simulation_plan",
        lambda payload: _stub("create_simulation_plan", payload),
    )
    monkeypatch.setattr(
        mcp_server_module,
        "mcp_run_simulation",
        lambda payload: _stub("run_simulation", payload),
    )
    monkeypatch.setattr(
        mcp_server_module,
        "mcp_analyze_results",
        lambda payload: _stub("analyze_results", payload),
    )
    monkeypatch.setattr(
        mcp_server_module,
        "mcp_generate_visualizations",
        lambda payload: _stub("generate_visualizations", payload),
    )
    result = mcp_server_module.mcp_execute_workflow({"prompt": "run something"})

    assert calls == [
        "create_simulation_plan",
        "run_simulation",
        "analyze_results",
        "generate_visualizations",
    ]
    assert result["final"]["generate_visualizations_result"] is True


def test_mcp_execute_workflow_runs_steps_in_order(mcp_server_module, monkeypatch):
    calls = []

    def _stub(step_name, payload):
        calls.append((step_name, dict(payload)))
        result = {f"{step_name}_result": True, "step": step_name}
        if step_name == "run_simulation":
            result["run_directory"] = "/tmp/fake_run"
        return result

    monkeypatch.setattr(
        mcp_server_module,
        "mcp_create_simulation_plan",
        lambda payload: _stub("create_simulation_plan", payload),
    )
    monkeypatch.setattr(
        mcp_server_module,
        "mcp_run_simulation",
        lambda payload: _stub("run_simulation", payload),
    )
    monkeypatch.setattr(
        mcp_server_module,
        "mcp_analyze_results",
        lambda payload: _stub("analyze_results", payload),
    )

    payload = {
        "prompt": "run something",
        "steps": ["create_simulation_plan", "run_simulation", "analyze_results"],
        "submit": {"dry_run": True},
    }

    result = mcp_server_module.mcp_execute_workflow(payload)

    assert [call[0] for call in calls] == [
        "create_simulation_plan",
        "run_simulation",
        "analyze_results",
    ]
    assert "create_simulation_plan" in result["steps"]
    assert "run_simulation" in result["steps"]
    assert "analyze_results" in result["steps"]
    assert result["steps"]["run_simulation"]["run_simulation_result"] is True
    assert result["final"]["analyze_results_result"] is True


@pytest.mark.asyncio
async def test_mcp_list_tools_includes_execute_workflow(mcp_server_module):
    tools = await mcp_server_module.list_tools()
    execute_tool = next(tool for tool in tools if tool.name == "execute_workflow")

    assert "steps" in execute_tool.inputSchema.get("properties", {})
    assert "steps" not in execute_tool.inputSchema.get("required", [])


def test_mcp_select_baseline_case_handles_missing_baseline(mcp_server_module, monkeypatch):
    monkeypatch.setattr(
        mcp_server_module.ArchitectService, "_select_baseline", lambda *args, **kwargs: None
    )

    result = mcp_server_module.mcp_select_baseline_case(
        {"prompt": "test", "code": "PeleC"}
    )

    assert result["selected_case"] == ""
    assert result["baseline_confidence"] == 0.0
    assert result["reasoning"] == "No baseline selected"


def test_mcp_select_baseline_case_maps_fields(mcp_server_module, monkeypatch, tmp_path):
    baseline = {
        "code": "PeleC",
        "path": "Exec/RegTests/PMF",
        "repo_path": str(tmp_path),
        "match_score": 0.9,
        "match_rationale": "good match",
    }

    monkeypatch.setattr(
        mcp_server_module.ArchitectService,
        "_select_baseline",
        lambda *args, **kwargs: baseline,
    )

    result = mcp_server_module.mcp_select_baseline_case(
        {"prompt": "test", "code": "PeleC"}
    )

    assert result["selected_case"] == baseline["path"]
    assert result["baseline"]["code_name"] == "PeleC"
    assert result["baseline_confidence"] == 0.9
    assert result["reasoning"] == "good match"


def test_mcp_validate_inputs_requires_path(mcp_server_module):
    with pytest.raises(ValueError):
        mcp_server_module.mcp_validate_inputs({})


def test_mcp_validate_config_requires_config(mcp_server_module):
    with pytest.raises(ValueError):
        mcp_server_module.mcp_validate_config({})


@pytest.mark.asyncio
async def test_mcp_list_tools_inprocess(mcp_server_module):
    tools = await mcp_server_module.list_tools()
    tool_names = {tool.name for tool in tools}
    expected_tools = {
        "query_knowledge",
        "execute_workflow",
        "create_simulation_plan",
        "create_proposed_modifications_with_plan",
        "select_baseline_case",
        "search_cases",
        "validate_inputs",
        "validate_config",
        "setup_job",
        "run_simulation",
        "analyze_results",
        "get_workflow_status",
        "generate_visualizations",
    }
    assert expected_tools.issubset(tool_names)


def test_mcp_validate_inputs_returns_validation(mcp_server_module, monkeypatch, tmp_path):
    inputs_path = _write_inputs_file(tmp_path)

    def fake_validate(self, config_dict, selected_solver=None):
        return {"valid": False, "errors": ["bad"], "warnings": ["warn"]}

    monkeypatch.setattr(
        mcp_server_module.ValidationService, "validate_config", fake_validate
    )

    result = mcp_server_module.mcp_validate_inputs(
        {"inputs_file_path": str(inputs_path)}
    )

    assert result["valid"] is False
    assert result["errors"] == ["bad"]


def test_mcp_validate_config_returns_validation(mcp_server_module, monkeypatch):
    def fake_validate(self, config_dict, selected_solver=None):
        return {"valid": True, "errors": [], "warnings": ["warn"]}

    monkeypatch.setattr(
        mcp_server_module.ValidationService, "validate_config", fake_validate
    )

    result = mcp_server_module.mcp_validate_config(
        {"config": {"amr.max_level": 1}, "solver": "PeleC"}
    )

    assert result["valid"] is True
    assert result["warnings"] == ["warn"]
    assert result["warnings"] == ["warn"]


def test_mcp_setup_job_dry_run(tmp_path, mcp_server_module, monkeypatch):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    inputs_path = _write_inputs_file(case_dir)
    _write_executable(case_dir)

    config = mcp_server_module.AMReXAgentConfig()
    config.output_dir = tmp_path
    monkeypatch.setattr(mcp_server_module, "config", config)

    result = mcp_server_module.mcp_setup_job(
        {"inputs_file_path": str(inputs_path), "case_dir": str(case_dir)}
    )

    assert Path(result["run_directory"]).exists()
    assert result["executable_path"].endswith(".ex")
    assert Path(result["submit_script_path"]).exists()


def test_mcp_run_simulation_requires_inputs_or_case(mcp_server_module):
    with pytest.raises(ValueError):
        mcp_server_module.mcp_run_simulation({})


def test_mcp_run_simulation_dry_run_local(tmp_path, mcp_server_module):
    inputs_path = _write_inputs_file(tmp_path)
    exe_path = _write_executable(tmp_path)

    result = mcp_server_module.mcp_run_simulation(
        {
            "inputs_file_path": str(inputs_path),
            "executable_path": str(exe_path),
            "submit": {"dry_run": True},
            "config_overrides": {"environment": "local", "output_dir": str(tmp_path)},
        }
    )

    assert result["job_status"] == "completed"
    assert Path(result["run_directory"]).exists()
    assert Path(result["script_path"]).exists()


def test_mcp_analyze_results_requires_run_directory(mcp_server_module):
    with pytest.raises(ValueError):
        mcp_server_module.mcp_analyze_results({})


def test_mcp_analyze_results_skips_when_disabled(mcp_server_module, tmp_path):
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()

    result = mcp_server_module.mcp_analyze_results(
        {
            "run_directory": str(run_dir),
            "config_overrides": {"analysis_always_enabled": False},
        }
    )

    assert result["job_status"] == "completed"
    assert result["analysis_report"]["status"] == "skipped"


def test_mcp_analyze_results_maps_success(mcp_server_module, monkeypatch, tmp_path):
    run_dir = tmp_path / "run_002"
    run_dir.mkdir()

    def fake_analyze(self, run_path, include_visual=False):
        return {"status": "success", "details": "ok"}

    monkeypatch.setattr(
        mcp_server_module.AnalysisService, "analyze_simulation", fake_analyze
    )

    result = mcp_server_module.mcp_analyze_results(
        {"run_directory": str(run_dir)}
    )

    assert result["job_status"] == "completed"
    assert result["analysis_report"]["status"] == "success"


def test_mcp_generate_visualizations_requires_run_directory(mcp_server_module):
    with pytest.raises(ValueError):
        mcp_server_module.mcp_generate_visualizations({})


def test_mcp_generate_visualizations_success(mcp_server_module, monkeypatch, tmp_path):
    run_dir = tmp_path / "run_003"
    run_dir.mkdir()
    output_dir = tmp_path / "viz"
    output_dir.mkdir()
    image_path = output_dir / "plot.png"

    class FakeBackend:
        pass

    class FakeVisualizationService:
        def __init__(self, config):
            self.backend = FakeBackend()

        def find_plotfiles(self, run_directory):
            return [Path(run_directory) / "plt00000"]

        def create_standard_plots(self, run_dir, output_dir, vis_config=None):
            image_path.write_text("image")
            return [image_path]

    monkeypatch.setattr(
        mcp_server_module, "VisualizationService", FakeVisualizationService
    )

    result = mcp_server_module.mcp_generate_visualizations(
        {"run_directory": str(run_dir), "output_dir": str(output_dir)}
    )

    assert result["visualization_status"] == "success"
    assert result["visualization_images"] == [str(image_path)]
    assert result["visualization_metadata"]["plotfile_count"] == 1


def _write_sweep_metadata(
    root: Path,
    sweep_id: str,
    session_id: str,
    status: str,
) -> Path:
    sweep_dir = root / "sweeps" / sweep_id
    sweep_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = sweep_dir / "sweep_metadata.json"
    metadata_path.write_text(
        (
            "{"
            f"\"sweep_id\": \"{sweep_id}\", "
            f"\"session_id\": \"{session_id}\", "
            f"\"status\": \"{status}\", "
            "\"created_at\": \"2026-03-10T00:00:00Z\""
            "}"
        ),
        encoding="utf-8",
    )
    return sweep_dir


def test_get_sweep_status_reads_from_filesystem(tmp_path, mcp_server_module, monkeypatch):
    monkeypatch.setattr(mcp_server_module.config, "output_dir", tmp_path)
    _write_sweep_metadata(tmp_path, "sweep-1", "sess1", "running")
    monkeypatch.setattr(
        mcp_server_module,
        "_SWEEP_REGISTRY",
        {"sweep-1": {"status": "completed"}},
        raising=False,
    )

    result = mcp_server_module.invoke_tool("get_sweep_status", {"sweep_id": "sweep-1"})

    assert result["status"] == "running"


def test_get_sweep_status_missing_returns_error(tmp_path, mcp_server_module, monkeypatch):
    monkeypatch.setattr(mcp_server_module.config, "output_dir", tmp_path)

    result = mcp_server_module.invoke_tool("get_sweep_status", {"sweep_id": "missing"})

    assert "error" in result


def test_get_sweep_results_returns_error_when_running(tmp_path, mcp_server_module, monkeypatch):
    monkeypatch.setattr(mcp_server_module.config, "output_dir", tmp_path)
    _write_sweep_metadata(tmp_path, "sweep-2", "sess1", "running")

    result = mcp_server_module.invoke_tool("get_sweep_results", {"sweep_id": "sweep-2"})

    assert "error" in result
    assert "complete" in result["error"].lower()
    assert "summary" not in result


def test_get_sweep_results_returns_summary_when_complete(tmp_path, mcp_server_module, monkeypatch):
    monkeypatch.setattr(mcp_server_module.config, "output_dir", tmp_path)
    sweep_dir = _write_sweep_metadata(tmp_path, "sweep-3", "sess1", "complete")
    summary_path = sweep_dir / "sweep_summary.json"
    summary_path.write_text(
        "{\"sweep_id\": \"sweep-3\", \"status\": \"complete\", \"metric\": 1.0}",
        encoding="utf-8",
    )

    result = mcp_server_module.invoke_tool("get_sweep_results", {"sweep_id": "sweep-3"})

    assert "error" not in result
    assert result["sweep_id"] == "sweep-3"
    assert result["status"] == "complete"
    assert result["metric"] == 1.0


def test_list_sweeps_returns_all_in_session(tmp_path, mcp_server_module, monkeypatch):
    monkeypatch.setattr(mcp_server_module.config, "output_dir", tmp_path)
    _write_sweep_metadata(tmp_path, "sweep-a", "sess1", "running")
    _write_sweep_metadata(tmp_path, "sweep-b", "sess1", "complete")
    _write_sweep_metadata(tmp_path, "sweep-c", "sess1", "failed")
    _write_sweep_metadata(tmp_path, "sweep-x", "sess2", "complete")

    result = mcp_server_module.invoke_tool("list_sweeps", {"session_id": "sess1"})

    assert "error" not in result
    assert sorted(result["sweep_ids"]) == ["sweep-a", "sweep-b", "sweep-c"]


def test_list_sweeps_empty_session(tmp_path, mcp_server_module, monkeypatch):
    monkeypatch.setattr(mcp_server_module.config, "output_dir", tmp_path)
    _write_sweep_metadata(tmp_path, "sweep-x", "other", "complete")

    result = mcp_server_module.invoke_tool("list_sweeps", {"session_id": "sess-empty"})

    assert "error" not in result
    assert result["sweep_ids"] == []
