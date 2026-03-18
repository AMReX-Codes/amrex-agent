"""
Graph Assembly: CLI Entry Point: CLI Entry Point Tests

TRUE TDD: Written BEFORE implementation.
Validates argument parsing, input handling, and execution flow.
"""
import pytest
import sys
import io
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestCLIEntryPoint:
    """
    Graph Assembly: CLI Entry Point: CLI Entry Point Tests.
    
    Verifies:
    - Argument parsing
    - Input sources (file/stdin/string)
    - Configuration overrides
    - Output formatting
    - Error handling
    
    Design Decisions:
    - Support --prompt and --prompt-path
    - --config for custom config file
    - --json for machine-readable output
    - --verbose for debug logging
    - --dry-run flag
    """

    @pytest.fixture
    def mock_run_agent(self):
        """Mock the run_agent function to avoid actual execution."""
        with patch("src.main.run_agent") as mock:
            mock.return_value = {
                "job_status": "completed",
                "job_id": "test-123",
                "run_directory": "/tmp/test_run"
            }
            yield mock

    @pytest.fixture
    def mock_load_config(self):
        """Mock configuration loader."""
        with patch("src.main.load_config") as mock:
            config = Mock()
            config.output_dir = Path("/default/output")
            config.dry_run = False
            config.run_mode = "full"
            mock.return_value = config
            yield mock

    @pytest.fixture(autouse=True)
    def mock_preflight(self):
        """Default preflight behavior for CLI tests."""
        with patch("src.main.run_startup_readiness_checks") as mock_check:
            with patch("src.main.apply_interactive_fixes") as mock_apply:
                mock_check.return_value = {"exit_code": 0, "issues": []}
                mock_apply.return_value = {
                    "mode": "interactive",
                    "attempted_actions": [],
                    "resolved": [],
                    "unresolved": [],
                    "exit_code": 0,
                }
                yield {"check": mock_check, "apply": mock_apply}

    def test_parses_inline_prompt(self, mock_run_agent, mock_load_config):
        """
        GIVEN: --prompt with inline text
        WHEN: CLI invoked
        THEN: Prompt passed to run_agent
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'simulate combustion']):
            main()
        
        mock_run_agent.assert_called_once()
        call_args = mock_run_agent.call_args
        prompt_arg = call_args[0][0]
        assert prompt_arg == 'simulate combustion'

    def test_parses_prompt_from_file(self, tmp_path, mock_run_agent, mock_load_config):
        """
        GIVEN: --prompt-path pointing to file
        WHEN: CLI invoked
        THEN: File content passed to run_agent
        """
        from src.main import main
        
        prompt_file = tmp_path / "request.txt"
        prompt_file.write_text("simulate flame dynamics")
        
        with patch('sys.argv', ['amrex_agent', '--prompt-path', str(prompt_file)]):
            main()
        
        call_args = mock_run_agent.call_args
        prompt_arg = call_args[0][0]
        assert prompt_arg == 'simulate flame dynamics'

    def test_reads_from_stdin(self, mock_run_agent, mock_load_config, monkeypatch):
        """
        GIVEN: --prompt-path - (stdin)
        WHEN: CLI invoked
        THEN: Stdin content passed to run_agent
        """
        from src.main import main
        
        # Mock stdin
        monkeypatch.setattr('sys.stdin', io.StringIO('stdin prompt content'))
        
        with patch('sys.argv', ['amrex_agent', '--prompt-path', '-']):
            main()
        
        call_args = mock_run_agent.call_args
        prompt_arg = call_args[0][0]
        assert prompt_arg == 'stdin prompt content'

    def test_output_dir_override(self, mock_run_agent, mock_load_config):
        """
        GIVEN: --output-dir flag
        WHEN: CLI invoked
        THEN: Config updated with custom output dir
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--output-dir', '/custom/path']):
            main()
        
        # Check config was modified
        config_arg = mock_run_agent.call_args[0][1]
        assert str(config_arg.output_dir) == '/custom/path'

    def test_dry_run_flag_sets_config(self, mock_run_agent, mock_load_config):
        """
        GIVEN: --dry-run flag
        WHEN: CLI invoked
        THEN: Config.dry_run = True and run_mode = dry
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--dry-run']):
            main()
        
        config_arg = mock_run_agent.call_args[0][1]
        assert config_arg.dry_run is True
        assert config_arg.run_mode == "dry"

    def test_run_mode_flag_sets_config(self, mock_run_agent, mock_load_config):
        """
        GIVEN: --run-mode flag
        WHEN: CLI invoked
        THEN: Config.run_mode set and dry_run reflects it
        """
        from src.main import main

        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--run-mode', 'stage']):
            main()

        config_arg = mock_run_agent.call_args[0][1]
        assert config_arg.run_mode == "stage"
        assert config_arg.dry_run is False



    def test_verbose_flag_enables_debug_logging(self, mock_run_agent, mock_load_config):
        """
        GIVEN: --verbose flag
        WHEN: CLI invoked
        THEN: Logging level set to DEBUG
        """
        from src.main import main
        import logging
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--verbose']):
            with patch('logging.basicConfig') as mock_logging:
                main()
        
        # Verify basicConfig called with DEBUG level
        assert mock_logging.called
        call_kwargs = mock_logging.call_args[1]
        assert call_kwargs.get('level') == logging.DEBUG

    def test_json_output_format(self, mock_run_agent, mock_load_config, capsys):
        """
        GIVEN: --json flag
        WHEN: CLI invoked
        THEN: Output is JSON-formatted state
        """
        from src.main import main
        import json
        
        mock_run_agent.return_value = {
            "job_status": "completed",
            "job_id": "json-test"
        }
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--json']):
            main()
        
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        
        assert output["job_status"] == "completed"
        assert output["job_id"] == "json-test"

    def test_exits_with_error_code_on_failure(self, mock_run_agent, mock_load_config):
        """
        GIVEN: Workflow fails
        WHEN: job_status = failed
        THEN: sys.exit(1) called
        """
        from src.main import main
        
        mock_run_agent.return_value = {
            "job_status": "failed",
            "error": "Validation error"
        }
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 1

    def test_missing_prompt_shows_error(self):
        """
        GIVEN: No prompt argument
        WHEN: CLI invoked
        THEN: Exits with error
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent']):
            with pytest.raises(SystemExit):
                main()

    def test_help_displays_usage(self, capsys):
        """
        GIVEN: --help flag
        WHEN: CLI invoked
        THEN: Help text displayed
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'AMReXAgent' in captured.out or 'usage' in captured.out

    def test_invalid_prompt_file_shows_error(self, mock_load_config):
        """
        GIVEN: --prompt-path to non-existent file
        WHEN: CLI invoked
        THEN: FileNotFoundError caught and exits
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent', '--prompt-path', '/nonexistent/file.txt']):
            with pytest.raises(SystemExit) as exc_info:
                main()
        
        assert exc_info.value.code == 1

    def test_exception_shows_traceback_in_verbose(self, mock_run_agent, mock_load_config, capsys):
        """
        GIVEN: Exception raised and --verbose
        WHEN: CLI invoked
        THEN: Full traceback printed
        """
        from src.main import main
        
        mock_run_agent.side_effect = RuntimeError("Test error")
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--verbose']):
            with pytest.raises(SystemExit):
                main()
        
        captured = capsys.readouterr()
        assert 'Traceback' in captured.err or 'RuntimeError' in captured.err


    def test_backward_compatible_prompt_path_underscore(self, tmp_path, mock_run_agent, mock_load_config):
        """
        GIVEN: Old style --prompt_path (underscore)
        WHEN: CLI invoked
        THEN: Still works (backward compatibility)
        """
        from src.main import main
        
        prompt_file = tmp_path / "legacy.txt"
        prompt_file.write_text("legacy format")
        
        with patch('sys.argv', ['amrex_agent', '--prompt_path', str(prompt_file)]):
            main()
        
        call_args = mock_run_agent.call_args
        prompt_arg = call_args[0][0]
        assert prompt_arg == 'legacy format'

    def test_backward_compatible_output_dir_underscore(self, mock_run_agent, mock_load_config):
        """
        GIVEN: Old style --output_dir (underscore)
        WHEN: CLI invoked
        THEN: Still works (backward compatibility)
        """
        from src.main import main
        
        with patch('sys.argv', ['amrex_agent', '--prompt', 'test', '--output_dir', '/legacy/path']):
            main()
        
        config_arg = mock_run_agent.call_args[0][1]
        assert str(config_arg.output_dir) == '/legacy/path'
