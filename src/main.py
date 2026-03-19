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
from src.first_run import apply_interactive_fixes, run_startup_readiness_checks
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
from src.nodes.execution_intent_node import build_execution_intent, execution_intent_node
from src.nodes.visualization_intent_node import build_visualization_intent
from src.services.viz_param_extractor import extract_viz_params_from_prompt
from src.utils.job_status import normalize_job_status


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


class PrivacyFilter(logging.Filter):
    """Scrub log messages based on configured privacy mode."""

    def __init__(self, config: AMReXAgentConfig):
        super().__init__()
        self._config = config

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from src.utils.privacy import scrub_log_message

            msg = record.getMessage()
            scrubbed = scrub_log_message(msg, config=self._config)
            if scrubbed != msg:
                record.msg = scrubbed
                record.args = ()
        except Exception:
            pass
        return True


_privacy_filter_installed = False


def apply_privacy_log_filter(config: AMReXAgentConfig) -> None:
    global _privacy_filter_installed
    if _privacy_filter_installed:
        return
    from src.utils.privacy import get_privacy_mode

    if get_privacy_mode(config) == "off":
        return
    privacy_filter = PrivacyFilter(config)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(privacy_filter)
    for name in ("httpx", "openai", "anthropic"):
        logging.getLogger(name).addFilter(privacy_filter)
    _privacy_filter_installed = True


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


def _infer_paper_input_type(paper_source: str | None) -> str | None:
    """Infer paper input type from source string when possible."""
    if not paper_source:
        return None
    source = paper_source.strip()
    if not source:
        return None
    if source.startswith("arxiv:"):
        return "arxiv"
    import re

    arxiv_patterns = (
        r"^\d{4}\.\d{4,5}(v\d+)?$",
        r"^[a-z\-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$",
    )
    if any(re.match(pattern, source, flags=re.IGNORECASE) for pattern in arxiv_patterns):
        return "arxiv"

    source_path = Path(source)
    if source_path.suffix.lower() == ".pdf":
        return "pdf"
    if source_path.is_dir():
        return "pdf+tex"
    return None


def _validate_paper_input_arguments(
    parser: argparse.ArgumentParser,
    parsed: argparse.Namespace,
) -> argparse.Namespace:
    """Enforce paper input argument constraints."""
    has_prompt = bool(parsed.prompt or parsed.prompt_path)
    has_paper_source = bool(parsed.paper_source)

    if not has_prompt and not has_paper_source:
        parser.error("one of --prompt/--prompt-path or --paper-source is required")

    if parsed.paper_input_type and not has_paper_source:
        parser.error("--paper-input-type requires --paper-source")

    if has_paper_source and not parsed.paper_input_type:
        inferred = _infer_paper_input_type(parsed.paper_source)
        if inferred is None:
            parser.error(
                "--paper-input-type is required when --paper-source cannot be inferred "
                "(choose from: arxiv, pdf, pdf+tex)"
            )
        parsed.paper_input_type = inferred

    parsed.paper_validator_enabled = has_paper_source
    return parsed


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
    group = parser.add_mutually_exclusive_group(required=False)
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
    parser.add_argument(
        '--benchmark-context',
        type=str,
        default=None,
        dest='benchmark_context',
        help='Optional JSON/YAML file with benchmark metadata to attach to metrics'
    )
    parser.add_argument(
        '--paper-source',
        type=str,
        default=None,
        dest='paper_source',
        help='Paper source: arXiv ID, PDF path, or TeX directory path'
    )
    parser.add_argument(
        '--paper-input-type',
        choices=['arxiv', 'pdf', 'pdf+tex'],
        default=None,
        dest='paper_input_type',
        help='Paper source type; inferred from --paper-source when possible'
    )

    parsed = parser.parse_args(args)
    return _validate_paper_input_arguments(parser, parsed)


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

    if getattr(args, "prompt_path", None) == "-":
        return sys.stdin.read().strip()

    if not getattr(args, "prompt_path", None):
        return ""

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


