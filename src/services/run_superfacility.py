"""
Superfacility runner service for AMReX codes.

Executes jobs on NERSC via Superfacility API (with sbatch fallback).
This is ONE way to run - alternatives: run_local.py, run_container.py.
"""

import logging
from pathlib import Path
from typing import Any

from amrex_tools import copy_to_rundir, setup_run_directory

from src.services.build_tools import compile_amrex
from src.services.run_superfacility_tools import (
    generate_slurm_script,
    _load_sfapi_key_file,
    monitor_job,
    stage_run_directory,
    submit_job,
)

logger = logging.getLogger(__name__)

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
        logger.info(f" Finding executable in {case_dir}")

        # Try to find existing executable (ONLY in case_dir, no fallback!)
        if not force_recompile:
            exe = self._find_exe_in_dir(case_dir, require_mpi, require_cuda)

            if exe:
                logger.info(f"[ OK ] Found existing executable: {exe.name}")
                return str(exe)

        # No executable found - compile it
        logger.info(" No suitable executable found, compiling...")
        logger.debug(f"       MPI: {require_mpi}, CUDA: {require_cuda}")

        success = compile_amrex(
            case_dir=str(case_dir),
            use_cuda=require_cuda,
            jobs=16,
        )

        if not success:
            raise RuntimeError(f"Compilation failed in {case_dir}")

        # Find the newly compiled executable
        exe = self._find_exe_in_dir(case_dir, require_mpi, require_cuda)

        if not exe:
            raise RuntimeError(f"Compiled but no executable found in {case_dir}")

        logger.info(f"[ OK ] Compiled: {exe.name}")
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

        # Find all .ex files
        executables = list(case_dir.glob('*.ex'))

        if not executables:
            return None

        # Filter by requirements
        for exe in executables:
            name_lower = exe.name.lower()

            # Check MPI
            if require_mpi and 'mpi' not in name_lower:
                continue

            # Check CUDA
            if require_cuda and 'cuda' not in name_lower:
                continue

            # Match!
            return exe

        # No exact match - return first executable if any
        return executables[0] if executables else None

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

        # Use config output_dir if not specified
        if output_dir is None:
            output_dir = self.config.output_dir

        # Create run directory
        run_dir = setup_run_directory.invoke({
            'base_name': base_name,
            'base_dir': str(output_dir) if output_dir else None
        })
        logger.info(f" Run directory: {run_dir}")

        # Find/compile executable if not provided
        if executable_path is None:
            if case_dir is None:
                raise ValueError("Must provide either executable_path or case_dir")

            executable_path = self.find_or_compile_executable(
                case_dir,
                require_mpi=True,  # Default: assume multi-rank
                require_cuda=True  # Default: assume GPU
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

        logger.info(f"[ OK ] Copied {len(files)} files to run directory")

        return {
            'run_dir': run_dir,
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
               dry_run: bool = False) -> dict[str, Any]:
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

        Returns
        -------
        dict
            Submission details including job_id, method, and script_path.
        """
        logger.debug("\n=== Submitting Job ===\n")

        run_dir = Path(run_directory)

        # Use config account if not provided
        if account is None:
            account = self.config.superfacility_account or "mp111_g"

        # Find executable in run directory
        exe_files = list(run_dir.glob("*.ex"))
        if not exe_files:
            raise FileNotFoundError(f"No executable found in {run_dir}")

        executable = exe_files[0].name

        # Generate SLURM script
        params = {
            'nodes': nodes,
            'walltime': walltime,
            'account': account,
            'qos': qos,
            'constraint': constraint,
            'executable': executable
        }

        script = generate_slurm_script(
            params=params,
            run_dir=str(run_dir),
        )

        # Write script
        script_path = run_dir / 'submit.sh'
        script_path.write_text(script)
        script_path.chmod(0o755)
        logger.info(f" Generated submit script: {script_path.name}")

        if dry_run:
            return {
                'script_path': str(script_path),
                'run_dir': str(run_dir),
                'method': 'dry_run',
                'submitted': False
            }

        remote_staging = getattr(self.config, "remote_staging", False)
        if remote_staging:
            remote_output_dir = getattr(self.config, "remote_output_dir", None) or self.config.output_dir
            remote_run_dir = Path(remote_output_dir) / run_dir.name
            cfg = self.config.model_dump() if hasattr(self.config, "model_dump") else {}
            client_id = cfg.get("superfacility_client_id")
            secret = cfg.get("superfacility_secret")
            if not client_id or not secret:
                parsed = _load_sfapi_key_file()
                if parsed:
                    client_id, secret = parsed
            stage_run_directory(
                local_run_dir=run_dir,
                remote_run_dir=str(remote_run_dir),
                client_id=client_id,
                secret=secret,
            )

            script_path = remote_run_dir / 'submit.sh'

        # Submit job (API with sbatch fallback)
        job_id, method = submit_job(
            script_path=str(script_path),
            system=system,
            is_path=remote_staging,
            config=self.config.model_dump() if hasattr(self.config, "model_dump") else None,
        )

        logger.info(f"[ OK ] Job submitted: {job_id} (via {method})")

        return {
            'job_id': job_id,
            'method': method,
            'run_dir': str(run_dir),
            'script_path': str(script_path),
            'params': params
        }

    def monitor(self,
                job_id: str,
                method: str = 'sbatch',
                poll_interval: int = 10,
                max_polls: int = 30) -> str:
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

        Returns
        -------
        str
            Final job state.
        """
        logger.debug(f"\n[INFO] Monitoring job {job_id} (method: {method})...")

        state = monitor_job(
            job_id=job_id,
            method=method,
            poll_interval=poll_interval,
            max_polls=max_polls,
            config=self.config.model_dump() if hasattr(self.config, "model_dump") else None,
        )

        logger.info(f"[ OK ] Final state: {state}")
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
            walltime=walltime
        )

        # Monitor (optional)
        if monitor_job_flag:
            final_state = self.monitor(
                job_id=job_result['job_id'],
                method=job_result['method']
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
