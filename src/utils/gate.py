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
    auto_approve: bool = False,
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

    options_metadata = _build_options_metadata(options)
    if not sys.stdin.isatty():
        logger.info("Pre-confirm gate skipped (stdin is not a TTY).")
        return {
            "action": "skipped",
            "selection": None,
            "history_entry": _build_gate_history(
                node_name,
                "skipped",
                None,
                "non_tty",
                details={
                    "options_count": len(options),
                    "allow_cancel": allow_cancel,
                    "options": options_metadata,
                },
            ),
        }

    if not options:
        logger.info("Pre-confirm gate skipped (no options provided).")
        return {
            "action": "skipped",
            "selection": None,
            "history_entry": _build_gate_history(
                node_name,
                "skipped",
                None,
                "no_options",
                details={
                    "options_count": 0,
                    "allow_cancel": allow_cancel,
                },
            ),
        }

    if auto_approve:
        selection = options[0]
        logger.info("Pre-confirm gate auto-approved for %s.", node_name)
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(
                node_name,
                "proceed",
                selection,
                "auto_approved",
                details={
                    "options_count": len(options),
                    "allow_cancel": allow_cancel,
                    "options": options_metadata,
                    "selected_index": 1,
                },
            ),
        }

    print("\n" + "=" * 72)
    print(f"Pre-confirmation Gate: {node_name}")
    print("=" * 72)
    redactor = _redactor()
    print("Context:")
    for line in summary_lines:
        print(f"- {redactor(line)}")
    print("")
    print("Options:")
    for idx, option in enumerate(options, 1):
        label = option.get('label', option.get('value', 'option'))
        default_marker = " [default]" if idx == 1 else ""
        print(f"{idx}) {redactor(str(label))}{default_marker}")
    if allow_cancel:
        print("c) Cancel")
    print("")

    choice = input(
        f"Select option [1-{len(options)}] (Enter for default) or c to cancel: "
    ).strip().lower()
    if allow_cancel and choice in {"c", "q", "cancel"}:
        logger.info("Pre-confirm gate canceled for %s.", node_name)
        return {
            "action": "cancel",
            "selection": None,
            "history_entry": _build_gate_history(
                node_name,
                "cancel",
                None,
                None,
                details={
                    "options_count": len(options),
                    "allow_cancel": allow_cancel,
                    "options": options_metadata,
                    "choice": choice,
                },
            ),
        }

    if not choice:
        selection = options[0]
        logger.info("Pre-confirm gate defaulted for %s.", node_name)
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(
                node_name,
                "proceed",
                selection,
                "default",
                details={
                    "options_count": len(options),
                    "allow_cancel": allow_cancel,
                    "options": options_metadata,
                    "selected_index": 1,
                    "choice": "",
                },
            ),
        }

    try:
        selected_idx = int(choice)
    except ValueError:
        selection = options[0]
        logger.info("Pre-confirm gate invalid choice for %s.", node_name)
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(
                node_name,
                "proceed",
                selection,
                "invalid_choice",
                details={
                    "options_count": len(options),
                    "allow_cancel": allow_cancel,
                    "options": options_metadata,
                    "selected_index": 1,
                    "choice": choice,
                },
            ),
        }

    if 1 <= selected_idx <= len(options):
        selection = options[selected_idx - 1]
        logger.info("Pre-confirm gate selection %s for %s.", selected_idx, node_name)
        return {
            "action": "proceed",
            "selection": selection,
            "history_entry": _build_gate_history(
                node_name,
                "proceed",
                selection,
                None,
                details={
                    "options_count": len(options),
                    "allow_cancel": allow_cancel,
                    "options": options_metadata,
                    "selected_index": selected_idx,
                    "choice": choice,
                },
            ),
        }

    selection = options[0]
    logger.info("Pre-confirm gate out-of-range choice for %s.", node_name)
    return {
        "action": "proceed",
        "selection": selection,
        "history_entry": _build_gate_history(
            node_name,
            "proceed",
            selection,
            "out_of_range",
            details={
                "options_count": len(options),
                "allow_cancel": allow_cancel,
                "options": options_metadata,
                "selected_index": 1,
                "choice": choice,
            },
        ),
    }


def _build_gate_history(
    node_name: str,
    action: str,
    selection: dict[str, Any] | None,
    reason: str | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate_details = {
        "gate_node": node_name,
        "selection": selection,
        "reason": reason,
    }
    if details:
        gate_details.update(details)
    return {
        "node": "preconfirm_gate",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "iteration": None,
        "details": {
            **gate_details,
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


def run_llm_pre_gate(prompt: str, strategy: str, auto_approve: bool = False) -> bool:
    """
    Pre-send gate for LLM prompts. Returns True to proceed, False to cancel.
    """
    if not sys.stdin.isatty():
        return True
    if not should_gate_prompt(prompt, strategy):
        return True
    if auto_approve:
        logger.info("LLM pre-gate auto-approved (strategy=%s).", strategy)
        return True

    redactor = _redactor()
    preview = prompt if len(prompt) <= 2000 else prompt[:2000] + "\n...[truncated]..."
    prompt_lines = prompt.count("\n") + 1 if prompt else 0
    print("\n" + "=" * 72)
    print("LLM Prompt Gate")
    print("=" * 72)
    print(f"Strategy: {strategy}")
    print(f"Characters: {len(prompt)}")
    print(f"Lines: {prompt_lines}")
    print("")
    print("Preview:")
    print(redactor(preview))
    print("")
    choice = input("Send this prompt? [Y/n]: ").strip().lower()
    approved = choice in {"", "y", "yes"}
    logger.info("LLM pre-gate decision: %s (strategy=%s).", "proceed" if approved else "cancel", strategy)
    return approved


def run_llm_post_gate(response_text: str, strategy: str, auto_approve: bool = False) -> None:
    """
    Post-output usefulness check. Logs the user's feedback.
    """
    if not sys.stdin.isatty():
        return
    if strategy not in {"feedback", "default", "gate-all", "gate-all-prompt", "gate-major", "gate-major-prompt"}:
        return
    if auto_approve:
        logger.info("LLM post-gate auto-approved (strategy=%s).", strategy)
        return

    redactor = _redactor()
    preview = response_text if len(response_text) <= 1200 else response_text[:1200] + "\n...[truncated]..."
    response_lines = response_text.count("\n") + 1 if response_text else 0
    print("\n" + "=" * 72)
    print("LLM Output Check")
    print("=" * 72)
    print(f"Strategy: {strategy}")
    print(f"Characters: {len(response_text)}")
    print(f"Lines: {response_lines}")
    print("")
    print("Preview:")
    print(redactor(preview))
    print("")
    choice = input("Is this output useful? [Y/n]: ").strip().lower()
    if choice in {"n", "no"}:
        logger.info("LLM output marked as not useful by user.")
    else:
        logger.info("LLM output confirmed useful by user.")


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


def _build_options_metadata(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redactor = _redactor()
    metadata = []
    for option in options:
        label = option.get("label", option.get("value", "option"))
        metadata.append(
            {
                "label": redactor(str(label)) if label is not None else None,
                "value": option.get("value"),
            }
        )
    return metadata
