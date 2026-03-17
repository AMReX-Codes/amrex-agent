import importlib.util
import os
import sys
from pathlib import Path


def _load_module() -> object:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "rename_schema_after_build.py"
    spec = importlib.util.spec_from_file_location("rename_schema_after_build", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Failed to load rename_schema_after_build module.")
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sync_complete_current_does_not_self_retarget_with_multiple_complete_files(tmp_path: Path) -> None:
    module = _load_module()
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()

    older = schema_dir / "solver_complete_v1_alpha.json"
    newer = schema_dir / "solver_complete_v1_beta.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    os.utime(older, (1_700_000_000, 1_700_000_000))
    os.utime(newer, (1_800_000_000, 1_800_000_000))

    current = schema_dir / "solver_complete_current.json"
    current.symlink_to(newer.name)

    group = module.SchemaGroup(
        solver="solver",
        kind="complete",
        files=[current, older, newer],
    )
    module._sync_complete_current_symlink(schema_dir, group)

    assert current.is_symlink()
    assert current.readlink().as_posix() == newer.name
    assert current.readlink().name != current.name


def test_sync_complete_current_uses_deterministic_tie_break_for_newest(tmp_path: Path) -> None:
    module = _load_module()
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()

    first = schema_dir / "solver_complete_v1_alpha.json"
    second = schema_dir / "solver_complete_v1_beta.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    shared_mtime = 1_800_000_000
    os.utime(first, (shared_mtime, shared_mtime))
    os.utime(second, (shared_mtime, shared_mtime))

    current = schema_dir / "solver_complete_current.json"
    current.symlink_to(first.name)

    group = module.SchemaGroup(solver="solver", kind="complete", files=[second, first])
    module._sync_complete_current_symlink(schema_dir, group)
    assert current.readlink().as_posix() == second.name

    group_reverse = module.SchemaGroup(solver="solver", kind="complete", files=[first, second])
    module._sync_complete_current_symlink(schema_dir, group_reverse)
    assert current.readlink().as_posix() == second.name


def test_complete_schema_candidates_excludes_current_pointer_files(tmp_path: Path) -> None:
    module = _load_module()
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()

    complete_a = schema_dir / "solver_complete_v1_a.json"
    complete_b = schema_dir / "solver_complete_v1_b.json"
    current = schema_dir / "solver_complete_current.json"
    complete_a.write_text("{}", encoding="utf-8")
    complete_b.write_text("{}", encoding="utf-8")
    current.symlink_to(complete_b.name)

    candidates = module._complete_schema_candidates([current, complete_a, complete_b])
    assert candidates == [complete_a, complete_b]
