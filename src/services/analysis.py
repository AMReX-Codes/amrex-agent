"""
AnalysisService - Post-execution log analysis and metrics extraction.

Purpose: Parse AMReX log files and extract simulation statistics, detect issues, check convergence
Runs: ALWAYS after simulation completion (based on user decision)

Based on: DESIGN_reviewer_visualization_analysis.md section 3
Note: Visual diagnostics deferred to Phase 5
"""

import json
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

from src.utils.status_icons import status_label

class AnalysisService:
    """AMReX simulation log analysis and metrics extraction.

    Analyzes:
    1. Timestep data (step number, time, dt)
    2. CFL violations (CFL > 1.0)
    3. NaN/Inf detection
    4. Timestep collapse (dt → 0)
    5. Conservation (mass/energy)
    6. Performance metrics (cells/sec, MPI balance)

    Example:
        >>> analyzer = AnalysisService(config)
        >>> report = analyzer.analyze_simulation(run_dir)
        >>> if report['status'] == 'failed':
        ...     print(report['issues'])
    """

    def __init__(self, config):
        self.config = config


    def _normalize_status(self, internal_status: str, issues: list) -> str:
        """
        Normalize internal status to canonical enum for Node/Router contract.

        Canonical statuses (defined by analysis_node.py + router_func.py):
          - "success": Run completed without issues
          - "failed": Run crashed or had fatal errors (triggers retry loop)
          - "unstable": Run completed but with warnings (proceeds to viz)

        Args:
            internal_status: Detailed service status
            issues: List of detected issues

        Returns
        -------
            Canonical status string
        """
        if internal_status == "incomplete":
            return "failed"

        if internal_status == "completed_with_warnings":
            # Check severity of warnings - CFL violations are unstable
            if any("CFL" in str(i).upper() for i in issues):
                return "unstable"
            # Minor warnings don't prevent success
            return "success"

        if internal_status == "no_log_file":
            return "failed"

        # Already canonical: success, failed, unstable
        return internal_status

    def analyze_simulation(self,
                          run_dir: Path,
                          include_visual: bool = False,
                          solver_name: str | None = None,
                          case_dir: Path | None = None,
                          repo_root: Path | None = None,
                          executable_path: str | None = None) -> dict:
        """
        Comprehensive post-execution analysis.

        Call context: Primary entry point used by the Analysis node.

        Parameters
        ----------
        run_dir : Path
            Simulation run directory.
        include_visual : bool, optional
            Enable visual diagnostics (deferred to Phase 5).
        solver_name : str or None, optional
            Solver name for context-aware diagnostics.
        case_dir : Path or None, optional
            Case directory for inputs and metadata.
        repo_root : Path or None, optional
            Repository root for tooling lookups.
        executable_path : str or None, optional
            Executable path for build flag inference.

        Returns
        -------
        dict
            Analysis report with status, issues, warnings, and metrics.
        """
        logger.debug(f"\n[INFO] Analyzing simulation in {run_dir}")

        if isinstance(run_dir, str):
            run_dir = Path(run_dir)

        report = {
            'status': 'unknown',
            'issues': [],
            'warnings': [],
            'metrics': {},
            'timesteps': [],
            'cfl_history': [],
            'visual_diagnostics': []  # Phase 5
        }

        # Find log file
        log_file = self._find_log_file(run_dir)
        if not log_file:
            report['status'] = 'failed'  # Canonical: no_log_file → failed
            report['issues'].append("No log file found in run directory")
            logger.warning("[WARN] No log file found")
            return report

        # Parse log file
        logger.info(f" Parsing log file: {log_file.name}")
        log_data = self.parse_log(log_file)

        # Merge log data into report
        report.update(log_data)

        # Capture stderr diagnostics (if present)
        stderr_text = self._read_stderr(run_dir)
        if stderr_text:
            report["stderr_excerpt"] = self._extract_stderr_excerpt(stderr_text)
            report["issues"].extend(
                self._extract_stderr_issues(
                    stderr_text,
                    solver_name=solver_name,
                    case_dir=case_dir,
                    repo_root=repo_root,
                    executable_path=executable_path,
                )
            )

        # Detect failures
        failures = self.detect_failures(log_data)
        report['issues'].extend(failures)

        # Check conservation
        conservation = self.check_conservation(log_data)
        report['conservation'] = conservation
        if conservation.get('errors'):
            report['issues'].extend(conservation['errors'])

        # Extract performance
        performance = self.extract_performance(log_data)
        report['performance'] = performance

        # Determine overall status
        if any('NaN' in issue or 'Inf' in issue for issue in report['issues']):
            report['status'] = 'failed'
        elif any('CFL' in issue and '>' in issue for issue in report['issues']):
            report['status'] = 'unstable'
        elif report['issues']:
            report['status'] = 'completed_with_warnings'
        elif log_data.get('completed'):
            report['status'] = 'success'
        else:
            report['status'] = 'incomplete'

        # Generate suggestions
        if report['issues'] or report['warnings']:
            report['suggestions'] = self.suggest_improvements(log_data, report['issues'])

        # Print summary
        self._print_summary(report)

        # Normalize status to canonical enum (Node/Router contract)
        report['status'] = self._normalize_status(
            report['status'],
            report.get('issues', [])
        )
        report_path = run_dir / "analysis_report.json"
        try:
            report_path.write_text(json.dumps(report, indent=2))
            logger.info(f"Analysis report saved to {report_path}")
        except Exception as exc:
            logger.warning(f"Failed to write analysis report to {report_path}: {exc}")

        return report

    def _read_stderr(self, run_dir: Path) -> str:
        stderr_path = Path(run_dir) / "stderr.log"
        if not stderr_path.exists():
            return ""
        try:
            return stderr_path.read_text()
        except Exception:
            return ""

    def _extract_stderr_excerpt(self, stderr_text: str, max_lines: int = 40) -> str:
        lines = stderr_text.splitlines()
        return "\n".join(lines[:max_lines])

    def _extract_stderr_issues(
        self,
        stderr_text: str,
        solver_name: str | None = None,
        case_dir: Path | None = None,
        repo_root: Path | None = None,
        executable_path: str | None = None,
    ) -> list[str]:
        issues = []
        if not stderr_text:
            return issues
        from database.configs.registry import get_config_class

        config_cls = get_config_class(solver_name)

        for entry in config_cls.analysis_error_patterns():
            pattern = entry.get("pattern")
            message = entry.get("message")
            if not pattern or not message:
                continue
            if re.search(pattern, stderr_text):
                issues.append(message)

        # Heuristic: look for stderr tokens that appear in GNUmakefile/Make.*
        if not repo_root and solver_name and hasattr(self.config, "repositories"):
            repo_root = self.config.repositories.get(solver_name)
        tokens = config_cls.find_makefile_tokens(case_dir=case_dir, repo_root=repo_root)
        if getattr(self.config, "allow_make_introspection", False) and case_dir:
            tokens.update(self._make_introspection_tokens(Path(case_dir), executable_path))
        if tokens:
            matches = self._match_tokens_in_text(stderr_text, tokens)
            if matches:
                issues.append(
                    "Stderr mentions build/config token(s) from Makefiles: "
                    + ", ".join(matches)
                )

        return issues

    def _match_tokens_in_text(self, text: str, tokens: set, max_hits: int = 10) -> list[str]:
        if not tokens:
            return []
        hits = []
        for token in sorted(tokens):
            if re.search(rf"\b{re.escape(token)}\b", text):
                hits.append(token)
                if len(hits) >= max_hits:
                    break
        return hits

    def _make_introspection_tokens(self, case_dir: Path, executable_path: str | None) -> set:
        if not case_dir.exists():
            return set()

        command = getattr(self.config, "make_introspection_command", None)
        if not command:
            flags = self._infer_make_flags(executable_path)
            command = ["make", "help"] + flags

        try:
            result = subprocess.run(
                command,
                cwd=case_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return set()

        if result.returncode != 0:
            return set()

        output = result.stdout or ""
        if len(output) > 200000:
            output = output[:200000]

        tokens = set(re.findall(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*[?:]?=", output, flags=re.M))
        tokens.update(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", output))
        return tokens

    def _infer_make_flags(self, executable_path: str | None) -> list[str]:
        flags = []
        use_mpi = getattr(self.config, "use_mpi", True)
        if use_mpi:
            flags.append("USE_MPI=TRUE")

        exe_name = Path(executable_path).name if executable_path else ""
        exe_upper = exe_name.upper()
        if any(token in exe_upper for token in ["CUDA", "GPU", "HIP"]):
            flags.append("USE_CUDA=TRUE")

        return flags

    def parse_log(self, log_file: Path) -> dict:
        """
        Parse AMReX stdout/log file into structured data.

        Extracts:
        - Timestep data: step number, time, dt
        - CFL numbers (if printed)
        - Min/max values (temperature, density, etc.)
        - AMR regrid events
        - Performance: cells/sec, MPI imbalance

        Call context: Used by analysis workflows to structure run logs.

        Parameters
        ----------
        log_file : Path
            Path to the log file to parse.

        Returns
        -------
        dict
            Parsed log data with timesteps, metrics, and completion status.
        """
        timesteps = []
        cfl_history = []
        min_max_values = {}
        regrid_events = []
        performance_data = []

        final_time = None
        total_steps = 0
        completed = False

        try:
            # Read entire log for failure detection
            log_text = log_file.read_text()

            with open(log_file) as f:
                for line in f:
                    # Parse timestep line
                    # Example: "STEP = 100 TIME = 1.234e-3 DT = 1.0e-5"
                    step_match = re.search(r'STEP\s*=\s*(\d+)\s+TIME\s*=\s*([\d.eE+-]+)\s+DT\s*=\s*([\d.eE+-]+)', line)
                    if step_match:
                        step = int(step_match.group(1))
                        time = float(step_match.group(2))
                        dt = float(step_match.group(3))

                        timesteps.append({
                            'step': step,
                            'time': time,
                            'dt': dt
                        })

                        total_steps = step
                        final_time = time

                    # Parse CFL number
                    # Example: "CFL = 0.456"
                    cfl_match = re.search(r'CFL\s*=\s*([\d.eE+-]+)', line)
                    if cfl_match:
                        cfl = float(cfl_match.group(1))
                        cfl_history.append(cfl)

                    # Parse min/max values
                    # Example: "min(Temp) = 300.0  max(Temp) = 2500.0"
                    minmax_match = re.search(r'min\((\w+)\)\s*=\s*([\d.eE+-]+)\s+max\(\1\)\s*=\s*([\d.eE+-]+)', line)
                    if minmax_match:
                        field = minmax_match.group(1)
                        min_val = float(minmax_match.group(2))
                        max_val = float(minmax_match.group(3))

                        if field not in min_max_values:
                            min_max_values[field] = {'min': [], 'max': []}

                        min_max_values[field]['min'].append(min_val)
                        min_max_values[field]['max'].append(max_val)

                    # Parse regrid events
                    # Example: "REGRID: After regridding, level 0 has 4 grids"
                    if 'REGRID' in line or 'regrid' in line.lower():
                        regrid_events.append(line.strip())

                    # Parse performance
                    # Example: "Cells advanced: 1.23e6  cells/s: 4.56e5"
                    perf_match = re.search(r'Cells advanced:\s*([\d.eE+-]+)\s+cells/s:\s*([\d.eE+-]+)', line)
                    if perf_match:
                        cells_advanced = float(perf_match.group(1))
                        cells_per_sec = float(perf_match.group(2))

                        performance_data.append({
                            'cells_advanced': cells_advanced,
                            'cells_per_sec': cells_per_sec
                        })

                    # Check for completion
                    if 'AMReX' in line and 'finalized' in line.lower():
                        completed = True

        except Exception as e:
            logger.warning(f"[WARN] Error parsing log file: {e}")

        return {
            'timesteps': timesteps,
            'cfl_history': cfl_history,
            'min_max_values': min_max_values,
            'regrid_events': regrid_events,
            'performance_data': performance_data,
            'final_time': final_time,
            'total_steps': total_steps,
            'completed': completed,
            'raw_log': log_text if 'log_text' in locals() else ""
        }

    def detect_failures(self, log_data: dict) -> list[str]:
        """
        Detect common simulation problems.

        Checks:
        - CFL violations: CFL > 1.0
        - NaN/Inf values: min/max are NaN
        - Timestep collapse: dt → 0
        - Regrid thrashing: too frequent regridding

        Call context: Used by analysis workflows to flag run failures.

        Parameters
        ----------
        log_data : dict
            Parsed log data from ``parse_log``.

        Returns
        -------
        list of str
            Failure descriptions.
        """
        failures = []

        # Get raw log text for pattern matching
        raw_log = log_data.get("raw_log", "")

        # Pattern 1: NaN/Divergence detection (AMReX FPE trapping)
        nan_patterns = [
            r"SIGFPE",                          # Signal caught by AMReX
            r"[Ff]loating point exception",     # FPE message
            r"[Ii]nvalid operation",            # Invalid FP operation (NaN)
            r"[Dd]ivision by zero",             # Another FPE type
            r"nan",                         # NaN value in output (e.g., "= nan")
            r"NaN detected",                    # Explicit NaN message
            r"Abort"                            # Generic abort
        ]
        for pattern in nan_patterns:
            if re.search(pattern, raw_log, re.IGNORECASE):
                failures.append("NaN/Divergence detected in simulation log")
                break

        # Pattern 2: Timestep collapse
        timestep_patterns = [
            r"dt\s*<\s*dt_min",
            r"timestep too small",
            r"Simulation collapsing"
        ]
        for pattern in timestep_patterns:
            if re.search(pattern, raw_log, re.IGNORECASE):
                failures.append("Timestep collapse detected (dt < dt_min)")
                break

        # Check 1: CFL violations
        cfl_history = log_data.get('cfl_history', [])
        if cfl_history:
            max_cfl = max(cfl_history)
            if max_cfl > 1.0:
                # Find when it exceeded
                for i, cfl in enumerate(cfl_history):
                    if cfl > 1.0:
                        failures.append(
                            f"CFL exceeded 1.0 at timestep ~{i} (CFL={cfl:.3f}) → simulation unstable"
                        )
                        break

        # Check 2: NaN/Inf detection
        min_max_values = log_data.get('min_max_values', {})
        for field, values in min_max_values.items():
            min_vals = values.get('min', [])
            max_vals = values.get('max', [])

            # Check last value for NaN/Inf
            if min_vals:
                last_min = min_vals[-1]
                if last_min != last_min:  # NaN check
                    failures.append(f"{field} = NaN detected (numerical failure)")
                elif abs(last_min) == float('inf'):
                    failures.append(f"{field} = Inf detected (numerical failure)")

            if max_vals:
                last_max = max_vals[-1]
                if last_max != last_max:  # NaN check
                    failures.append(f"{field} = NaN detected (numerical failure)")
                elif abs(last_max) == float('inf'):
                    failures.append(f"{field} = Inf detected (numerical failure)")

        # Check 3: Timestep collapse
        timesteps = log_data.get('timesteps', [])
        if len(timesteps) > 10:
            # Check if dt is decreasing rapidly
            dt_values = [ts['dt'] for ts in timesteps[-10:]]
            min_dt = min(dt_values)

            if min_dt < 1e-12:
                failures.append(
                    f"Timestep collapsed to dt={min_dt:.2e} → stiff problem, consider implicit solver"
                )

        # Check 4: Regrid thrashing
        regrid_events = log_data.get('regrid_events', [])
        total_steps = log_data.get('total_steps', 0)

        if total_steps > 0 and len(regrid_events) > total_steps / 5:
            failures.append(
                f"Excessive regridding ({len(regrid_events)} events in {total_steps} steps) → "
                f"increase regrid_int to reduce overhead"
            )

        return failures

    def check_conservation(self, log_data: dict) -> dict:
        """
        Check mass/energy conservation.

        Call context: Used by analysis workflows to summarize conservation drift.

        Parameters
        ----------
        log_data : dict
            Parsed log data from ``parse_log``.

        Returns
        -------
        dict
            Conservation summary with error metrics.
        """
        # AMReX typically prints conservation errors in log
        # For now, return placeholder (full implementation would parse specific lines)

        return {
            'mass_conserved': True,  # Placeholder
            'energy_conserved': True,  # Placeholder
            'max_error': 0.0,  # Placeholder
            'errors': []
        }

    def extract_performance(self, log_data: dict) -> dict:
        """
        Extract cells/sec, MPI balance, regrid overhead.

        Call context: Used by analysis workflows to summarize run performance.

        Parameters
        ----------
        log_data : dict
            Parsed log data from ``parse_log``.

        Returns
        -------
        dict
            Performance metrics extracted from the log.
        """
        performance_data = log_data.get('performance_data', [])

        if not performance_data:
            return {}

        cells_per_sec_values = [p['cells_per_sec'] for p in performance_data]

        avg_cells_per_sec = sum(cells_per_sec_values) / len(cells_per_sec_values)
        peak_cells_per_sec = max(cells_per_sec_values)

        return {
            'avg_cells_per_sec': avg_cells_per_sec,
            'peak_cells_per_sec': peak_cells_per_sec,
            'num_samples': len(cells_per_sec_values)
        }

    def suggest_improvements(self, log_data: dict, issues: list[str]) -> list[str]:
        """
        Suggest parameter adjustments based on analysis.

        Examples
        --------
        - "Reduce CFL from 0.9 to 0.5 to improve stability"
        - "Increase amr.blocking_factor to improve MPI balance"
        - "Use smaller chemistry timestep to avoid NaN"

        Call context: Used by analysis workflows to generate follow-up guidance.

        Parameters
        ----------
        log_data : dict
            Parsed log data from ``parse_log``.
        issues : list of str
            Issues detected during analysis.

        Returns
        -------
        list of str
            List of suggestion strings.
        """
        suggestions = []

        for issue in issues:
            if 'CFL' in issue and 'exceeded' in issue:
                suggestions.append("Reduce timestep (dt) by 50% to lower CFL number")

            elif 'NaN' in issue:
                suggestions.append("Check initial conditions and boundary conditions for unphysical values")
                suggestions.append("Reduce timestep or enable limiter for robustness")

            elif 'timestep collapsed' in issue.lower():
                suggestions.append("Switch to implicit time integration or use subcycling for stiff terms")

            elif 'regrid' in issue.lower():
                suggestions.append("Increase amr.regrid_int to reduce regridding frequency")
                suggestions.append("Review refinement criteria (may be too aggressive)")

        # Performance suggestions
        performance = log_data.get('performance_data', [])
        if performance:
            avg_cells_per_sec = sum(p['cells_per_sec'] for p in performance) / len(performance)

            if avg_cells_per_sec < 100_000:  # Low throughput
                suggestions.append("Performance is low - consider increasing amr.max_grid_size for better GPU utilization")

        return suggestions

    def _find_log_file(self, run_dir: Path) -> Path | None:
        """Find AMReX log file in run directory."""
        # Common log file patterns (prioritize LocalRunner format)
        candidates = [
            run_dir / 'stdout.log',     # LocalRunner format
            run_dir / 'output.log',
            run_dir / 'stdout.txt',
            run_dir / 'run.log',
            run_dir / 'slurm.out',
        ]

        # Check for SLURM output files
        slurm_files = list(run_dir.glob('slurm-*.out'))
        candidates.extend(slurm_files)

        # Return first existing file
        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Check for any .log or .out files
        for pattern in ['*.log', '*.out']:
            files = list(run_dir.glob(pattern))
            if files:
                return files[0]

        return None

    def _print_summary(self, report: dict):
        """Print human-readable summary of analysis."""
        logger.debug(f"\n{'='*80}")
        logger.debug("ANALYSIS SUMMARY")
        logger.debug(f"{'='*80}")

        status = report['status']
        logger.debug(f"\nStatus: {status_label(status)} {status.upper()}")

        if report.get('total_steps'):
            logger.debug(f"Total steps: {report['total_steps']}")
        if report.get('final_time'):
            logger.debug(f"Final time: {report['final_time']:.6e}")

        # CFL summary
        cfl_history = report.get('cfl_history', [])
        if cfl_history:
            logger.debug(f"\nCFL: min={min(cfl_history):.3f}, avg={sum(cfl_history)/len(cfl_history):.3f}, max={max(cfl_history):.3f}")

        # Issues
        issues = report.get('issues', [])
        if issues:
            logger.debug(f"\n[CRIT] Issues ({len(issues)}):")
            for issue in issues[:5]:
                logger.debug(f"   - {issue}")
            if len(issues) > 5:
                logger.debug(f"   ... and {len(issues) - 5} more")

        # Warnings
        warnings = report.get('warnings', [])
        if warnings:
            logger.debug(f"\n[PEND] Warnings ({len(warnings)}):")
            for warning in warnings[:3]:
                logger.debug(f"   - {warning}")

        # Suggestions
        suggestions = report.get('suggestions', [])
        if suggestions:
            logger.debug("\n[TIP] Suggestions:")
            for suggestion in suggestions[:3]:
                logger.debug(f"   - {suggestion}")

        # Performance
        performance = report.get('performance', {})
        if performance:
            logger.debug("\n[FAST] Performance:")
            if 'avg_cells_per_sec' in performance:
                logger.debug(f"   Average: {performance['avg_cells_per_sec']:,.0f} cells/s")
            if 'peak_cells_per_sec' in performance:
                logger.debug(f"   Peak: {performance['peak_cells_per_sec']:,.0f} cells/s")

        logger.debug(f"\n{'='*80}\n")


# Test
if __name__ == "__main__":
    from src.config import load_config

    logger.debug("\n=== Testing AnalysisService ===\n")

    config = load_config()
    analyzer = AnalysisService(config)

    # Create test log data
    test_log_data = {
        'timesteps': [
            {'step': 0, 'time': 0.0, 'dt': 1e-6},
            {'step': 10, 'time': 1e-5, 'dt': 1e-6},
            {'step': 20, 'time': 2e-5, 'dt': 1e-6},
        ],
        'cfl_history': [0.3, 0.35, 0.4],
        'min_max_values': {
            'Temp': {
                'min': [300, 300, 300],
                'max': [2000, 2100, 2200]
            }
        },
        'total_steps': 20,
        'final_time': 2e-5,
        'completed': True,
        'regrid_events': [],
        'performance_data': [
            {'cells_advanced': 1e6, 'cells_per_sec': 500000},
            {'cells_advanced': 1e6, 'cells_per_sec': 520000},
        ]
    }

    # Test failure detection
    failures = analyzer.detect_failures(test_log_data)
    logger.debug(f"Failures detected: {len(failures)}")

    # Test with CFL violation
    test_log_data_bad = test_log_data.copy()
    test_log_data_bad['cfl_history'] = [0.3, 0.8, 1.2]

    failures_bad = analyzer.detect_failures(test_log_data_bad)
    logger.debug(f"Failures with high CFL: {len(failures_bad)}")
    if failures_bad:
        logger.debug(f"  - {failures_bad[0]}")

    logger.debug("\n[OK] AnalysisService test complete")
