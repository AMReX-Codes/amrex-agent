#!/usr/bin/env python3
"""
AMReXAgent MCP Adapter.

Exposes thin functions that validate inputs and call service-layer wrappers.
Pattern: Follows foam-agent's mcp/adapter.py approach - thin validation layer.

This can be used with any MCP server runtime (stdio, HTTP, etc.).

Usage:
    # In Claude Code or Cursor - .mcprc.json
    {
      "mcpServers": {
        "pele-agent": {
          "command": "python",
          "args": ["/path/to/amrex_agent/mcp_server.py"],
          "env": {
            "AMREX_DATABASE_PATH": "/global/cfs/cdirs/mp111/.../database"
          }
        }
      }
    }

    # Or run standalone
    python mcp_server.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Import for MCP server
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("[WARN] MCP library not available. Install with: pip install mcp")

# Initialize AMReXAgent
try:
    from src.config import AMReXAgentConfig
    from src.services.analysis import AnalysisService
    from src.services.architect import ArchitectService
    from src.services.input_writer import InputWriterService
    from src.services.knowledge import PeleKnowledgeService
    from src.services.plan import SimulationPlan
    from src.services.run_local import LocalRunner
    from src.services.run_superfacility import SuperfacilityRunner
    from src.services.validation import ValidationService
    from src.services.visualization import VisualizationService
except ModuleNotFoundError:
    PELE_AGENT_ROOT = Path(__file__).parent
    sys.path.insert(0, str(PELE_AGENT_ROOT))
    from src.config import AMReXAgentConfig
    from src.services.analysis import AnalysisService
    from src.services.architect import ArchitectService
    from src.services.input_writer import InputWriterService
    from src.services.knowledge import PeleKnowledgeService
    from src.services.plan import SimulationPlan
    from src.services.run_local import LocalRunner
    from src.services.run_superfacility import SuperfacilityRunner
    from src.services.validation import ValidationService
    from src.services.visualization import VisualizationService

# ============================================================================
# MCP Adapter Functions (foam-agent pattern)
# Thin validation layer that calls services
# ============================================================================

# Global config (loaded once at startup)
config = AMReXAgentConfig()

print("[MCP] AMReXAgent starting...")
print(f"[MCP] Environment: {config.environment}")
print(f"[MCP] FAISS DB path: {config.faiss_db_path}")
print(f"[MCP] Knowledge base path: {config.knowledge_base_path}")

SIMULATION_PLAN_ESSENTIAL_FIELDS = {
    "selected_solver",
    "selected_case",
    "modifications",
    "reasoning",
    "baseline",
    "indexing_strategy",
    "solver_confidence",
    "baseline_confidence",
    "cbr_confidence",
    "used_llm",
}


def _filter_simulation_plan(plan_dict: dict[str, Any]) -> dict[str, Any]:
    """Return a curated SimulationPlan subset for MCP output."""
    return {key: plan_dict.get(key) for key in SIMULATION_PLAN_ESSENTIAL_FIELDS}


def _apply_config_overrides(
    base_config: AMReXAgentConfig,
    overrides: dict[str, Any] | None
) -> AMReXAgentConfig:
    """Return config with tool-scoped overrides applied."""
    if not overrides:
        return base_config

    updates = dict(overrides)
    if updates.get("output_dir") is not None:
        updates["output_dir"] = Path(updates["output_dir"])
    if updates.get("amrex_tools_path") is not None:
        updates["amrex_tools_path"] = Path(updates["amrex_tools_path"])

    return base_config.model_copy(update=updates)


def _select_runner(active_config: AMReXAgentConfig):
    """Select execution runner based on config environment."""
    environment = (active_config.environment or "").lower()
    if environment == "local":
        return LocalRunner(active_config)
    if environment in {"perlmutter", "mcp"}:
        return SuperfacilityRunner(active_config)
    if active_config.allow_local_run:
        return LocalRunner(active_config)
    return SuperfacilityRunner(active_config)


def mcp_query_knowledge(payload: dict) -> dict:
    """
    Query knowledge base (FAISS-first).

    Parameters
    ----------
    payload : Dict
        Request payload with ``question`` (required) and optional ``code``.

    Returns
    -------
    Dict
        Response with ``answer``, ``sources``, ``confidence``, and ``method``.
    """
    kb = PeleKnowledgeService(config)

    question = payload["question"]
    code = payload.get("code")  # Optional - will use default from config if not specified
    if not code:
        code = config.default_solver
    if not code:
        raise ValueError("No default solver configured for knowledge query")

    context = {"code": code} if code else None
    result = kb.query(question, context=context)

    return {
        "answer": result.get("answer", "No answer available"),
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", 0.0),
        "method": result.get("method", "unknown")
    }


def mcp_create_simulation_plan(payload: dict) -> dict:
    """
    Create a simulation plan and generate inputs.

    Parameters
    ----------
    payload : Dict
        Payload with ``prompt`` and optional ``output_dir`` and ``baseline_override``.

    Returns
    -------
    Dict
        Plan details and input writer outputs.
    """
    architect = ArchitectService(config)
    writer = InputWriterService(config)

    prompt = payload["prompt"]
    baseline_override = payload.get("baseline_override")
    strategy = payload.get("strategy")
    output_dir = payload.get("output_dir") or config.output_dir

    # Create plan via execute_planning
    plan = architect.execute_planning(
        user_prompt=prompt,
        baseline_override=baseline_override,
        strategy=strategy,
    )

    result = writer.apply_plan(
        selected_case=plan.selected_case,
        modifications=plan.modifications,
        baseline=plan.baseline or {},
        reasoning=plan.reasoning,
        output_dir=output_dir,
    )

    return {
        "selected_case": plan.selected_case,
        "modifications": plan.modifications,
        "reasoning": plan.reasoning,
        "baseline": plan.baseline,
        "indexing_strategy": plan.indexing_strategy,
        "run_directory": result.get("run_dir") or result.get("output_dir"),
        "inputs_file_path": result.get("inputs_path"),
        "modifications_applied": result.get("modifications_applied"),
        "status": result.get("status"),
        "requires_parameter_resolution": result.get("requires_parameter_resolution"),
        "unresolved_parameters": result.get("unresolved_parameters"),
        "available_schema_params": result.get("available_schema_params"),
        "suggested_params": result.get("suggested_params"),
        "resolution_guidance": result.get("resolution_guidance"),
    }


def mcp_create_proposed_modifications_with_plan(payload: dict) -> dict:
    """Create a simulation plan without applying it.

    Parameters
    ----------
    payload : Dict
        Payload with ``prompt`` and optional ``baseline_override``.

    Returns
    -------
    Dict
        Curated plan fields and optional full plan/schema.
    """
    architect = ArchitectService(config)

    prompt = payload["prompt"]
    baseline_override = payload.get("baseline_override")
    strategy = payload.get("strategy")
    include_full_plan = payload.get("include_full_plan", False)
    include_plan_schema = payload.get("include_plan_schema", False)

    plan = architect.execute_planning(
        user_prompt=prompt,
        baseline_override=baseline_override,
        strategy=strategy,
    )

    plan_dict = plan.to_dict()
    response = _filter_simulation_plan(plan_dict)

    if include_full_plan:
        response["plan_full"] = plan_dict
    if include_plan_schema:
        response["plan_schema"] = SimulationPlan.model_json_schema()

    return response


def mcp_select_baseline_case(payload: dict) -> dict:
    """Select baseline case using 5-bucket scoring.

    Parameters
    ----------
    payload : Dict
        Payload with ``prompt`` and optional ``code`` and ``top_k``.

    Returns
    -------
    Dict
        Baseline selection details and confidence.
    """
    architect = ArchitectService(config)

    prompt = payload["prompt"]
    code = payload.get("code")  # Optional - will use default from config if not specified
    if not code:
        code = config.default_solver
    if not code:
        raise ValueError("No default solver configured for baseline selection")
    payload.get("top_k", 5)

    # Use architect's baseline selection
    baseline = architect._select_baseline(
        user_prompt=prompt,
        requirements={"code": code}
    )

    if not baseline:
        return {
            "selected_case": "",
            "baseline": {},
            "baseline_confidence": 0.0,
            "reasoning": "No baseline selected"
        }

    case_path = baseline.get("path", "")
    repo_path = baseline.get("repo_path")
    local_path = ""
    if repo_path and case_path:
        local_path = str(Path(repo_path) / case_path)

    return {
        "selected_case": case_path,
        "baseline": {
            "code_name": baseline.get("code") or baseline.get("code_name", ""),
            "repo_path": repo_path or "",
            "case_path": case_path,
            "local_path": local_path,
        },
        "baseline_confidence": baseline.get("match_score", 0.0),
        "reasoning": baseline.get("match_rationale", "")
    }


def mcp_validate_inputs(payload: dict) -> dict:
    """Validate AMReX inputs file.

    Parameters
    ----------
    payload : Dict
        Payload with ``inputs_file_path`` or ``inputs_path``.

    Returns
    -------
    Dict
        Validation results with errors and warnings.
    """
    from amrex_tools import parse_pele_inputs

    validator = ValidationService(config)
    inputs_path = payload.get("inputs_file_path") or payload.get("inputs_path")
    if not inputs_path:
        raise ValueError("Missing inputs_file_path")

    # Parse inputs file
    inputs_dict = parse_pele_inputs(inputs_path)

    # Validate
    result = validator.validate_config(inputs_dict)

    return {
        "valid": result.get("valid", False),
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", [])
    }


def mcp_setup_job(payload: dict) -> dict:
    """Set up job directory for simulation run.

    Parameters
    ----------
    payload : Dict
        Payload with ``inputs_file_path`` and ``case_dir`` plus optional ``job_name``.

    Returns
    -------
    Dict
        Job setup details including run directory and submit script.
    """
    from src.services.run_superfacility import SuperfacilityRunner

    runner = SuperfacilityRunner(config)

    inputs_path = payload.get("inputs_file_path") or payload.get("inputs_path")
    if not inputs_path:
        raise ValueError("Missing inputs_file_path")
    case_dir = payload["case_dir"]
    job_name = payload.get("job_name", "amrex_agent")

    # Setup job
    setup_result = runner.setup_job(
        inputs_path=inputs_path,
        case_dir=case_dir,
        base_name=job_name
    )

    # Generate submit script (dry-run)
    submit_result = runner.submit(
        run_directory=setup_result["run_dir"],
        nodes=1,
        walltime="00:10:00",
        qos="debug",
        dry_run=True
    )

    return {
        "run_directory": setup_result["run_dir"],
        "executable_path": setup_result["executable"],
        "submit_script_path": submit_result["script_path"]
    }


def mcp_run_simulation(payload: dict) -> dict:
    """
    Run simulation via local or superfacility runner (dry-run preferred).

    Parameters
    ----------
    payload : Dict
        Execution payload with inputs paths, case dir, and submission config.

    Returns
    -------
    Dict
        Execution status and output paths.
    """
    config_overrides = payload.get("config_overrides")
    active_config = _apply_config_overrides(config, config_overrides)
    runner = _select_runner(active_config)

    inputs_path = payload.get("inputs_file_path") or payload.get("inputs_path")
    case_dir = payload.get("case_dir")
    executable_path = payload.get("executable_path")
    base_name = payload.get("base_name")

    if not inputs_path and not case_dir:
        raise ValueError("Must provide inputs_file_path or case_dir")

    submit_config = payload.get("submit") or {}
    monitor_config = payload.get("monitor") or {}

    nodes = submit_config.get("nodes", 1)
    walltime = submit_config.get("walltime", "00:10:00")
    account = submit_config.get("account")
    qos = submit_config.get("qos", "regular")
    constraint = submit_config.get("constraint", "gpu&hbm40g")
    system = submit_config.get("system", "perlmutter")
    dry_run = submit_config.get("dry_run", True)

    setup_result: dict[str, Any] = {}
    dry_run_steps: list[str] = []

    if inputs_path and not case_dir:
        inputs_candidate = Path(inputs_path)
        if inputs_candidate.exists() and inputs_candidate.is_file():
            case_dir = str(inputs_candidate.parent)

    if inputs_path and case_dir and not executable_path:
        exe_files = list(Path(case_dir).glob("*.ex"))
        if exe_files:
            executable_path = str(exe_files[0])

    if dry_run and executable_path is None and case_dir:
        dry_run_steps.append(
            f"Skipping compile in {case_dir}: make USE_MPI=TRUE"
        )
        dry_run_steps.append(
            f"Skipping run directory setup under {active_config.output_dir}"
        )
        if isinstance(runner, LocalRunner):
            dry_run_steps.append(
                f"Skipping local run: mpirun -np {nodes} <executable> inputs"
            )
        else:
            dry_run_steps.append(
                "Skipping submission: sbatch <run_dir>/submit.sh"
            )
        return {
            "run_directory": None,
            "inputs_file_path": inputs_path,
            "executable_path": None,
            "job_id": None,
            "job_status": "completed",
            "script_path": None,
            "method": "dry_run",
            "dry_run_steps": dry_run_steps,
        }

    if not setup_result:
        setup_result = runner.setup_job(
            inputs_path=inputs_path,
            case_dir=case_dir,
            executable_path=executable_path,
            base_name=base_name,
            output_dir=active_config.output_dir,
        )

    job_result = runner.submit(
        run_directory=setup_result["run_dir"],
        nodes=nodes,
        walltime=walltime,
        account=account,
        qos=qos,
        constraint=constraint,
        system=system,
        dry_run=dry_run,
    )

    if monitor_config.get("enabled") and not dry_run and hasattr(runner, "monitor"):
        job_result["final_state"] = runner.monitor(
            job_id=job_result.get("job_id", ""),
            method=job_result.get("method", "sbatch"),
            poll_interval=monitor_config.get("poll_interval", 10),
            max_polls=monitor_config.get("max_polls", 30),
        )

    job_status = job_result.get("job_status")
    if not job_status:
        if job_result.get("method") == "dry_run":
            job_status = "completed"
        elif job_result.get("job_id"):
            job_status = "queued"
        else:
            job_status = "unknown"

    response = {
        "run_directory": setup_result.get("run_dir"),
        "inputs_file_path": setup_result.get("inputs") or inputs_path,
        "executable_path": setup_result.get("executable") or executable_path,
        "job_id": job_result.get("job_id"),
        "job_status": job_status,
        "script_path": job_result.get("script_path"),
        "method": job_result.get("method"),
    }
    if dry_run and dry_run_steps:
        response["dry_run_steps"] = dry_run_steps
    return response


def mcp_analyze_results(payload: dict) -> dict:
    """
    Analyze run directory logs and return normalized status.

    Parameters
    ----------
    payload : Dict
        Payload with ``run_directory`` and optional overrides.

    Returns
    -------
    Dict
        Analysis status and report.
    """
    run_dir = payload.get("run_directory")
    if not run_dir:
        raise ValueError("Missing run_directory")

    config_overrides = payload.get("config_overrides")
    active_config = _apply_config_overrides(config, config_overrides)

    if not active_config.analysis_always_enabled:
        return {
            "job_status": "completed",
            "analysis_report": {
                "status": "skipped",
                "message": "Analysis disabled by config override"
            }
        }

    include_visual = payload.get("include_visual", False)
    analyzer = AnalysisService(active_config)
    report = analyzer.analyze_simulation(Path(run_dir), include_visual=include_visual)

    status = report.get("status", "unknown")
    status_map = {
        "success": "completed",
        "failed": "failed",
        "unstable": "unstable",
    }
    job_status = status_map.get(status, "failed")

    return {
        "job_status": job_status,
        "analysis_report": report
    }


def mcp_generate_visualizations(payload: dict) -> dict:
    """
    Generate visualization images for a run directory.

    Parameters
    ----------
    payload : Dict
        Payload with ``run_directory`` and visualization settings.

    Returns
    -------
    Dict
        Visualization results and generated image paths.
    """
    run_dir = payload.get("run_directory")
    if not run_dir:
        raise ValueError("Missing run_directory")

    config_overrides = payload.get("config_overrides")
    active_config = _apply_config_overrides(config, config_overrides)

    output_dir = payload.get("output_dir")
    visualization_config = payload.get("visualization_config")

    viz = VisualizationService(active_config)

    output_path = output_dir or str(Path(run_dir) / "visualization")
    plotfiles = viz.find_plotfiles(run_dir)

    try:
        images = viz.create_standard_plots(
            run_dir=run_dir,
            output_dir=output_path,
            vis_config=visualization_config,
        )
        viz_status = "success" if images else "skipped"
    except Exception as exc:
        return {
            "visualization_status": "failed",
            "visualization_backend": viz.backend.__class__.__name__,
            "visualization_images": [],
            "visualization_metadata": {
                "error": str(exc)
            }
        }

    return {
        "visualization_status": viz_status,
        "visualization_backend": viz.backend.__class__.__name__,
        "visualization_images": [str(image) for image in images],
        "visualization_metadata": {
            "plotfile_count": len(plotfiles),
            "output_dir": output_path,
            "plots_requested": visualization_config.get("plots") if visualization_config else [],
        }
    }


# ============================================================================
# MCP Server (if MCP library available)
# ============================================================================

if not HAS_MCP:
    print("[ERROR] MCP library required for server mode")
    print("        Install with: pip install mcp")
    sys.exit(1)

app = Server("pele-agent")


@app.list_tools()
async def list_tools():
    """List available AMReXAgent tools.

    Returns
    -------
    List[Dict[str, Any]]
        Tool specifications for the MCP client.
    """
    available_solvers = config.available_solvers
    return [
        {
            "name": "query_knowledge",
            "description": "Query AMReX knowledge base for simulation guidance. "
                          "Uses FAISS vector search first, falls back to LLM if needed.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about AMReX simulations"
                    },
                    "code": {
                        "type": "string",
                        "enum": available_solvers,
                        "description": "Target AMReX code (optional, defaults to config default solver)"
                    }
                },
                "required": ["question"]
            }
        },
        {
            "name": "create_simulation_plan",
            "description": "Create a simulation plan and generate an inputs file using InputWriter. "
                          "Executes planning, applies modifications, and writes to output_dir.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Natural language description of simulation requirements"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Output directory for inputs file (optional, defaults to config.output_dir)"
                    },
                    "baseline_override": {
                        "type": "string",
                        "description": "Explicit baseline path (optional)"
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["simple", "hierarchical"],
                        "description": "Planning strategy override (optional)"
                    }
                },
                "required": ["prompt"]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "selected_case": {
                        "type": "string",
                        "description": "Selected baseline case path"
                    },
                    "modifications": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "description": "Proposed parameter modifications"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Planning rationale"
                    },
                    "baseline": {
                        "type": "object",
                        "description": "Baseline metadata (code_name, repo_path, case_path, local_path)"
                    },
                    "indexing_strategy": {
                        "type": "string",
                        "description": "Strategy used for planning"
                    },
                    "run_directory": {
                        "type": "string",
                        "description": "Run directory containing generated inputs"
                    },
                    "inputs_file_path": {
                        "type": "string",
                        "description": "Generated inputs file path"
                    },
                    "modifications_applied": {
                        "type": "integer",
                        "description": "Number of modifications applied"
                    },
                    "status": {
                        "type": "string",
                        "description": "Input writer status"
                    },
                    "requires_parameter_resolution": {
                        "type": "boolean",
                        "description": "Whether unresolved parameters remain"
                    },
                    "unresolved_parameters": {
                        "type": "array",
                        "description": "List of unresolved parameter entries"
                    },
                    "available_schema_params": {
                        "type": "array",
                        "description": "Available schema parameters for mapping"
                    },
                    "suggested_params": {
                        "type": "object",
                        "description": "Suggested parameter remappings"
                    },
                    "resolution_guidance": {
                        "type": "string",
                        "description": "Human-readable guidance for parameter resolution"
                    }
                }
            }
        },
        {
            "name": "create_proposed_modifications_with_plan",
            "description": "Create a simulation plan without writing inputs. "
                          "Returns curated SimulationPlan fields with optional full plan/schema.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Natural language description of simulation requirements"
                    },
                    "baseline_override": {
                        "type": "string",
                        "description": "Explicit baseline path (optional)"
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["simple", "hierarchical"],
                        "description": "Planning strategy override (optional)"
                    },
                    "include_full_plan": {
                        "type": "boolean",
                        "description": "Include the full SimulationPlan payload"
                    },
                    "include_plan_schema": {
                        "type": "boolean",
                        "description": "Include SimulationPlan JSON schema"
                    }
                },
                "required": ["prompt"]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "selected_solver": {"type": "string"},
                    "selected_case": {"type": "string"},
                    "modifications": {"type": "array"},
                    "reasoning": {"type": "string"},
                    "baseline": {"type": "object"},
                    "indexing_strategy": {"type": "string"},
                    "solver_confidence": {"type": "number"},
                    "baseline_confidence": {"type": "number"},
                    "cbr_confidence": {"type": "number"},
                    "used_llm": {"type": "boolean"},
                    "plan_full": {"type": "object"},
                    "plan_schema": {"type": "object"}
                }
            }
        },
        {
            "name": "select_baseline_case",
            "description": "Find and score baseline cases for a given simulation requirement. "
                          "Uses 5-bucket scoring with FAISS semantic search.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Simulation description for baseline selection"
                    },
                    "code": {
                        "type": "string",
                        "enum": available_solvers,
                        "description": "Target AMReX code (optional, defaults to config default solver)"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top cases to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["prompt"]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "selected_case": {
                        "type": "string",
                        "description": "Selected baseline case path"
                    },
                    "baseline": {
                        "type": "object",
                        "description": "Baseline metadata (code_name, repo_path, case_path, local_path)"
                    },
                    "baseline_confidence": {
                        "type": "number",
                        "description": "Baseline selection confidence score"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Selection rationale"
                    }
                }
            }
        },
        {
            "name": "validate_inputs",
            "description": "Validate an AMReX inputs file for common errors and issues.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "inputs_file_path": {
                        "type": "string",
                        "description": "Path to inputs file to validate"
                    }
                },
                "required": ["inputs_file_path"]
            }
        },
        {
            "name": "setup_job",
            "description": "Setup job directory for HPC submission (via Superfacility API). "
                          "Creates run directory, copies inputs and executable, generates SLURM script.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "inputs_file_path": {
                        "type": "string",
                        "description": "Path to inputs file"
                    },
                    "case_dir": {
                        "type": "string",
                        "description": "Path to baseline case directory"
                    },
                    "job_name": {
                        "type": "string",
                        "description": "Job name prefix (optional, default: amrex_agent)"
                    }
                },
                "required": ["inputs_file_path", "case_dir"]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_directory": {
                        "type": "string",
                        "description": "Run directory path"
                    },
                    "executable_path": {
                        "type": "string",
                        "description": "Executable path used in the run"
                    },
                    "submit_script_path": {
                        "type": "string",
                        "description": "Path to generated submit script"
                    }
                }
            }
        },
        {
            "name": "run_simulation",
            "description": "Run an AMReX simulation by setting up a run directory and submitting it "
                          "via SuperfacilityRunner or LocalRunner based on config.environment.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "inputs_file_path": {
                        "type": "string",
                        "description": "Path to inputs file (required if case_dir not provided)"
                    },
                    "case_dir": {
                        "type": "string",
                        "description": "Baseline case directory (required if inputs_file_path not provided)"
                    },
                    "executable_path": {
                        "type": "string",
                        "description": "Path to an existing executable (optional)"
                    },
                    "base_name": {
                        "type": "string",
                        "description": "Run directory prefix (optional, defaults to config.default_solver)"
                    },
                    "submit": {
                        "type": "object",
                        "properties": {
                            "nodes": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Number of nodes for submission (default: 1)"
                            },
                            "walltime": {
                                "type": "string",
                                "description": "Walltime in HH:MM:SS (default: 00:10:00)"
                            },
                            "account": {
                                "type": "string",
                                "description": "NERSC account override (optional)"
                            },
                            "qos": {
                                "type": "string",
                                "description": "Queue/QOS (default: regular)"
                            },
                            "constraint": {
                                "type": "string",
                                "description": "Node constraint (default: gpu&hbm40g)"
                            },
                            "system": {
                                "type": "string",
                                "description": "Target system name (default: perlmutter)"
                            },
                            "dry_run": {
                                "type": "boolean",
                                "description": "Generate submission script without submitting"
                            }
                        }
                    },
                    "monitor": {
                        "type": "object",
                        "properties": {
                            "enabled": {
                                "type": "boolean",
                                "description": "Monitor job to completion"
                            },
                            "poll_interval": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Seconds between checks (default: 10)"
                            },
                            "max_polls": {
                                "type": "integer",
                                "minimum": 1,
                                "description": "Maximum number of checks (default: 30)"
                            }
                        }
                    },
                    "config_overrides": {
                        "type": "object",
                        "properties": {
                            "environment": {
                                "type": "string",
                                "enum": ["local", "perlmutter", "mcp"],
                                "description": "Execution environment override"
                            },
                            "allow_local_run": {
                                "type": "boolean",
                                "description": "Allow local execution when Superfacility is unavailable"
                            },
                            "output_dir": {
                                "type": "string",
                                "description": "Base output directory for run directories"
                            },
                            "superfacility_account": {
                                "type": "string",
                                "description": "Default NERSC account to use for submission"
                            }
                        },
                        "additionalProperties": False
                    }
                },
                "anyOf": [
                    {"required": ["inputs_file_path"]},
                    {"required": ["case_dir"]}
                ]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_directory": {
                        "type": "string",
                        "description": "Run directory containing inputs and executable"
                    },
                    "inputs_file_path": {
                        "type": "string",
                        "description": "Inputs file path used for the run"
                    },
                    "executable_path": {
                        "type": "string",
                        "description": "Executable used for the run"
                    },
                    "job_id": {
                        "type": "string",
                        "description": "Submitted job ID (absent for dry_run)"
                    },
                    "job_status": {
                        "type": "string",
                        "description": "Submission status (e.g., submitted, dry_run, failed)"
                    },
                    "script_path": {
                        "type": "string",
                        "description": "Path to generated submission script"
                    },
                    "method": {
                        "type": "string",
                        "description": "Submission method (api, sbatch, dry_run)"
                    }
                }
            }
        },
        {
            "name": "analyze_results",
            "description": "Analyze AMReX log output in a run directory and return status, issues, "
                          "warnings, and performance metrics.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_directory": {
                        "type": "string",
                        "description": "Run directory containing log files"
                    },
                    "include_visual": {
                        "type": "boolean",
                        "description": "Include visual diagnostics (default: false)"
                    },
                    "config_overrides": {
                        "type": "object",
                        "properties": {
                            "analysis_always_enabled": {
                                "type": "boolean",
                                "description": "Override analysis toggle (default: true)"
                            }
                        },
                        "additionalProperties": False
                    }
                },
                "required": ["run_directory"]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "job_status": {
                        "type": "string",
                        "description": "Canonical status: completed, failed, unstable"
                    },
                    "analysis_report": {
                        "type": "object",
                        "description": "Full analysis report payload"
                    }
                }
            }
        },
        {
            "name": "generate_visualizations",
            "description": "Generate visualization images from AMReX plotfiles in a run directory "
                          "using the configured visualization backend.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_directory": {
                        "type": "string",
                        "description": "Run directory containing plotfiles"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for visualization outputs (defaults to run_directory/visualization)"
                    },
                    "analysis_report": {
                        "type": "object",
                        "description": "Optional analysis report used for adaptive plot selection"
                    },
                    "visualization_config": {
                        "type": "object",
                        "properties": {
                            "plots": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "description": "Plot type (e.g., slice)"
                                        },
                                        "field": {
                                            "type": "string",
                                            "description": "Field name to plot (e.g., Temp, density)"
                                        },
                                        "axis": {
                                            "type": "string",
                                            "description": "Slice axis (x, y, z)"
                                        },
                                        "colormap": {
                                            "type": "string",
                                            "description": "Colormap name (backend-specific)"
                                        },
                                        "vmin": {
                                            "type": "number",
                                            "description": "Minimum value for scaling"
                                        },
                                        "vmax": {
                                            "type": "number",
                                            "description": "Maximum value for scaling"
                                        },
                                        "max_level": {
                                            "type": "integer",
                                            "description": "Maximum AMR level to plot"
                                        }
                                    },
                                    "required": ["type", "field", "axis"]
                                }
                            }
                        }
                    },
                    "config_overrides": {
                        "type": "object",
                        "properties": {
                            "visualization_backend": {
                                "type": "string",
                                "description": "Backend selection (auto, amrex_tools, pyamrex, yt)"
                            },
                            "amrex_tools_path": {
                                "type": "string",
                                "description": "Override path to AMReX Tools/Plotfile directory"
                            },
                            "container_mode": {
                                "type": "boolean",
                                "description": "Enable container extraction/rendering split"
                            }
                        },
                        "additionalProperties": False
                    }
                },
                "required": ["run_directory"]
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "visualization_status": {
                        "type": "string",
                        "description": "Visualization status (success, failed, skipped)"
                    },
                    "visualization_backend": {
                        "type": "string",
                        "description": "Backend used (AMReXToolsBackend, YtBackend, etc.)"
                    },
                    "visualization_images": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Generated image paths"
                    },
                    "visualization_metadata": {
                        "type": "object",
                        "description": "Metadata including plotfile count and fields plotted"
                    }
                }
            }
        }
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> Any:
    """Handle tool calls from MCP client.

    Uses adapter functions (foam-agent pattern) for thin validation layer.

    Args:
        name: Tool name to invoke
        arguments: Tool arguments from client

    Returns
    -------
        Tool execution result
    """
    try:
        # Dispatch to adapter functions
        if name == "query_knowledge":
            return mcp_query_knowledge(arguments)

        elif name == "create_simulation_plan":
            return mcp_create_simulation_plan(arguments)

        elif name == "create_proposed_modifications_with_plan":
            return mcp_create_proposed_modifications_with_plan(arguments)

        elif name == "select_baseline_case":
            return mcp_select_baseline_case(arguments)

        elif name == "validate_inputs":
            return mcp_validate_inputs(arguments)

        elif name == "setup_job":
            return mcp_setup_job(arguments)

        elif name == "run_simulation":
            return mcp_run_simulation(arguments)

        elif name == "analyze_results":
            return mcp_analyze_results(arguments)

        elif name == "generate_visualizations":
            return mcp_generate_visualizations(arguments)

        else:
            return {
                "error": f"Unknown tool: {name}"
            }

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


async def main():
    """Start the MCP server."""
    print("[MCP] Starting stdio server...")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream)


if __name__ == "__main__":
    print("[MCP] AMReXAgent MCP Server")
    print(f"[MCP] Environment: {config.environment}")
    print(f"[MCP] FAISS indices: {config.faiss_db_path}")
    print("[MCP] Starting...")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[MCP] Server stopped by user")
    except Exception as e:
        print(f"[MCP] Server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
