"""
Unit tests for deterministic visualization slice-axis defaults.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from src.nodes.visualization_node import _build_vis_config
from src.nodes.visualization_node import _infer_preferred_slice_axis
from src.nodes.visualization_node import _resolve_requested_fields


def test_erf_defaults_to_y_for_vertical_z():
    axis = _infer_preferred_slice_axis(
        prompt="visualize temperature",
        solver_name="ERF",
        n_cell=[256, 128, 128],
    )
    assert axis == "y"


def test_remora_defaults_to_y_for_vertical_z():
    axis = _infer_preferred_slice_axis(
        prompt="show salinity cross-section",
        solver_name="REMORA",
        n_cell=[256, 128, 128],
    )
    assert axis == "y"


def test_prompt_xz_forces_y_slice_normal():
    axis = _infer_preferred_slice_axis(
        prompt="plot an x-z slice through the center",
        solver_name="PeleC",
        n_cell=[128, 128, 128],
    )
    assert axis == "y"


def test_prompt_xy_forces_z_slice_normal():
    axis = _infer_preferred_slice_axis(
        prompt="show plan view in x-y",
        solver_name="PeleC",
        n_cell=[128, 128, 128],
    )
    assert axis == "z"


def test_collapsed_dimension_used_when_present():
    axis = _infer_preferred_slice_axis(
        prompt="visualize velocity",
        solver_name="PeleC",
        n_cell=[256, 1, 256],
    )
    assert axis == "y"


def test_generic_shortest_axis_fallback_for_3d():
    axis = _infer_preferred_slice_axis(
        prompt="visualize density",
        solver_name="PeleC",
        n_cell=[256, 64, 128],
    )
    assert axis == "y"


def test_config_default_axis_is_used(monkeypatch):
    module = importlib.import_module("src.nodes.visualization_node")
    monkeypatch.setattr(module, "_get_config_default_slice_axis", lambda _solver: "x")
    axis = _infer_preferred_slice_axis(
        prompt="visualize density",
        solver_name="SomeSolver",
        n_cell=[128, 128, 128],
    )
    assert axis == "x"


def test_resolve_requested_fields_maps_cloud_water_to_qc():
    resolved = _resolve_requested_fields(
        requested=["cloud_water"],
        available_fields=["density", "qc", "temp"],
    )
    assert resolved == ["qc"]


def test_resolve_requested_fields_keeps_direct_match():
    resolved = _resolve_requested_fields(
        requested=["density", "temperature"],
        available_fields=["density", "temp", "z_velocity"],
    )
    assert resolved == ["density", "temp"]


def test_build_vis_config_prioritizes_requested_over_plan_fields():
    class _Backend:
        @staticmethod
        def get_field_list(_plotfile):
            return ["density", "qc", "temp", "x_velocity", "y_velocity", "z_velocity"]

    class _VizService:
        backend = _Backend()

    vis_config = _build_vis_config(
        plan={
            "visualization": {
                "plots": [
                    {"type": "slice", "field": "velocity_magnitude"},
                    {"type": "slice", "field": "density"},
                ]
            }
        },
        analysis_report={},
        plotfiles=[Path("plt00000")],
        viz_service=_VizService(),
        prompt="show cloud water",
        solver_name="ERF",
        inputs_file_path=None,
        requested_plot_vars=["cloud_water"],
    )
    fields = [p["field"] for p in vis_config.get("plots", [])]
    assert fields[0] == "qc"
    assert "density" in fields
    assert "velocity_magnitude" not in fields


def test_build_vis_config_preserves_plot_types_and_extra_options():
    class _Backend:
        @staticmethod
        def get_field_list(_plotfile):
            return ["Temp", "density", "pressure"]

    class _VizService:
        backend = _Backend()

    vis_config = _build_vis_config(
        plan={
            "visualization": {
                "plots": [
                    {
                        "type": "slice",
                        "field": "Temp",
                        "axis": "z",
                        "colormap": "magma",
                        "vmin": 200.0,
                        "vmax": 1800.0,
                    },
                    {
                        "type": "line",
                        "field": "pressure",
                        "lineout_axis": "x",
                        "position": 0.5,
                    },
                ]
            }
        },
        analysis_report={},
        plotfiles=[Path("plt00001")],
        viz_service=_VizService(),
        prompt="render diagnostics",
        solver_name="ERF",
        inputs_file_path=None,
        requested_plot_vars=None,
    )

    plots = vis_config.get("plots", [])
    assert len(plots) == 2
    assert plots[0]["type"] == "slice"
    assert plots[0]["field"] == "Temp"
    assert plots[0]["axis"] == "z"
    assert plots[0]["colormap"] == "magma"
    assert plots[0]["vmin"] == 200.0
    assert plots[0]["vmax"] == 1800.0
    assert plots[1]["type"] == "line"
    assert plots[1]["field"] == "pressure"
    assert plots[1]["lineout_axis"] == "x"
    assert plots[1]["position"] == 0.5


def test_build_vis_config_uses_prompt_timestep_scope():
    class _Backend:
        @staticmethod
        def get_field_list(_plotfile):
            return ["qc"]

    class _VizService:
        backend = _Backend()

    vis_config = _build_vis_config(
        plan={"visualization": {"plots": [{"type": "slice", "field": "qc"}]}},
        analysis_report={},
        plotfiles=[Path("plt00000")],
        viz_service=_VizService(),
        prompt="show cloud water every 2 minutes",
        solver_name="ERF",
        inputs_file_path=None,
        requested_plot_vars=["cloud_water"],
        prompt_visualization_config={"timesteps": "all"},
    )
    assert vis_config.get("timesteps") == "all"
