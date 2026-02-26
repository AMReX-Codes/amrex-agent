"""Loader for repo-local AGENTS.md skill registrations."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path


@dataclass(frozen=True)
class SkillDefinition:
    """Parsed skill registration from AGENTS.md."""

    name: str
    description: str
    skill_md_path: Path


_SKILL_ENTRY_RE = re.compile(
    r"^- (?P<name>[a-z0-9-]+): (?P<desc>.+?) \(file: (?P<path>.+?)\)\s*$"
)


def load_skills_from_agents_md(agents_md_path: Path) -> list[SkillDefinition]:
    """Parse skills listed in AGENTS.md."""
    if not agents_md_path.is_file():
        return []

    skills: list[SkillDefinition] = []
    for line in agents_md_path.read_text(encoding="utf-8").splitlines():
        match = _SKILL_ENTRY_RE.match(line.strip())
        if not match:
            continue
        skill_path = Path(match.group("path")).expanduser()
        skills.append(
            SkillDefinition(
                name=match.group("name"),
                description=match.group("desc").strip(),
                skill_md_path=skill_path,
            )
        )
    return skills
