"""Filesystem write policy helpers."""

from __future__ import annotations

import logging
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
    mode = getattr(config, "write_policy_mode", "warn")
    if mode == "off":
        return

    output_path = Path(output_dir)
    allow_paths = []
    for attr in ("output_dir", "metrics_output_dir", "remote_output_dir"):
        value = getattr(config, attr, None) if config is not None else None
        if value:
            allow_paths.append(Path(value))

    allow_list = getattr(config, "allow_write_paths", None) if config is not None else None
    if allow_list:
        allow_paths.extend(Path(p) for p in allow_list)

    allowed = any(_is_within(output_path, root) for root in allow_paths)

    require_prefix = bool(getattr(config, "require_run_dir_prefix", False)) if config is not None else False
    if require_prefix:
        prefix = getattr(config, "run_dir_prefix", "run_")
        allowed = allowed and output_path.name.startswith(prefix)

    if allowed:
        return

    context = f" ({purpose})" if purpose else ""
    roots = ", ".join(str(p) for p in allow_paths) if allow_paths else "none"
    message = f"Write blocked{context}: {output_path} not under allowed roots ({roots})"
    if mode == "deny":
        raise WritePolicyViolation(message)
    logger.warning(message)
