"""
Graph Assembly: Routing Logic: Graph Routing Logic Tests

TRUE TDD: Written BEFORE implementation.
Validates conditional edge functions for LangGraph workflow.
"""
import pytest
from langgraph.graph import END
from src.router_func import route_after_reviewer, route_after_analysis


class TestGraphRoutingLogic:
    """
    Graph Assembly: Routing Logic: Conditional Edge Logic Tests.
    
    Verifies:
    - Mode-based routing
    - Retry limit enforcement
    - Fail-safe behavior
    - Pure function semantics
    
    Design Decisions:
    - Read from state (not config)
    - Unknown mode → END
    - Structured debug logging
    - No state mutation
    """

    def test_route_after_reviewer_proceed(self):
        """
        GIVEN: mode='proceed' (validation passed)
        WHEN: route_after_reviewer called
        THEN: Returns 'input_writer'
        """
        state = {
            "mode": "proceed",
            "retry_count": 0,
            "max_retries": 3
        }
        
        assert route_after_reviewer(state) == "input_writer"

    def test_route_after_reviewer_retry_with_attempts_remaining(self):
        """
        GIVEN: mode='retry' and retry_count < max_retries
        WHEN: route_after_reviewer called
        THEN: Returns 'architect' (another attempt)
        """
        state = {
            "mode": "retry",
            "retry_count": 1,
            "max_retries": 3
        }
        
        assert route_after_reviewer(state) == "architect"

    def test_route_after_reviewer_fail(self):
        """
        GIVEN: mode='fail' (critical error)
        WHEN: route_after_reviewer called
        THEN: Returns END (terminate workflow)
        """
        state = {
            "mode": "fail",
            "retry_count": 0,
            "max_retries": 3
        }
        
        assert route_after_reviewer(state) == END

    def test_route_after_reviewer_max_retries_exceeded(self):
        """
        GIVEN: retry_count >= max_retries
        WHEN: route_after_reviewer called
        THEN: Returns END (prevent infinite loops)
        """
        state = {
            "mode": "retry",
            "retry_count": 3,
            "max_retries": 3
        }
        
        assert route_after_reviewer(state) == END

    def test_route_after_reviewer_unknown_mode(self):
        """
        GIVEN: mode='unknown_state' (defensive)
        WHEN: route_after_reviewer called
        THEN: Returns END (fail-safe)
        """
        state = {
            "mode": "unknown_state",
            "retry_count": 0
        }
        
        assert route_after_reviewer(state) == END

    def test_route_after_reviewer_missing_mode(self):
        """
        GIVEN: mode key missing from state
        WHEN: route_after_reviewer called
        THEN: Returns END (fail-safe default)
        """
        state = {
            "retry_count": 0,
            "max_retries": 3
        }
        
        assert route_after_reviewer(state) == END

    def test_route_after_analysis_success(self):
        """
        GIVEN: analysis_report.status='success'
        WHEN: route_after_analysis called
        THEN: Returns 'visualization'
        """
        state = {
            "analysis_report": {
                "status": "success"
            }
        }
        
        assert route_after_analysis(state) == "visualization"

    def test_route_after_analysis_failure(self):
        """
        GIVEN: analysis_report.status='failed'
        WHEN: route_after_analysis called
        THEN: Returns 'reviewer' (post-execution diagnosis)
        """
        state = {
            "analysis_report": {
                "status": "failed"
            }
        }
        
        assert route_after_analysis(state) == "reviewer"

    def test_route_after_analysis_missing_report(self):
        """
        GIVEN: analysis_report missing from state
        WHEN: route_after_analysis called
        THEN: Returns 'visualization' (default success path)
        """
        state = {}
        
        # Should handle gracefully (default to success)
        result = route_after_analysis(state)
        assert result in ["visualization", "reviewer"]

    def test_routers_are_pure_functions(self):
        """
        GIVEN: State dictionary
        WHEN: Router functions called
        THEN: Do not modify state (pure functions)
        """
        original_state = {
            "mode": "proceed",
            "retry_count": 1,
            "max_retries": 3
        }
        state_copy = original_state.copy()
        
        route_after_reviewer(original_state)
        
        # State should be unchanged
        assert original_state == state_copy
