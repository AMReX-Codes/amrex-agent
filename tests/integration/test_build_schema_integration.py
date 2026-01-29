import json
from pathlib import Path

from database.scripts.build_schema import SchemaBuilder


def test_build_schema_extracts_parmparse_from_source(tmp_path: Path) -> None:
    repo_root = tmp_path / "amrex"
    source_dir = repo_root / "Source"
    source_dir.mkdir(parents=True)

    cpp_file = source_dir / "Test.cpp"
    cpp_file.write_text(
        """#include <AMReX_ParmParse.H>

void foo() {
  amrex::ParmParse pp("amr");
  int n_cell = 0;
  pp.query("n_cell", n_cell);
}
"""
    )

    builder = SchemaBuilder(repo_root)
    schema = builder.scan_source_code(["Source"])

    assert "amr.n_cell" in schema

    output_dir = tmp_path / "schemas"
    output_path = builder.save(output_dir, solver_name="amrex")

    assert output_path.exists()
    saved = json.loads(output_path.read_text())
    assert "amr.n_cell" in saved


def test_build_schema_handles_parmparse_without_prefix(tmp_path: Path) -> None:
    repo_root = tmp_path / "amrex"
    source_dir = repo_root / "Source"
    source_dir.mkdir(parents=True)

    cpp_file = source_dir / "NoPrefix.cpp"
    cpp_file.write_text(
        """#include <AMReX_ParmParse.H>

void foo() {
  amrex::ParmParse pp;
  int steps = 0;
  pp.query("max_step", steps);
}
"""
    )

    builder = SchemaBuilder(repo_root)
    schema = builder.scan_source_code(["Source"])

    assert "max_step" in schema


def test_build_schema_handles_multiple_prefixes(tmp_path: Path) -> None:
    repo_root = tmp_path / "amrex"
    source_dir = repo_root / "Source"
    source_dir.mkdir(parents=True)

    cpp_file = source_dir / "MultiPrefix.cpp"
    cpp_file.write_text(
        """#include <AMReX_ParmParse.H>

void foo() {
  amrex::ParmParse pp_amr("amr");
  amrex::ParmParse pp_geom("geometry");
  int n_cell = 0;
  int is_periodic = 0;
  pp_amr.query("n_cell", n_cell);
  pp_geom.query("is_periodic", is_periodic);
}
"""
    )

    builder = SchemaBuilder(repo_root)
    schema = builder.scan_source_code(["Source"])

    assert "amr.n_cell" in schema
    assert "geometry.is_periodic" in schema


def test_build_schema_preserves_compile_time_default(tmp_path: Path) -> None:
    repo_root = tmp_path / "amrex"
    source_dir = repo_root / "Source"
    source_dir.mkdir(parents=True)

    cpp_file = source_dir / "Defaults.cpp"
    cpp_file.write_text(
        """#include <AMReX_ParmParse.H>

void foo() {
  amrex::ParmParse pp("amr");
  int max_threads = amrex::maxGpuThreads();
  pp.query("max_threads", max_threads);
}
"""
    )

    builder = SchemaBuilder(repo_root)
    schema = builder.scan_source_code(["Source"])

    assert "amr.max_threads" in schema
    assert schema["amr.max_threads"]["default"] == "amrex::maxGpuThreads()"
