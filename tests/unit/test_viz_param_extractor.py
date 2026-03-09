"""
Unit tests for visualization parameter extraction.
"""

import logging

import pytest

from src.services.viz_param_extractor import (
    extract_viz_params_from_prompt,
    get_plotfile_var_param,
)


class TestVizParamExtractor:
    """
    Keyword-based visualization parameter extraction.
    Deterministic. No LLM calls. Testable offline.
    B1 handoff: superseded by Intent Extraction when
    enable_intent_extraction=True.
    """

    def test_temperature_keyword_extracted(self):
        """
        Given: prompt 'plot temperature as pseudocolor'
        When:  extract_viz_params_from_prompt runs
        Then:  'temperature' in requested_plot_vars
               len(requested_plot_vars) == 1
        """
        requested_plot_vars, _ = extract_viz_params_from_prompt(
            "plot temperature as pseudocolor"
        )
        assert "temperature" in requested_plot_vars
        assert len(requested_plot_vars) == 1

    def test_vertical_velocity_phrase_extracted(self):
        """
        Given: prompt 'show vertical velocity'
        When:  extract_viz_params_from_prompt runs
        Then:  'vertical_velocity' in requested_plot_vars
        """
        requested_plot_vars, _ = extract_viz_params_from_prompt("show vertical velocity")
        assert "vertical_velocity" in requested_plot_vars

    def test_multiple_quantities_all_extracted(self):
        """
        Given: 'plot temperature, vorticity, and
                vertical velocity'
        When:  extract_viz_params_from_prompt runs
        Then:  all three in requested_plot_vars
               no extras added
               len == 3
        """
        requested_plot_vars, _ = extract_viz_params_from_prompt(
            "plot temperature, vorticity, and vertical velocity"
        )
        assert "temperature" in requested_plot_vars
        assert "vorticity" in requested_plot_vars
        assert "vertical_velocity" in requested_plot_vars
        assert len(requested_plot_vars) == 3

    def test_log_scale_sets_color_scale_logarithmic(self):
        """
        Given: prompt containing 'log scale'
        When:  extract_viz_params_from_prompt runs
        Then:  visualization_config['color_scale']
               == 'logarithmic'
        """
        _, visualization_config = extract_viz_params_from_prompt(
            "plot temperature with log scale"
        )
        assert visualization_config["color_scale"] == "logarithmic"

    def test_no_viz_language_returns_empty(self):
        """
        Given: prompt 'run a squall line simulation'
               no visualization language
        When:  extract_viz_params_from_prompt runs
        Then:  requested_plot_vars == []
               visualization_config == {}
        Empty means unspecified — not defaulted.
        Caller is responsible for Priority 2 fallback.
        """
        requested_plot_vars, visualization_config = extract_viz_params_from_prompt(
            "run a squall line simulation"
        )
        assert requested_plot_vars == []
        assert visualization_config == {}

    def test_extraction_is_deterministic(self):
        """
        Given: same prompt run twice
        When:  extract_viz_params_from_prompt runs
        Then:  identical output both times
        """
        prompt = "plot temperature, vorticity, and vertical velocity with log scale"
        first = extract_viz_params_from_prompt(prompt)
        second = extract_viz_params_from_prompt(prompt)
        assert first == second

    def test_squall_line_viz_prompt_extracted(self):
        """
        Given: 'simulate squall line, plot vertical
                velocity and temperature, log scale'
        When:  extract_viz_params_from_prompt runs
        Then:  'vertical_velocity' in requested_plot_vars
               'temperature' in requested_plot_vars
               visualization_config['color_scale']
               == 'logarithmic'
        """
        requested_plot_vars, visualization_config = extract_viz_params_from_prompt(
            "simulate squall line, plot vertical velocity and temperature, log scale"
        )
        assert "vertical_velocity" in requested_plot_vars
        assert "temperature" in requested_plot_vars
        assert visualization_config["color_scale"] == "logarithmic"


class TestPlotfileParamLookup:
    """
    Code-specific plotfile variable parameter name lookup.
    amr.plot_vars is not universal — each solver has
    its own parameter name.
    """

    def test_amrex_returns_amr_plot_vars(self):
        """
        Given: code_name = 'AMReX'
        When:  get_plotfile_var_param(code_name) runs
        Then:  returns 'amr.plot_vars'
        """
        assert get_plotfile_var_param("AMReX") == "amr.plot_vars"

    def test_pelec_returns_amr_plot_vars(self):
        """
        Given: code_name = 'PeleC'
        When:  get_plotfile_var_param(code_name) runs
        Then:  returns correct PeleC plotfile param
        (confirm from Step 1b diagnosis)
        """
        assert get_plotfile_var_param("PeleC") == "amr.plot_vars"

    def test_pelelmex_returns_peleLM_derive(self):
        """
        Given: code_name = 'PeleLMeX'
        When:  get_plotfile_var_param(code_name) runs
        Then:  returns 'peleLM.derive_plot_vars'
        """
        assert get_plotfile_var_param("PeleLMeX") == "peleLM.derive_plot_vars"

    def test_erf_returns_amr_plot_vars(self):
        """
        Given: code_name = 'ERF'
        When:  get_plotfile_var_param(code_name) runs
        Then:  returns 'amr.plot_vars'
        """
        assert get_plotfile_var_param("ERF") == "amr.plot_vars"

    def test_remora_returns_correct_param(self):
        """
        Given: code_name = 'REMORA'
        When:  get_plotfile_var_param(code_name) runs
        Then:  returns REMORA-specific plotfile param
        (confirmed from Step 1b diagnosis)
        """
        assert get_plotfile_var_param("REMORA") == "amr.plot_vars"

    def test_unknown_solver_returns_amr_plot_vars(self, caplog):
        """
        Given: code_name = 'UnknownSolver'
        When:  get_plotfile_var_param(code_name) runs
        Then:  returns 'amr.plot_vars' as safe fallback
               logs a warning about unknown solver
        """
        caplog.set_level(logging.WARNING)
        assert get_plotfile_var_param("UnknownSolver") == "amr.plot_vars"
        assert "Unknown solver" in caplog.text
