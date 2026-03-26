"""Unit tests for schema-aware clarification handler node."""

from __future__ import annotations

from src.models.clarification_schemas import ClarificationQuestion, ClarificationRecord
from src.nodes.clarification_handler_node import (
    _route_after_clarification,
    clarification_handler_node,
)


def _base_state(**overrides):
    state = {
        "resolved_config": {},
        "requested_plot_vars": [],
        "clarification_history": [],
        "clarification_needed": True,
        "clarification_turns": 0,
        "skip_further_clarification": False,
        "user_response": None,
        "ai_agent_response": None,
    }
    state.update(overrides)
    return state


def _pending_record(
    field_name: str,
    *,
    decision_level: int = 1,
    fallback_tier: str = "report",
) -> dict:
    question = ClarificationQuestion(
        field_name=field_name,
        question_text=f"Question for {field_name}",
        decision_level=decision_level,
        fallback_tier=fallback_tier,
        context={},
    )
    record = ClarificationRecord(
        question=question,
        answered_by="pending",
        resolved_value=None,
        turn=0,
    )
    return record.model_dump()


class TestSchemaAwareHandler:
    def test_pending_record_found_and_answered(self):
        """
        Given: clarification_history has one
               ClarificationRecord with
               answered_by='pending'
               question.field_name='n_cell'
               user_response='128 128 64'
        When:  clarification_handler_node runs
        Then:  record answered_by='human'
               record resolved_value='128 128 64'
               resolved_config['n_cell']='128 128 64'
        """
        state = _base_state(
            clarification_history=[_pending_record("n_cell")],
            user_response="128 128 64",
        )

        updates = clarification_handler_node(state)
        record = updates["clarification_history"][0]

        assert record["answered_by"] == "human"
        assert record["resolved_value"] == "128 128 64"
        assert updates["resolved_config"]["n_cell"] == "128 128 64"

    def test_ai_agent_answer_marks_record(self):
        """
        Given: clarification_history has pending
               record for field_name='stop_time'
               state has ai_agent_response set
               (not user_response)
        When:  clarification_handler_node runs
        Then:  record answered_by='ai_agent'
               record resolved_value populated
               resolved_config['stop_time'] set
        """
        state = _base_state(
            clarification_history=[_pending_record("stop_time")],
            ai_agent_response="0.02",
        )

        updates = clarification_handler_node(state)
        record = updates["clarification_history"][0]

        assert record["answered_by"] == "ai_agent"
        assert record["resolved_value"] == "0.02"
        assert updates["resolved_config"]["stop_time"] == "0.02"

    def test_human_response_takes_precedence_when_both_present(self):
        """
        Given: pending clarification record and both
               user_response + ai_agent_response are set
        When:  clarification_handler_node runs
        Then:  human response is used as resolved value
               and answered_by='human'
        """
        state = _base_state(
            clarification_history=[_pending_record("stop_time")],
            user_response="0.03",
            ai_agent_response="0.02",
        )

        updates = clarification_handler_node(state)
        record = updates["clarification_history"][0]

        assert record["answered_by"] == "human"
        assert record["resolved_value"] == "0.03"
        assert updates["resolved_config"]["stop_time"] == "0.03"

    def test_level_4_response_updates_plot_vars(self):
        """
        Given: pending record with decision_level=4
               field_name='requested_plot_vars'
               user_response='temperature vorticity'
        When:  clarification_handler_node runs
        Then:  requested_plot_vars contains
               'temperature' and 'vorticity'
               record answered_by='human'
               resolved_value set
        """
        state = _base_state(
            clarification_history=[
                _pending_record(
                    "requested_plot_vars",
                    decision_level=4,
                    fallback_tier="amrex_generic",
                )
            ],
            user_response="temperature vorticity",
        )

        updates = clarification_handler_node(state)
        record = updates["clarification_history"][0]

        assert "temperature" in updates["requested_plot_vars"]
        assert "vorticity" in updates["requested_plot_vars"]
        assert record["answered_by"] == "human"
        assert record["resolved_value"] == "temperature vorticity"

    def test_level_4_ai_answer_must_match_candidate_set(self):
        record = _pending_record(
            "requested_plot_vars",
            decision_level=4,
            fallback_tier="amrex_generic",
        )
        record["question"]["context"] = {
            "token": "velocity",
            "candidates": ["x_velocity", "y_velocity"],
        }
        state = _base_state(
            clarification_history=[record],
            ai_agent_response="z_velocity",
        )
        updates = clarification_handler_node(state)
        assert updates["clarification_history"][0]["answered_by"] == "pending"
        assert updates["clarification_needed"] is True

    def test_fallback_tier_faiss_empty_response(self):
        """
        Given: pending record with
               fallback_tier='faiss'
               user_response='' (empty)
        When:  clarification_handler_node runs
        Then:  record stays answered_by='pending'
               clarification_needed remains True
               clarification_turns incremented
        """
        state = _base_state(
            clarification_history=[_pending_record("node_count", fallback_tier="faiss")],
            user_response="",
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_history"][0]["answered_by"] == "pending"
        assert updates["clarification_needed"] is True
        assert updates["clarification_turns"] == 1

    def test_fallback_tier_amrex_generic_empty(self):
        """
        Given: pending record with
               fallback_tier='amrex_generic'
               user_response='' (empty)
        When:  clarification_handler_node runs
        Then:  same as faiss empty - not resolved
               clarification_needed remains True
        """
        state = _base_state(
            clarification_history=[_pending_record("plot_vars", fallback_tier="amrex_generic")],
            user_response="",
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_history"][0]["answered_by"] == "pending"
        assert updates["clarification_needed"] is True
        assert updates["clarification_turns"] == 1

    def test_multiple_pending_records_one_at_a_time(self):
        """
        Given: clarification_history has two
               pending ClarificationRecords
               user_response addresses first only
        When:  clarification_handler_node runs
        Then:  first record answered
               second record still pending
               clarification_needed remains True
               (more questions remain)
        """
        state = _base_state(
            clarification_history=[
                _pending_record("n_cell"),
                _pending_record("stop_time"),
            ],
            user_response="128 128 64",
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_history"][0]["answered_by"] == "human"
        assert updates["clarification_history"][1]["answered_by"] == "pending"
        assert updates["clarification_needed"] is True

    def test_last_pending_resolved_clears_flag(self):
        """
        Given: clarification_history has one
               pending ClarificationRecord
               valid user_response provided
        When:  clarification_handler_node runs
        Then:  no pending records remain
               clarification_needed=False
        """
        state = _base_state(
            clarification_history=[_pending_record("max_step")],
            user_response="300",
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_history"][0]["answered_by"] == "human"
        assert updates["clarification_needed"] is False

    def test_max_turns_forces_resolution(self):
        """
        Given: clarification_turns >= 3
               pending records still exist
        When:  clarification_handler_node runs
        Then:  clarification_needed=False
               skip_further_clarification=True
               pending records left as-is
               (not answered, not blocking)
        """
        pending = _pending_record("n_cell")
        state = _base_state(
            clarification_history=[pending],
            clarification_turns=3,
            user_response="128 128 64",
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_needed"] is False
        assert updates["skip_further_clarification"] is True
        assert updates["clarification_history"][0]["answered_by"] == "pending"

    def test_no_pending_records_clears_flag(self):
        """
        Given: clarification_history has records
               but all answered_by != 'pending'
        When:  clarification_handler_node runs
        Then:  clarification_needed=False
               no crash
        """
        record = _pending_record("n_cell")
        record["answered_by"] = "human"
        record["resolved_value"] = "128 128 64"

        state = _base_state(
            clarification_history=[record],
            user_response="ignored",
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_needed"] is False

    def test_none_response_does_not_crash(self):
        """
        Given: user_response=None
               pending record exists
        When:  clarification_handler_node runs
        Then:  no exception
               record remains pending
               turns incremented
        """
        state = _base_state(
            clarification_history=[_pending_record("n_cell")],
            user_response=None,
        )

        updates = clarification_handler_node(state)

        assert updates["clarification_history"][0]["answered_by"] == "pending"
        assert updates["clarification_turns"] == 1


class TestRoutingAfterHandler:
    def test_unresolved_routes_back_to_clarification(self):
        """
        Given: after handler runs
               clarification_needed=True
               (more pending records)
        When:  _route_after_clarification evaluated
        Then:  routes to clarification_node
               not to input_writer_node
        """
        route = _route_after_clarification({"clarification_needed": True})

        assert route == "clarification_node"
        assert route != "input_writer_node"

    def test_resolved_routes_to_input_writer(self):
        """
        Given: after handler runs
               clarification_needed=False
        When:  _route_after_clarification evaluated
        Then:  routes to input_writer_node
        """
        route = _route_after_clarification({"clarification_needed": False})

        assert route == "input_writer_node"
