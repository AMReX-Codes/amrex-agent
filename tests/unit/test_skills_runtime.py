"""Unit tests for repo-local skill loading/runtime helpers."""

from __future__ import annotations

from pathlib import Path

from src.skills.loader import load_skills_from_agents_md
from src.skills.runtime import run_skill_calls


def test_load_skills_from_agents_md_parses_entries(tmp_path: Path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "\n".join(
            [
                "### Available skills",
                "- skill-a: first skill (file: /tmp/skill-a/SKILL.md)",
                "- skill-b: second skill (file: /tmp/skill-b/SKILL.md)",
            ]
        ),
        encoding="utf-8",
    )
    skills = load_skills_from_agents_md(agents_md)
    assert [s.name for s in skills] == ["skill-a", "skill-b"]
    assert skills[0].skill_md_path == Path("/tmp/skill-a/SKILL.md")


def test_run_skill_calls_uses_invoke_tool(monkeypatch):
    captured = []
    monkeypatch.setattr(
        "src.skills.runtime.invoke_tool",
        lambda name, arguments, **kwargs: captured.append((name, arguments, kwargs)) or {"ok": True},
    )
    outputs = run_skill_calls(
        [{"name": "query_knowledge", "arguments": {"question": "q"}}],
        session_id="s-1",
        surface="academy",
        caller_action="skill_demo",
    )
    assert outputs[0]["result"] == {"ok": True}
    assert captured[0][0] == "query_knowledge"
    assert captured[0][1]["question"] == "q"
    assert captured[0][2]["session_id"] == "s-1"
