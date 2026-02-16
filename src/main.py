"""Pele agent CLI entry point and workflow orchestration."""

# ========================================
# Path Setup (allows direct execution)
# ========================================
# Add project root to path when running directly
# ========================================
# COMPONENT 12f: CLI ENTRY POINT
# ========================================
import argparse
import contextlib
import json
import logging
import os
import shutil
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.config import AMReXAgentConfig, load_config
from src.models import GraphState
from src.nodes import (
    analysis_node,  # Phase 4
    architect_node,
    input_writer_node,
    reviewer_node,
    runner_node,
    visualization_node,  # Phase 4
)
from src.router_func import (
    route_after_analysis,  # Phase 4
    route_after_reviewer,
    route_after_runner,  # Phase 4
)


class RedactingFilter(logging.Filter):
    """Redact known secrets from log messages."""

    _bearer_re = None

    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self._secrets = [s for s in secrets if s]
        if RedactingFilter._bearer_re is None:
            import re
            RedactingFilter._bearer_re = re.compile(r"(Authorization:\\s*Bearer\\s+)[^\\s]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Redact secrets and bearer tokens from a log record.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to sanitize in-place.

        Returns
        -------
        bool
            True to keep the record in the logging pipeline.
        """
        try:
            msg = record.getMessage()
            if self._secrets:
                for secret in self._secrets:
                    if secret and secret in msg:
                        msg = msg.replace(secret, "[REDACTED]")
            msg = RedactingFilter._bearer_re.sub(r"\\1[REDACTED]", msg)
            record.msg = msg
            record.args = ()
        except Exception:
            pass
        return True


class ColorFormatter(logging.Formatter):
    """Optional ANSI color formatting for log levels."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[31;1m",
    }
    RESET = "\033[0m"

    def __init__(self, *args, use_color: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record, optionally applying ANSI colors.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to format.

        Returns
        -------
        str
            Formatted log message.
        """
        msg = super().format(record)
        if not self._use_color:
            return msg
        color = self.COLORS.get(record.levelname, "")
        if not color:
            return msg
        return f"{color}{msg}{self.RESET}"


class TeeStream:
    """Duplicate writes to a file while preserving stdout/stderr."""

    _ansi_re = None

    def __init__(self, primary: Any, secondary: Any, strip_secondary: bool = False) -> None:
        self._primary = primary
        self._secondary = secondary
        self._strip_secondary = strip_secondary
        if strip_secondary and TeeStream._ansi_re is None:
            import re
            TeeStream._ansi_re = re.compile(r"\x1b\\[[0-9;]*m")

    def write(self, data: str) -> None:
        """
        Write data to the primary stream and optionally to the secondary.

        Parameters
        ----------
        data : str
            Data to write to the streams.

        Returns
        -------
        None
            This method writes to streams in-place.
        """
        self._primary.write(data)
        if self._strip_secondary and TeeStream._ansi_re:
            data = TeeStream._ansi_re.sub("", data)
        with contextlib.suppress(ValueError):
            # Secondary may be closed during interpreter shutdown.
            self._secondary.write(data)

    def flush(self) -> None:
        """
        Flush the primary and secondary streams.

        Parameters
        ----------
        None
            This method does not accept parameters.

        Returns
        -------
        None
            This method flushes streams in-place.
        """
        self._primary.flush()
        with contextlib.suppress(ValueError):
            # Secondary may be closed during interpreter shutdown.
            self._secondary.flush()

    def isatty(self) -> bool:
        """
        Report whether the primary stream is a TTY.

        Parameters
        ----------
        None
            This method does not accept parameters.

        Returns
        -------
        bool
            True if the primary stream is a TTY.
        """
        return getattr(self._primary, "isatty", lambda: False)()


def _should_color_logs(mode: str) -> bool:
    """
    Determine whether colorized logging should be enabled.

    Parameters
    ----------
    mode : str
        Color mode setting ("auto", "always", "never").

    Returns
    -------
    bool
        True when color output should be used.
    """
    if os.getenv("NO_COLOR"):
        return False
    if mode == "always":
        return True
    if mode == "never":
        return False
    return sys.stderr.isatty()


def setup_logging(parsed_args: argparse.Namespace) -> None:
    """
    Configure logging based on parsed CLI arguments.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    None
        This function configures global logging state.
    """
    log_level = logging.DEBUG if parsed_args.verbose else logging.INFO
    use_color = _should_color_logs(parsed_args.color_logs)

    formatter = ColorFormatter(
        fmt='%(levelname)s: %(message)s' if parsed_args.verbose else '%(message)s',
        use_color=use_color,
    )

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(formatter)

    secrets = [
        os.getenv("CBORG_API_KEY"),
        os.getenv("ALCF_API_KEY"),
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("SUPERFACILITY_CLIENT_ID"),
        os.getenv("SUPERFACILITY_SECRET"),
        os.getenv("NERSC_API_TOKEN"),
        os.getenv("SFAPI_TOKEN"),
    ]
    redactor = RedactingFilter(secrets)
    handler.addFilter(redactor)

    logging.basicConfig(
        level=log_level,
        handlers=[handler],
        force=True,
    )

    for name in ("httpx", "openai", "anthropic"):
        logging.getLogger(name).addFilter(redactor)


def start_log_capture(parsed_args: argparse.Namespace) -> dict[str, Any] | None:
    """
    Start capturing console output to a timestamped log file.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    dict or None
        Capture metadata dict when enabled, otherwise None.
    """
    if not getattr(parsed_args, "save_log", False):
        return None
    base_dir = Path(parsed_args.output_dir) if parsed_args.output_dir else Path("output")
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = base_dir / f"console_{timestamp}.log"
    log_file = log_path.open("w")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = TeeStream(original_stdout, log_file, strip_secondary=True)
    sys.stderr = TeeStream(original_stderr, log_file, strip_secondary=True)
    return {
        "path": log_path,
        "file": log_file,
        "stdout": original_stdout,
        "stderr": original_stderr,
    }


def finalize_log_capture(
    capture: dict[str, Any] | None,
    result: dict[str, Any] | None = None,
) -> None:
    """
    Restore console streams and persist captured logs if available.

    Parameters
    ----------
    capture : dict or None
        Capture metadata returned from ``start_log_capture``.
    result : dict, optional
        Final workflow result for locating the run directory.

    Returns
    -------
    None
        This function restores streams and closes file handles.
    """
    if not capture:
        return
    try:
        sys.stdout = capture["stdout"]
        sys.stderr = capture["stderr"]
    except Exception:
        pass
    try:
        if result and "run_directory" in result:
            run_dir = Path(result["run_directory"])
            shutil.copy2(capture["path"], run_dir / "console.log")
    except Exception:
        pass
    with contextlib.suppress(Exception):
        capture["file"].close()


def baseline_override_help() -> str:
    """
    Build the help string for the baseline override CLI option.

    Parameters
    ----------
    None
        This function does not accept parameters.

    Returns
    -------
    str
        Help text describing the baseline override option.
    """
    try:
        config = AMReXAgentConfig()
        if hasattr(config, "get_code_registry"):
            registry = config.get_code_registry()
            codes = sorted(registry.keys())
            if codes:
                return (
                    "Force specific baseline case (e.g., <Solver>/Exec/RegTests/<Case>). "
                    f"Known solvers: {', '.join(codes)}"
                )
    except Exception:
        pass
    return "Force specific baseline case (e.g., <Solver>/Exec/RegTests/<Case>)"


def parse_arguments(args: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command line arguments for the CLI.

    Call context: CLI entry point.

    Parameters
    ----------
    args : list[str] or None, optional
        Optional argument list for testing; defaults to ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed CLI arguments.
    """
    parser = argparse.ArgumentParser(
        prog='amrex_agent',
        description='AMReXAgent: AI-driven simulation setup for AMReX codes.'
    )

    # Input Source (Mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--prompt',
        type=str,
        help='Natural language simulation request (inline string)'
    )
    group.add_argument(
        '--prompt-path', '--prompt_path',  # Support both styles
        type=str,
        dest='prompt_path',
        help='Path to text file containing request (use "-" for stdin)'
    )

    # Configuration Overrides
    parser.add_argument(
        '--output-dir', '--output_dir',  # Support both styles
        type=str,
        dest='output_dir',
        help='Directory for generated simulation files'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to custom configuration file'
    )
    parser.add_argument(
        '--environment',
        type=str,
        choices=['local', 'perlmutter', 'mcp'],
        help='Override environment detection (local, perlmutter, mcp)'
    )

    # Flags
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output result as JSON'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Generate scripts but do not submit job (deprecated; use --run-mode dry)'
    )
    parser.add_argument(
        '--run-mode',
        choices=['dry', 'stage', 'submit', 'full'],
        help='Run execution strategy: dry, stage, submit, full'
    )
    parser.add_argument(
        '--preconfirm',
        action='store_true',
        help='Pause for a pre-confirmation gate before validation'
    )
    parser.add_argument(
        '--llm-gate-strategy',
        choices=[
            'off',
            'default',
            'feedback',
            'gate-major',
            'gate-all',
            'gate-major-prompt',
            'gate-all-prompt',
        ],
        dest='llm_gate_strategy',
        help='LLM prompt gate strategy: off, default, feedback, gate-major, gate-all'
    )
    parser.add_argument(
        '--save-workflow',
        action='store_true',
        help='Save workflow_history.json to run directory'
    )
    parser.add_argument(
        '--save-transcript',
        action='store_true',
        help='Save agent reasoning transcript to run directory'
    )
    parser.add_argument(
        '--save-log',
        action='store_true',
        help='Save full console output to a log file'
    )
    parser.add_argument(
        '--color-logs',
        choices=['auto', 'always', 'never'],
        default='auto',
        help='Colorize log output (default: auto)'
    )
    parser.add_argument(
        '--indexing-strategy', '--indexing_strategy',
        type=str,
        choices=['simple', 'hierarchical', 'override_static'],
        dest='indexing_strategy',
        help='Indexing strategy: simple (single FAISS), hierarchical (L0/L1/L2), or override_static (no embeddings)'
    )
    parser.add_argument(
        '--inputs-file-strategy', '--inputs_file_strategy',
        choices=['oldest', 'newest', 'smallest', 'llm_compare', 'override'],
        default='newest',
        dest='inputs_file_strategy',
        help='Inputs file selection: oldest, newest, smallest, llm_compare, override'
    )
    parser.add_argument(
        '--remap-strategy', '--remap_strategy',
        choices=['last_write', 'append'],
        default=None,
        dest='remap_strategy',
        help='Remap duplicate array strategy: last_write (default), append'
    )
    parser.add_argument(
        '--inputs-file-override', '--inputs_file_override',
        type=str,
        default=None,
        dest='inputs_file_override',
        help='Explicit inputs file to use (absolute path or relative to case dir)'
    )
    parser.add_argument(
        '--baseline-override', '--baseline_override',
        type=str,
        default=None,
        dest='baseline_override',
        help=baseline_override_help()
    )
    parser.add_argument(
        '--baseline-switch-after-retries', '--baseline_switch_after_retries',
        type=int,
        default=None,
        dest='baseline_switch_after_retries',
        help='Retry attempts to fix inputs/mods before switching baseline directory (default: 3)'
    )
    parser.add_argument(
        '--run-serial',
        action='store_true',
        help='Run locally without MPI (use serial executable if available)'
    )
    parser.add_argument(
        '--run-ntasks', '--run_ntasks',
        type=int,
        default=None,
        dest='mpi_ranks',
        help='Local run tasks (mpirun -np)'
    )

    return parser.parse_args(args)


