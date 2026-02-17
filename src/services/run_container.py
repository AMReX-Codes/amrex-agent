"""
Container execution service for local/HPC runs.

Supports local Docker/Podman, NERSC podman-hpc, and ALCF Apptainer.
"""
import logging
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from amrex_tools import copy_to_rundir, setup_run_directory

from src.services.run_superfacility_tools import (
    _load_sfapi_key_file,
    ensure_remote_directory_rest,
    resolve_remote_output_dir,
    stage_run_directory,
    submit_job,
)

logger = logging.getLogger(__name__)


class ContainerRunner:
    """Run AMReX simulations inside a container runtime."""

    def __init__(self, config):
        self.config = config
        logger.debug("ContainerRunner initialized")

    def setup_job(
        self,
        inputs_path: str | Path | None = None,
        case_dir: str | Path | None = None,
        executable_path: str | None = None,
        base_name: str | None = None,
        output_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """
        Set up run directory without compiling or copying executables.

        Container images are expected to include the executable/entrypoint.
        """
        if base_name is None:
            default_solver = self.config.default_solver
            if not default_solver:
                raise ValueError("No default solver configured for run directory naming")
            base_name = default_solver.lower()

        if output_dir is None:
            output_dir = self.config.output_dir

        output_path = Path(output_dir)
        if output_path.name.startswith("run_"):
            run_dir = str(output_path)
            logger.debug("Using existing run directory: %s", run_dir)
        else:
            run_dir = setup_run_directory.invoke({
                "base_name": base_name,
                "base_dir": str(output_dir) if output_dir else None,
            })
            logger.debug("Run directory: %s", run_dir)

        run_dir_path = Path(run_dir)

        if inputs_path:
            files = copy_to_rundir.invoke({
                "run_dir": run_dir,
                "executable_path": "",
                "inputs_path": str(inputs_path),
            })
        elif case_dir:
            files = copy_to_rundir.invoke({
                "run_dir": run_dir,
                "executable_path": "",
                "inputs_dir": str(case_dir),
            })
        else:
            raise ValueError("Must provide either inputs_path or case_dir")

        logger.debug("[ OK ] Copied %d files to run directory", len(files))

        return {
            "run_dir": str(run_dir_path),
            "executable": self._resolve_container_entrypoint(),
            "inputs": files.get("inputs"),
            "files": files,
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
        case_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """
        Submit or run a containerized job (local, NERSC, or ALCF).
        """
        logger.debug("\n=== Submitting Container Job ===\n")
        run_dir = Path(run_directory)

        effective_mode = run_mode or ("dry" if dry_run else "full")
        runtime = self._resolve_runtime()
        if account is None:
            account = getattr(self.config, "container_account", None)
        if getattr(self.config, "container_qos", None):
            qos = getattr(self.config, "container_qos")
        if getattr(self.config, "container_constraint", None):
            constraint = getattr(self.config, "container_constraint")
        if getattr(self.config, "container_walltime", None):
            walltime = getattr(self.config, "container_walltime")
        container_cmd = self._build_container_command(run_dir, runtime)

        if self._is_local_runtime(runtime):
            return self._run_local_container(run_dir, container_cmd, effective_mode)

        if self._is_nersc_runtime(runtime):
            return self._submit_nersc_container(
                run_dir=run_dir,
                container_cmd=container_cmd,
                nodes=nodes,
                walltime=walltime,
                account=account,
                qos=qos,
                constraint=constraint,
                system=system,
                effective_mode=effective_mode,
            )

        return self._submit_slurm_container(
            run_dir=run_dir,
            container_cmd=container_cmd,
            nodes=nodes,
            walltime=walltime,
            account=account,
            qos=qos,
            constraint=constraint,
            effective_mode=effective_mode,
        )

    def _resolve_runtime(self) -> str:
        runtime = getattr(self.config, "container_runtime", None)
        if runtime:
            return runtime.lower()
        environment = (getattr(self.config, "environment", "") or "").lower()
        if environment in {"perlmutter", "nersc"}:
            return "podman-hpc"
        if environment == "alcf":
            return "apptainer"
        return "docker"

    def _resolve_container_image(self) -> str:
        image = getattr(self.config, "container_image", None)
        if image:
            return str(image)
        environment = (getattr(self.config, "environment", "") or "").lower()
        default_ref = "registry.nersc.gov/amsc014/superfacility/pele:latest"
        if environment == "alcf":
            return f"docker://{default_ref}"
        return default_ref

    def _resolve_container_entrypoint(self) -> str:
        entrypoint = getattr(self.config, "container_entrypoint", None)
        if entrypoint:
            return str(entrypoint)
        return "/usr/local/bin/run_pelelmex"

    def _build_container_command(self, run_dir: Path, runtime: str) -> list[str]:
        image = self._resolve_container_image()
        workdir = getattr(self.config, "container_workdir", "/work")
        entrypoint = self._resolve_container_entrypoint()
        inputs_name = getattr(self.config, "container_inputs_name", "inputs")
        extra_args = getattr(self.config, "container_extra_args", []) or []
        use_cuda = bool(getattr(self.config, "use_cuda", True))

        if runtime in {"docker", "podman", "podman-hpc"}:
            cmd = [runtime, "run", "--rm"]
            if use_cuda:
                if runtime == "podman-hpc":
                    cmd.append("--gpu")
                else:
                    cmd += ["--gpus", "all"]
            cmd += ["-v", f"{run_dir}:{workdir}", "-w", workdir]
            cmd += list(extra_args)
            cmd += [image, entrypoint, inputs_name]
            return cmd

        if runtime in {"apptainer", "singularity"}:
            cmd = [runtime, "exec"]
            if use_cuda:
                cmd.append("--nv")
            cmd += ["--bind", f"{run_dir}:{workdir}", "--pwd", workdir]
            cmd += list(extra_args)
            cmd += [image, entrypoint, inputs_name]
            return cmd

        raise ValueError(f"Unsupported container runtime: {runtime}")

    def _run_local_container(
        self,
        run_dir: Path,
        container_cmd: list[str],
        effective_mode: str,
    ) -> dict[str, Any]:
        script_path = run_dir / "run_container.sh"
        script_path.write_text(self._format_shell_script(container_cmd, run_dir))
        script_path.chmod(0o755)
        logger.debug("Generated local container script: %s", script_path.name)

        if effective_mode in {"dry", "stage"}:
            return {
                "script_path": str(script_path),
                "run_dir": str(run_dir),
                "method": "dry_run",
                "submitted": False,
                "job_status": "completed",
            }

        logger.info("Executing container locally: %s", " ".join(container_cmd))
        with open(run_dir / "stdout.log", "w") as stdout_file, open(
            run_dir / "stderr.log", "w"
        ) as stderr_file:
            proc = subprocess.Popen(
                container_cmd,
                cwd=run_dir,
                stdout=stdout_file,
                stderr=stderr_file,
            )
            return_code = proc.wait()

        job_status = "completed" if return_code == 0 else "failed"
        return {
            "job_id": str(proc.pid),
            "method": "local_container",
            "run_dir": str(run_dir),
            "script_path": str(script_path),
            "params": {"nodes": 1, "walltime": "n/a"},
            "job_status": job_status,
            "exit_code": return_code,
        }

    def _submit_nersc_container(
        self,
        run_dir: Path,
        container_cmd: list[str],
        nodes: int,
        walltime: str,
        account: str | None,
        qos: str,
        constraint: str,
        system: str,
        effective_mode: str,
    ) -> dict[str, Any]:
        if account is None:
            account = self.config.superfacility_account or "amsc014"
        account = os.path.expandvars(str(account))

        params = {
            "nodes": nodes,
            "walltime": walltime,
            "account": account,
            "qos": qos,
            "constraint": constraint,
            "use_srun": True,
        }

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

        run_dir_for_script = remote_run_dir if remote_run_dir else run_dir
        script_content = self._generate_slurm_script(
            params=params,
            run_dir=str(run_dir_for_script),
            container_cmd=container_cmd,
        )

        script_path = run_dir / "submit.sh"
        script_path.write_text(script_content)
        script_path.chmod(0o755)
        logger.debug("Generated submit script: %s", script_path.name)

        if effective_mode == "dry":
            return {
                "script_path": str(script_path),
                "run_dir": str(run_dir),
                "method": "dry_run",
                "submitted": False,
                "job_status": "completed",
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
            )
            script_path = remote_run_dir / "submit.sh"

        if effective_mode == "stage":
            return {
                "script_path": str(script_path),
                "run_dir": str(run_dir),
                "method": "stage_only",
                "submitted": False,
                "job_status": "completed",
            }

        job_id, method = submit_job(
            script_path=str(script_path),
            system=system,
        )

        return {
            "job_id": job_id,
            "method": method or "superfacility",
            "run_dir": str(run_dir),
            "remote_run_dir": str(remote_run_dir) if remote_run_dir else None,
            "script_path": str(script_path),
            "params": params,
            "job_status": "submitted",
        }

    def _submit_slurm_container(
        self,
        run_dir: Path,
        container_cmd: list[str],
        nodes: int,
        walltime: str,
        account: str | None,
        qos: str,
        constraint: str,
        effective_mode: str,
    ) -> dict[str, Any]:
        params = {
            "nodes": nodes,
            "walltime": walltime,
            "account": account,
            "qos": qos,
            "constraint": constraint,
            "use_srun": True,
        }

        script_content = self._generate_slurm_script(
            params=params,
            run_dir=str(run_dir),
            container_cmd=container_cmd,
        )

        script_path = run_dir / "submit.sh"
        script_path.write_text(script_content)
        script_path.chmod(0o755)

        if effective_mode in {"dry", "stage"}:
            return {
                "script_path": str(script_path),
                "run_dir": str(run_dir),
                "method": "dry_run",
                "submitted": False,
                "job_status": "completed",
            }

        try:
            result = subprocess.run(
                ["sbatch", str(script_path)],
                cwd=run_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            job_id = self._parse_sbatch_job_id(result.stdout)
            return {
                "job_id": job_id or "unknown",
                "method": "sbatch",
                "run_dir": str(run_dir),
                "script_path": str(script_path),
                "params": params,
                "job_status": "submitted",
            }
        except subprocess.CalledProcessError as exc:
            logger.error("sbatch submission failed: %s", exc.stderr)
            return {
                "job_id": None,
                "method": "sbatch",
                "run_dir": str(run_dir),
                "script_path": str(script_path),
                "params": params,
                "job_status": "failed",
                "error": exc.stderr,
            }

    def _generate_slurm_script(
        self,
        params: dict[str, Any],
        run_dir: str,
        container_cmd: list[str],
    ) -> str:
        nodes = params.get("nodes", 1)
        walltime = params.get("walltime", "00:10:00")
        account = params.get("account")
        qos = params.get("qos")
        constraint = params.get("constraint")
        use_srun = params.get("use_srun", True)
        ntasks = max(1, int(nodes))
        run_dir_name = Path(run_dir).name

        sbatch_lines = [
            "#!/bin/bash",
            f"#SBATCH --nodes={nodes}",
            f"#SBATCH --time={walltime}",
            f"#SBATCH --job-name=amrex_{run_dir_name}",
            "#SBATCH --output=job_stdout.log",
            "#SBATCH --error=job_stderr.log",
        ]
        if account:
            sbatch_lines.append(f"#SBATCH --account={account}")
        if qos:
            sbatch_lines.append(f"#SBATCH --qos={qos}")
        if constraint:
            sbatch_lines.append(f"#SBATCH --constraint={constraint}")
        if getattr(self.config, "use_cuda", True):
            sbatch_lines.append("#SBATCH --gpus-per-task=1")
            sbatch_lines.append("#SBATCH --gpu-bind=none")

        command_str = self._format_command(container_cmd)
        if use_srun:
            command_str = f"srun -n {ntasks} {command_str}"

        return "\n".join(sbatch_lines) + f"""

echo "========================================"
echo "AMReX Container Run"
echo "Run: {run_dir_name}"
echo "Nodes: {nodes} | Tasks: {ntasks}"
echo "========================================"
echo ""

cd {Path(run_dir).absolute()}
echo "Starting at $(date)"
{command_str} > stdout.log 2> stderr.log

echo ""
echo "Finished at $(date)"
echo ""
ls -lh stdout.log stderr.log job_stdout.log job_stderr.log plt* 2>/dev/null || echo "  (no plotfiles yet)"
"""

    def _format_shell_script(self, cmd: list[str], run_dir: Path) -> str:
        return "\n".join([
            "#!/bin/bash",
            "# Local container execution script",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"cd {run_dir}",
            self._format_command(cmd),
            "",
        ])

    def _format_command(self, cmd: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in cmd)

    def _is_local_runtime(self, runtime: str) -> bool:
        return runtime in {"docker", "podman"}

    def _is_nersc_runtime(self, runtime: str) -> bool:
        return runtime == "podman-hpc"

    def _parse_sbatch_job_id(self, stdout: str) -> str | None:
        for token in stdout.split():
            if token.isdigit():
                return token
        return None
