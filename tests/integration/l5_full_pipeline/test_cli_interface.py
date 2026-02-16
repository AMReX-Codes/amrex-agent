"""
Level 5 Integration: CLI Interface Testing

Tests command-line interface:
- Argument parsing
- Prompt loading (string, file, stdin)
- Output formatting (human, JSON)
- Exit codes
- Error handling

These tests validate the user-facing interface.
"""
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from src.main import load_prompt_content, main, parse_arguments


@pytest.mark.integration_full
class TestCLIInterface:
    """Level 5: CLI interface tests."""

    def test_parse_arguments_with_prompt_string(self):
        """
        Test 1: --prompt argument parsed correctly

        Given: CLI args with --prompt
        When: parse_arguments() called
        Then: Returns namespace with prompt field
        """
        args = parse_arguments(["--prompt", "Test simulation"])

        assert args.prompt == "Test simulation"
        assert args.prompt_path is None

    def test_parse_arguments_with_prompt_file(self):
        """
        Test 2: --prompt-path argument parsed correctly

        Given: CLI args with --prompt-path
        When: parse_arguments() called
        Then: Returns namespace with prompt_path field
        """
        args = parse_arguments(["--prompt-path", "test.txt"])

        assert args.prompt_path == "test.txt"
        assert args.prompt is None

    def test_load_prompt_from_string(self):
        """
        Test 3: load_prompt_content handles inline string

        Given: Args with prompt string
        When: load_prompt_content() called
        Then: Returns prompt string
        """
        args = parse_arguments(["--prompt", "Inline test"])
        content = load_prompt_content(args)

        assert content == "Inline test"

    def test_load_prompt_from_file(self, tmp_path):
        """
        Test 4: load_prompt_content reads from file

        Given: File with prompt content
        When: load_prompt_content() called
        Then: Returns file contents
        """
        prompt_file = tmp_path / "test_prompt.txt"
        prompt_file.write_text("File-based prompt")

        args = parse_arguments(["--prompt-path", str(prompt_file)])
        content = load_prompt_content(args)

        assert content == "File-based prompt"

    def test_load_prompt_from_stdin(self, monkeypatch):
        """
        Test 5: load_prompt_content reads from stdin

        Given: --prompt-path - (stdin marker)
        When: load_prompt_content() called
        Then: Reads from sys.stdin
        """
        fake_stdin = StringIO("Stdin prompt\n")
        monkeypatch.setattr("sys.stdin", fake_stdin)

        args = parse_arguments(["--prompt-path", "-"])
        content = load_prompt_content(args)

        assert content == "Stdin prompt"

    def test_main_success_exit_code(self, tmp_path):
        """
        Test 6: main() returns 0 on success

        Given: Successful workflow
        When: main() executes
        Then: no exception
        """
        # Mock run_agent to return success
        with patch("src.main.run_agent") as mock_run:
            mock_run.return_value = {
                "job_status": "completed",
                "mode": "proceed"
            }

            main(["--prompt", "Test", "--output-dir", str(tmp_path)])

    def test_main_failure_exit_code(self, tmp_path):
        """
        Test 7: main() returns 1 on failure

        Given: Failed workflow
        When: main() executes
        Then: sys.exit(1)
        """
        with patch("src.main.run_agent") as mock_run:
            mock_run.return_value = {
                "job_status": "failed",
                "error": "Test error",
                "mode": "fail"
            }

            with pytest.raises(SystemExit) as exc_info:
                main(["--prompt", "Test", "--output-dir", str(tmp_path)])

            assert exc_info.value.code == 1

    def test_json_output_format(self, tmp_path, capsys):
        """
        Test 8: --json flag produces JSON output

        Given: --json flag
        When: main() executes
        Then: Stdout is valid JSON
        """
        import json

        with patch("src.main.run_agent") as mock_run:
            mock_run.return_value = {
                "job_status": "completed",
                "job_id": "test_123"
            }

            main(["--prompt", "Test", "--output-dir", str(tmp_path), "--json"])

            captured = capsys.readouterr()

            # Verify valid JSON
            output = json.loads(captured.out)
            assert output["job_status"] == "completed"
            assert output["job_id"] == "test_123"

    def test_main_uses_short_dns_prompt_file(self, tmp_path):
        """
        Test 9: main() passes prompt file content to run_agent.

        Given: Short DNS-mod prompt file
        When: main() executes with --prompt-path
        Then: run_agent receives prompt text with step-count instruction
        """
        repo_root = Path(__file__).resolve().parents[3]
        prompt_path = repo_root / "demo" / "pelelmex" / "user_requirements_test_DNS_mod_short.txt"
        assert prompt_path.exists(), f"Prompt file missing: {prompt_path}"

        with patch("src.main.run_agent") as mock_run:
            mock_run.return_value = {
                "job_status": "completed",
                "mode": "proceed"
            }

            main(["--prompt-path", str(prompt_path), "--output-dir", str(tmp_path), "--dry-run"])

            assert mock_run.call_count == 1
            passed_prompt = mock_run.call_args[0][0]
            assert "50 steps" in passed_prompt