def load_prompt_content(args: argparse.Namespace) -> str:
    """
    Load a prompt from inline text, a file, or stdin.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments.

    Returns
    -------
    str
        Prompt text with surrounding whitespace stripped.
    """
    import sys

    if args.prompt:
        return args.prompt

    if args.prompt_path == "-":
        return sys.stdin.read().strip()

    path = Path(args.prompt_path)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    return path.read_text().strip()


def _warn_if_schema_missing(config: AMReXAgentConfig, baseline_override: str | None) -> None:
    """Warn if schema is missing for the baseline override solver."""
    if not baseline_override:
        return

    parts = baseline_override.split("/")
    if not parts:
        return

    try:
        code_registry = config.get_code_registry()
    except Exception:
        return

    code_lookup = {key.lower(): key for key in code_registry}
    code_key = parts[0].lower()
    if code_key not in code_lookup:
        return

    solver_name = code_lookup[code_key]
    solver_config_class = code_registry.get(solver_name)
    if not solver_config_class:
        return

    schema_dir = config.amrex_agent_root / "database/schemas"
    pattern = getattr(solver_config_class, "schema_pattern", f"{solver_name.lower()}_schema_*.json")
    if list(schema_dir.glob(pattern)):
        return

    repo_root = None
    if hasattr(config, "repositories"):
        repo_root = config.repositories.get(solver_name)
    solver_flag = solver_name.lower()
    repo_arg = repo_root or "<path-to-repo>"
    schema_cmd = f"python database/scripts/build_schema.py {repo_arg} --solver {solver_flag}"
    logging.getLogger(__name__).warning("Schema missing for %s. Run: %s", solver_name, schema_cmd)


