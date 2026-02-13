import os

import pytest

from tests.e2e.readme_command_runner import run_commands_by_file


@pytest.mark.e2e
def test_readme_command_runner_dry_run() -> None:
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    results = run_commands_by_file(repo_root, dry_run=True)

    assert results, "No README commands discovered for dry-run execution"

    for path, entries in results.items():
        assert entries, f"No commands for {path}"
        for entry in entries:
            assert entry["status"] == "dry_run", f"Unexpected status for {entry['id']}"


@pytest.mark.e2e
def test_readme_command_runner_execute_amrex_agent_only() -> None:
    if not _assets_available():
        pytest.skip("Required repos/schemas/indices not available for README execution.")
    if not _llm_available():
        pytest.skip("LLM API key not available for README execution.")

    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    file_filter = [
        "README.md",
        "demo/amrex/README.md",
        "demo/pelec/README.md",
        "demo/pelelmex/README.md",
        "demo/erf/README.md",
    ]
    results = run_commands_by_file(
        repo_root,
        file_filter=file_filter,
        dry_run=False,
        timeout_seconds=30,
        stop_on_failure=True,
        entry_filter=_is_executable_readme_command,
        command_transform=_force_dry_run,
    )

    failures = [
        (path, entry)
        for path, entries in results.items()
        for entry in entries
        if entry["status"] in {"failed", "timeout"}
    ]
    if failures:
        lines = ["README command execution failures:"]
        for path, entry in failures[:20]:
            lines.append(
                f"  - {path} :: {entry['id']} ({entry['status']}, rc={entry.get('returncode')})"
            )
        if len(failures) > 20:
            lines.append(f"  - ... and {len(failures) - 20} more")
        pytest.fail("\n".join(lines))


@pytest.mark.e2e
@pytest.mark.use_real_services
@pytest.mark.requires_repos
@pytest.mark.requires_schema
def test_readme_command_runner_execute_superfacility_sfapi() -> None:
    if not _assets_available():
        pytest.skip("Required repos/schemas/indices not available for README execution.")
    if not _llm_available():
        pytest.skip("LLM API key not available for README execution.")
    if not _sfapi_available():
        pytest.skip("SFAPI credentials not available for README execution.")

    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    file_filter = ["demo/superfacility/README.md"]
    results = run_commands_by_file(
        repo_root,
        file_filter=file_filter,
        dry_run=False,
        timeout_seconds=120,
        stop_on_failure=True,
        entry_filter=_is_executable_readme_command,
        command_transform=_force_stage_run,
    )

    failures = [
        (path, entry)
        for path, entries in results.items()
        for entry in entries
        if entry["status"] in {"failed", "timeout"}
    ]
    if failures:
        lines = ["Superfacility README command execution failures:"]
        for path, entry in failures[:20]:
            lines.append(
                f"  - {path} :: {entry['id']} ({entry['status']}, rc={entry.get('returncode')})"
            )
        if len(failures) > 20:
            lines.append(f"  - ... and {len(failures) - 20} more")
        pytest.fail("\n".join(lines))


@pytest.mark.e2e
@pytest.mark.skip(reason="Manual-only: run full README commands when needed.")
def test_readme_command_runner_execute_full_file_manual() -> None:
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    file_filter = ["demo/README.md"]
    results = run_commands_by_file(
        repo_root,
        file_filter=file_filter,
        dry_run=False,
        timeout_seconds=60,
        stop_on_failure=True,
        command_transform=_force_dry_run,
    )

    failures = [
        (path, entry)
        for path, entries in results.items()
        for entry in entries
        if entry["status"] in {"failed", "timeout"}
    ]
    if failures:
        lines = ["Full README command execution failures:"]
        for path, entry in failures[:20]:
            lines.append(
                f"  - {path} :: {entry['id']} ({entry['status']}, rc={entry.get('returncode')})"
            )
        if len(failures) > 20:
            lines.append(f"  - ... and {len(failures) - 20} more")
        pytest.fail("\n".join(lines))


def _assets_available() -> bool:
    from tests.conftest import _indices_available, _repos_available, _schemas_available

    solvers = ("PeleC", "PeleLMeX", "ERF", "AMReX")
    if not _repos_available(solvers):
        return False
    if not _schemas_available(solvers):
        return False
    if not _indices_available(("faiss", "level0", "level1", "level2")):
        return False
    return True


def _llm_available() -> bool:
    from tests.conftest import _has_cborg_key

    if _has_cborg_key():
        return True
    if os.getenv("OPENAI_API_KEY"):
        return True
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    if os.getenv("ALCF_API_KEY"):
        return True
    return False


def _force_dry_run(command: str) -> str:
    if "amrex_agent.py" not in command:
        return command
    if "--run-mode" in command or "--dry-run" in command:
        return command
    return f"{command} --run-mode dry"


def _force_stage_run(command: str) -> str:
    if "amrex_agent.py" not in command:
        return command
    if "--run-mode" in command or "--dry-run" in command:
        return command
    return f"{command} --run-mode stage"


def _is_executable_readme_command(entry: dict) -> bool:
    text = entry["text"]
    return "amrex_agent.py" in text


def _sfapi_available() -> bool:
    from src.services.run_superfacility_tools import _resolve_sfapi_credentials

    client_id, secret = _resolve_sfapi_credentials()
    if client_id and secret:
        return True
    if os.getenv("NERSC_API_TOKEN") or os.getenv("SFAPI_TOKEN"):
        return True
    return False
