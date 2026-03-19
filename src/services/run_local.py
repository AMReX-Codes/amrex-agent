"""
Local execution service for development/testing.

Matches SuperfacilityRunner interface exactly.
"""
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from amrex_tools import copy_to_rundir, setup_run_directory

from src.services.build_tools import compile_solver
from src.services.solver_build_policy import (
    central_build_candidates,
    derive_central_build_dir,
    get_solver_build_policy,
    resolve_local_executable_fallback,
)

logger = logging.getLogger(__name__)

# ERF Build Layout (investigated 2026-03-12)
# - Case-local builds place ERF executables directly in the case directory.
# - Executable naming follows ERF3d.*.ex (for example: ERF3d.gnu.TEST.MPI.ex).
# - Some ERF workflows use a central build directory (BUILDDIR) shared by cases.
# - For nested cases under Exec/<group>/<case>, central executables are commonly in
#   Exec/<group>, not in the deepest case directory.


class LocalRunner:
    """Local execution using subprocess (no SLURM queue).

    Implements identical interface to SuperfacilityRunner but executes
    simulations locally via subprocess instead of remote queue.
    """

    def __init__(self, config):
        self.config = config
        logger.debug("LocalRunner initialized for local execution")

    def find_or_compile_executable(
        self,
        case_dir: str | Path,
        require_mpi: bool = True,
        require_cuda: bool = True,
        force_recompile: bool = False
    ) -> str:
        """
        Find existing executable or compile if needed (CPU-only for local).

        Call context: Used by runner setup when local execution is selected.

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
            exe = self._find_exe_in_dir(case_dir, require_mpi, require_cuda=False)

            if exe:
                logger.debug(f"[ OK ] Found existing executable: {exe.name}")
                return str(exe)
            solver_code = self._active_solver_code(case_dir)
            if solver_code:
                exe, checked_paths = self._resolve_executable_fallbacks(
                    solver_code=solver_code,
                    case_dir=case_dir,
                    require_mpi=require_mpi,
                    require_cuda=False,
                )
                if exe:
                    logger.debug("[ OK ] Found %s fallback executable: %s", solver_code, exe.name)
                    return str(exe)
                logger.info("No %s executable found in fallback paths. Checked: %s", solver_code, checked_paths)

        # No executable found - compile it (FORCE CPU for local).
        logger.info("No suitable executable found, compiling (CPU-only)...")
        logger.debug(f"       MPI: {require_mpi}, CUDA: False (forced for local)")
        solver_code = self._active_solver_code(case_dir)
        compile_success = compile_solver(
            case_dir=case_dir,
            solver_code=solver_code or "AMREX",
            runtime_config=self.config,
            use_cuda=False,
            jobs=12,
        )
        if not compile_success:
            preference = "gnumake"
            if solver_code:
                preference = str(
                    get_solver_build_policy(solver_code, runtime_config=self.config).get(
                        "build_system_preference", "gnumake"
                    )
                ).strip().lower()
            if solver_code and preference == "cmake":
                checked = [case_dir]
                _, checked = self._resolve_executable_fallbacks(
                    solver_code=solver_code,
                    case_dir=case_dir,
                    require_mpi=require_mpi,
                    require_cuda=False,
                )
                raise RuntimeError(
                    f"No {solver_code} executable found. Checked paths: {', '.join(str(path) for path in checked)}"
                )
            raise RuntimeError(f"Compilation failed in {case_dir}")

        # Find newly compiled executable in case dir and policy fallbacks
        exe = self._find_exe_in_dir(case_dir, require_mpi, require_cuda=False)
        if not exe and solver_code:
            exe, _ = self._resolve_executable_fallbacks(
                solver_code=solver_code,
                case_dir=case_dir,
                require_mpi=require_mpi,
                require_cuda=False,
            )

        if not exe:
            raise RuntimeError(f"Compiled but no executable found in {case_dir}")

        logger.info(f"Compiled: {exe.name}")
        return str(exe)

    def _find_exe_in_dir(
        self,
        case_dir: Path,
        require_mpi: bool = True,
        require_cuda: bool = True
    ) -> Path | None:
        """Find executable in case_dir matching MPI/CUDA requirements."""
        case_dir = Path(case_dir)

        # Find .ex files
        ex_files = list(case_dir.glob("*.ex"))
        if not ex_files:
            return None

        # Filter by MPI requirement
        for exe in ex_files:
            name = exe.name.lower()
            has_mpi = "mpi" in name or "2d.gnu.ex" in name or "3d.gnu.ex" in name

            if require_mpi and has_mpi or not require_mpi and not has_mpi:
                return exe

        # Fallback: return first .ex file
        return ex_files[0] if ex_files else None

    def _active_solver_code(self, case_dir: Path | None = None) -> str | None:
        if case_dir is not None:
            case_path = Path(case_dir).resolve()

            for code, repo in getattr(self.config, "repositories", {}).items():
                if not repo:
                    continue
                try:
                    case_path.relative_to(Path(repo).resolve())
                    return str(code).strip().upper()
                except (ValueError, FileNotFoundError):
                    continue

            for attr, repo in vars(self.config).items():
                if not attr.endswith("_repo_path") or not repo:
                    continue
                try:
                    case_path.relative_to(Path(repo).resolve())
                    return attr[: -len("_repo_path")].upper()
                except (ValueError, FileNotFoundError):
                    continue

        solver = str(getattr(self.config, "default_solver", "")).strip().upper()
        return solver or None

    def _solver_repo_path(self, solver_code: str) -> Path | None:
        attr = f"{solver_code.lower()}_repo_path"
        value = getattr(self.config, attr, None)
        return Path(value).expanduser() if value else None

    def _configured_solver_executable_path(self, solver_code: str) -> str | Path | None:
        return getattr(self.config, f"{solver_code.lower()}_executable_path", None)

    def _configured_solver_central_build_dir(self, solver_code: str) -> str | Path | None:
        return getattr(self.config, f"{solver_code.lower()}_central_build_dir", None)

    def _solver_central_build_candidates(self, case_dir: Path, solver_code: str) -> list[Path]:
        return central_build_candidates(
            case_dir=case_dir,
            repo_root=self._solver_repo_path(solver_code),
            configured_central_build_dir=self._configured_solver_central_build_dir(solver_code),
        )

    def _is_erf_context(self, case_dir: Path | None = None) -> bool:
        return self._active_solver_code(case_dir) == "ERF"

    def _derive_erf_central_build_dir(self, case_dir: Path) -> Path | None:
        repo_root = self._solver_repo_path("ERF")
        derived = derive_central_build_dir(case_dir=case_dir, repo_root=repo_root)
        if derived is not None:
            return derived

        case_path = Path(case_dir).resolve()
        parts = case_path.parts
        if "ERF" not in parts:
            return None
        erf_index = parts.index("ERF")
        repo_path = Path(*parts[:erf_index + 1])
        relative_case = case_path.relative_to(repo_path)
        if not relative_case.parts or relative_case.parts[0] != "Exec" or len(relative_case.parts) < 2:
            return None
        return repo_path / "Exec" / relative_case.parts[1]

    def _compile_targets(self, case_dir: Path) -> list[Path]:
        """Return ordered compile targets for the selected solver."""
        targets: list[Path] = []
        solver = self._active_solver_code(case_dir)
        if solver:
            targets.extend(self._solver_central_build_candidates(case_dir, solver))
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

    def _resolve_executable_fallbacks(
        self,
        solver_code: str,
        case_dir: Path,
        require_mpi: bool = True,
        require_cuda: bool = False,
    ) -> tuple[Path | None, list[Path]]:
        resolved = resolve_local_executable_fallback(
            solver_code=solver_code,
            runtime_config=self.config,
            case_dir=Path(case_dir),
            repo_root=self._solver_repo_path(solver_code),
            configured_executable_path=self._configured_solver_executable_path(solver_code),
            central_build_dirs=self._solver_central_build_candidates(Path(case_dir), solver_code),
            require_mpi=require_mpi,
            require_cuda=require_cuda,
            find_default_executable=self._find_exe_in_dir,
        )
        return resolved["executable_path"], resolved["checked_paths"]

    def _resolve_erf_executable_fallbacks(
        self,
        case_dir: Path,
        require_mpi: bool = True,
        require_cuda: bool = False,
    ) -> tuple[Path | None, list[Path]]:
        return self._resolve_executable_fallbacks(
            solver_code="ERF",
            case_dir=case_dir,
            require_mpi=require_mpi,
            require_cuda=require_cuda,
        )

    def _active_submit_solver_code(self, case_dir: str | Path | None = None) -> str | None:
        if case_dir is not None:
            return self._active_solver_code(Path(case_dir))
        return self._active_solver_code(None)

    def _find_submit_executable(self, run_path: Path, case_dir: str | Path | None = None) -> Path | None:
        solver_code = self._active_submit_solver_code(case_dir)
        if solver_code:
            policy = get_solver_build_policy(solver_code, runtime_config=self.config)
            preference = str(policy.get("build_system_preference", "gnumake")).strip().lower()
            branch_order = ["cmake", "gnumake"] if preference == "cmake" else ["gnumake", "cmake"]

            for branch in branch_order:
                if branch == "cmake":
                    for name in policy.get("cmake_executable_names", []):
                        candidate = run_path / str(name)
                        if candidate.is_file():
                            return candidate
                else:
                    for pattern in policy.get("gnumake_executable_globs", ["*.ex"]):
                        matches = sorted(run_path.glob(str(pattern)))
                        for candidate in matches:
                            if candidate.is_file():
                                return candidate

        executables = sorted(run_path.glob("*.ex"))
        return executables[0] if executables else None

    def setup_job(
        self,
        inputs_path: str | Path | None = None,
        case_dir: str | Path | None = None,
        executable_path: str | None = None,
        base_name: str | None = None,
        output_dir: str | Path | None = None
    ) -> dict[str, Any]:
        """
        Set up run directory - matches SuperfacilityRunner.setup_job() interface.

        Call context: Entry point used by Runner node for local runs.

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
            Keys include run_dir, executable, inputs, files.
        """
        # Use default solver for base_name if not specified
        if base_name is None:
            default_solver = self.config.default_solver
            if not default_solver:
                raise ValueError("No default solver configured for run directory naming")
            base_name = default_solver.lower()

        logger.debug("\n=== Setting Up Job (Local) ===\n")

        # Use config output_dir if not specified
        if output_dir is None:
            output_dir = self.config.output_dir

        # If output_dir is already a timestamped run directory (from input_writer),
        # use it directly instead of creating a nested directory
        output_path = Path(output_dir)
        if output_path.name.startswith('run_'):
            # Already a run directory - use it directly
            run_dir = str(output_path)
            logger.debug(f" Using existing run directory: {run_dir}")
        else:
            # Create new run directory
            run_dir = setup_run_directory.invoke({
                'base_name': base_name,
                'base_dir': str(output_dir) if output_dir else None
            })
            logger.debug(f" Run directory: {run_dir}")

        # Find/compile executable if not provided
        if executable_path is None:
            if case_dir is None:
                raise ValueError("Must provide either executable_path or case_dir")

            executable_path = self.find_or_compile_executable(
                case_dir,
                require_mpi=self.config.use_mpi if hasattr(self.config, 'use_mpi') else True,
                require_cuda=False  # Force CPU
            )

        # Copy files to run directory
        if inputs_path:
            # Explicit inputs file
            files = copy_to_rundir.invoke({
                'run_dir': run_dir,
                'executable_path': executable_path,
                'inputs_path': str(inputs_path)
            })
        elif case_dir:
            # Auto-find inputs in case_dir
            files = copy_to_rundir.invoke({
                'run_dir': run_dir,
                'executable_path': executable_path,
                'inputs_dir': str(case_dir)
            })
        else:
            raise ValueError("Must provide either inputs_path or case_dir")

        logger.debug(f"[ OK ] Copied {len(files)} files to run directory")

        return {
            'run_dir': run_dir,
            'executable': executable_path,
            'inputs': files.get('inputs'),
            'files': files
        }

    def submit(
        self,
        run_directory: str | Path,
        nodes: int = 1,
        walltime: str = "00:10:00",
        account: str | None = None,
        qos: str = "regular",
        constraint: str = "gpu&hbm40g",
        system: str = "perlmutter",
        dry_run: bool = False,
        run_mode: str | None = None,
        case_dir: str | Path | None = None
    ) -> dict[str, Any]:
        """
        Execute locally via subprocess - matches SuperfacilityRunner.submit() interface.

        Call context: Entry point used by Runner node for local runs.

        Parameters
        ----------
        run_directory : str or Path
            Run directory with executable and inputs.
        nodes : int, optional
            Number of nodes (used for mpirun -np).
        walltime : str, optional
            Ignored (not applicable for local).
        account : str or None, optional
            Ignored (not applicable for local).
        qos : str, optional
            Ignored (not applicable for local).
        constraint : str, optional
            Ignored (not applicable for local).
        system : str, optional
            Ignored (not applicable for local).
        dry_run : bool, optional
            If True, generate script but don't execute.
        run_mode : str or None, optional
            Execution strategy (dry/stage/submit/full). Overrides dry_run when set.

        Returns
        -------
        dict
            Submission details including job_id, method, and script_path.
        """
        logger.debug("\n=== Submitting Job (Local) ===\n")

        run_path = Path(run_directory)

        # Find executable
        exe = self._find_submit_executable(run_path, case_dir=case_dir)
        if exe is None:
            raise FileNotFoundError(f"No executable found in {run_path}")

        # Build command
        if self.config.use_mpi if hasattr(self.config, 'use_mpi') else True:
            cmd = ["mpirun", "-np", str(nodes), str(exe.name), "inputs"]
        else:
            cmd = [str(exe.name), "inputs"]

        # Generate bash script (for consistency with SuperfacilityRunner)
        script_path = run_path / "run_local.sh"
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Local execution script\n")
            f.write(f"# Generated: {datetime.utcnow().isoformat()}Z\n")
            f.write(f"# Nodes: {nodes}\n\n")
            f.write(f"cd {run_path}\n")
            f.write(f"{' '.join(cmd)}\n")
        script_path.chmod(0o755)
        logger.debug(f" Generated script: {script_path.name}")

        effective_mode = run_mode or ("dry" if dry_run else "full")
        if effective_mode in {"dry", "stage"}:
            logger.debug(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return {
                'script_path': str(script_path),
                'run_dir': str(run_path),
                'method': 'dry_run',
                'submitted': False,
                'job_status': 'completed'
            }

        # Execute process and WAIT for completion (blocking)
        logger.info(f"Executing: {' '.join(cmd)}")

        # Open log files for writing
        with open(run_path / "stdout.log", "w") as stdout_file, open(
            run_path / "stderr.log", "w"
        ) as stderr_file:
            proc = subprocess.Popen(
                cmd,
                cwd=run_path,
                stdout=stdout_file,
                stderr=stderr_file
            )

            logger.debug(f"[ OK ] Process started with PID: {proc.pid}")

            # WAIT for process to complete (BLOCKING)
            logger.info("Waiting for job to complete...")
            return_code = proc.wait()

        # Determine job status from exit code
        if return_code == 0:
            job_status = "completed"
            logger.info("Job completed successfully (exit code: 0)")
        else:
            job_status = "failed"
            logger.error(f"Job failed (exit code: {return_code})")

        return {
            'job_id': str(proc.pid),
            'method': 'local_subprocess',
            'run_dir': str(run_path),
            'script_path': str(script_path),
            'params': {'nodes': nodes, 'walltime': walltime},
            'job_status': job_status,
            'exit_code': return_code
        }
