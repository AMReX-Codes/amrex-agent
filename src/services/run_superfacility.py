"""
Superfacility runner service for AMReX codes.

Executes jobs on NERSC via Superfacility API (with sbatch fallback).
This is ONE way to run - alternatives: run_local.py, run_container.py.
"""

import logging
import math
import os
from pathlib import Path
from typing import Any

from amrex_tools import copy_to_rundir, setup_run_directory

from src.services.build_tools import compile_amrex
from src.services.run_superfacility_tools import (
    ensure_remote_directory_rest,
    generate_slurm_script,
    _load_sfapi_key_file,
    find_remote_executable,
    list_remote_entries,
    monitor_job,
    resolve_remote_output_dir,
    stage_out_outputs,
    stage_run_directory,
    submit_job,
)

logger = logging.getLogger(__name__)


def _walltime_to_seconds(walltime: str | None) -> int | None:
    if not walltime:
        return None
    parts = str(walltime).split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = [int(value) for value in parts]
    except ValueError:
        return None
    return max(0, hours) * 3600 + max(0, minutes) * 60 + max(0, seconds)


def _monitor_max_polls_for_walltime(
    walltime: str | None,
    poll_interval: int,
    default_max_polls: int,
) -> int:
    if poll_interval <= 0:
        return default_max_polls
    walltime_seconds = _walltime_to_seconds(walltime)
    if walltime_seconds is None:
        return default_max_polls
    grace_polls = 6
    required = int(math.ceil(walltime_seconds / poll_interval)) + grace_polls
    return max(default_max_polls, required)


