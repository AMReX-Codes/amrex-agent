import json
from pathlib import Path

import pytest

from tests.e2e.readme_command_registry import extract_readme_entries


@pytest.mark.e2e
def test_readme_command_registry_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    registry_path = repo_root / "tests" / "e2e" / "readme_command_registry.json"
    if not registry_path.exists():
        pytest.fail("Registry file missing: tests/e2e/readme_command_registry.json")

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    expected = extract_readme_entries(repo_root)

    def key(entry: dict) -> tuple[str, str, str]:
        return (entry["path"], entry["kind"], entry["hash"])

    registry_keys = {key(entry) for entry in registry}
    expected_keys = {key(entry) for entry in expected}

    missing = sorted(expected_keys - registry_keys)
    extra = sorted(registry_keys - expected_keys)

    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append("Missing registry entries:")
            parts.extend(f"  - {path} ({kind}) {hash_value}" for path, kind, hash_value in missing[:25])
            if len(missing) > 25:
                parts.append(f"  - ... and {len(missing) - 25} more")
        if extra:
            parts.append("Extra registry entries (no longer in readmes):")
            parts.extend(f"  - {path} ({kind}) {hash_value}" for path, kind, hash_value in extra[:25])
            if len(extra) > 25:
                parts.append(f"  - ... and {len(extra) - 25} more")
        pytest.fail("\n".join(parts))
