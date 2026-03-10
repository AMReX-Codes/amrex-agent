"""
Intent Extraction Node tests.
"""

import importlib
from unittest.mock import Mock, patch


intent_extraction_node_module = importlib.import_module("src.nodes.intent_extraction_node")


class TestIntentExtractionNode:
    def test_flag_false_skips_llm_call(self):
        """
        Given: enable_intent_extraction = False
        When:  intent_extraction_node runs
        Then:  no LLM call is made
               intent_extraction_applied = False
               resolved_config populated from
               Tier 1/Tier 2 only
        """
        state = {
            "prompt": "test prompt",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=False),
            "cli_values": {"max_level": 2},
            "config_values": {"n_cell": "64 64 64"},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent") as mock_llm:
            updates = intent_extraction_node_module.intent_extraction_node(state)

        mock_llm.assert_not_called()
        assert updates["intent_extraction_applied"] is False
        assert updates["resolved_config"]["max_level"] == 2
        assert updates["resolved_config"]["n_cell"] == "64 64 64"

    def test_flag_true_calls_llm(self):
        """
        Given: enable_intent_extraction = True
               mock LLM returns valid JSON
        When:  intent_extraction_node runs
        Then:  LLM called exactly once
               intent_extraction_applied = True
               intent_extraction_error = None
        """
        state = {
            "prompt": "set max_level to 2",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {},
            "config_values": {},
        }

        mock_llm = Mock(return_value={"max_level": 2})
        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", mock_llm):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        mock_llm.assert_called_once()
        assert updates["intent_extraction_applied"] is True
        assert updates["intent_extraction_error"] is None

    def test_locked_field_not_overridden_by_llm(self):
        """
        Given: enable_intent_extraction = True
               CLI explicitly set max_level = 2
               LLM returns max_level = 5
        When:  intent_extraction_node runs
        Then:  resolved_config['max_level'] = 2
               'max_level' in intent_locked_fields
        """
        state = {
            "prompt": "set max_level to 5",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {"max_level": 2},
            "config_values": {},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(return_value={"max_level": 5})):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert updates["resolved_config"]["max_level"] == 2
        assert "max_level" in updates["intent_locked_fields"]

    def test_llm_populates_unlocked_field(self):
        """
        Given: enable_intent_extraction = True
               no CLI value for n_cell
               LLM returns n_cell = '128 128 128'
        When:  intent_extraction_node runs
        Then:  resolved_config['n_cell'] =
               '128 128 128'
               'n_cell' NOT in intent_locked_fields
        """
        state = {
            "prompt": "set n_cell to 128 128 128",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {},
            "config_values": {},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(return_value={"n_cell": "128 128 128"})):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert updates["resolved_config"]["n_cell"] == "128 128 128"
        assert "n_cell" not in updates["intent_locked_fields"]

    def test_llm_failure_proceeds_no_block(self):
        """
        Given: enable_intent_extraction = True
               mock LLM raises exception
        When:  intent_extraction_node runs
        Then:  node returns without raising
               intent_extraction_applied = False
               intent_extraction_error contains
               error description
               mode != 'fail'
        """
        state = {
            "prompt": "test prompt",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {"max_level": 2},
            "config_values": {"n_cell": "64 64 64"},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(side_effect=RuntimeError("LLM down"))):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert updates["intent_extraction_applied"] is False
        assert "LLM down" in (updates["intent_extraction_error"] or "")
        assert updates.get("mode", state["mode"]) != "fail"

    def test_llm_invalid_json_proceeds_no_block(self):
        """
        Given: enable_intent_extraction = True
               mock LLM returns non-JSON string
        When:  intent_extraction_node runs
        Then:  same as LLM failure - no block
               intent_extraction_error set
               intent_extraction_applied = False
        """
        state = {
            "prompt": "test prompt",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {"max_level": 2},
            "config_values": {"n_cell": "64 64 64"},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(side_effect=ValueError("invalid JSON"))):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert updates["intent_extraction_applied"] is False
        assert "invalid JSON" in (updates["intent_extraction_error"] or "")
        assert updates.get("mode", state["mode"]) != "fail"

    def test_tier1_beats_tier2_beats_llm(self):
        """
        Given: CLI sets param_a = 'cli_value'
               config sets param_a = 'config_value'
               LLM returns param_a = 'llm_value'
        When:  intent_extraction_node runs
        Then:  resolved_config['param_a'] = 'cli_value'
        """
        state = {
            "prompt": "set param_a",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {"param_a": "cli_value"},
            "config_values": {"param_a": "config_value"},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(return_value={"param_a": "llm_value"})):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert updates["resolved_config"]["param_a"] == "cli_value"

    def test_tier2_beats_llm_when_no_cli(self):
        """
        Given: no CLI value for param_b
               config sets param_b = 'config_value'
               LLM returns param_b = 'llm_value'
        When:  intent_extraction_node runs
        Then:  resolved_config['param_b'] =
               'config_value'
        """
        state = {
            "prompt": "set param_b",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {},
            "config_values": {"param_b": "config_value"},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(return_value={"param_b": "llm_value"})):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert updates["resolved_config"]["param_b"] == "config_value"

    def test_resolved_config_written_to_state(self):
        """
        Given: extraction runs successfully
        When:  intent_extraction_node returns
        Then:  state['resolved_config'] is a dict
               state['intent_extraction_applied']
               is bool
               state['intent_locked_fields'] is list
        """
        state = {
            "prompt": "set cfl to 0.7",
            "mode": "initial",
            "config": Mock(enable_intent_extraction=True),
            "cli_values": {},
            "config_values": {"max_level": 1},
        }

        with patch.object(intent_extraction_node_module, "_call_llm_for_intent", Mock(return_value={"cfl": 0.7})):
            updates = intent_extraction_node_module.intent_extraction_node(state)

        assert isinstance(updates["resolved_config"], dict)
        assert isinstance(updates["intent_extraction_applied"], bool)
        assert isinstance(updates["intent_locked_fields"], list)