def main(args: list[str] | None = None) -> None:
    """
    Run the AMReXAgent CLI workflow.

    Call context: CLI entry point.

    Parameters
    ----------
    args : list[str] or None, optional
        Optional argument list for testing; defaults to ``sys.argv``.

    Returns
    -------
    None
        This function exits the process based on workflow status.
    """
    import sys

    try:
        parsed_args = parse_arguments(args)
    except SystemExit:
        raise

    # Setup Logging
    capture = start_log_capture(parsed_args)
    setup_logging(parsed_args)
    result = None

    try:
        # Load Configuration
        config_path = Path(parsed_args.config) if parsed_args.config else None
        config = load_config(config_path)
        disabled_validators_env = os.getenv("PELE_DISABLED_VALIDATORS")
        if disabled_validators_env:
            disabled = [v.strip() for v in disabled_validators_env.split(",") if v.strip()]
            config.disabled_validators = disabled

        if parsed_args.output_dir:
            config.output_dir = Path(parsed_args.output_dir)

        if parsed_args.run_mode:
            config.run_mode = parsed_args.run_mode
            config.dry_run = parsed_args.run_mode == "dry"
        elif parsed_args.dry_run:
            config.dry_run = True
            config.run_mode = "dry"

        if parsed_args.environment:
            config.environment = parsed_args.environment

        if parsed_args.preconfirm:
            config.preconfirm_gate = True

        if parsed_args.llm_gate_strategy:
            config.llm_gate_strategy = parsed_args.llm_gate_strategy

        if hasattr(parsed_args, 'indexing_strategy') and parsed_args.indexing_strategy:
            config.indexing_strategy = parsed_args.indexing_strategy

        if hasattr(parsed_args, 'inputs_file_strategy') and parsed_args.inputs_file_strategy:
            config.inputs_file_strategy = parsed_args.inputs_file_strategy
        if hasattr(parsed_args, 'inputs_file_override') and parsed_args.inputs_file_override:
            config.inputs_file_override = parsed_args.inputs_file_override
        if hasattr(parsed_args, 'remap_strategy') and parsed_args.remap_strategy:
            config.remap_strategy = parsed_args.remap_strategy

        if hasattr(parsed_args, 'baseline_override') and parsed_args.baseline_override:
            config.baseline_override = parsed_args.baseline_override
        if getattr(parsed_args, 'baseline_switch_after_retries', None) is not None:
            config.baseline_switch_after_retries = parsed_args.baseline_switch_after_retries
        if getattr(parsed_args, 'run_serial', False):
            config.use_mpi = False
        if getattr(parsed_args, 'mpi_ranks', None) is not None:
            if parsed_args.mpi_ranks < 1:
                raise ValueError("--run-ntasks must be >= 1")
            config.mpi_ranks = parsed_args.mpi_ranks

        _warn_if_schema_missing(config, getattr(parsed_args, "baseline_override", None))

        # Disable schema validator temporarily (modifications format issue)
        # config.disabled_validators = ["SchemaSyntaxValidator"]  # Re-enabled for parameter resolution

        # Load Prompt
        user_requirement = load_prompt_content(parsed_args)
        if not user_requirement:
            raise ValueError("Prompt cannot be empty")

        # Run Agent
        logger.debug("Starting AMReXAgent workflow...")
        result = run_agent(user_requirement, config)

        # Save metrics JSONL (if enabled)
        try:
            from src.utils.metrics import metrics_collector, metrics_extra

            if getattr(config, "metrics_enabled", True) and metrics_collector.events():
                summary = metrics_collector.build_workflow_summary()
                summary.update({
                    "job_status": result.get("job_status", "unknown"),
                    "iteration": result.get("iteration", 0),
                    "run_directory": result.get("run_directory"),
                })
                with metrics_extra(result.get("metrics_context") or None):
                    metrics_collector.record_event(
                        "workflow_summary",
                        summary,
                        stage="workflow",
                        node="main",
                        iteration=result.get("iteration", 0),
                    )
                if 'run_directory' in result:
                    run_dir = Path(result['run_directory'])
                    metrics_path = run_dir / getattr(config, "metrics_filename", "metrics.jsonl")
                else:
                    base_dir = (
                        Path(parsed_args.output_dir)
                        if parsed_args.output_dir
                        else (config.metrics_output_dir or config.output_dir)
                    )
                    base_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"metrics_{timestamp}.jsonl"
                    metrics_path = base_dir / filename
                metrics_collector.write_jsonl(str(metrics_path))
                logger.info(f"Metrics saved to {metrics_path}")
        except Exception as e:
            logger.warning(f"Failed to save metrics JSONL: {e}")

        # Save workflow_history if requested
        if parsed_args.save_workflow:
            try:
                if 'run_directory' in result:
                    run_dir = Path(result['run_directory'])
                    workflow_path = run_dir / "workflow_history.json"
                else:
                    base_dir = Path(parsed_args.output_dir) if parsed_args.output_dir else Path("output")
                    base_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    workflow_path = base_dir / f"workflow_history_{timestamp}.json"
                with open(workflow_path, 'w') as f:
                    json.dump(result.get('workflow_history', []), f, indent=2, default=str)
                logger.info(f"Workflow history saved to {workflow_path}")
            except Exception as e:
                logger.warning(f"Failed to save workflow history: {e}")

        # Save transcript if requested
        if parsed_args.save_transcript and 'run_directory' in result:
            run_dir = Path(result['run_directory'])
            transcript_path = run_dir / "agent_transcript.txt"
            try:
                transcript_lines = ["=== Agent Transcript ===\n\n"]
                transcript_lines.append(f"User Prompt:\n{user_requirement}\n\n")
                transcript_lines.append("=" * 80 + "\n\n")

                for entry in result.get('workflow_history', []):
                    if not isinstance(entry, dict):
                        continue
                    node = entry.get('node', 'unknown')
                    action = entry.get('action', 'unknown')
                    timestamp = entry.get('timestamp', '')
                    details = entry.get('details', {})

                    transcript_lines.append(f"[{timestamp}] NODE: {node.upper()}\n")
                    transcript_lines.append(f"ACTION: {action}\n")

                    if node == 'architect' and 'level0_routing' in details:
                        routing = details['level0_routing']
                        transcript_lines.append("  Level 0 Routing Decision:\n")
                        transcript_lines.append(f"    Selected Code: {routing.get('selected_code')}\n")
                        transcript_lines.append(f"    Confidence: {routing.get('confidence', 0):.2f}\n")
                        transcript_lines.append(f"    Reasoning: {routing.get('reasoning')}\n")

                    if node == 'architect' and 'level2_cbr' in details:
                        cbr = details['level2_cbr']
                        match = cbr.get('top_match', {})
                        transcript_lines.append("  Level 2 Case-Based Reasoning:\n")
                        transcript_lines.append(f"    Best Match: {match.get('case_name')}\n")
                        transcript_lines.append(f"    Path: {match.get('repo_path')}\n")
                        transcript_lines.append(f"    Similarity: {match.get('similarity_score', 0):.2f}\n")
                        transcript_lines.append(f"    Reason: {match.get('match_reason')}\n")

                    if node == 'architect' and 'modifications' in details:
                        mods = details.get('modifications', [])
                        if mods:
                            transcript_lines.append(f"  Planned Modifications: {len(mods)} changes\n")
                            for mod in mods[:3]:  # Show first 3
                                if isinstance(mod, dict):
                                    section = mod.get('section', '')
                                    param = mod.get('parameter', '')
                                    reason = mod.get('reason', '')
                                    label = f"{section}.{param}".strip('.')
                                    transcript_lines.append(f"    - {label}: {reason}\n")
                                elif isinstance(mod, (list, tuple)) and len(mod) == 2:
                                    param, value = mod
                                    transcript_lines.append(f"    - {param} = {value}\n")
                                else:
                                    transcript_lines.append(f"    - {mod}\n")

                    if node == 'analysis' and 'report' in details:
                        report = details.get('report', {})
                        transcript_lines.append("  Analysis Results:\n")
                        transcript_lines.append(f"    Status: {report.get('status')}\n")
                        if report.get('performance'):
                            perf = report.get('performance', {})
                            transcript_lines.append(f"    Performance: {perf.get('avg_cells_per_sec', 0):,.0f} cells/sec\n")

                    transcript_lines.append("\n")

                with open(transcript_path, 'w') as f:
                    f.writelines(transcript_lines)
                logger.info(f"Agent transcript saved to {transcript_path}")
            except Exception as e:
                logger.warning(f"Failed to save transcript: {e}")

        # Output Results
        if parsed_args.json:
            print(json.dumps(result, default=str, indent=2))
        else:
            status = result.get("job_status", "unknown")
            if status == "completed":
                logger.info("Workflow completed successfully")
            elif status == "failed":
                logger.error(f"Workflow failed: {result.get('error', 'Unknown error')}")

        # Exit code based on status
        if result.get("job_status") == "failed":
            sys.exit(1)

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        finalize_log_capture(capture, result)



