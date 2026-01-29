"""
Generic AMReX file generation service.

Creates config.json, inputs, resources.json, submit script, and README
using solver-specific metadata provided by database/configs/*.
"""

from __future__ import annotations

import json
import math
import os
import socket
from pathlib import Path
from typing import Any

from amrex_tools import dict_to_pele_inputs
from database.configs import BaseAMReXConfig, discover_code_configs


class FileGenerationService:
    """Generate a runnable AMReX case directory from a validated config."""

    def __init__(self, config: Any | None = None) -> None:
        self.config = config
        if config and hasattr(config, "get_code_registry"):
            self.code_registry = config.get_code_registry()
        else:
            self.code_registry = {c.code_name: c for c in discover_code_configs()}

    def write_simulation_files(
        self,
        config_json: str,
        output_dir: str | Path,
        selected_solver: str | None = None,
        executable_path: str | None = None,
        system: str = "perlmutter",
    ) -> dict[str, str]:
        """
        Write config, inputs, resources, and submit files for a run.

        Call context: Used by inputs services to materialize a runnable case.

        Parameters
        ----------
        config_json : str
            JSON-encoded configuration payload.
        output_dir : str or Path
            Directory to write output files.
        selected_solver : str or None, optional
            Solver name override.
        executable_path : str or None, optional
            Explicit executable path to use.
        system : str, optional
            Target system for resource estimation.

        Returns
        -------
        dict
            Paths to generated files (config, inputs, resources, submit_script, readme).
        """
        config = json.loads(config_json)

        solver_config, solver_name = self._resolve_solver_config(
            config=config,
            selected_solver=selected_solver,
        )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if not executable_path:
            executable_path = solver_config.resolve_executable_path(self.config)
        if not executable_path:
            raise ValueError(
                f"Executable path is required for {solver_name}. "
                "Provide executable_path or configure a solver-specific default."
            )

        # 1. Save config as JSON
        config_file = output_path / "config.json"
        config_file.write_text(config_json)

        # 2. Generate inputs file
        inputs_dict = {k: v for k, v in config.items() if k != "_metadata"}
        inputs_file = dict_to_pele_inputs(inputs_dict, output_path / "inputs")

        # 3. Generate resource estimates
        resources = solver_config.estimate_resources(config, system=system)
        metadata = config.get("_metadata", {})
        resources["timestamp"] = metadata.get("timestamp", "unknown")
        resources["solver"] = solver_name
        resources_file = output_path / "resources.json"
        resources_file.write_text(json.dumps(resources, indent=2))

        # 4. Generate SLURM script
        slurm_content = self._generate_slurm_script(
            solver_config=solver_config,
            resources=resources,
            executable_path=str(executable_path),
        )
        slurm_file = output_path / "submit.sh"
        slurm_file.write_text(slurm_content)
        slurm_file.chmod(0o755)

        # 5. Generate README
        readme_content = self._generate_readme(
            solver_config=solver_config,
            config=config,
            resources=resources,
            executable_path=str(executable_path),
        )
        readme_file = output_path / "README.md"
        readme_file.write_text(readme_content)

        return {
            "config": str(config_file),
            "inputs": str(inputs_file),
            "resources": str(resources_file),
            "submit_script": str(slurm_file),
            "readme": str(readme_file),
        }

    def _resolve_solver_config(
        self,
        config: dict[str, Any],
        selected_solver: str | None,
    ) -> tuple[type[BaseAMReXConfig], str]:
        solver_name = selected_solver or self._infer_solver_from_config(config)
        if not solver_name:
            raise ValueError("selected_solver is required for file generation")

        solver_config = self.code_registry.get(solver_name)
        if not solver_config:
            raise ValueError(f"Unknown solver: {solver_name}")

        return solver_config, solver_name

    def _infer_solver_from_config(self, config: dict[str, Any]) -> str | None:
        metadata = config.get("_metadata", {}) if isinstance(config, dict) else {}
        for key in ("selected_solver", "solver", "code", "code_name"):
            if key in metadata:
                return metadata[key]
            if key in config:
                return config[key]

        lower_registry = {name.lower(): name for name in self.code_registry}
        for section in config:
            name = lower_registry.get(str(section).lower())
            if name:
                return name

        return None

    def _generate_slurm_script(
        self,
        solver_config: type[BaseAMReXConfig],
        resources: dict[str, Any],
        executable_path: str,
    ) -> str:
        which_site, _ = self._detect_hpc_system()

        nodes = int(resources.get("recommended_nodes", 1))
        hours = int(math.ceil(resources.get("estimated_walltime_hours", 1)))

        slurm_meta = solver_config.get_slurm_metadata()
        job_name = slurm_meta.get("job_name", f"{solver_config.code_name.lower()}_sim")
        display_name = slurm_meta.get("display_name", solver_config.code_name)

        if which_site == "nersc":
            partition = "regular"
            constraint = "cpu"
            cores_per_node = 128
            account = os.environ.get("SBATCH_ACCOUNT", "m1234")
            total_cores = resources.get("total_cores", nodes * cores_per_node)
            srun_cmd = f"srun -n {total_cores} -c 2 --cpu_bind=cores"
        elif which_site == "olcf":
            partition = "batch"
            constraint = ""
            cores_per_node = 64
            account = os.environ.get("SBATCH_ACCOUNT", "ABC123")
            total_cores = resources.get("total_cores", nodes * cores_per_node)
            srun_cmd = f"srun -n {total_cores} --gpus-per-task=1"
        elif which_site == "alcf":
            partition = "prod"
            constraint = ""
            cores_per_node = 64
            account = os.environ.get("SBATCH_ACCOUNT", "datascience")
            total_cores = resources.get("total_cores", nodes * cores_per_node)
            srun_cmd = f"mpiexec -n {total_cores} --ppn {cores_per_node}"
        else:
            partition = "regular"
            constraint = ""
            cores_per_node = 64
            account = "default"
            total_cores = resources.get("total_cores", nodes * cores_per_node)
            srun_cmd = f"mpirun -np {total_cores}"

        cells_per_core = int(resources.get("cells_per_core", 0) or 0)
        memory_gb = float(resources.get("memory_gb", 0.0) or 0.0)
        base_cells = int(resources.get("base_cells", 0) or 0)
        max_cells = int(resources.get("max_cells", 0) or 0)

        script = f"""#!/bin/bash
#SBATCH -A {account}
#SBATCH -J {job_name}
#SBATCH -o %x-%j.out
#SBATCH -e %x-%j.err
#SBATCH -N {nodes}
#SBATCH -t {hours}:00:00
#SBATCH -q {partition}
"""

        if constraint:
            script += f"#SBATCH -C {constraint}\n"

        script += f"""
# ==============================================================================
# {display_name} Simulation - Generated by Pele Assistant
# ==============================================================================
#
# Configuration:
#   Base grid: {base_cells:,} cells
#   Max cells (AMR): {max_cells:,} cells
#   Estimated memory: {memory_gb:.1f} GB
#   Cells per core: {cells_per_core:,}
#
# Generated: {resources.get('timestamp', '')}
# ==============================================================================

echo "Job started: $(date)"
echo "Running on: $(hostname)"
echo "Working directory: $(pwd)"
echo ""

# Load modules (adjust for your system)
"""

        if which_site == "nersc":
            script += """module load PrgEnv-gnu
module load cmake
module load cray-hdf5
module load cray-netcdf
"""
        elif which_site == "olcf":
            script += """module load PrgEnv-gnu
module load cmake
module load hdf5
module load netcdf
"""
        else:
            script += """# Load your system-specific modules here
# module load gcc
# module load openmpi
# module load cmake
"""

        script += f"""
echo "Loaded modules:"
module list
echo ""

# Run simulation
echo "Starting {display_name}..."
echo "Command: {srun_cmd} {executable_path} inputs"
echo ""

{srun_cmd} \\
    {executable_path} \\
    inputs

EXIT_CODE=$?

echo ""
echo "Simulation finished: $(date)"
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "SUCCESS"
else
    echo "FAILED - check error log"
fi

exit $EXIT_CODE
"""

        return script

    def _generate_readme(
        self,
        solver_config: type[BaseAMReXConfig],
        config: dict[str, Any],
        resources: dict[str, Any],
        executable_path: str,
    ) -> str:
        metadata = config.get("_metadata", {})
        readme_parts = [
            f"# {solver_config.get_readme_title()}\n",
            f"\n**Generated:** {metadata.get('timestamp', 'unknown')}  ",
            f"\n**Intent:** {metadata.get('user_intent', 'unknown')}  ",
            f"\n**Baseline:** {metadata.get('baseline', 'unknown')}\n",
            "\n## Configuration Summary\n",
        ]

        summary_lines = solver_config.get_readme_summary_lines(config)
        summary_lines.extend(solver_config.get_readme_solver_lines(config))
        for line in summary_lines:
            if ":" in line:
                label, value = line.split(":", 1)
                readme_parts.append(f"\n- **{label.strip()}:** {value.strip()}")
            else:
                readme_parts.append(f"\n- {line}")

        readme_parts.extend([
            "\n\n## Resource Estimates\n",
            f"\n- **Base cells:** {resources.get('base_cells', 0):,}",
            f"\n- **Max cells (AMR):** {resources.get('max_cells', 0):,}",
            f"\n- **Memory:** {resources.get('memory_gb', 0.0):.1f} GB",
            f"\n- **Recommended nodes:** {resources.get('recommended_nodes', 1)}",
            f"\n- **Total cores:** {resources.get('total_cores', 0)}",
            f"\n- **Estimated walltime:** {resources.get('estimated_walltime_hours', 0.0):.1f} hours",
            f"\n- **Cost:** {resources.get('cost_node_hours', 0.0):.1f} node-hours\n",
            "\n## Files\n",
            "\n- `config.json` - Complete configuration in JSON format",
            "\n- `inputs` - ParmParse inputs file",
            "\n- `resources.json` - Resource estimates and metadata",
            "\n- `submit.sh` - SLURM batch script (edit account/partition as needed)",
            "\n- `README.md` - This file\n",
            "\n## Running\n",
            "\n1. **Review configuration:**\n",
        ])

        readme_parts.append("   " + "```" + "bash\n")
        readme_parts.append("   cat inputs\n")
        readme_parts.append("   " + "```" + "\n\n")

        readme_parts.append("2. **Edit batch script if needed:**\n")
        readme_parts.append("   " + "```" + "bash\n")
        readme_parts.append("   vim submit.sh  # Update SBATCH account, partition, etc.\n")
        readme_parts.append("   " + "```" + "\n\n")

        readme_parts.append("3. **Submit job:**\n")
        readme_parts.append("   " + "```" + "bash\n")
        readme_parts.append("   sbatch submit.sh\n")
        readme_parts.append("   " + "```" + "\n\n")

        readme_parts.append("4. **Monitor:**\n")
        readme_parts.append("   " + "```" + "bash\n")
        readme_parts.append("   squeue -u $USER\n")
        readme_parts.append("   tail -f *.out\n")
        readme_parts.append("   " + "```" + "\n\n")

        readme_parts.extend([
            "## Generated by Pele Assistant\n",
            "\nThis simulation was generated using the Pele Assistant tool.\n",
            f"Executable: `{executable_path}`\n",
        ])

        return "".join(readme_parts)

    @staticmethod
    def _detect_hpc_system() -> tuple[str, str]:
        nersc_host = os.environ.get("NERSC_HOST")
        if nersc_host and nersc_host in ["perlmutter", "alvarez", "muller"]:
            return "nersc", "perlmutter"

        if os.environ.get("LMOD_SITE_NAME") == "OLCF":
            host_name = socket.getfqdn()
            if "frontier" in host_name:
                return "olcf", "frontier"
            if "crusher" in host_name:
                return "olcf", "crusher"

        fqdn = socket.getfqdn()
        if "alcf.anl.gov" in fqdn and "polaris" in fqdn:
            return "alcf", "polaris"

        return "unknown", "unknown"


