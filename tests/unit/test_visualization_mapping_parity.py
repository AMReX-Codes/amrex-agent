"""Parity test for architect visualization semantics and intent-node mapping."""

from types import SimpleNamespace

from src.nodes.visualization_intent_node import visualization_intent_node
from src.services.architect import ArchitectService


def test_architect_and_visualization_intent_node_resolve_same_fields(monkeypatch):
    class _MockConfig:
        @classmethod
        def get_viz_tier1_intents(cls):
            return {"cloud_water": {"aliases": ["cloud water", "cloud_water"]}}

        @classmethod
        def build_viz_tier2_candidates(cls, repo_root=None):
            del cls, repo_root
            return {
                "cloud_water": [
                    {"name": "qc", "aliases": ["cloud_water", "cloud water"]},
                ]
            }

    monkeypatch.setattr(
        "database.configs.registry.get_config_class",
        lambda code_name: _MockConfig,
    )

    architect = ArchitectService.__new__(ArchitectService)
    architect.config = SimpleNamespace(environment="local")

    vis_plan = architect._plan_visualization(
        {"user_prompt": "show cloud water"},
        {"code_name": "ERF", "repo_path": "/tmp/ERF"},
    )
    assert vis_plan["requested_semantic_tokens"] == ["cloud_water"]

    updates = visualization_intent_node(
        {
            "prompt": "show cloud water",
            "selected_solver": "ERF",
            "plan": {"baseline": {"repo_path": "/tmp/ERF", "code_name": "ERF"}},
        }
    )
    assert updates["requested_plot_vars"] == ["qc"]
