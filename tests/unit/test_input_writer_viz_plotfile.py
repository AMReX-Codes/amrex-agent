"""
Unit tests for Input Writer plotfile variable injection priorities.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.nodes.input_writer_node import input_writer_node
from src.services.input_writer import (
    _resolve_plotfile_vars,
    apply_plotfile_vars_to_inputs_text,
)


class TestInputWriterPlotfileInjection:
    """
    Input Writer priority logic for plotfile vars.
    Priority 1: user specified → write exactly that
    Priority 2: user silent → preserve baseline value
    Priority 3: baseline has none → write nothing
    """

    def test_priority1_requested_vars_written_exactly(
            self, tmp_path):
        """
        Given: requested_plot_vars = ['temperature']
               baseline inputs has amr.plot_vars =
               density pressure
        When:  Input Writer runs
        Then:  generated inputs has
               amr.plot_vars = temperature
               ONLY temperature — baseline not merged
               baseline value overridden by user request
        """
        baseline = "amr.plot_vars = density pressure\nmax_step = 10\n"
        setting = _resolve_plotfile_vars(["temperature"], baseline, "PeleC")
        updated = apply_plotfile_vars_to_inputs_text(baseline, setting)
        assert "amr.plot_vars = temperature" in updated

    def test_priority1_no_extras_added(
            self, tmp_path):
        """
        Given: requested_plot_vars = ['temperature']
        When:  Input Writer runs
        Then:  'density' NOT in amr.plot_vars
               'pressure' NOT in amr.plot_vars
               User asked for temperature only.
        Guards against silent default injection.
        """
        baseline = "amr.plot_vars = density pressure\n"
        setting = _resolve_plotfile_vars(["temperature"], baseline, "PeleC")
        updated = apply_plotfile_vars_to_inputs_text(baseline, setting)
        assert "density pressure" not in updated
        assert "amr.plot_vars = temperature" in updated

    def test_priority2_baseline_preserved_when_silent(
            self, tmp_path):
        """
        Given: requested_plot_vars = []
               baseline inputs file contains:
               amr.plot_vars = density pressure velocity
        When:  Input Writer runs
        Then:  generated inputs preserves exactly:
               amr.plot_vars = density pressure velocity
        User did not specify — preserve baseline intent.
        """
        baseline = "amr.plot_vars = density pressure velocity\n"
        setting = _resolve_plotfile_vars([], baseline, "PeleC")
        updated = apply_plotfile_vars_to_inputs_text(baseline, setting)
        assert "amr.plot_vars = density pressure velocity" in updated

    def test_priority3_no_line_when_baseline_absent(
            self, tmp_path):
        """
        Given: requested_plot_vars = []
               baseline inputs file has NO plotfile
               var line
        When:  Input Writer runs
        Then:  generated inputs has NO plotfile var line
               solver uses compile-time defaults
        """
        baseline = "amr.n_cell = 64 64 64\n"
        setting = _resolve_plotfile_vars([], baseline, "PeleC")
        updated = apply_plotfile_vars_to_inputs_text(baseline, setting)
        assert "plot_vars" not in updated

    def test_code_specific_param_used_for_pelelmex(
            self, tmp_path):
        """
        Given: code_name = 'PeleLMeX'
               requested_plot_vars = ['temperature']
        When:  Input Writer runs
        Then:  generated inputs contains:
               peleLM.derive_plot_vars = temperature
               NOT amr.plot_vars
        """
        baseline = "amr.plot_vars = density pressure\n"
        setting = _resolve_plotfile_vars(["temperature"], baseline, "PeleLMeX")
        updated = apply_plotfile_vars_to_inputs_text(baseline, setting)
        assert "peleLM.derive_plot_vars = temperature" in updated
        assert "amr.plot_vars = temperature" not in updated

    def test_input_writer_reads_state_not_prompt(
            self, tmp_path):
        """
        Given: Input Writer node runs
        When:  it needs plot vars
        Then:  reads requested_plot_vars from state
               does not parse prompt text
               does not call extract_viz_params
        Extraction happens at graph entry, not here.
        """
        captured = {}

        class DummyService:
            def __init__(self, _config):
                self.cases_svc = None

            def apply_plan(
                self,
                selected_case,
                modifications,
                baseline,
                reasoning,
                output_dir,
                requested_plot_vars=None,
            ):
                captured["requested_plot_vars"] = requested_plot_vars
                run_dir = Path(output_dir)
                run_dir.mkdir(parents=True, exist_ok=True)
                inputs = run_dir / "inputs"
                inputs.write_text("amr.n_cell = 64 64 64\n")
                return {
                    "status": "success",
                    "inputs_path": str(inputs),
                    "run_dir": str(run_dir),
                    "modifications_applied": 0,
                    "requires_parameter_resolution": False,
                }

        state = {
            "prompt": "plot temperature",
            "config": SimpleNamespace(
                output_dir=tmp_path,
                preconfirm_gate=False,
                preconfirm_gate_auto_approve=False,
                baseline_override=None,
                inputs_default_precedence="strategy_first",
            ),
            "iteration": 0,
            "retry_count": 0,
            "workflow_history": [
                {
                    "node": "architect",
                    "details": {
                        "selected_case": "PeleC/Exec/RegTests/PMF",
                        "modifications": [],
                        "baseline": {"local_path": str(tmp_path)},
                        "reasoning": "test",
                    },
                }
            ],
            "requested_plot_vars": ["temperature"],
        }

        with patch("src.services.viz_param_extractor.extract_viz_params_from_prompt") as mock_extract, \
             patch("src.nodes.input_writer_node.InputWriterService", DummyService), \
             patch("src.services.cases.AMReXCasesService", return_value=object()):
            mock_extract.side_effect = AssertionError("should not be called")
            input_writer_node(state)

        assert captured["requested_plot_vars"] == ["temperature"]