def _load_benchmark_context(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    context_path = Path(path)
    if not context_path.exists():
        raise FileNotFoundError(f"Benchmark context file not found: {context_path}")
    suffix = context_path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        import yaml
        data = yaml.safe_load(context_path.read_text(encoding="utf-8"))
    else:
        data = json.loads(context_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Benchmark context file must contain a JSON/YAML object.")
    return data


def _is_tty_session() -> bool:
    stdin_tty = bool(getattr(sys.stdin, "isatty", lambda: False)())
    stdout_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
    return stdin_tty and stdout_tty


def _log_preflight_issues(issues: list[dict[str, Any]]) -> None:
    if not issues:
        return
    logger.error("Startup readiness preflight found unresolved issues:")
    for issue in issues:
        code = issue.get("code", "UNKNOWN")
        severity = str(issue.get("severity", "unknown")).upper()
        action = issue.get("suggested_action", "No suggested action provided.")
        logger.error("  [%s] %s: %s", code, severity, action)


def _has_blocking_issues(issues: list[dict[str, Any]]) -> bool:
    return any(str(issue.get("severity", "")).lower() == "error" for issue in issues)


def _run_startup_preflight(config: AMReXAgentConfig) -> None:
    raw_repo_root = getattr(config, "amrex_agent_root", None)
    if isinstance(raw_repo_root, Path):
        repo_root = raw_repo_root
    elif isinstance(raw_repo_root, (str, os.PathLike)):
        repo_root = Path(raw_repo_root)
    else:
        repo_root = Path.cwd()
    is_tty = _is_tty_session()
    readiness_result = run_startup_readiness_checks(
        repo_root=repo_root,
        config=config,
        is_tty=is_tty,
        allow_clone_missing=is_tty,
        erf_repo_path=getattr(config, "erf_repo_path", None),
    )

    def _apply_resolved_repo_paths(result: dict[str, Any]) -> None:
        resolved_repo_paths = result.get("resolved_repo_paths") or {}
        if not isinstance(resolved_repo_paths, dict):
            return
        erf_path = resolved_repo_paths.get("erf")
        if erf_path:
            setattr(config, "erf_repo_path", Path(erf_path))

    if (
        is_tty
        and isinstance(readiness_result, dict)
        and readiness_result.get("mode") == "interactive"
        and readiness_result.get("issues")
    ):
        readiness_result = apply_interactive_fixes(
            repo_root=repo_root,
            config=config,
            issues=readiness_result.get("issues") or [],
        )
        _apply_resolved_repo_paths(readiness_result)

        unresolved_after_interactive = list(readiness_result.get("unresolved") or [])
        if unresolved_after_interactive:
            unresolved_codes = {
                str(issue.get("code") or "").strip()
                for issue in unresolved_after_interactive
                if isinstance(issue, dict)
            }
            attempted_actions = list(readiness_result.get("attempted_actions") or [])
            attempted_rebuild = any("rebuild" in str(action) for action in attempted_actions)
            if attempted_rebuild and "ERF_COMMIT_MISMATCH" in unresolved_codes:
                logger.warning(
                    "Skipping immediate second interactive remediation pass after rebuild failure."
                )
                unresolved = unresolved_after_interactive
                readiness_result.setdefault("issues", unresolved)
                readiness_result["exit_code"] = 1
                _log_preflight_issues(unresolved)
                raise ValueError("Startup readiness preflight failed. Resolve blocking issues and retry.")

        # Re-run checks immediately so post-selection commit mismatch and other
        # follow-on gates are evaluated in the same preflight session.
        followup_result = run_startup_readiness_checks(
            repo_root=repo_root,
            config=config,
            is_tty=is_tty,
            allow_clone_missing=False,
            erf_repo_path=getattr(config, "erf_repo_path", None),
        )
        if followup_result.get("mode") == "interactive" and followup_result.get("issues"):
            followup_result = apply_interactive_fixes(
                repo_root=repo_root,
                config=config,
                issues=followup_result.get("issues") or [],
            )
            _apply_resolved_repo_paths(followup_result)
        readiness_result = followup_result

    unresolved = list(readiness_result.get("unresolved") or readiness_result.get("issues") or [])
    exit_code = int(readiness_result.get("exit_code") or 0)
    if not unresolved and exit_code == 0:
        return

    _log_preflight_issues(unresolved)
    if _has_blocking_issues(unresolved) or exit_code != 0:
        if not is_tty:
            logger.error(
                "Interactive remediation is disabled in non-TTY mode. Re-run from a terminal "
                "without output redirection to enable interactive fixes."
            )
        raise ValueError("Startup readiness preflight failed. Resolve blocking issues and retry.")


def _resolve_metrics_workflow_id(
    result: dict[str, Any],
    benchmark_context: dict[str, Any] | None,
) -> str:
    """Resolve a stable workflow identifier for persisted metrics records."""
    candidates = [
        result.get("workflow_id"),
        result.get("run_id"),
    ]
    if isinstance(benchmark_context, dict):
        candidates.extend(
            [
                benchmark_context.get("workflow_id"),
                benchmark_context.get("run_id"),
            ]
        )

    run_directory = result.get("run_directory")
    if run_directory:
        run_name = Path(str(run_directory)).name.strip()
        if run_name:
            candidates.append(run_name)

    for candidate in candidates:
        if isinstance(candidate, str):
            cleaned = candidate.strip()
            if cleaned:
                return cleaned
    return "unknown"


def _resolve_metrics_path(
    result: dict[str, Any],
    parsed_args: argparse.Namespace,
    config: AMReXAgentConfig,
) -> Path:
    """Resolve metrics JSONL output path using append-friendly naming."""
    filename = getattr(config, "metrics_filename", "metrics.jsonl") or "metrics.jsonl"
    if result.get("run_directory"):
        return Path(result["run_directory"]) / filename

    base_dir = (
        Path(parsed_args.output_dir)
        if parsed_args.output_dir
        else (config.metrics_output_dir or config.output_dir)
    )
    base_dir.mkdir(parents=True, exist_ok=True)
    return Path(base_dir) / filename


def _persist_metrics_jsonl(
    result: dict[str, Any],
    parsed_args: argparse.Namespace,
    config: AMReXAgentConfig,
    benchmark_context: dict[str, Any] | None,
) -> Path | None:
    """Persist collector events to JSONL with workflow-id contract enforcement."""
    from src.utils.metrics import metrics_collector, metrics_extra

    if not getattr(config, "metrics_enabled", True) or not metrics_collector.events():
        return None

    workflow_id = _resolve_metrics_workflow_id(result, benchmark_context)
    summary = metrics_collector.build_workflow_summary()
    summary.update(
        {
            "job_status": result.get("job_status", "unknown"),
            "iteration": result.get("iteration", 0),
            "run_directory": result.get("run_directory"),
        }
    )
    with metrics_extra(benchmark_context):
        metrics_collector.record_event(
            "workflow_summary",
            summary,
            stage="workflow",
            node="main",
            iteration=result.get("iteration", 0),
        )

    raw_events = getattr(metrics_collector, "_events", None)
    if isinstance(raw_events, list):
        for event in raw_events:
            if isinstance(event, dict) and not str(event.get("workflow_id", "")).strip():
                event["workflow_id"] = workflow_id

    metrics_path = _resolve_metrics_path(result, parsed_args, config)
    metrics_collector.write_jsonl(str(metrics_path), config=config)
    return metrics_path


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

        apply_privacy_log_filter(config)

        _warn_if_schema_missing(config, getattr(parsed_args, "baseline_override", None))
        _run_startup_preflight(config)

        # Disable schema validator temporarily (modifications format issue)
        # config.disabled_validators = ["SchemaSyntaxValidator"]  # Re-enabled for parameter resolution

        # Load Prompt
        user_requirement = load_prompt_content(parsed_args)
        if not user_requirement and not getattr(parsed_args, "paper_source", None):
            raise ValueError("Prompt cannot be empty")

        # Run Agent
        logger.debug("Starting AMReXAgent workflow...")
        benchmark_context = _load_benchmark_context(parsed_args.benchmark_context)
        from src.utils.metrics import metrics_extra

        with metrics_extra(benchmark_context):
            result = run_agent(
                user_requirement,
                config,
                paper_source=getattr(parsed_args, "paper_source", None),
                paper_input_type=getattr(parsed_args, "paper_input_type", None),
                paper_validator_enabled=getattr(parsed_args, "paper_validator_enabled", False),
            )

        # Save metrics JSONL (if enabled)
        try:
            metrics_path = _persist_metrics_jsonl(result, parsed_args, config, benchmark_context)
            if metrics_path is not None:
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
                from src.utils.privacy import sanitize_payload

                workflow_payload = sanitize_payload(
                    result.get('workflow_history', []),
                    config=config,
                )
                with open(workflow_path, 'w') as f:
                    json.dump(workflow_payload, f, indent=2, default=str)
                logger.info(f"Workflow history saved to {workflow_path}")
            except Exception as e:
                logger.warning(f"Failed to save workflow history: {e}")

        # Save transcript if requested
        if parsed_args.save_transcript and 'run_directory' in result:
            run_dir = Path(result['run_directory'])
            transcript_path = run_dir / "agent_transcript.txt"
            try:
                from src.utils.privacy import get_privacy_mode, scrub_text

                privacy_mode = get_privacy_mode(config)
                if privacy_mode == "strict":
                    logger.info("Privacy mode strict: skipping transcript output.")
                else:
                    transcript_lines = ["=== Agent Transcript ===\n\n"]
                    prompt_text = user_requirement
                    if privacy_mode == "shared":
                        prompt_text = scrub_text(
                            prompt_text,
                            mode=privacy_mode,
                            salt=getattr(config, "privacy_hash_salt", None),
                            config=config,
                        ).text
                    transcript_lines.append(f"User Prompt:\n{prompt_text}\n\n")
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
                                transcript_lines.append(
                                    f"    Performance: {perf.get('avg_cells_per_sec', 0):,.0f} cells/sec\n"
                                )

                        transcript_lines.append("\n")

                    if privacy_mode == "shared":
                        transcript_lines = [
                        scrub_text(
                            line,
                            mode=privacy_mode,
                            salt=getattr(config, "privacy_hash_salt", None),
                            config=config,
                        ).text
                            for line in transcript_lines
                        ]
                    with open(transcript_path, 'w') as f:
                        f.writelines(transcript_lines)
                    logger.info(f"Agent transcript saved to {transcript_path}")
            except Exception as e:
                logger.warning(f"Failed to save transcript: {e}")

        # Output Results
        if parsed_args.json:
            print(json.dumps(result, default=str, indent=2))
        else:
            status = normalize_job_status(result.get("job_status"), default="unknown")
            if status == "completed":
                logger.info("Workflow completed successfully")
            elif status == "failed":
                logger.error(f"Workflow failed: {result.get('error', 'Unknown error')}")

        # Exit code based on status
        if normalize_job_status(result.get("job_status"), default="unknown") == "failed":
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

def initialize_state(
    user_requirement: str,
    config: AMReXAgentConfig,
    paper_source: str | None = None,
    paper_input_type: str | None = None,
    paper_validator_enabled: bool = False,
) -> dict[str, Any]:
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
    # 1. Load prompt (file or string)
    if os.path.exists(user_requirement) and os.path.isfile(user_requirement):
        with open(user_requirement) as f:
            prompt_content = f.read().strip()
    else:
        prompt_content = user_requirement.strip()

    if not prompt_content and paper_validator_enabled and paper_source:
        prompt_content = f"Paper reproduction request for source: {paper_source}"

    # 2. Validate prompt
    if not prompt_content and not paper_validator_enabled:
        raise ValueError("User requirement prompt cannot be empty")

    requested_plot_vars, visualization_config = extract_viz_params_from_prompt(prompt_content)
    visualization_intent = build_visualization_intent(
        prompt=prompt_content,
        solver_name="",
        repo_root=None,
        requested_plot_vars=requested_plot_vars,
        visualization_config=visualization_config,
        prior_intent=None,
    ).model_dump()
    execution_intent = build_execution_intent(
        prompt=prompt_content,
        resolved_config={},
        prior_intent=None,
    ).model_dump()

    # 3. Initialize state with defaults
    return {
        # Inputs
        "prompt": prompt_content,
        "config": config,
        "requested_plot_vars": requested_plot_vars,
        "visualization_config": visualization_config,
        "visualization_intent": visualization_intent,
        "execution_intent": execution_intent,
        "paper_source": paper_source,
        "paper_input_type": paper_input_type,
        "paper_validator_enabled": paper_validator_enabled,

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
    workflow.add_node("execution_intent", execution_intent_node)
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
    workflow.add_edge("input_writer", "execution_intent")
    workflow.add_edge("execution_intent", "runner")

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




def run_agent(
    user_requirement: str,
    config: AMReXAgentConfig,
    paper_source: str | None = None,
    paper_input_type: str | None = None,
    paper_validator_enabled: bool = False,
) -> dict[str, Any]:
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
        initial_state = initialize_state(
            user_requirement,
            config,
            paper_source=paper_source,
            paper_input_type=paper_input_type,
            paper_validator_enabled=paper_validator_enabled,
        )
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

        status = normalize_job_status(final_state.get("job_status"), default="unknown")
        final_state["job_status"] = status
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