class SuperfacilityRunner:
    """Execute AMReX codes on NERSC via Superfacility API.

    Common solvers are defined by the configured registry.

    Workflow:
    1. Find/compile executable
    2. Setup run directory
    3. Submit via API (fallback to sbatch)
    4. Monitor job

    Example:
        >>> runner = SuperfacilityRunner(config)
        >>> job = runner.run_simulation(
        ...     inputs_path="inputs",
        ...     case_dir="../<Solver>/Exec/RegTests/<Case>",
        ...     nodes=2,
        ...     walltime="00:10:00"
        ... )
        >>> status = runner.monitor(job['job_id'], job['method'])
    """

    def __init__(self, config):
        self.config = config

    def find_or_compile_executable(self,
                                   case_dir: str | Path,
                                   require_mpi: bool = True,
                                   require_cuda: bool = True,
                                   force_recompile: bool = False) -> str:
        """
        Find existing executable or compile if needed.

        Only searches the provided case_dir - no fallbacks.

        Call context: Used by runner setup before remote submission.

        Parameters
        ----------
        case_dir : str or Path
            Case directory to search/compile in.
        require_mpi : bool, optional
            Whether to require an MPI-enabled executable.
        require_cuda : bool, optional
            Whether to require a CUDA-enabled executable.
        force_recompile : bool, optional
            Force recompilation even if an executable exists.

        Returns
        -------
        str
            Path to the selected executable.
        """
        case_dir = Path(case_dir)
        logger.debug(f" Finding executable in {case_dir}")

        # Try to find existing executable
        if not force_recompile:
            exe = self._find_exe_in_dir(case_dir, require_mpi, require_cuda)

            if exe:
                logger.debug(f"[ OK ] Found existing executable: {exe.name}")
                return str(exe)
            if self._is_erf_context(case_dir):
                exe, checked_paths = self._resolve_erf_executable_fallbacks(
                    case_dir=case_dir,
                    require_mpi=require_mpi,
                    require_cuda=require_cuda,
                )
                if exe:
                    logger.debug(f"[ OK ] Found ERF fallback executable: {exe.name}")
                    return str(exe)
                checked = ", ".join(str(path) for path in checked_paths)
                logger.info("No ERF executable found in fallback paths. Checked: %s", checked)

        # No executable found - compile it.
        # For ERF, prefer compiling in central build dir when available.
        logger.info("No suitable executable found, compiling...")
        logger.debug(f"       MPI: {require_mpi}, CUDA: {require_cuda}")

        compile_targets = self._compile_targets(case_dir)
        compiled_target: Path | None = None
        for target in compile_targets:
            success = compile_amrex(
                case_dir=str(target),
                use_cuda=require_cuda,
                jobs=16,
            )
            if success:
                compiled_target = target
                logger.info("Compilation succeeded in %s", target)
                break
            logger.warning("Compilation attempt failed in %s", target)

        if compiled_target is None:
            checked = ", ".join(str(path) for path in compile_targets)
            raise RuntimeError(f"Compilation failed in all targets: {checked}")

        # Find the newly compiled executable
        exe = self._find_exe_in_dir(compiled_target, require_mpi, require_cuda)
        if not exe and self._is_erf_context(case_dir):
            exe, _ = self._resolve_erf_executable_fallbacks(
                case_dir=case_dir,
                require_mpi=require_mpi,
                require_cuda=require_cuda,
            )

        if not exe:
            raise RuntimeError(f"Compiled but no executable found in {compiled_target}")

        logger.info(f"Compiled: {exe.name}")
        return str(exe)


    def _find_exe_in_dir(self, case_dir: Path,
                         require_mpi: bool = True,
                         require_cuda: bool = True) -> Path | None:
        """
        Find executable ONLY in case_dir (no fallback search).

        Returns first matching .ex file based on requirements.
        """
        if not case_dir.exists():
            return None
        executables = list(case_dir.glob("*.ex"))
        if not executables:
            return None

        for exe in executables:
            name_lower = exe.name.lower()
            has_mpi = "mpi" in name_lower
            has_cuda = "cuda" in name_lower
            if require_mpi and not has_mpi:
                continue
            if require_cuda and not has_cuda:
                continue
            return exe

        return executables[0]

    def _is_erf_context(self, case_dir: Path | None = None) -> bool:
        """Return True when execution context is ERF (config or case path)."""
        if str(getattr(self.config, "default_solver", "")).strip().upper() == "ERF":
            return True

        if case_dir is None:
            return False

        case_path = Path(case_dir).resolve()
        repo_root = getattr(self.config, "erf_repo_path", None)
        if repo_root:
            try:
                case_path.relative_to(Path(repo_root).resolve())
                return True
            except ValueError:
                pass

        return "ERF" in case_path.parts

    def _derive_erf_central_build_dir(self, case_dir: Path) -> Path | None:
        """Derive ERF central build directory (Exec/<group>) from a case path."""
        case_path = Path(case_dir).resolve()

        repo_root = getattr(self.config, "erf_repo_path", None)
        repo_path = Path(repo_root).resolve() if repo_root else None
        relative_case = None

        if repo_path:
            try:
                relative_case = case_path.relative_to(repo_path)
            except ValueError:
                relative_case = None

        if relative_case is None:
            parts = case_path.parts
            if "ERF" not in parts:
                return None
            erf_index = parts.index("ERF")
            repo_path = Path(*parts[:erf_index + 1])
            relative_case = case_path.relative_to(repo_path)

        if not relative_case.parts or relative_case.parts[0] != "Exec":
            return None
        if len(relative_case.parts) < 2:
            return None
        return repo_path / "Exec" / relative_case.parts[1]

    def _configured_erf_central_build_dir(self) -> Path | None:
        configured = getattr(self.config, "erf_central_build_dir", None)
        if not configured:
            return None
        return Path(os.path.expandvars(str(configured))).expanduser()

    def _erf_central_build_candidates(self, case_dir: Path) -> list[Path]:
        """Return ordered central-build candidates (case-derived first)."""
        candidates: list[Path] = []
        derived = self._derive_erf_central_build_dir(case_dir)
        if derived:
            candidates.append(derived)
        configured = self._configured_erf_central_build_dir()
        if configured:
            candidates.append(configured)

        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(Path(candidate).resolve())
            if key in seen:
                continue
            seen.add(key)
            unique.append(Path(candidate))
        return unique

    def _compile_targets(self, case_dir: Path) -> list[Path]:
        """Return ordered compile targets for the selected solver."""
        targets: list[Path] = []
        if self._is_erf_context(case_dir):
            targets.extend(self._erf_central_build_candidates(case_dir))
        targets.append(case_dir)

        unique_targets: list[Path] = []
        seen: set[str] = set()
        for target in targets:
            key = str(Path(target).resolve())
            if key in seen:
                continue
            seen.add(key)
            unique_targets.append(Path(target))
        return unique_targets

    def _resolve_erf_executable_fallbacks(
        self,
        case_dir: Path,
        require_mpi: bool = True,
        require_cuda: bool = True,
    ) -> tuple[Path | None, list[Path]]:
        """
        Resolve ERF executable fallback chain after case-dir search fails.

        Order:
        1. config.erf_executable_path
        2. derived central build directory (Exec/<group>)
        """
        checked_paths: list[Path] = [Path(case_dir)]

        configured = getattr(self.config, "erf_executable_path", None)
        if configured:
            configured_path = Path(os.path.expandvars(str(configured))).expanduser()
            checked_paths.append(configured_path)
            if configured_path.is_file():
                return configured_path, checked_paths

        for central_build_dir in self._erf_central_build_candidates(Path(case_dir)):
            if central_build_dir in checked_paths:
                continue
            checked_paths.append(central_build_dir)
            exe = self._find_exe_in_dir(central_build_dir, require_mpi, require_cuda)
            if exe:
                return exe, checked_paths

        return None, checked_paths

    def _resolve_remote_executable(
        self,
        case_dir: str | Path | None,
        system: str = "perlmutter",
    ) -> Path | None:
        if case_dir is None:
            return None

        case_dir_path = Path(case_dir)
        relative_case_dir = None
        repo_name = None
        for repo_path in getattr(self.config, "repositories", {}).values():
            if not repo_path:
                continue
            try:
                rel = case_dir_path.resolve().relative_to(Path(repo_path).resolve())
            except (ValueError, FileNotFoundError):
                continue
            relative_case_dir = str(rel)
            repo_name = Path(repo_path).name
            break

        case_dir_value = relative_case_dir or case_dir_path.name
        case_dir_name = case_dir_path.name

        template = getattr(self.config, "remote_executable_template", None)
        if template:
            try:
                rendered = template.format(
                    case_dir=case_dir_value,
                    case_dir_name=case_dir_name,
                    repo_name=repo_name,
                    solver_name=repo_name,
                )
            except KeyError as exc:
                raise ValueError(f"remote_executable_template missing key: {exc}") from exc
            rendered = os.path.expandvars(rendered)
            rendered_path = Path(rendered)
            if rendered_path.suffix == ".ex":
                return rendered_path
            if getattr(self.config, "remote_executable_find", False):
                try:
                    list_remote_entries(str(rendered_path), system=system)
                except Exception as exc:
                    hint = ""
                    if "No NERSC session" in str(exc):
                        hint = (
                            " (SFAPI auth missing; set SFAPI_KEY_PATH or NERSC_API_TOKEN "
                            "to enable remote directory listing)"
                        )
                    raise RuntimeError(
                        "Remote case directory not available for executable search: "
                        f"{rendered_path}{hint}"
                    ) from exc
                found = find_remote_executable(
                    remote_case_dir=str(rendered_path),
                    system=system,
                )
                return Path(found) if found else None
            return None

        if not getattr(self.config, "remote_executable_find", False):
            return None

        account = os.getenv("SBATCH_ACCOUNT")
        user = os.getenv("USER")
        if not account or not user or not repo_name or not relative_case_dir:
            return None

        remote_case_dir = Path("/global/cfs/cdirs") / account / user / repo_name / relative_case_dir
        try:
            list_remote_entries(str(remote_case_dir), system=system)
        except Exception as exc:
            hint = ""
            if "No NERSC session" in str(exc):
                hint = (
                    " (SFAPI auth missing; set SFAPI_KEY_PATH or NERSC_API_TOKEN "
                    "to enable remote directory listing)"
                )
            raise RuntimeError(
                "Remote case directory not available for executable search: "
                f"{remote_case_dir}{hint}"
            ) from exc
        found = find_remote_executable(
            remote_case_dir=str(remote_case_dir),
            system=system,
        )
        return Path(found) if found else None

        # No exact match - return first executable if any
        return None

    def setup_job(self,
                  inputs_path: str | Path | None = None,
                  case_dir: str | Path | None = None,
                  executable_path: str | None = None,
                  base_name: str | None = None,
                  output_dir: str | Path | None = None) -> dict[str, Any]:
        """
        Set up run directory with all files.

        Call context: Entry point used by Runner node for remote runs.

        Parameters
        ----------
        inputs_path : str or Path, optional
            Path to inputs file (optional if case_dir provided).
        case_dir : str or Path, optional
            Case directory (optional, will auto-find inputs).
        executable_path : str or None, optional
            Path to executable (optional, will find/compile).
        base_name : str or None, optional
            Base name for run directory.
        output_dir : str or Path or None, optional
            Parent directory for run (default: config.output_dir).

        Returns
        -------
        dict
            Dict with run_dir, executable, inputs, and copied files.
        """
        # Use default solver for base_name if not specified
        if base_name is None:
            default_solver = self.config.default_solver
            if not default_solver:
                raise ValueError("No default solver configured for run directory naming")
            base_name = default_solver.lower()

        logger.debug("\n=== Setting Up Job ===\n")

        # Use config output_dir if not specified (prefer remote_output_dir on Perlmutter)
        if output_dir is None:
            if getattr(self.config, "environment", None) == "perlmutter":
                output_dir = getattr(self.config, "remote_output_dir", None) or self.config.output_dir
            else:
                output_dir = self.config.output_dir

        output_dir_path = Path(output_dir) if output_dir else None
        if output_dir_path and output_dir_path.exists() and (output_dir_path / "inputs").exists():
            run_dir = output_dir_path
            logger.debug(f" Using existing run directory: {run_dir}")
        else:
            # Create run directory
            run_dir = setup_run_directory.invoke({
                'base_name': base_name,
                'base_dir': str(output_dir) if output_dir else None
            })
            logger.debug(f" Run directory: {run_dir}")

        # Find/compile executable if not provided
        if executable_path is None:
            if case_dir is None:
                raise ValueError("Must provide either executable_path or case_dir")

            remote_resolution_enabled = bool(
                getattr(self.config, "remote_executable_path", None)
                or getattr(self.config, "remote_executable_template", None)
                or getattr(self.config, "remote_executable_find", False)
            )
            if getattr(self.config, "environment", None) in {"local", None}:
                remote_resolution_enabled = False

            if remote_resolution_enabled:
                logger.debug(" Skipping local compile; remote executable resolution enabled.")
                executable_path = None
            else:
                executable_path = self.find_or_compile_executable(
                    case_dir,
                    require_mpi=True,  # Default: assume multi-rank
                    require_cuda=True  # Default: assume GPU
                )

        run_dir_str = str(run_dir)

        # Copy files to run directory
        executable_arg = executable_path or ""
        if inputs_path:
            # Explicit inputs file
            files = copy_to_rundir.invoke({
                'run_dir': run_dir_str,
                'executable_path': executable_arg,
                'inputs_path': str(inputs_path)
            })
        elif case_dir:
            # Auto-find inputs in case_dir
            files = copy_to_rundir.invoke({
                'run_dir': run_dir_str,
                'executable_path': executable_arg,
                'inputs_dir': str(case_dir)
            })
        else:
            raise ValueError("Must provide either inputs_path or case_dir")

        logger.debug(f"[ OK ] Copied {len(files)} files to run directory")

        return {
            'run_dir': run_dir_str,
            'executable': executable_path,
            'inputs': files.get('inputs'),
            'files': files
        }

    def submit(self,
               run_directory: str | Path,
               nodes: int = 1,
               walltime: str = "00:10:00",
               account: str | None = None,
               qos: str = "regular",
               constraint: str = "gpu&hbm40g",
               system: str = "perlmutter",
               dry_run: bool = False,
               run_mode: str | None = None,
               case_dir: str | Path | None = None) -> dict[str, Any]:
        """
        Submit job via Superfacility API (with sbatch fallback).

        Call context: Entry point used by Runner node for remote submission.

        Parameters
        ----------
        run_directory : str or Path
            Run directory with executable and inputs.
        nodes : int, optional
            Number of nodes.
        walltime : str, optional
            Walltime (HH:MM:SS).
        account : str or None, optional
            NERSC account (uses config if not provided).
        qos : str, optional
            Queue (regular/debug/premium).
        constraint : str, optional
            Node constraint.
        system : str, optional
            System name (perlmutter).
        dry_run : bool, optional
            If True, generate script but don't submit.
        run_mode : str or None, optional
            Execution strategy (dry/stage/submit/full). Overrides dry_run when set.

        Returns
        -------
        dict
            Submission details including job_id, method, and script_path.
        """
        logger.debug("\n=== Submitting Job ===\n")

        run_dir = Path(run_directory)

        # Use config account if not provided
        if account is None:
            account = self.config.superfacility_account or "amsc014"
        account = os.path.expandvars(str(account))

        # Find executable in run directory
        exe_files = list(run_dir.glob("*.ex"))
        executable = exe_files[0].name if exe_files else None
        remote_executable_path = getattr(self.config, "remote_executable_path", None)
        if remote_executable_path:
            remote_executable_path = Path(os.path.expandvars(str(remote_executable_path)))
        elif getattr(self.config, "remote_executable_template", None) or getattr(self.config, "remote_executable_find", True):
            remote_executable_path = self._resolve_remote_executable(
                case_dir=case_dir,
                system=system,
            )
        if remote_executable_path is None and executable is None:
            raise FileNotFoundError(
                f"No executable found in {run_dir} and remote executable could not be resolved. "
                "Set remote_executable_path or remote_executable_template."
            )

        # Generate SLURM script
        if remote_executable_path:
            logger.info(f"Using remote executable: {remote_executable_path}")
        else:
            logger.info(f"Using local executable: {executable}")

        params = {
            'nodes': nodes,
            'walltime': walltime,
            'account': account,
            'qos': qos,
            'constraint': constraint,
            'executable': str(remote_executable_path) if remote_executable_path else executable
        }

        effective_mode = run_mode or ("dry" if dry_run else "full")

        try:
            if hasattr(self.config, "should_stage_run"):
                remote_staging = self.config.should_stage_run()
            else:
                from src.config import detect_environment, should_stage_run
                remote_staging = should_stage_run(
                    getattr(self.config, "environment", None),
                    detect_environment(),
                )
        except Exception:
            remote_staging = False
        remote_run_dir = None
        exclude_names = None
        if remote_staging:
            preferred_output_dir = getattr(self.config, "remote_output_dir", None)
            if preferred_output_dir is None:
                preferred_output_dir = self.config.output_dir
                logger.warning(
                    "[Config] remote_output_dir not set; defaulting staging target to %s",
                    preferred_output_dir,
                )
            remote_output_dir = resolve_remote_output_dir(
                preferred_output_dir=preferred_output_dir,
                account=account,
                user=os.getenv("USER"),
                system=system,
            )
            fixed_remote_run_dir = getattr(self.config, "remote_run_dir", None)
            if fixed_remote_run_dir:
                remote_run_dir = Path(os.path.expandvars(str(fixed_remote_run_dir)))
                ensure_remote_directory_rest(
                    remote_run_dir=str(remote_run_dir),
                    upload_host=system,
                )
            else:
                remote_run_dir = Path(remote_output_dir) / run_dir.name
            if remote_executable_path and executable:
                exclude_names = [Path(executable).name]

        run_dir_for_script = remote_run_dir if remote_run_dir else run_dir
        script = generate_slurm_script(
            params=params,
            run_dir=str(run_dir_for_script),
        )

        # Write script
        script_path = run_dir / 'submit.sh'
        script_path.write_text(script)
        script_path.chmod(0o755)
        logger.debug(f" Generated submit script: {script_path.name}")

        if effective_mode == "dry":
            return {
                'script_path': str(script_path),
                'run_dir': str(run_dir),
                'method': 'dry_run',
                'submitted': False,
                'job_status': 'completed'
            }

        if remote_staging and effective_mode in {"stage", "submit", "full"}:
            cfg = self.config.model_dump() if hasattr(self.config, "model_dump") else {}
            client_id = cfg.get("superfacility_client_id")
            secret = cfg.get("superfacility_secret")
            if not client_id or not secret:
                parsed = _load_sfapi_key_file()
                if parsed:
                    client_id, secret = parsed
            staging_method = getattr(self.config, "remote_staging_method", "auto")
            stage_run_directory(
                local_run_dir=run_dir,
                remote_run_dir=str(remote_run_dir),
                client_id=client_id,
                secret=secret,
                method=staging_method,
                exclude_names=exclude_names,
            )

            script_path = remote_run_dir / 'submit.sh'

        if effective_mode == "stage":
            return {
                'script_path': str(script_path),
                'run_dir': str(run_dir),
                'method': 'stage_only',
                'submitted': False,
                'job_status': 'completed'
            }

        # Submit job (API with sbatch fallback)
        job_id, method = submit_job(
            script_path=str(script_path),
            system=system,
            is_path=remote_staging,
            config=self.config.model_dump() if hasattr(self.config, "model_dump") else None,
        )

        logger.info(f"Job submitted: {job_id} (via {method})")

        return {
            'job_id': job_id,
            'method': method,
            'run_dir': str(run_dir),
            'script_path': str(script_path),
            'remote_run_dir': str(remote_run_dir) if remote_run_dir else None,
            'params': params,
            'job_status': 'queued'
        }

    def monitor(self,
                job_id: str,
                method: str = 'sbatch',
                poll_interval: int = 10,
                max_polls: int = 30,
                walltime: str | None = None) -> str:
        """
        Monitor job until completion or timeout.

        Call context: Used by Runner node when monitoring is requested.

        Parameters
        ----------
        job_id : str
            Job ID from submission.
        method : str, optional
            "api" or "sbatch".
        poll_interval : int, optional
            Seconds between checks.
        max_polls : int, optional
            Maximum number of checks.
        walltime : str or None, optional
            HH:MM:SS requested walltime used to scale max polls.

        Returns
        -------
        str
            Final job state.
        """
        logger.debug(f"\n[INFO] Monitoring job {job_id} (method: {method})...")
        resolved_max_polls = _monitor_max_polls_for_walltime(
            walltime=walltime,
            poll_interval=poll_interval,
            default_max_polls=max_polls,
        )

        state = monitor_job(
            job_id=job_id,
            method=method,
            poll_interval=poll_interval,
            max_polls=resolved_max_polls,
            config=self.config.model_dump() if hasattr(self.config, "model_dump") else None,
        )

        logger.info(f"Final state: {state}")
        return state

    def run_simulation(self,
                      inputs_path: str | Path | None = None,
                      case_dir: str | Path | None = None,
                      nodes: int = 1,
                      walltime: str = "00:10:00",
                      base_name: str | None = None,
                      monitor_job_flag: bool = False) -> dict[str, Any]:
        """
        Complete workflow: setup → submit → (optional) monitor.

        Call context: Convenience entry point for end-to-end runs.

        Parameters
        ----------
        inputs_path : str or Path, optional
            Path to inputs file.
        case_dir : str or Path, optional
            Case directory.
        nodes : int, optional
            Number of nodes.
        walltime : str, optional
            Walltime.
        base_name : str or None, optional
            Run directory name prefix.
        monitor_job_flag : bool, optional
            Whether to wait for job completion.

        Returns
        -------
        dict
            Job info combined with run directory details.
        """
        # Use default solver for base_name if not specified
        if base_name is None:
            default_solver = self.config.default_solver
            if not default_solver:
                raise ValueError("No default solver configured for run directory naming")
            base_name = default_solver.lower()

        # Setup
        setup_result = self.setup_job(
            inputs_path=inputs_path,
            case_dir=case_dir,
            base_name=base_name
        )

        # Submit
        job_result = self.submit(
            run_dir=setup_result['run_dir'],
            nodes=nodes,
            walltime=walltime,
            case_dir=case_dir,
        )

        # Monitor (optional)
        if monitor_job_flag:
            final_state = self.monitor(
                job_id=job_result['job_id'],
                method=job_result['method'],
                walltime=walltime,
            )
            job_result['final_state'] = final_state

        return {**setup_result, **job_result}


# Test
if __name__ == "__main__":
    from src.config import load_config

    logger.debug("\n=== Testing Superfacility Runner ===\n")

    config = load_config()
    runner = SuperfacilityRunner(config)

    # Test: Setup job only (don't submit)
    case_dir = "../PeleC/Exec/RegTests/PMF"

    logger.debug("[Test] Setup job (no submission):")
    result = runner.setup_job(
        case_dir=case_dir,
        base_name="test_runner"
    )

    logger.debug("\n[OK] Setup complete:")
    logger.debug(f"  Run dir: {result['run_dir']}")
    logger.debug(f"  Executable: {Path(result['executable']).name}")
    logger.debug(f"  Files: {list(result['files'].keys())}")

    logger.debug("\n[OK] Runner service test complete")
    logger.debug("  (To submit: runner.submit(result['run_dir'], nodes=1, walltime='00:30:00'))")
