"""
Terminal gating helpers for pre-confirm pauses and LLM prompt checks.
"""
from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Callable

logger = logging.getLogger(__name__)


def run_preconfirm_gate(
    node_name: str,
    summary_lines: list[str],
    options: list[dict[str, Any]],
    enabled: bool,
    allow_cancel: bool = True,
) -> dict[str, Any]:
    """
    Run a terminal pre-confirmation gate.

    Returns:
        {
            "action": "proceed" | "cancel" | "skipped",
            "selection": option dict or None,
            "history_entry": workflow_history entry or None
        }
    """
    if not enabled:
        return {"action": "proceed", "selection": None, "history_entry": None}

    if not sys.stdin.isatty():
        logger.info("Pre-confirm gate skipped (stdin is not a TTY).")
        return {
            "action": "skipped",
            "selection": None,
            "history_entry": _build_gate_history(node_name, "skipped", None, "non_tty"),
        }

    if not options:
        logger.info("Pre-confirm gate skipped (no options provided).")
        return {
            "action": "skipped",
            "selection": None,
            "history_entry": _build_gate_history(node_name, "skipped", None, "no_options"),
        }

    print("\n" + "=" * 72)
    print(f"Pre-confirmation Gate: {node_name}")
    print("=" * 72)
    redactor = _redactor()
    for line in summary_lines:
        print(redactor(line))
    print("")
    print("Options:")
    for idx, option in enumerate(options, 1):
        label = option.get('label', option.get('value', 'option'))
        print(f"{idx}) {redactor(str(label))}")
    if allow_cancel:
        print("c) Cancel")
    print("")

    choice = input(f"Select option [1-{len(options)}] or c to cancel: ").strip().lower()
    if allow_cancel and choice in {"c", "q", "cancel"}:
        return {
            "action": "cancel",
            "selection": None,
            "history_entry": _build_gate_history(node_name, "cancel", None, None),
        }

    if not choice:
        selection = options[0]
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(node_name, "proceed", selection, None),
        }

    try:
        selected_idx = int(choice)
    except ValueError:
        selection = options[0]
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(node_name, "proceed", selection, "invalid_choice"),
        }

    if 1 <= selected_idx <= len(options):
        selection = options[selected_idx - 1]
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(node_name, "proceed", selection, None),
        }

    selection = options[0]
    return {
        "action": "proceed",
        "selection": selection,
        "history_entry": _build_gate_history(node_name, "proceed", selection, "out_of_range"),
    }


def _build_gate_history(
    node_name: str,
    action: str,
    selection: dict[str, Any] | None,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "node": "preconfirm_gate",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "iteration": None,
        "details": {
            "gate_node": node_name,
            "selection": selection,
            "reason": reason,
        },
    }


def should_gate_prompt(prompt: str, strategy: str) -> bool:
    """
    Decide whether to gate a prompt based on strategy.
    """
    if strategy in {"gate-all", "gate-all-prompt"}:
        return True
    if strategy in {"gate-major", "gate-major-prompt"}:
        return len(prompt) >= 800 or prompt.count("\n") >= 20
    return False


def run_llm_pre_gate(prompt: str, strategy: str) -> bool:
    """
    Pre-send gate for LLM prompts. Returns True to proceed, False to cancel.
    """
    if not sys.stdin.isatty():
        return True
    if not should_gate_prompt(prompt, strategy):
        return True

    redactor = _redactor()
    preview = prompt if len(prompt) <= 2000 else prompt[:2000] + "\n...[truncated]..."
    print("\n" + "=" * 72)
    print("LLM Prompt Gate")
    print("=" * 72)
    print(redactor(preview))
    print("")
    choice = input("Send this prompt? [Y/n]: ").strip().lower()
    return choice in {"", "y", "yes"}


def run_llm_post_gate(response_text: str, strategy: str) -> None:
    """
    Post-output usefulness check. Logs the user's feedback.
    """
    if not sys.stdin.isatty():
        return
    if strategy not in {"feedback", "default", "gate-all", "gate-all-prompt", "gate-major", "gate-major-prompt"}:
        return

    redactor = _redactor()
    preview = response_text if len(response_text) <= 1200 else response_text[:1200] + "\n...[truncated]..."
    print("\n" + "=" * 72)
    print("LLM Output Check")
    print("=" * 72)
    print(redactor(preview))
    print("")
    choice = input("Is this output useful? [Y/n]: ").strip().lower()
    if choice in {"n", "no"}:
        logger.info("LLM output marked as not useful by user.")


def _redactor() -> Callable[[str], str]:
    secrets = [
        os.getenv("CBORG_API_KEY"),
        os.getenv("ALCF_API_KEY"),
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("NERSC_API_TOKEN"),
        os.getenv("SFAPI_TOKEN"),
    ]
    bearer_re = re.compile(r"(Authorization:\s*Bearer\s+)[^\s]+", re.IGNORECASE)

    def redact(text: str) -> str:
        if not text:
            return text
        for secret in secrets:
            if secret and secret in text:
                text = text.replace(secret, "[REDACTED]")
        return bearer_re.sub(r"\1[REDACTED]", text)

    return redact
