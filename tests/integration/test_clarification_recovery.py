from __future__ import annotations

from types import SimpleNamespace

from src.graph import _route_after_clarification
from src.nodes.clarification_node import MAX_CLARIFICATION_TURNS, clarification_node


def _config(**overrides):
    base = {
        "enable_clarification_subgraph": True,
        "require_high_cost_confirmation": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _base_state(**overrides):
    state = {
        "config": _config(),
        "prompt": "Run a combustion flame case.",
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
        "clarification_history": [],
        "clarification_turns": 0,
        "interactive_available": True,
        "high_cost_operation_pending": False,
    }
    state.update(overrides)
    return state


def _run_and_merge(state: dict) -> dict:
    updates = clarification_node(state)
    merged = dict(state)
    merged.update(updates)
    return merged


class TestAmbiguousPromptEntersClarification:
    def test_missing_required_field_routes_to_clarification(self):
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
                "amr.plot_vars": "density temperature",
                "node_count": 2,
                "time_limit": "00:15:00",
                "cluster": "perlmutter",
            }
        )

        updates = clarification_node(state)

        assert updates["clarification_needed"] is True
        assert updates["clarification_questions"]
        assert any(
            (q.get("field_name") == "n_cell")
            or ("n_cell" in q.get("question_text", "").lower())
            or ("grid resolution" in q.get("question_text", "").lower())
            for q in updates["clarification_questions"]
        )

    def test_complete_config_skips_clarification(self):
        state = _base_state()

        updates = clarification_node(state)

        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []

    def test_flag_false_bypasses_clarification(self):
        state = _base_state(
            config=_config(enable_clarification_subgraph=False),
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
        )

        updates = clarification_node(state)

        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []


class TestConflictingConstraintsRouting:
    def test_level_2_physics_ambiguity_flagged(self):
        state = _base_state(prompt="Need a flame turbulence study", resolved_config=_base_state()["resolved_config"])

        updates = clarification_node(state)

        level_2 = [q for q in updates["clarification_questions"] if q["decision_level"] == 2]
        assert level_2
        assert level_2[0]["fallback_tier"] in {"free_text", "report", "faiss", "amrex_generic"}

    def test_level_6_high_cost_triggers_confirm(self):
        state = _base_state(
            high_cost_operation_pending=True,
            prompt="Run a standard setup",
        )

        updates = clarification_node(state)

        level_6 = [q for q in updates["clarification_questions"] if q["decision_level"] == 6]
        assert level_6
        assert level_6[0]["fallback_tier"] == "report"

    def test_conflicting_levels_asks_highest_first(self):
        state = _base_state(
            resolved_config={
                "stop_time": 0.01,
                "max_step": 100,
                "amr.plot_vars": "density temperature",
            },
            prompt="flame turbulence setup",
        )

        updates = clarification_node(state)

        assert updates["clarification_needed"] is True
        assert any(q["decision_level"] == 1 for q in updates["clarification_questions"])


class TestNonInteractiveGracefulFail:
    def test_non_interactive_mode_no_block(self):
        state = _base_state(
            interactive_available=False,
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
        )

        updates = clarification_node(state)

        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []

    def test_non_interactive_max_turns_exits(self):
        state = _base_state(
            interactive_available=False,
            clarification_turns=MAX_CLARIFICATION_TURNS,
            resolved_config={},
        )

        updates = clarification_node(state)

        # Current behavior signals forced exit by returning no clarification questions.
        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []


class TestRetryNonConvergence:
    def test_repeated_turns_increment_counter(self):
        state = _base_state(
            clarification_turns=1,
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
        )

        updates = clarification_node(state)

        assert updates["clarification_turns"] == 2
        assert updates["clarification_questions"]

    def test_max_turns_forces_exit(self):
        state = _base_state(
            clarification_turns=MAX_CLARIFICATION_TURNS,
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            },
        )

        updates = clarification_node(state)

        assert updates["clarification_needed"] is False
        assert updates["clarification_questions"] == []

    def test_non_convergence_does_not_loop_forever(self):
        state = _base_state(
            resolved_config={
                "max_level": 1,
                "stop_time": 0.01,
                "max_step": 100,
            }
        )

        for _ in range(MAX_CLARIFICATION_TURNS):
            state = _run_and_merge(state)
            assert state["clarification_turns"] <= MAX_CLARIFICATION_TURNS

        state = _run_and_merge(state)

        assert state["clarification_needed"] is False
        assert state["clarification_turns"] == MAX_CLARIFICATION_TURNS
        assert state["clarification_questions"] == []

    def test_resolved_field_reduces_questions(self):
        state = _base_state(
            resolved_config={
                "stop_time": 0.01,
                "max_step": 100,
                "amr.plot_vars": "density temperature",
            }
        )

        first = _run_and_merge(state)
        first_fields = {q["field_name"] for q in first["clarification_questions"]}
        assert {"n_cell", "max_level"}.issubset(first_fields)

        second_input = dict(first)
        second_input["resolved_config"] = dict(first["resolved_config"], n_cell="96 96 96")
        second = clarification_node(second_input)

        second_fields = {q["field_name"] for q in second["clarification_questions"]}
        assert "max_level" in second_fields
        assert "n_cell" not in second_fields
        assert second["clarification_turns"] == first["clarification_turns"] + 1


class TestRecoveryRouting:
    def test_still_needed_does_not_route_forward(self):
        route = _route_after_clarification({"clarification_needed": True})

        assert route != "input_writer_node"
        assert route == "clarification_handler"

    def test_resolved_routes_to_input_writer(self):
        route = _route_after_clarification(
            {
                "clarification_needed": False,
                "skip_further_clarification": False,
            }
        )

        assert route == "input_writer_node"

    def test_forced_exit_routes_forward(self):
        route = _route_after_clarification(
            {
                "clarification_needed": False,
                "skip_further_clarification": True,
            }
        )

        assert route == "input_writer_node"
