"""Paper design validator used by B4 deferred-design gating."""

from __future__ import annotations

from typing import Any


class PaperValidator:
    """Validate whether a paper design payload is complete or explicitly deferred."""

    def validate(self, state: dict[str, Any]) -> dict[str, Any]:
        """Return normalized validation results for graph-level routing."""
        plan = state.get("plan")
        if not isinstance(plan, dict):
            return {
                "paper_validation_passed": False,
                "paper_validation_status": "failed",
                "paper_validation_reason": "missing_plan",
                "paper_design_deferred": False,
            }

        design = plan.get("paper_design")
        if not isinstance(design, dict):
            return {
                "paper_validation_passed": False,
                "paper_validation_status": "failed",
                "paper_validation_reason": "missing_paper_design",
                "paper_design_deferred": False,
            }

        if bool(design.get("deferred", False)):
            return {
                "paper_validation_passed": True,
                "paper_validation_status": "deferred",
                "paper_validation_reason": "design_deferred",
                "paper_design_deferred": True,
            }

        sections = design.get("sections")
        has_sections = isinstance(sections, list) and len(sections) > 0
        if not has_sections:
            return {
                "paper_validation_passed": False,
                "paper_validation_status": "failed",
                "paper_validation_reason": "missing_sections",
                "paper_design_deferred": False,
            }

        return {
            "paper_validation_passed": True,
            "paper_validation_status": "passed",
            "paper_validation_reason": "ok",
            "paper_design_deferred": False,
        }