# ========================================
# AMReXAgent - Graph Orchestration
# (Added in Step C)
# ========================================

logger = logging.getLogger(__name__)

def initialize_state(user_requirement: str, config: AMReXAgentConfig) -> dict[str, Any]:
    """
    Initialize the workflow state for the agent graph.

    Parameters
    ----------
    user_requirement : str
        User requirement string or path to a prompt file.
    config : AMReXAgentConfig
        Active configuration for the run.

    Returns
    -------
    dict
        Initialized graph state for the workflow.
    """
    import os

    # 1. Load prompt (file or string)
    if os.path.exists(user_requirement) and os.path.isfile(user_requirement):
        with open(user_requirement) as f:
            prompt_content = f.read().strip()
    else:
        prompt_content = user_requirement.strip()

    # 2. Validate prompt
    if not prompt_content:
        raise ValueError("User requirement prompt cannot be empty")

    metrics_context = {
        "case_id": os.getenv("BENCHMARK_CASE_ID"),
        "solver": os.getenv("BENCHMARK_SOLVER"),
        "difficulty_tier": os.getenv("BENCHMARK_DIFFICULTY_TIER"),
        "novelty_tier": os.getenv("BENCHMARK_NOVELTY_TIER"),
        "prompt_id": os.getenv("BENCHMARK_PROMPT_ID"),
        "model_id": os.getenv("BENCHMARK_MODEL_ID"),
        "provider": os.getenv("BENCHMARK_PROVIDER"),
    }
    metrics_context = {k: v for k, v in metrics_context.items() if v}

    # 3. Initialize state with defaults
    return {
        # Inputs
        "prompt": prompt_content,
        "config": config,

        # Flow control
        "mode": "initial",
        "iteration": 0,
        "retry_count": 0,
        "max_retries": getattr(config, "max_iterations", 3),

        # Collections
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
        "error_logs": [],         # Required by visualization_node
        "modifications": [],
        "workflow_history": [],
        "history": [],            # Legacy field required by visualization_node
        "metrics_context": metrics_context,
    }


