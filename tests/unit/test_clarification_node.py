"""Unit tests for the B1c clarification node."""

from __future__ import annotations

from unittest.mock import Mock, patch

from src.nodes.clarification_node import clarification_node


def _enabled_config(**overrides):
    base = {
        "enable_clarification_subgraph": True,
        "require_high_cost_confirmation": True,
    }
    base.update(overrides)
    return Mock(**base)


def _base_state(**overrides):
    state = {
        "config": _enabled_config(),
        "resolved_config": {
            "n_cell": "128 128 128",
            "max_level": 1,
            "stop_time": 0.01,
            "max_step": 100,
            "amr.plot_vars": "density temperature",
            "node_count": 2,
            "time_limit": "00:15:00",
            "cluster": "perlmutter",
        },
        "intent_locked_fields": [],
        "requested_plot_vars": ["temperature"],
        "prompt": "Run a combustion flame case.",
        "clarification_turns": 0,
        "clarification_history": [],
        "interactive_available": True,
        "high_cost_operation_pending": False,
    }
    state.update(overrides)
    return state


def _questions(updates):
    return updates["clarification_questions"]


class TestClarificationNode:
    def test_complete_config_needs_no_clarification(self):
        """
        Given: resolved_config has all required fields
        When:  clarification_node runs
        Then:  clarification_needed = False
               clarification_questions = []
        """
        state = _base_state()

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
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )

        updates = clarification_node(state)
        joined = " ".join(q["question_text"] for q in _questions(updates)).lower()

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
        state = _base_state(
            resolved_config={
                "n_cell": "128 128 128",
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
            },
            requested_plot_vars=[],
        )

        updates = clarification_node(state)
        joined = " ".join(q["question_text"] for q in _questions(updates)).lower()

        assert updates["clarification_needed"] is True
        assert "visual" in joined or "plot" in joined

    def test_locked_fields_not_asked_about(self):
        """
        Given: max_level in intent_locked_fields
               (set by CLI, already resolved)
        When:  clarification_node runs
        Then:  no question about max_level generated
        """
        state = _base_state(
            resolved_config={
                "n_cell": "128 128 128",
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            },
            intent_locked_fields=["max_level"],
        )

        updates = clarification_node(state)
        joined = " ".join(q["question_text"] for q in _questions(updates)).lower()

        assert "max_level" not in joined

    def test_multiple_missing_fields_all_questioned(self):
        """
        Given: resolved_config missing n_cell
               and stop_time
        When:  clarification_node runs
        Then:  clarification_needed = True
               missing fields are recorded in context
               and at least one clarification question exists
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )

        updates = clarification_node(state)

        assert updates["clarification_needed"] is True
        assert len(updates["clarification_questions"]) >= 1
        assert "n_cell" in updates["clarification_context"]["missing_fields"]
        assert "stop_time" in updates["clarification_context"]["missing_fields"]

    def test_clarification_context_records_reason(self):
        """
        Given: clarification triggered by missing n_cell
        When:  clarification_node runs
        Then:  clarification_context records which
               fields caused the questions
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )

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
        state = _base_state(
            resolved_config={},
            requested_plot_vars=[],
        )

        with patch("src.utils.llm_calls.call_llm", side_effect=AssertionError("LLM must not be called")) as mock_call:
            clarification_node(state)

        mock_call.assert_not_called()


