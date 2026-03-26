"""
Graph Assembly: Execution Engine: Graph Execution Engine Tests

TRUE TDD: Written BEFORE implementation.
Verifies workflow orchestration, limits, and error handling.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from langgraph.errors import GraphRecursionError
from src.main import run_agent
from src.config import AMReXAgentConfig


class TestGraphExecutionEngine:
    """
    Graph Assembly: Execution Engine: Graph Execution Engine Tests.
    
    Verifies:
    - Workflow invocation
    - Recursion limits
    - Error boundaries
    - State management
    
    Design Decisions:
    - Synchronous execution (invoke)
    - Recursion limit = 50
    - In-memory persistence
    - Graceful error handling
    """

    @pytest.fixture
    def mock_config(self):
        """Mock AMReXAgentConfig."""
        config = Mock(spec=AMReXAgentConfig)
        config.max_iterations = 3
        return config

    @pytest.fixture
    def mock_compiled_app(self):
        """Mock the compiled LangGraph application."""
        return Mock()

    @pytest.fixture
    def mock_graph_builder(self, mock_compiled_app):
        """Mock create_amrex_agent_graph to return a builder that compiles to our app."""
        builder = Mock()
        builder.compile.return_value = mock_compiled_app
        return builder

    def test_successful_execution_returns_final_state(self, mock_config, mock_compiled_app, mock_graph_builder):
        """
        GIVEN: Valid prompt and config
        WHEN: run_agent executes successfully
        THEN: Returns final state from graph
        """
        expected_state = {
            "job_status": "completed",
            "job_id": "123",
            "workflow_history": ["architect", "reviewer", "writer"]
        }
        mock_compiled_app.invoke.return_value = expected_state

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            result = run_agent("test prompt", mock_config)

        assert result["job_status"] == "completed"
        assert result["job_id"] == "123"
        assert len(result["workflow_history"]) == 3

    def test_invoke_called_with_initial_state(self, mock_config, mock_compiled_app, mock_graph_builder):
        """
        GIVEN: Initialized state
        WHEN: run_agent executes
        THEN: app.invoke called with state containing prompt and config
        """
        mock_compiled_app.invoke.return_value = {"job_status": "success"}

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            run_agent("simulation request", mock_config)

        # Verify invoke was called
        assert mock_compiled_app.invoke.called
        
        # Get the state that was passed
        call_args = mock_compiled_app.invoke.call_args
        initial_state = call_args[0][0]
        
        assert "prompt" in initial_state
        assert initial_state["prompt"] == "simulation request"
        assert "config" in initial_state

    def test_normalizes_success_job_status_to_completed(
        self, mock_config, mock_compiled_app, mock_graph_builder
    ):
        mock_compiled_app.invoke.return_value = {"job_status": "success"}

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            result = run_agent("simulation request", mock_config)

        assert result["job_status"] == "completed"

    def test_recursion_limit_set_to_50(self, mock_config, mock_compiled_app, mock_graph_builder):
        """
        GIVEN: Graph execution
        WHEN: run_agent calls invoke
        THEN: recursion_limit=50 passed in config
        """
        mock_compiled_app.invoke.return_value = {"job_status": "success"}

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            run_agent("test", mock_config)

        # Get the config dict passed to invoke
        call_args = mock_compiled_app.invoke.call_args
        run_config = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        
        assert run_config["recursion_limit"] == 50

    def test_handles_graph_recursion_error(self, mock_config, mock_compiled_app, mock_graph_builder):
        """
        GIVEN: Infinite loop in graph
        WHEN: GraphRecursionError raised
        THEN: Returns error state with failed status
        """
        mock_compiled_app.invoke.side_effect = GraphRecursionError("Limit reached")

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            result = run_agent("infinite loop", mock_config)

        assert result["job_status"] == "failed"
        assert "recursion limit" in result["error"].lower()
        assert result["mode"] == "fail"

    def test_handles_general_exceptions(self, mock_config, mock_compiled_app, mock_graph_builder):
        """
        GIVEN: Node crashes during execution
        WHEN: Exception raised
        THEN: Returns error state with details
        """
        mock_compiled_app.invoke.side_effect = RuntimeError("Node crashed unexpectedly")

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            result = run_agent("crash test", mock_config)

        assert result["job_status"] == "failed"
        assert "Node crashed" in result["error"]
        assert result["mode"] == "fail"

    def test_handles_state_initialization_error(self, mock_config):
        """
        GIVEN: Invalid prompt (empty)
        WHEN: State initialization fails
        THEN: Returns error immediately
        """
        # Empty prompt should fail validation in initialize_state
        result = run_agent("", mock_config)

        assert result["job_status"] == "failed"
        assert "error" in result

    def test_handles_graph_compilation_error(self, mock_config, mock_graph_builder):
        """
        GIVEN: Graph construction fails
        WHEN: create_amrex_agent_graph raises exception
        THEN: Returns error state
        """
        with patch("src.main.create_amrex_agent_graph", side_effect=RuntimeError("Graph error")):
            result = run_agent("test", mock_config)

        assert result["job_status"] == "failed"
        assert "Graph" in result["error"]

    def test_paper_only_mode_initializes_nonempty_prompt(
        self, mock_config, mock_compiled_app, mock_graph_builder
    ):
        mock_compiled_app.invoke.return_value = {"job_status": "success"}

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            run_agent(
                "",
                mock_config,
                paper_source="2401.12345",
                paper_input_type="arxiv",
                paper_validator_enabled=True,
            )

        call_args = mock_compiled_app.invoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["prompt"]
        assert "2401.12345" in initial_state["prompt"]

    def test_preserves_initial_state_on_error(self, mock_config, mock_compiled_app, mock_graph_builder):
        """
        GIVEN: Execution fails
        WHEN: Error occurs
        THEN: Initial state data preserved in error response
        """
        mock_compiled_app.invoke.side_effect = RuntimeError("Failure")

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            result = run_agent("test prompt", mock_config)

        # Should still have initial state fields
        assert "prompt" in result or "error" in result
        assert result["job_status"] == "failed"

    def test_logs_workflow_start(self, mock_config, mock_compiled_app, mock_graph_builder, caplog):
        """
        GIVEN: Workflow starts
        WHEN: run_agent called
        THEN: Logs startup message
        """
        mock_compiled_app.invoke.return_value = {"job_status": "success"}

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            import logging
            with caplog.at_level(logging.INFO):
                run_agent("test", mock_config)

        # Should have logged something about starting
        log_messages = [rec.message for rec in caplog.records]
        assert any("AMReXAgent" in msg or "Starting" in msg for msg in log_messages)

    def test_logs_completion_status(self, mock_config, mock_compiled_app, mock_graph_builder, caplog):
        """
        GIVEN: Workflow completes
        WHEN: Execution finishes
        THEN: Logs completion with status
        """
        mock_compiled_app.invoke.return_value = {"job_status": "completed"}

        with patch("src.main.create_amrex_agent_graph", return_value=mock_graph_builder):
            import logging
            with caplog.at_level(logging.INFO):
                run_agent("test", mock_config)

        log_messages = [rec.message for rec in caplog.records]
        assert any("complete" in msg.lower() for msg in log_messages)