def create_amrex_agent_graph(checkpointer: Any = None) -> StateGraph:
    """
    Build the AMReXAgent workflow graph with Phase 4 nodes.

    Parameters
    ----------
    checkpointer : object, optional
        Optional LangGraph checkpointer.

    Returns
    -------
    StateGraph
        Workflow graph ready for compilation.
    """
    workflow = StateGraph(GraphState)

    # Add all nodes (Phase 4: includes analysis and visualization)
    workflow.add_node("architect", architect_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("input_writer", input_writer_node)
    workflow.add_node("runner", runner_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("visualization", visualization_node)

    # Add edges
    workflow.add_edge(START, "architect")

    # ========================================
    # COMPONENT 12d: CONDITIONAL WIRING
    # ========================================

    # 1. Entry point
    workflow.add_edge(START, "architect")

    # 2. Architect always sends plan to reviewer
    workflow.add_edge("architect", "reviewer")

    # 3. Reviewer conditional routing (reflexion loop)
    workflow.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "input_writer": "input_writer",  # Proceed (validation passed)
            "architect": "architect",         # Retry (validation failed, attempts remain)
            END: END                          # Fail (max retries or critical error)
        }
    )

    # 4. Linear execution path
    workflow.add_edge("input_writer", "runner")

    # 4b. Conditional routing from runner (check for failures)
    workflow.add_conditional_edges(
        "runner",
        route_after_runner,
        {
            "analysis": "analysis",  # Proceed to analysis on success
            END: END                 # Stop execution if runner fails
        }
    )

    # 5. Analysis conditional routing
    workflow.add_conditional_edges(
        "analysis",
        route_after_analysis,
        {
            "visualization": "visualization",  # Success (simulation completed)
            "reviewer": "reviewer",            # Failure (post-execution diagnosis)
            END: END                           # Terminal analysis failure
        }
    )

    # 6. Terminal node
    workflow.add_edge("visualization", END)

    # ========================================
    # COMPILATION
    # ========================================
    return workflow