if __name__ == "__main__":
    import sys
    import tempfile

    from amrex_tools import find_inputs_file, parse_pele_inputs
    from database.configs import discover_code_configs

    # Minimal smoke test: use AMReX test inputs as the source.
    config_candidates = discover_code_configs()
    sample_solver = config_candidates[0].code_name if config_candidates else None
    if not sample_solver:
        raise ValueError("No solver configs available for smoke test")

    amrex_agent_root = Path(__file__).parent.parent.parent
    amrex_root = amrex_agent_root.parent / "amrex"
    if not amrex_root.exists():
        alt_root = amrex_agent_root.parent.parent / "amrex"
        if alt_root.exists():
            amrex_root = alt_root
    exec_dir = amrex_root / "Tests/Amr/Advection_AmrCore/Exec"
    inputs_path = find_inputs_file.invoke({"directory": str(exec_dir)}) if exec_dir.exists() else None
    if not inputs_path:
        print(f"No AMReX inputs found under {exec_dir}; skipping smoke test.")
        sys.exit(0)

    sample_config = parse_pele_inputs(inputs_path)
    sample_config["_metadata"] = {
        "timestamp": "smoke-test",
        "user_intent": "smoke test",
        "baseline": str(inputs_path),
        "selected_solver": sample_solver,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        service = FileGenerationService()
        result = service.write_simulation_files(
            config_json=json.dumps(sample_config),
            output_dir=tmpdir,
            selected_solver=sample_solver,
            executable_path=f"/path/to/{sample_solver}.ex",
        )
        print("Smoke test generated files:")
        for key, path in result.items():
            print(f"  {key}: {path}")
