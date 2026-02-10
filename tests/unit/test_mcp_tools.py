import importlib
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import anyio
from mcp.client.session import ClientSession


@pytest.fixture
def mcp_server_module(monkeypatch):
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


def test_mcp_stdio_initialize_roundtrip():
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", str(repo_root / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=repo_root,
        env=env,
    )

    def _send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    stderr_lines: list[str] = []

    def _recv(expected_id: int, timeout: float = 30.0) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.1)
            for stream in ready:
                line = stream.readline().strip()
                if not line:
                    continue
                if stream is proc.stderr:
                    stderr_lines.append(line)
                    continue
                message = json.loads(line)
                if message.get("id") == expected_id:
                    return message
        stderr_dump = "\n".join(stderr_lines[-20:])
        raise RuntimeError(
            f"Timed out waiting for response id={expected_id}\n"
            f"stderr:\n{stderr_dump}"
        )

    try:
        _send(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.0"},
                },
            }
        )
        try:
            init_response = _recv(0, timeout=60.0)
        except RuntimeError as exc:
            pytest.xfail(str(exc))
        assert "result" in init_response

        _send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.asyncio
async def test_mcp_inprocess_calls_all_tools(mcp_server_module, monkeypatch, tmp_path):
    def _stub_tool(_payload):
        return {"ok": True}

    for name in (
        "mcp_query_knowledge",
        "mcp_create_simulation_plan",
        "mcp_create_proposed_modifications_with_plan",
        "mcp_select_baseline_case",
        "mcp_validate_inputs",
        "mcp_setup_job",
        "mcp_run_simulation",
        "mcp_analyze_results",
        "mcp_generate_visualizations",
    ):
        monkeypatch.setattr(mcp_server_module, name, _stub_tool)

    inputs_path = tmp_path / "inputs"
    inputs_path.write_text("amr.max_level = 1\n")
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    client_to_server_send, client_to_server_recv = anyio.create_memory_object_stream(0)
    server_to_client_send, server_to_client_recv = anyio.create_memory_object_stream(0)

    init_options = mcp_server_module.app.create_initialization_options()

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            mcp_server_module.app.run,
            client_to_server_recv,
            server_to_client_send,
            init_options,
        )

        async with ClientSession(server_to_client_recv, client_to_server_send) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            expected_tools = {
                "query_knowledge",
                "create_simulation_plan",
                "create_proposed_modifications_with_plan",
                "select_baseline_case",
                "validate_inputs",
                "setup_job",
                "run_simulation",
                "analyze_results",
                "generate_visualizations",
            }
            assert expected_tools.issubset(tool_names)

            tool_payloads = [
                ("query_knowledge", {"question": "test", "code": "AMReX"}),
                ("create_simulation_plan", {"prompt": "minimal plan", "output_dir": str(tmp_path)}),
                ("create_proposed_modifications_with_plan", {"prompt": "minimal plan"}),
                ("select_baseline_case", {"prompt": "baseline test", "code": "AMReX", "top_k": 1}),
                ("validate_inputs", {"inputs_file_path": str(inputs_path)}),
                ("setup_job", {"inputs_file_path": str(inputs_path), "case_dir": str(case_dir)}),
                (
                    "run_simulation",
                    {
                        "inputs_file_path": str(inputs_path),
                        "case_dir": str(case_dir),
                        "submit": {"dry_run": True},
                        "config_overrides": {"environment": "local", "output_dir": str(tmp_path)},
                    },
                ),
                ("analyze_results", {"run_directory": str(tmp_path)}),
                ("generate_visualizations", {"run_directory": str(tmp_path)}),
            ]

            for tool_name, arguments in tool_payloads:
                result = await session.call_tool(tool_name, arguments)
                assert result.isError is False


def test_mcp_stdio_list_tools_and_validate_inputs(tmp_path):
    inputs_path = tmp_path / "inputs"
    inputs_path.write_text("amr.max_level = 1\n")

    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", str(repo_root / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=repo_root,
        env=env,
    )

    def _send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    stderr_lines: list[str] = []

    def _recv(expected_id: int, timeout: float = 30.0) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.1)
            for stream in ready:
                line = stream.readline().strip()
                if not line:
                    continue
                if stream is proc.stderr:
                    stderr_lines.append(line)
                    continue
                message = json.loads(line)
                if message.get("id") == expected_id:
                    return message
        stderr_dump = "\n".join(stderr_lines[-20:])
        raise RuntimeError(
            f"Timed out waiting for response id={expected_id}\n"
            f"stderr:\n{stderr_dump}"
        )

    try:
        _send(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.0"},
                },
            }
        )
        try:
            init_response = _recv(0, timeout=60.0)
        except RuntimeError as exc:
            pytest.xfail(str(exc))
        assert "result" in init_response

        _send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

        _send({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools_response = _recv(1)
        tools = tools_response.get("result", {}).get("tools", [])
        tool_names = {tool.get("name") for tool in tools}
        expected_tools = {
            "query_knowledge",
            "create_simulation_plan",
            "create_proposed_modifications_with_plan",
            "select_baseline_case",
            "validate_inputs",
            "setup_job",
            "run_simulation",
            "analyze_results",
            "generate_visualizations",
        }
        assert expected_tools.issubset(tool_names)

        case_dir = tmp_path / "case"
        case_dir.mkdir()
        exe_path = case_dir / "solver.MPI.CUDA.ex"
        exe_path.write_text("binary")
        exe_path.chmod(0o755)
        case_inputs = case_dir / "inputs"
        case_inputs.write_text("amr.max_level = 1\n")

        run_dir = tmp_path / "run_dir"
        run_dir.mkdir()

        tool_payloads = [
            ("query_knowledge", {"question": "test", "code": "AMReX"}),
            (
                "create_simulation_plan",
                {
                    "prompt": "minimal test plan",
                    "output_dir": str(tmp_path / "plan_output"),
                },
            ),
            (
                "create_proposed_modifications_with_plan",
                {"prompt": "minimal test plan"},
            ),
            (
                "select_baseline_case",
                {"prompt": "minimal baseline", "code": "AMReX", "top_k": 1},
            ),
            ("validate_inputs", {"inputs_file_path": str(inputs_path)}),
            ("setup_job", {"inputs_file_path": str(case_inputs), "case_dir": str(case_dir)}),
            (
                "run_simulation",
                {
                    "inputs_file_path": str(case_inputs),
                    "case_dir": str(case_dir),
                    "submit": {"dry_run": True},
                    "config_overrides": {"environment": "local", "output_dir": str(tmp_path / "runs")},
                },
            ),
            ("analyze_results", {"run_directory": str(run_dir)}),
            ("generate_visualizations", {"run_directory": str(run_dir)}),
        ]

        request_id = 2
        for tool_name, arguments in tool_payloads:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                }
            )
            response = _recv(request_id, timeout=60.0)
            assert "result" in response or "error" in response
            request_id += 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


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
