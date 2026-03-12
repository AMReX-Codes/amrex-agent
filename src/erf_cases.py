"""ERF case discovery and natural-language matching utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_MATCH_WEIGHTS: dict[str, float] = {
    "alias": 0.35,
    "path": 0.25,
    "tag": 0.20,
    "name": 0.15,
    "description": 0.05,
}

_README_NAMES = ("README", "README.md", "README.rst", "README.txt")
_EXCLUDED_DIR_NAMES = {"tmp_build_dir", "PythonScripts"}


@dataclass(frozen=True)
class ERFCase:
    """Structured metadata for a single ERF case."""

    canonical_name: str
    relative_path: str
    category: str
    physics_tags: tuple[str, ...]
    short_description: str
    input_files: tuple[str, ...]
    aliases: tuple[str, ...]


def _normalize(text: str) -> str:
    lowered = text.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", lowered).strip()


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _normalize(text)))


def _camel_to_words(text: str) -> str:
    return re.sub(r"(?<!^)([A-Z])", r" \1", text)


def _first_description_line(case_dir: Path) -> str:
    for readme_name in _README_NAMES:
        readme = case_dir / readme_name
        if not readme.exists():
            continue
        for raw_line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip().lstrip("#").strip()
            if line:
                return line[:160]
    return f"ERF case in {case_dir.name}"


def _infer_physics_tags(text: str) -> tuple[str, ...]:
    tokens = _tokenize(text)
    tag_map = {
        "abl": {"abl", "boundary", "layer", "ekman", "neutral", "convective", "stable"},
        "terrain": {"terrain", "schar", "agnesi", "hemisphere", "hill"},
        "moist": {"moist", "cloud", "rain", "microphysics", "squall"},
        "wind": {"wind", "turbine", "windfarm"},
        "hurricane": {"hurricane", "cyclone", "tropical", "tornado"},
        "radiation": {"radiation"},
        "dns": {"dns", "taylor", "vortex", "channel"},
        "regression": {"regtests", "regression"},
    }
    found: list[str] = []
    for tag, words in tag_map.items():
        if tokens & words:
            found.append(tag)
    if not found:
        found.append("general")
    return tuple(found)


def _looks_like_case_dir(case_dir: Path) -> bool:
    if case_dir.name in _EXCLUDED_DIR_NAMES:
        return False
    files = [p.name for p in case_dir.iterdir() if p.is_file()]
    has_inputs = any(name.startswith("inputs") for name in files)
    has_readme = any(name in _README_NAMES for name in files)
    return has_inputs or has_readme


def _discover_input_files(case_dir: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            item.name
            for item in case_dir.iterdir()
            if item.is_file() and item.name.startswith("inputs")
        )
    )


def _build_aliases(
    relative_path: str,
    canonical_name: str,
    category: str,
    input_files: tuple[str, ...],
) -> tuple[str, ...]:
    aliases = {
        canonical_name,
        _camel_to_words(canonical_name),
        canonical_name.replace("_", " "),
        relative_path,
        relative_path.lower(),
        f"{category} {canonical_name}",
        f"{category} {_camel_to_words(canonical_name)}",
    }
    normalized_name = _normalize(canonical_name)
    aliases.add(normalized_name)
    for input_file in input_files:
        input_words = input_file.replace("_", " ")
        aliases.add(input_file)
        aliases.add(input_words)
        aliases.add(f"{canonical_name} {input_words}")
        aliases.add(f"{category} {canonical_name} {input_words}")
        aliases.add(f"{relative_path}/{input_file}")
    if "squallline" in normalized_name or "squall line" in normalized_name:
        aliases.update({"squallline", "squall line", "squall line 2d"})
    return tuple(sorted(_normalize(alias) for alias in aliases if alias))


def discover_erf_cases(erf_repo_root: str | Path) -> list[ERFCase]:
    """Discover ERF cases from ``Exec/`` and return structured metadata."""
    root = Path(erf_repo_root)
    exec_root = root / "Exec"
    if not exec_root.exists():
        return []

    case_dirs: list[Path] = []
    for candidate in sorted(exec_root.rglob("*")):
        if not candidate.is_dir():
            continue
        if any(part in _EXCLUDED_DIR_NAMES for part in candidate.parts):
            continue
        if _looks_like_case_dir(candidate):
            case_dirs.append(candidate)

    cases: list[ERFCase] = []
    seen_paths: set[str] = set()
    for case_dir in case_dirs:
        rel = case_dir.relative_to(root).as_posix()
        if rel in seen_paths:
            continue
        seen_paths.add(rel)

        parts = rel.split("/")
        category = parts[1] if len(parts) > 1 else "Uncategorized"
        canonical_name = parts[-1]
        description = _first_description_line(case_dir)
        input_files = _discover_input_files(case_dir)
        tag_text = f"{rel} {description} {canonical_name}"
        tags = _infer_physics_tags(tag_text)
        aliases = _build_aliases(rel, canonical_name, category, input_files)
        cases.append(
            ERFCase(
                canonical_name=canonical_name,
                relative_path=rel,
                category=category,
                physics_tags=tags,
                short_description=description,
                input_files=input_files,
                aliases=aliases,
            )
        )
    return cases


def _overlap_score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    return len(query_tokens & candidate_tokens) / len(query_tokens)


class ERFCaseMatcher:
    """Weighted matcher for selecting ERF cases from user queries."""

    def __init__(
        self,
        cases: Iterable[ERFCase],
        *,
        config_weights: dict[str, float] | None = None,
        min_score: float = 0.25,
    ) -> None:
        self.cases = list(cases)
        self.config_weights = dict(config_weights or {})
        self.min_score = min_score

    def _weights(self, overrides: dict[str, float] | None = None) -> dict[str, float]:
        weights = dict(DEFAULT_MATCH_WEIGHTS)
        weights.update(self.config_weights)
        if overrides:
            weights.update(overrides)
        return weights

    def _score_case(
        self,
        query_n: str,
        query_tokens: set[str],
        query_pathish: bool,
        case: ERFCase,
        weights: dict[str, float],
    ) -> float:
        alias_scores = [
            1.0 if query_n == alias else _overlap_score(query_tokens, _tokenize(alias))
            for alias in case.aliases
        ]
        alias_score = max(alias_scores) if alias_scores else 0.0

        path_score = _overlap_score(query_tokens, _tokenize(case.relative_path))
        if query_pathish and _normalize(case.relative_path) in query_n:
            path_score = 1.0

        tag_score = _overlap_score(query_tokens, set(case.physics_tags))
        name_score = _overlap_score(query_tokens, _tokenize(case.canonical_name))
        desc_score = _overlap_score(query_tokens, _tokenize(case.short_description))

        return (
            alias_score * weights.get("alias", 0.0)
            + path_score * weights.get("path", 0.0)
            + tag_score * weights.get("tag", 0.0)
            + name_score * weights.get("name", 0.0)
            + desc_score * weights.get("description", 0.0)
        )

    def match(self, query: str, *, weight_overrides: dict[str, float] | None = None) -> ERFCase | None:
        query_n = _normalize(query)
        query_tokens = _tokenize(query_n)
        if not query_tokens:
            return None

        weights = self._weights(weight_overrides)
        best: tuple[float, ERFCase | None] = (0.0, None)
        query_pathish = "/" in query or "exec/" in query_n

        for case in self.cases:
            total = self._score_case(query_n, query_tokens, query_pathish, case, weights)
            if total > best[0]:
                best = (total, case)

        if best[0] < self.min_score:
            return None
        return best[1]


def select_best_erf_case(
    query: str,
    erf_repo_root: str | Path,
    *,
    config_weights: dict[str, float] | None = None,
    weight_overrides: dict[str, float] | None = None,
) -> ERFCase | None:
    """Discover cases and return the best match for a natural-language query."""
    cases = discover_erf_cases(erf_repo_root)
    matcher = ERFCaseMatcher(cases, config_weights=config_weights)
    return matcher.match(query, weight_overrides=weight_overrides)
