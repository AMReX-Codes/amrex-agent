"""
Graph Assembly: State Initialization: Graph State Initialization Tests

TRUE TDD: Written BEFORE implementation.
Validates state setup before workflow execution.
"""
import pytest
from unittest.mock import Mock
from pathlib import Path
from src.main import initialize_state
from src.config import AMReXAgentConfig


class TestGraphStateInitialization:
    """
    Graph Assembly: State Initialization: Graph State Initialization Tests.
    
    Verifies:
    - Default counter initialization
    - Prompt loading (file vs string)
    - Config injection
    - Required field presence
    
    Design Decisions:
    - TypedDict (not Pydantic BaseModel)
    - Defaults set at initialization
    - JSON-serializable for checkpointer
    """

    @pytest.fixture
    def mock_config(self):
        """Mock AMReXAgentConfig with defaults."""
        config = Mock(spec=AMReXAgentConfig)
        config.max_iterations = 3
        return config

    def test_initializes_default_counters(self, mock_config):
        """
        GIVEN: Fresh initialization
        WHEN: initialize_state called
        THEN: Counters set to 0, mode='initial'
        """
        state = initialize_state("simulation request", mock_config)
        
        assert state["retry_count"] == 0
        assert state["iteration"] == 0
        assert state["mode"] == "initial"

    def test_initializes_empty_collections(self, mock_config):
        """
        GIVEN: Fresh initialization
        WHEN: initialize_state called
        THEN: Lists initialized as empty
        """
        state = initialize_state("test request", mock_config)
        
        assert state["workflow_history"] == []
        assert state["errors_active"] == []
        assert state["modifications"] == []

    def test_loads_prompt_from_file_path(self, mock_config, tmp_path):
        """
        GIVEN: Path to file containing prompt
        WHEN: initialize_state called with file path
        THEN: Prompt content read from file
        """
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("simulate combustion")
        
        state = initialize_state(str(prompt_file), mock_config)
        
        assert state["prompt"] == "simulate combustion"

    def test_loads_prompt_from_string(self, mock_config):
        """
        GIVEN: Direct string prompt
        WHEN: initialize_state called
        THEN: Prompt used as-is
        """
        raw_prompt = "run flame simulation"
        
        state = initialize_state(raw_prompt, mock_config)
        
        assert state["prompt"] == "run flame simulation"

    def test_injects_config_object(self, mock_config):
        """
        GIVEN: AMReXAgentConfig instance
        WHEN: initialize_state called
        THEN: Config accessible in state
        """
        state = initialize_state("test", mock_config)
        
        assert state["config"] == mock_config

    def test_sets_max_retries_from_config(self, mock_config):
        """
        GIVEN: Config with max_iterations=5
        WHEN: State initialized
        THEN: max_retries set from config
        """
        mock_config.max_iterations = 5
        
        state = initialize_state("test", mock_config)
        
        assert state["max_retries"] == 5

    def test_schema_has_node_required_fields(self, mock_config):
        """
        GIVEN: Initialized state
        WHEN: Nodes access standard keys
        THEN: Keys exist (even if empty/default)
        """
        state = initialize_state("test", mock_config)
        
        # Reviewer needs these
        assert "errors_active" in state
        assert "mode" in state
        assert "retry_count" in state
        
        # Writer needs these (will be populated by Architect)
        assert "modifications" in state
        
        # History tracking
        assert "workflow_history" in state

    def test_validates_empty_prompt(self, mock_config):
        """
        GIVEN: Empty string prompt
        WHEN: initialize_state called
        THEN: Raises ValueError
        """
        with pytest.raises(ValueError, match="cannot be empty"):
            initialize_state("", mock_config)

    def test_validates_whitespace_only_prompt(self, mock_config):
        """
        GIVEN: Whitespace-only prompt
        WHEN: initialize_state called
        THEN: Raises ValueError
        """
        with pytest.raises(ValueError, match="cannot be empty"):
            initialize_state("   \n  ", mock_config)

    def test_handles_missing_prompt_file(self, mock_config):
        """
        GIVEN: Path to non-existent file
        WHEN: initialize_state called
        THEN: Treats as literal prompt (doesn't crash)
        """
        # Non-existent file path should be treated as string prompt
        state = initialize_state("/non/existent/file.txt", mock_config)
        
        # Should use the path string itself as prompt
        assert state["prompt"] == "/non/existent/file.txt"
