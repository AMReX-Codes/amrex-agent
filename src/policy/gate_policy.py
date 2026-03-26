"""Shared gate policy for interactive tool invocation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

POLICY_VERSION = "v1"
CRITICAL_TOOLS = frozenset({"run_simulation", "stage_out_globus"})
DEMO_BYPASS_ACTIONS = frozenset({"amrex_demo_agent"})


@dataclass(frozen=True)
class GateDecision:
    """Decision for whether a call requires approval or bypasses gating."""

    gate_required: bool
    approved: bool
    bypass_applied: bool
    reason_code: str
    policy_version: str = POLICY_VERSION

    @property
    def allowed(self) -> bool:
        """Return whether execution is allowed under this decision."""
        return self.bypass_applied or not self.gate_required or self.approved


def _has_explicit_approval(context: dict[str, Any]) -> bool:
    """Check request/session context for explicit gate approval."""
    approval_source = str(context.get("approval_source") or "").strip().lower()
    if context.get("gate_approved") is True and approval_source in {"interactive", "ui", "human"}:
        return True
    token = context.get("approval_token")
    return isinstance(token, str) and bool(token.strip())


def _workflow_requires_critical_gate(tool_name: str, context: dict[str, Any]) -> bool:
    """Return True if this invocation includes critical operations."""
    if tool_name in CRITICAL_TOOLS:
        return True
    if tool_name != "execute_workflow":
        return False
    steps = context.get("steps")
    if not isinstance(steps, list):
        # execute_workflow defaults to a sequence that includes run_simulation.
        return True
    return any(step in CRITICAL_TOOLS for step in steps)


def evaluate_gate_policy(
    *,
    tool_name: str,
    context: dict[str, Any],
    caller_action: str | None = None,
) -> GateDecision:
    """
    Evaluate gate policy for a single invocation.

    Default behavior:
    - Critical tools are gated
    - Allowlisted demo actions bypass all gates
    """
    if caller_action in DEMO_BYPASS_ACTIONS:
        return GateDecision(
            gate_required=False,
            approved=True,
            bypass_applied=True,
            reason_code="demo_allowlist",
        )

    if _workflow_requires_critical_gate(tool_name, context):
        approved = _has_explicit_approval(context)
        return GateDecision(
            gate_required=True,
            approved=approved,
            bypass_applied=False,
            reason_code="approved" if approved else "approval_required",
        )

    return GateDecision(
        gate_required=False,
        approved=True,
        bypass_applied=False,
        reason_code="non_critical",
    )