class TestDecisionLevels:
    def test_level_1_required_field_missing(self):
        """
        Given: resolved_config missing n_cell
               (level 1: required simulation param)
        When:  clarification_node runs
        Then:  ClarificationQuestion with
               decision_level=1 generated
               clarification_needed=True
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )
        updates = clarification_node(state)
        assert updates["clarification_needed"] is True
        assert any(q["decision_level"] == 1 for q in _questions(updates))

    def test_level_1_batches_all_missing_required_fields(self):
        """
        Given: all required fields are missing
        When:  clarification_node runs
        Then:  one turn asks about all required fields
               so turn cap cannot starve a required field
        """
        state = _base_state(
            resolved_config={
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )
        updates = clarification_node(state)
        asked_fields = {q["field_name"] for q in _questions(updates)}
        assert updates["clarification_needed"] is True
        assert updates["unresolved_level"] == 1
        assert asked_fields == {"n_cell", "max_level", "stop_time", "max_step"}

    def test_level_2_physics_ambiguity(self):
        """
        Given: prompt contains both 'flame' and
               'turbulence' with no clear priority
        When:  clarification_node runs
        Then:  ClarificationQuestion with
               decision_level=2 generated
        """
        state = _base_state(prompt="Need flame turbulence study")
        updates = clarification_node(state)
        assert any(q["decision_level"] == 2 for q in _questions(updates))

    def test_level_3_resource_unspecified(self):
        """
        Given: no node_count, no time_limit,
               no cluster in resolved_config
        When:  clarification_node runs
        Then:  ClarificationQuestion with
               decision_level=3 generated
        """
        state = _base_state(
            resolved_config={
                "n_cell": "128 128 128",
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "amr.plot_vars": "temperature",
            }
        )
        updates = clarification_node(state)
        assert any(q["decision_level"] == 3 for q in _questions(updates))

    def test_level_4_viz_preference_missing(self):
        """
        Given: no plot vars requested or configured
        When:  clarification_node runs
        Then:  ClarificationQuestion with
               decision_level=4 generated
        """
        state = _base_state(
            resolved_config={
                "n_cell": "128 128 128",
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
            },
            requested_plot_vars=[],
        )
        updates = clarification_node(state)
        assert any(q["decision_level"] == 4 for q in _questions(updates))

    def test_level_5_optional_refinement(self):
        """
        Given: required fields present
               optional fields have defaults
        When:  clarification_node runs
        Then:  decision_level 5 question or
               clarification_needed=False
        """
        state = _base_state()
        updates = clarification_node(state)
        has_level_5 = any(q["decision_level"] == 5 for q in _questions(updates))
        assert has_level_5 or updates["clarification_needed"] is False

    def test_level_6_confirmation(self):
        """
        Given: all fields resolved
               high-cost operation pending
        When:  clarification_node runs
        Then:  decision_level=6 confirmation
               question generated or skipped
               based on config
        """
        state = _base_state(high_cost_operation_pending=True)
        updates = clarification_node(state)
        has_level_6 = any(q["decision_level"] == 6 for q in _questions(updates))
        assert has_level_6 or updates["clarification_needed"] is False


class TestFallbackChain:
    def test_report_fallback_tier(self):
        """
        Given: clarification about a field that
               has a known report/documentation
               reference
        When:  ClarificationQuestion created
        Then:  fallback_tier = 'report'
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )
        updates = clarification_node(state)
        q = next(q for q in _questions(updates) if q["field_name"] == "n_cell")
        assert q["fallback_tier"] == "report"

    def test_amrex_generic_fallback_tier(self):
        """
        Given: clarification about a field with
               AMReX-generic documentation
        When:  ClarificationQuestion created
        Then:  fallback_tier = 'amrex_generic'
        """
        state = _base_state(
            resolved_config={
                "n_cell": "128 128 128",
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            }
        )
        updates = clarification_node(state)
        q = next(q for q in _questions(updates) if q["field_name"] == "max_level")
        assert q["fallback_tier"] == "amrex_generic"

    def test_faiss_fallback_tier(self):
        """
        Given: clarification about a field where
               similar cases exist in FAISS index
        When:  ClarificationQuestion created
        Then:  fallback_tier = 'faiss'
        """
        state = _base_state(
            resolved_config={
                "n_cell": "128 128 128",
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "amr.plot_vars": "temperature",
            }
        )
        updates = clarification_node(state)
        q = next(q for q in _questions(updates) if q["decision_level"] == 3)
        assert q["fallback_tier"] == "faiss"

    def test_free_text_fallback_tier(self):
        """
        Given: clarification about a novel field
               with no known reference
        When:  ClarificationQuestion created
        Then:  fallback_tier = 'free_text'
        """
        state = _base_state(prompt="Need to optimize alchemical phase-space process")
        updates = clarification_node(state)
        q = next(q for q in _questions(updates) if q["decision_level"] == 5)
        assert q["fallback_tier"] == "free_text"