def run_agent(user_requirement: str, config: AMReXAgentConfig) -> dict[str, Any]:
    """
    Execute the AMReXAgent workflow.

    Call context: Programmatic entry point.

    Parameters
    ----------
    user_requirement : str
        Natural language prompt for the run.
    config : AMReXAgentConfig
        System configuration for the workflow.

    Returns
    -------
    dict
        Final graph state produced by the workflow.
    """
    # 1. Initialize State
    try:
        initial_state = initialize_state(user_requirement, config)
        logger.info("=" * 80)
        logger.info("Starting AMReXAgent workflow")
        logger.info("=" * 80)
        logger.debug(f"Prompt: {user_requirement[:50]}...")
    except Exception as e:
        logger.error(f"State initialization failed: {e}")
        return {
            "error": f"Init Failed: {str(e)}",
            "job_status": "failed",
            "mode": "fail"
        }

    # 2. Build & Compile Graph
    try:
        graph = create_amrex_agent_graph()
        app = graph.compile()
    except Exception as e:
        logger.error(f"Graph compilation failed: {e}")
        return {
            **initial_state,
            "error": f"Graph Error: {str(e)}",
            "job_status": "failed",
            "mode": "fail"
        }

    # 3. Execute with Safety Limits
    # Limit = (Nodes * Max_Retries) + Buffer.
    # 5 nodes * 3 retries = 15. Set to 50 to be safe.
    run_config = {"recursion_limit": 50}

    try:
        from langgraph.errors import GraphRecursionError

        from src.utils.metrics import metrics_extra

        with metrics_extra(initial_state.get("metrics_context") or None):
            final_state = app.invoke(initial_state, run_config)

        status = final_state.get("job_status", "unknown")
        logger.info("-" * 80)
        logger.info(f"Workflow complete. Status: {status}")
        logger.info("-" * 80)
        return final_state

    except GraphRecursionError:
        error_msg = "Workflow exceeded recursion limit (Infinite Loop Detected)"
        logger.error(error_msg)
        return {
            **initial_state,
            "error": error_msg,
            "job_status": "failed",
            "mode": "fail"
        }
    except Exception as e:
        logger.exception("Unhandled workflow error")
        return {
            **initial_state,
            "error": str(e),
            "job_status": "failed",
            "mode": "fail"
        }




if __name__ == "__main__":
    main()
