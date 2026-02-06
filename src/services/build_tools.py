"""Build helpers for AMReX-based codes."""

import logging
import subprocess
from pathlib import Path

from database.configs.registry import is_pele_case_path

logger = logging.getLogger(__name__)


def compile_amrex(
    case_dir: str,
    use_cuda: bool = True,
    jobs: int = 16,
    config: dict | None = None,
) -> bool:
    """
    Compile any AMReX code in a case directory.

    Call context: Used by runner services to build executables on demand.

    Works for AMReX-based codes using the GNUmakefile build system.
    Auto-detects whether to use TPL targets (Pele codes only).

    Parameters
    ----------
    case_dir : str
        Path to the case directory containing the build files.
    use_cuda : bool, optional
        Whether to enable CUDA/HIP builds when available.
    jobs : int, optional
        Number of parallel build jobs to use.
    config : dict or None, optional
        Optional configuration data for build customization.

    Returns
    -------
    bool
        True if compilation succeeded, otherwise False.
    """
    case_dir = Path(case_dir)

    if not case_dir.exists():
        return False

    if not (case_dir / "GNUmakefile").exists():
        return False

    make_flags = []
    if use_cuda:
        make_flags.append("USE_CUDA=TRUE")

    make_flags.append("USE_MPI=TRUE")

    is_pele_code = is_pele_case_path(case_dir)

    if is_pele_code:
        logger.debug("Detected Pele code - using TPL targets")
        commands = [
            ["make", "TPLrealclean"] + make_flags,
            ["make", "realclean"],
            ["make", "TPL"] + make_flags,
            ["nice", "make", f"-j{jobs}"] + make_flags,
        ]
    else:
        logger.debug("Detected non-Pele AMReX code - skipping TPL targets")
        commands = [
            ["make", "realclean"],
            ["nice", "make", f"-j{jobs}"] + make_flags,
        ]

    try:
        for cmd in commands:
            result = subprocess.run(
                cmd,
                cwd=case_dir,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                logger.error("Compilation failed: %s", " ".join(cmd))
                if result.stdout:
                    logger.error("STDOUT: %s", result.stdout[-500:])
                if result.stderr:
                    logger.error("STDERR: %s", result.stderr[-500:])
                return False

        return True

    except (subprocess.TimeoutExpired, Exception) as exc:
        logger.error("Compilation exception: %s", exc)
        return False