class TestFeatureFlag:
    def test_flag_false_skips_clarification(self):
        """
        Given: enable_clarification_subgraph=False
        When:  clarification_node runs
        Then:  clarification_needed=False
               clarification_questions=[]
               no ClarificationQuestion generated
        """
        state = _base_state(config=_enabled_config(enable_clarification_subgraph=False))
        updates = clarification_node(state)
        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []

    def test_flag_false_insufficient_prompt(self):
        """
        Given: enable_clarification_subgraph=False
               prompt has no required fields
        When:  clarification_node runs
        Then:  node returns without blocking
               state flag set for downstream
               handling
        """
        state = _base_state(
            config=_enabled_config(enable_clarification_subgraph=False),
            resolved_config={},
            prompt="help",
        )
        updates = clarification_node(state)
        assert updates["clarification_needed"] is False
        assert updates["insufficient_prompt"] is True


class TestInteractiveAvailability:
    def test_interactive_unavailable_no_block(self):
        """
        Given: interactive_available=False in state
               clarification would normally trigger
        When:  clarification_node runs
        Then:  clarification_needed=False
               state carries insufficient_prompt flag
               pipeline not blocked
        """
        state = _base_state(
            interactive_available=False,
            resolved_config={},
        )
        updates = clarification_node(state)
        assert updates["clarification_needed"] is False
        assert updates["insufficient_prompt"] is True


class TestClarificationRecord:
    def test_record_written_to_history(self):
        """
        Given: clarification_needed=True
               ClarificationQuestion generated
        When:  clarification_node runs
        Then:  clarification_history has one entry
               entry is ClarificationRecord.model_dump()
               answered_by='pending'
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            },
            clarification_history=[],
        )
        updates = clarification_node(state)
        assert len(updates["clarification_history"]) == 1
        assert updates["clarification_history"][0]["answered_by"] == "pending"
        assert updates["clarification_history"][0]["question"]["decision_level"] == 1

    def test_max_turns_no_block(self):
        """
        Given: clarification_turns >= 3
        When:  clarification_node runs
        Then:  clarification_needed=False
               pipeline proceeds with best available
               config
        """
        state = _base_state(
            clarification_turns=3,
            resolved_config={},
        )
        updates = clarification_node(state)
        assert updates["clarification_needed"] is False

    def test_ai_agent_answer_path_identical(self):
        """
        Given: answer provided programmatically
               (ai_agent path)
        When:  ClarificationRecord created
        Then:  answered_by='ai_agent'
               resolved_value populated
               same record structure as human path
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            },
            ai_clarification_answers={"n_cell": "64 64 64"},
            clarification_history=[],
        )
        updates = clarification_node(state)
        assert len(updates["clarification_history"]) == 1
        record = updates["clarification_history"][0]
        assert record["answered_by"] == "ai_agent"
        assert record["resolved_value"] == "64 64 64"
        assert isinstance(record["question"], dict)

    def test_ai_agent_answer_applied_to_resolved_config(self):
        """
        Given: n_cell is missing and ai_clarification_answers provides it
        When:  clarification_node runs
        Then:  resolved_config is updated with AI answer before unblocking
        """
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
                "amr.plot_vars": "temperature",
            },
            ai_clarification_answers={"n_cell": "96 96 96"},
            clarification_history=[],
        )
        updates = clarification_node(state)
        assert updates["clarification_needed"] is False
        assert updates["resolved_config"]["n_cell"] == "96 96 96"
