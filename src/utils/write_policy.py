"""Filesystem write policy helpers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WritePolicyViolation(RuntimeError):
    pass


def _is_within(child: Path, root: Path) -> bool:
    try:
        return child.resolve().is_relative_to(root.resolve())
    except Exception:
        return False


def _coerce_path(value: Any) -> Path | None:
    """Best-effort conversion to Path; ignores mocks and non-path values."""
    if isinstance(value, Path):
        return value
    if isinstance(value, str):
        return Path(value)
    if isinstance(value, os.PathLike):
        try:
            return Path(value)
        except TypeError:
            return None
    return None


def ensure_write_allowed(
    output_dir: str | Path,
    config: Any | None,
    *,
    purpose: str | None = None,
) -> None:
    """Ensure output_dir is allowed by policy.

    Policy is configured via config attributes:
    - write_policy_mode: "off" | "warn" | "deny" (default: "warn")
    - allow_write_paths: list[str | Path] (optional)
    - require_run_dir_prefix: bool (optional)
    - run_dir_prefix: str (default: "run_")
    - output_dir / metrics_output_dir / remote_output_dir: allowed roots
    """
    mode_raw = getattr(config, "write_policy_mode", "warn")
    mode = mode_raw if isinstance(mode_raw, str) else "warn"
    if mode == "off":
        return

    output_path = Path(output_dir)
    allow_paths = []
    for attr in ("output_dir", "metrics_output_dir", "remote_output_dir"):
        value = getattr(config, attr, None) if config is not None else None
        path_value = _coerce_path(value)
        if path_value is not None:
            allow_paths.append(path_value)

    allow_list = getattr(config, "allow_write_paths", None) if config is not None else None
    if isinstance(allow_list, (str, Path, os.PathLike)):
        allow_list = [allow_list]
    if isinstance(allow_list, (list, tuple, set)):
        for item in allow_list:
            item_path = _coerce_path(item)
            if item_path is not None:
                allow_paths.append(item_path)

    allowed = any(_is_within(output_path, root) for root in allow_paths)

    require_prefix_raw = getattr(config, "require_run_dir_prefix", False) if config is not None else False
    require_prefix = require_prefix_raw if isinstance(require_prefix_raw, bool) else False
    if require_prefix:
        prefix_raw = getattr(config, "run_dir_prefix", "run_")
        prefix = prefix_raw if isinstance(prefix_raw, str) and prefix_raw else "run_"
        allowed = allowed and output_path.name.startswith(prefix)

    if allowed:
        return

    context = f" ({purpose})" if purpose else ""
    roots = ", ".join(str(p) for p in allow_paths) if allow_paths else "none"
    message = f"Write blocked{context}: {output_path} not under allowed roots ({roots})"
    if mode == "deny":
        raise WritePolicyViolation(message)
    logger.warning(message)
