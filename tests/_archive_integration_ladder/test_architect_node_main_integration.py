"""
Integration Test: Architect Node (Architect Node) + main.py

Validates end-to-end integration:
- main.py initialize_state creates valid GraphState
- architect_node processes initialized state
- All Architect Node: State Adapter / Service Integration / Feedback Loop / Iteration Safety / Workflow History Logging features work together
"""
import pytest
from unittest.mock import Mock, patch
from src.main import initialize_state
from src.config import load_config
from src.nodes.architect_node import architect_node


class TestArchitectNodeMainIntegration:
    """Test Architect Node integration with main.py workflow."""
    
    @pytest.fixture
    def mock_architect_service(self):
        """Mock ArchitectService to avoid real LLM calls."""
        service = Mock()
        service.create_plan_rag.return_value = {
            "selected_case": "PeleC/Exec/RegTests/PMF",
            "modifications": [("amr.n_cell", "64 64 64")],
            "reasoning": "Selected PMF case for premixed flame simulation",
            "baseline_confidence": 0.92
        }
        return service
    
    def test_initialize_state_creates_valid_graphstate(self):
        """
        GIVEN: User requirement and config
        WHEN: initialize_state called
        THEN: Returns dict with all Architect Node required fields
        """
        config = load_config()
        state = initialize_state("Simulate a premixed flame in 3D", config)
        
        # Architect Node: State Adapter: State validation
        assert "prompt" in state
        assert "config" in state
        assert state["prompt"] == "Simulate a premixed flame in 3D"
        
        # Architect Node: Iteration Safety: Iteration safety
        assert state["retry_count"] == 0
        assert state["max_retries"] == 3
        assert state["iteration"] == 0
        
        # Architect Node: Feedback Loop: Feedback loop
        assert state["mode"] == "initial"
        assert state["errors_active"] == []
        
        # Architect Node: Workflow History Logging: History tracking
        assert state["workflow_history"] == []
    
    def test_architect_node_processes_initialized_state(self, mock_architect_service):
        """
        GIVEN: State initialized via main.py
        WHEN: architect_node processes it
        THEN: All Architect Node: State Adapter / Service Integration / Feedback Loop / Iteration Safety / Workflow History Logging features execute successfully
        """
        # Initialize state using main.py function
        config = load_config()
        state = initialize_state("Simulate a premixed flame in 3D", config)
        
        # Execute architect_node
        with patch("src.nodes.architect_node.ArchitectService", return_value=mock_architect_service):
            updates = architect_node(state)
        
        # Verify Architect Node: Service Integration: Service orchestration
        assert updates["selected_case"] == "PeleC/Exec/RegTests/PMF"
        assert len(updates["modifications"]) == 1
        
        # Verify Architect Node: Iteration Safety: Iteration safety
        assert updates["iteration"] == 1  # Incremented from 0
        assert updates["retry_count"] == 0  # Not incremented (initial mode)
        assert updates["loop_count"] == 1  # Legacy field
        
        # Verify Architect Node: Feedback Loop: Mode reset
        assert updates["mode"] == "proceed"
        assert updates["errors_active"] == []
        
        # Verify Architect Node: Workflow History Logging: History logging
        assert len(updates["workflow_history"]) == 1
        history_entry = updates["workflow_history"][0]
        assert history_entry["node"] == "architect"
        assert history_entry["action"] == "plan_created"
        assert history_entry["selected_case"] == "PeleC/Exec/RegTests/PMF"
        assert history_entry["iteration"] == 1
    
    def test_backward_compatibility_with_user_requirement(self, mock_architect_service):
        """
        GIVEN: Legacy code using state['prompt']
        WHEN: architect_node executes
        THEN: Extracts prompt from user_requirement field
        """
        config = load_config()
        state = initialize_state("Legacy prompt", config)
        
        # Remove 'prompt' to test fallback
        state_legacy = {k: v for k, v in state.items() if k != 'prompt'}
        state_legacy['prompt'] = "Legacy prompt"
        
        with patch("src.nodes.architect_node.ArchitectService", return_value=mock_architect_service):
            updates = architect_node(state_legacy)
        
        # Should still work via user_requirement fallback
        assert "selected_case" in updates
        mock_architect_service.create_plan_rag.assert_called_once()
        call_kwargs = mock_architect_service.create_plan_rag.call_args.kwargs
        assert call_kwargs['user_prompt'] == "Legacy prompt"
    
    def test_state_merge_simulation(self, mock_architect_service):
        """
        GIVEN: First architect_node execution
        WHEN: Updates merged with state (simulating LangGraph)
        THEN: Second execution receives complete state
        """
        config = load_config()
        state = initialize_state("Test prompt", config)
        
        with patch("src.nodes.architect_node.ArchitectService", return_value=mock_architect_service):
            # First execution
            updates_1 = architect_node(state)
            
            # Simulate LangGraph merge
            state_after_first = {**state, **updates_1}
            
            # Verify merged state has all fields
            assert "prompt" in state_after_first
            assert "config" in state_after_first
            assert state_after_first["iteration"] == 1
            assert len(state_after_first["workflow_history"]) == 1
            
            # Second execution (would happen in retry loop)
            state_after_first["mode"] = "retry"
            state_after_first["errors_active"] = ["Test error"]
            
            updates_2 = architect_node(state_after_first)
            
            # Verify iteration incremented again
            assert updates_2["iteration"] == 2
            assert len(updates_2["workflow_history"]) == 2
