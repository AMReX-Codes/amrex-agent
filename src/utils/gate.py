"""
Terminal gating helpers for pre-confirm pauses and LLM prompt checks.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


GateStrategy = str
GatePoint = str


@dataclass
class GateDecision:
    gate_point: GatePoint
    selected_option: str
    user_action: str
    reasoning: str
    alternatives: List[str]
    evidence: Dict[str, Any]
    timestamp: str
    user_modification: Optional[Dict[str, Any]] = None


class GateManager:
    def __init__(self, strategy: GateStrategy, gate_points: List[GatePoint]) -> None:
        self.strategy = strategy
        self.gate_points = set(gate_points)
        self.history: List[GateDecision] = []

    def should_gate(self, gate_point: GatePoint) -> bool:
        if self.strategy == "auto":
            return False
        if self.strategy == "llm":
            return True
        if self.strategy == "terminal":
            return True
        if self.strategy == "selective":
            return gate_point in self.gate_points
        return False

    def present_gate(
        self,
        gate_point: GatePoint,
        selected: str,
        confidence: float,
        reasoning: str,
        evidence: Dict[str, Any],
        alternatives: List[Dict[str, str]],
    ) -> GateDecision:
        print(f"\n[GATE: {gate_point}]")
        print(f"Selected: {selected}")
        print(f"Confidence: {confidence:.2f}")
        print(f"Reasoning: {reasoning}")
        if evidence:
            print("Evidence:")
            for key, value in evidence.items():
                print(f"- {key}: {value}")
        if alternatives:
            print("Alternatives:")
            for alt in alternatives:
                name = alt.get("name", "unknown")
                reason = alt.get("rejected_reason", "")
                print(f"- {name}: {reason}")

        while True:
            print("\nOptions:")
            print("  [a] Approve and continue")
            print("  [v] View detailed evidence")
            print("  [r] Reject and refine prompt")
            print("  [m] Manually select alternative")
            print("  [s] Skip this decision")
            if gate_point in {"baseline", "modifications"}:
                print("  [e] Edit/modify")
            choice = input("Choice: ").strip().lower()

            if choice == "v":
                self._display_evidence_detail(evidence)
                continue

            if choice == "a":
                decision = GateDecision(
                    gate_point=gate_point,
                    selected_option=selected,
                    user_action="approved",
                    reasoning=reasoning,
                    alternatives=[a.get("name", "") for a in alternatives],
                    evidence=evidence,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
                break

            if choice == "s":
                decision = GateDecision(
                    gate_point=gate_point,
                    selected_option=selected,
                    user_action="skipped",
                    reasoning=reasoning,
                    alternatives=[a.get("name", "") for a in alternatives],
                    evidence=evidence,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
                break

            if choice == "r":
                try:
                    feedback = input("Feedback: ").strip()
                except (EOFError, StopIteration):
                    feedback = ""
                decision = GateDecision(
                    gate_point=gate_point,
                    selected_option=selected,
                    user_action="rejected",
                    reasoning=reasoning,
                    alternatives=[a.get("name", "") for a in alternatives],
                    evidence=evidence,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    user_modification={"feedback": feedback},
                )
                break

            if choice == "m":
                manual_selection = self._manual_select(alternatives)
                decision = GateDecision(
                    gate_point=gate_point,
                    selected_option=manual_selection,
                    user_action="modified",
                    reasoning=reasoning,
                    alternatives=[a.get("name", "") for a in alternatives],
                    evidence=evidence,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    user_modification={"manual_selection": manual_selection},
                )
                break

            if choice == "e" and gate_point in {"baseline", "modifications"}:
                modifications = self._edit_parameters()
                decision = GateDecision(
                    gate_point=gate_point,
                    selected_option=selected,
                    user_action="modified",
                    reasoning=reasoning,
                    alternatives=[a.get("name", "") for a in alternatives],
                    evidence=evidence,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    user_modification=modifications,
                )
                break

            print("Invalid choice. Please select a, v, r, m, s, or e.")

        self.history.append(decision)
        return decision

    def save_history(self, output_dir: str) -> None:
        history_file = os.path.join(output_dir, "gate_history.json")
        with open(history_file, "w", encoding="utf-8") as handle:
            json.dump({"gates": [asdict(d) for d in self.history]}, handle, indent=2)

    def _display_evidence_detail(self, evidence: Dict[str, Any]) -> None:
        print("\n[DETAIL]")
        for key, value in evidence.items():
            print(f"{key}: {value}")

    def _manual_select(self, alternatives: List[Dict[str, str]]) -> str:
        print("\n[MANUAL SELECTION]")
        for idx, alt in enumerate(alternatives, 1):
            print(f"{idx}. {alt.get('name', 'unknown')}")
        while True:
            choice = input(f"Select 1-{len(alternatives)}: ").strip()
            try:
                idx = int(choice) - 1
            except ValueError:
                print("Invalid input. Enter a number.")
                continue
            if 0 <= idx < len(alternatives):
                return alternatives[idx].get("name", "")
            print(f"Invalid choice. Enter 1-{len(alternatives)}")

    def _edit_parameters(self) -> Dict[str, Dict[str, str]]:
        print("\n[EDIT MODE]")
        modifications: Dict[str, str] = {}
        while True:
            param_input = input("Parameter (or 'done'): ").strip()
            if param_input.lower() == "done":
                break
            value_input = input(f"New value for {param_input}: ").strip()
            modifications[param_input] = value_input
            print(f"Set {param_input} = {value_input}")
        if modifications:
            self._validate_modifications(modifications)
        return {"parameters": modifications}

    def _validate_modifications(self, modifications: Dict[str, str]) -> None:
        from src.services.validators.resource_validator import ResourceValidator

        warnings = ResourceValidator.check_modifications(modifications)
        if warnings:
            print("\n[RESOURCE WARNINGS]")
            for warning in warnings:
                print(f"- {warning}")
            confirm = input("Continue with these modifications? (y/n): ").strip().lower()
            if confirm != "y":
                raise ValueError("User canceled due to resource warnings")


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
    print(f"Pre-confirm Gate: {node_name}")
    print("=" * 72)
    redactor = _redactor()
    print("Decision: select an option to continue, or cancel.")
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
        f"Select option [1-{len(options)}] (Enter for default, c to cancel): "
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
    if action == "cancel":
        decision_type = "cancel"
    elif action == "skipped":
        decision_type = "skip"
    else:
        decision_type = "select"

    gate_details = {
        "gate_node": node_name,
        "gate_type": "preconfirm",
        "decision_type": decision_type,
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


def build_gate_history_from_workflow_history(
    workflow_history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Build PRD gate_history.json payload from workflow_history gate entries.
    """
    gate_entries: list[dict[str, Any]] = []
    for entry in workflow_history or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("node") != "preconfirm_gate":
            continue
        details = entry.get("details", {}) if isinstance(entry.get("details", {}), dict) else {}
        selection = details.get("selection")
        selected_value = None
        if isinstance(selection, dict):
            selected_value = (
                selection.get("value")
                or selection.get("label")
                or selection.get("case")
            )
        elif selection is not None:
            selected_value = str(selection)
        action = entry.get("action")
        if action == "proceed":
            user_action = "approved"
        elif action == "cancel":
            user_action = "cancel"
        elif action == "skipped":
            user_action = "skipped"
        elif action in {"reject", "rejected"}:
            user_action = "rejected"
        else:
            user_action = action or "unknown"
        gate_record = {
            "gate_point": details.get("gate_node"),
            "selected": selected_value,
            "user_action": user_action,
            "timestamp": entry.get("timestamp"),
        }
        user_modification = (
            details.get("user_modification")
            or details.get("modification")
            or details.get("parameters")
        )
        if user_modification:
            gate_record["user_modification"] = user_modification
        gate_entries.append(gate_record)
    return gate_entries
