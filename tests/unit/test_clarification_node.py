"""Unit tests for the B1c clarification node."""

from __future__ import annotations

from unittest.mock import patch

from src.nodes.clarification_node import clarification_node


class TestClarificationNode:
    def test_complete_config_needs_no_clarification(self):
        """
        Given: resolved_config has all required fields
        When:  clarification_node runs
        Then:  clarification_needed = False
               clarification_questions = []
        """
        state = {
            "resolved_config": {
                "n_cell": "128 128 128",
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "amr.plot_vars": "density",
            },
            "intent_locked_fields": [],
            "requested_plot_vars": ["temperature"],
        }

        updates = clarification_node(state)

        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []

    def test_missing_required_field_triggers_question(self):
        """
        Given: resolved_config missing n_cell
        When:  clarification_node runs
        Then:  clarification_needed = True
               at least one question mentions n_cell
               or grid resolution
        """
        state = {
            "resolved_config": {
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
            "intent_locked_fields": [],
            "requested_plot_vars": ["temperature"],
        }

        updates = clarification_node(state)
        joined = " ".join(updates["clarification_questions"]).lower()

        assert updates["clarification_needed"] is True
        assert "n_cell" in joined or "grid resolution" in joined

    def test_missing_viz_vars_triggers_question(self):
        """
        Given: requested_plot_vars = []
               resolved_config has no plotfile vars
        When:  clarification_node runs
        Then:  clarification_needed = True
               a question about visualization appears
        """
        state = {
            "resolved_config": {
                "n_cell": "128 128 128",
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
            "intent_locked_fields": [],
            "requested_plot_vars": [],
        }

        updates = clarification_node(state)
        joined = " ".join(updates["clarification_questions"]).lower()

        assert updates["clarification_needed"] is True
        assert "visual" in joined or "plot" in joined

    def test_locked_fields_not_asked_about(self):
        """
        Given: max_level in intent_locked_fields
               (set by CLI, already resolved)
        When:  clarification_node runs
        Then:  no question about max_level generated
        """
        state = {
            "resolved_config": {
                "n_cell": "128 128 128",
                "stop_time": 0.01,
                "max_step": 100,
            },
            "intent_locked_fields": ["max_level"],
            "requested_plot_vars": ["temperature"],
        }

        updates = clarification_node(state)
        joined = " ".join(updates["clarification_questions"]).lower()

        assert "max_level" not in joined

    def test_multiple_missing_fields_all_questioned(self):
        """
        Given: resolved_config missing n_cell
               and stop_time
        When:  clarification_node runs
        Then:  clarification_needed = True
               len(clarification_questions) >= 2
        """
        state = {
            "resolved_config": {
                "max_level": 1,
                "max_step": 100,
            },
            "intent_locked_fields": [],
            "requested_plot_vars": ["temperature"],
        }

        updates = clarification_node(state)

        assert updates["clarification_needed"] is True
        assert len(updates["clarification_questions"]) >= 2

    def test_clarification_context_records_reason(self):
        """
        Given: clarification triggered by missing n_cell
        When:  clarification_node runs
        Then:  clarification_context records which
               fields caused the questions
        """
        state = {
            "resolved_config": {
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
            "intent_locked_fields": [],
            "requested_plot_vars": ["temperature"],
        }

        updates = clarification_node(state)
        context = updates["clarification_context"]

        assert "missing_fields" in context
        assert "n_cell" in context["missing_fields"]

    def test_no_llm_call_in_clarification_node(self):
        """
        Given: clarification_node runs
        When:  any input
        Then:  no LLM call is made
               questions are generated from field
               inspection only — deterministic
        """
        state = {
            "resolved_config": {},
            "intent_locked_fields": [],
            "requested_plot_vars": [],
        }

        with patch("src.utils.llm_calls.call_llm", side_effect=AssertionError("LLM must not be called")) as mock_call:
            clarification_node(state)

        mock_call.assert_not_called()
