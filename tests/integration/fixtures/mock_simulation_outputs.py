'''
Mock generators for simulation file structures.
Creates fake AMReX output for testing Analysis/Viz nodes.
'''
from pathlib import Path

def create_mock_run_directory(base_path: Path, status="success"):
    '''
    Populates a directory with fake AMReX log files and plotfiles.

    Args:
        base_path: The 'run_directory' to populate
        status: 'success', 'failed', or 'unstable'

    Returns:
        Path to the created directory
    '''
    base_path.mkdir(parents=True, exist_ok=True)

    # 1. Create Inputs file
    (base_path / "inputs").write_text("""# Generated inputs
amr.n_cell = 64 64 64
amr.max_level = 2
amr.cfl = 0.5
""")

    # 2. Create Run Log
    log_content = """
AMReX: Starting simulation...
STEP = 0    TIME = 0.0000000e+00  DT = 1.000000e-06
STEP = 10   TIME = 1.0000000e-05  DT = 1.000000e-06
STEP = 20   TIME = 2.0000000e-05  DT = 1.000000e-06
"""
    if status == "success":
        log_content += "AMReX: Run completed successfully.\n"
        log_content += "AMReX (24.12) finalized\n"
    elif status == "failed":
        log_content += "Abort: CFL condition violated.\n"
    elif status == "unstable":
        log_content += "Warning: dt < dtmin detected.\n"

    (base_path / "run.log").write_text(log_content)

    # 3. Create Mock Plotfiles (Folders with Header)
    for i in [0, 10, 20]:
        plt_dir = base_path / f"plt{i:05d}"
        plt_dir.mkdir()
        (plt_dir / "Header").write_text("AMReX Plotfile Version 1.0\n")
        (plt_dir / "Level_0").mkdir()
        (plt_dir / "Level_0" / "Cell_H").write_text("dummy data")

    return base_path

def create_failed_simulation(base_path: Path):
    '''Creates a simulation that crashed early.'''
    return create_mock_run_directory(base_path, status="failed")

def create_unstable_simulation(base_path: Path):
    '''Creates a simulation with CFL warnings.'''
    return create_mock_run_directory(base_path, status="unstable")
