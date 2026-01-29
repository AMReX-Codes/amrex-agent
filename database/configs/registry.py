"""
Registry helpers for solver metadata.

Sources solver heuristics from config classes to keep services lean.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any


def _iter_solver_configs() -> list[type[Any]]:
    from database.configs import discover_code_configs
    return list(discover_code_configs())


def _get_config_class(code_name: str) -> type[Any] | None:
    for config_cls in _iter_solver_configs():
        if config_cls.code_name == code_name:
            return config_cls
    return None


def get_config_class(code_name: str | None) -> type[Any]:
    """
    Resolve a solver config class by code name.

    Parameters
    ----------
    code_name : str or None
        Code identifier to resolve (e.g., "PeleC").

    Returns
    -------
    type
        Config class for the solver, or BaseAMReXConfig if unknown.
    """
    from database.configs import BaseAMReXConfig

    if not code_name:
        return BaseAMReXConfig
    return _get_config_class(code_name) or BaseAMReXConfig


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def get_solver_keywords() -> dict[str, str]:
    """
    Build keyword-to-solver mapping from config classes.

    Returns
    -------
    dict[str, str]
        Mapping of selection keyword to solver code name.
    """
    keywords: dict[str, str] = {}
    for config_cls in _iter_solver_configs():
        for keyword in getattr(config_cls, "selection_keywords", []):
            keywords[keyword] = config_cls.code_name
    return keywords


def get_solver_guidance_lines() -> list[str]:
    """
    Collect solver guidance lines across config classes.

    Returns
    -------
    list[str]
        Deduplicated guidance lines in priority order.
    """
    from database.configs import BaseAMReXConfig

    lines: list[str] = []
    lines.extend(getattr(BaseAMReXConfig, "selection_guidance", []))
    for config_cls in _iter_solver_configs():
        if "selection_guidance" not in config_cls.__dict__:
            continue
        lines.extend(getattr(config_cls, "selection_guidance", []))
    return _dedupe_preserve_order(lines)


def get_github_search_paths(code_name: str) -> list[str]:
    """
    Resolve GitHub search paths for a given solver.

    Parameters
    ----------
    code_name : str
        Solver code name.

    Returns
    -------
    list[str]
        Repo-relative paths to scan for cases.
    """
    from database.configs import BaseAMReXConfig

    config_cls = _get_config_class(code_name)
    if config_cls and hasattr(config_cls, "github_search_paths"):
        return list(config_cls.github_search_paths)
    return list(BaseAMReXConfig.github_search_paths)


def is_pele_solver(code_name: str) -> bool:
    """
    Check whether a solver belongs to the Pele family.

    Parameters
    ----------
    code_name : str
        Solver code name.

    Returns
    -------
    bool
        True if the solver is marked as Pele-family.
    """
    config_cls = _get_config_class(code_name)
    return bool(config_cls and getattr(config_cls, "is_pele_family", False))


def is_pele_case_path(case_dir: Path | str) -> bool:
    """
    Determine whether a case path looks like a Pele case.

    Parameters
    ----------
    case_dir : pathlib.Path or str
        Case directory path to inspect.

    Returns
    -------
    bool
        True if any Pele markers match the path.
    """
    case_dir_str = str(case_dir).lower()
    for config_cls in _iter_solver_configs():
        if not getattr(config_cls, "is_pele_family", False):
            continue
        markers = getattr(config_cls, "case_path_markers", set())
        if any(marker in case_dir_str for marker in markers):
            return True
    return False


def filter_keyword_map_for_codes(available_codes: Iterable[str]) -> dict[str, str]:
    """
    Filter keyword map to only include available solvers.

    Parameters
    ----------
    available_codes : iterable[str]
        Solver code names to keep.

    Returns
    -------
    dict[str, str]
        Keyword map restricted to the supplied solvers.
    """
    available = set(available_codes)
    return {k: v for k, v in get_solver_keywords().items() if v in available}


def is_low_mach_solver(code_name: str) -> bool:
    """
    Check whether a solver targets low-Mach/incompressible regimes.

    Parameters
    ----------
    code_name : str
        Solver code name.

    Returns
    -------
    bool
        True if the solver is marked as low-Mach.
    """
    config_cls = _get_config_class(code_name)
    return bool(config_cls and getattr(config_cls, "is_low_mach_solver", False))


def get_solver_match_exclusions(code_name: str) -> list[str]:
    """
    Get substring exclusions for solver-name matching.

    Parameters
    ----------
    code_name : str
        Solver code name.

    Returns
    -------
    list[str]
        List of substrings to exclude during matching.
    """
    config_cls = _get_config_class(code_name)
    if not config_cls:
        return []
    return list(getattr(config_cls, "match_exclusions", []))


def get_cfl_param_name(code_name: str) -> str:
    """
    Resolve the CFL parameter name for a solver.

    Parameters
    ----------
    code_name : str
        Solver code name.

    Returns
    -------
    str
        Dot-notation parameter name for CFL.
    """
    from database.configs import BaseAMReXConfig

    config_cls = _get_config_class(code_name)
    if config_cls:
        return getattr(config_cls, "cfl_param_name", BaseAMReXConfig.cfl_param_name)
    return BaseAMReXConfig.cfl_param_name


def get_cfl_model_aliases() -> list[str]:
    """
    Return CFL model alias names used in validation.

    Returns
    -------
    list[str]
        Model aliases for CFL validation.
    """
    from database.configs import BaseAMReXConfig

    return list(BaseAMReXConfig.cfl_model_aliases)


def get_explicit_cfl_param_name() -> str:
    """
    Find the CFL parameter name for explicit-CFL solvers.

    Returns
    -------
    str
        CFL parameter name for the first explicit solver, or default.
    """
    from database.configs import BaseAMReXConfig

    for config_cls in _iter_solver_configs():
        if getattr(config_cls, "explicit_cfl", False):
            return getattr(config_cls, "cfl_param_name", BaseAMReXConfig.cfl_param_name)
    return BaseAMReXConfig.cfl_param_name


def get_chemistry_param_keys(code_name: str | None) -> list[str]:
    """
    Get chemistry parameter keys for a solver or all solvers.

    Parameters
    ----------
    code_name : str or None
        Solver code name, or None to aggregate all.

    Returns
    -------
    list[str]
        Chemistry parameter keys.
    """
    if code_name:
        config_cls = _get_config_class(code_name)
        if config_cls:
            return list(getattr(config_cls, "chemistry_param_keys", []))
        code_name = None

    keys: list[str] = []
    for config_cls in _iter_solver_configs():
        keys.extend(getattr(config_cls, "chemistry_param_keys", []))
    return _dedupe_preserve_order(keys)


def get_reaction_flag_keys(code_name: str | None) -> list[str]:
    """
    Get reaction flag keys for a solver or all solvers.

    Parameters
    ----------
    code_name : str or None
        Solver code name, or None to aggregate all.

    Returns
    -------
    list[str]
        Reaction-flag parameter keys.
    """
    if code_name:
        config_cls = _get_config_class(code_name)
        if config_cls:
            return list(getattr(config_cls, "reaction_flag_keys", []))
        code_name = None

    keys: list[str] = []
    for config_cls in _iter_solver_configs():
        keys.extend(getattr(config_cls, "reaction_flag_keys", []))
    return _dedupe_preserve_order(keys)


def build_chemistry_search_paths(
    chem_file: str,
    repo_paths: Iterable[Path]
) -> list[Path]:
    """
    Build candidate paths for chemistry mechanism files.

    Parameters
    ----------
    chem_file : str
        Chemistry file name or relative path.
    repo_paths : iterable[pathlib.Path]
        Repository roots to search.

    Returns
    -------
    list[pathlib.Path]
        Search paths in priority order.
    """
    search_paths: list[Path] = [Path.cwd() / chem_file]

    for repo_path in repo_paths:
        search_paths.append(
            Path(repo_path) / "Submodules" / "PelePhysics" / "Mechanisms" / chem_file
        )
        if "/" not in chem_file and not chem_file.endswith(".yaml"):
            search_paths.append(
                Path(repo_path)
                / "Submodules"
                / "PelePhysics"
                / "Mechanisms"
                / chem_file
                / "mechanism.yaml"
            )

    return search_paths


def get_low_mach_solver(
    code_registry: dict[str, Any],
    default_solver: str | None
) -> str | None:
    """
    Select the low-Mach solver from a code registry if present.

    Parameters
    ----------
    code_registry : dict[str, Any]
        Registry of available solvers keyed by code name.
    default_solver : str or None
        Fallback solver name if no low-Mach solver is present.

    Returns
    -------
    str or None
        Low-Mach solver name if found, otherwise the default.
    """
    for config_cls in _iter_solver_configs():
        if not getattr(config_cls, "is_low_mach_solver", False):
            continue
        if config_cls.code_name in code_registry:
            return config_cls.code_name
    return default_solver


def get_solver_ode_tolerance_plan(code_name: str) -> dict[str, str] | None:
    """
    Fetch the ODE tolerance adjustment plan for a solver.

    Parameters
    ----------
    code_name : str
        Solver code name.

    Returns
    -------
    dict[str, str] or None
        ODE tolerance plan, if configured.
    """
    config_cls = _get_config_class(code_name)
    if not config_cls:
        return None
    plan = getattr(config_cls, "ode_tolerance_plan", None)
    if not plan:
        return None
    return dict(plan)


def get_feedback_physics_prefixes() -> list[str]:
    """
    Collect physics feedback prefixes from config classes.

    Returns
    -------
    list[str]
        Deduplicated prefix list in priority order.
    """
    from database.configs import BaseAMReXConfig

    prefixes: list[str] = []
    prefixes.extend(getattr(BaseAMReXConfig, "feedback_physics_prefixes", []))
    for config_cls in _iter_solver_configs():
        if "feedback_physics_prefixes" not in config_cls.__dict__:
            continue
        prefixes.extend(getattr(config_cls, "feedback_physics_prefixes", []))
    return _dedupe_preserve_order(prefixes)
