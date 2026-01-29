from src.services.execution_tools import validate_executable_for_job


def test_validate_executable_passes_for_mpi_cuda():
    result = validate_executable_for_job(
        "solver.MPI.CUDA.ex",
        nodes=2,
        ntasks_per_node=4,
        constraint="gpu",
    )

    assert result["valid"] is True
    assert result["has_mpi"] is True
    assert result["has_cuda"] is True
    assert result["executable_type"] == "MPI+CUDA"


def test_validate_executable_flags_missing_mpi_and_cuda():
    result = validate_executable_for_job(
        "solver.ex",
        nodes=2,
        ntasks_per_node=2,
        constraint="gpu&hbm40g",
    )

    assert result["valid"] is False
    assert result["has_mpi"] is False
    assert result["has_cuda"] is False
    assert result["warnings"]
