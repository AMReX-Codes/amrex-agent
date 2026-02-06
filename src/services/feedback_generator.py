"""
Reviewer Service: Feedback Generator: Feedback Generator.

Translates technical validation errors (RuleViolations) into natural language
prompts (Markdown) for the Architect Agent to guide retry logic.

Architecture Decisions:
- Template-based formatting (deterministic, no LLM)
- Severity sorting (Critical > Error > Warning)
- Prefix-based parameter grouping
- Markdown output for LLM consumption
- No deduplication (show all violations for precision)
"""
import logging
from collections import defaultdict

from database.configs.registry import get_feedback_physics_prefixes

from src.services.rules.base import RuleViolation
from src.utils.status_icons import icon_for_severity

logger = logging.getLogger(__name__)


class FeedbackGenerator:
    """
    Reviewer Service: Feedback Generator: Feedback Generator.

    Bridges Reviewer (validation) and Architect (planning) for autonomous retry loop.
    """

    def __init__(self):
        """Initialize generator with severity ranking."""
        # Rank severities for sorting (lower is more critical)
        self.severity_rank = {
            "critical": 0,
            "error": 1,
            "warning": 2,
            "info": 3
        }

    def generate_feedback(self, violations: list[RuleViolation]) -> str:
        """
        Convert list of violations into constructive feedback prompt.

        Call context: Used by Reviewer to build feedback for retry loops.

        Parameters
        ----------
        violations : list of RuleViolation
            RuleViolation objects from Reviewer components.

        Returns
        -------
        str
            Markdown-formatted feedback for Architect retry context.
        """
        if not violations:
            return "Configuration is valid. No issues found."

        # 1. Sort by severity (critical first)
        sorted_violations = sorted(
            violations,
            key=lambda x: self.severity_rank.get(x.severity.lower(), 99)
        )

        # 2. Group by Category
        grouped_issues = defaultdict(list)
        for v in sorted_violations:
            category = self._infer_category(v.parameter)
            grouped_issues[category].append(v)

        # 3. Build Markdown Prompt
        lines = ["## Feedback on Proposed Configuration", ""]

        # Summary header
        error_count = sum(1 for v in violations if v.severity in ['critical', 'error'])
        if error_count > 0:
            lines.append(f"The plan contains **{error_count} blocking issue(s)** that must be resolved.")
        else:
            lines.append("The plan is valid but has warnings to consider.")
        lines.append("")

        # 4. Generate Sections (Fixed Order for consistency)
        priority_order = [
            "System & Resources",
            "Grid & Geometry",
            "Physics & Solver",
            "Particles & EB",
            "I/O",
            "General"
        ]

        for category in priority_order:
            if category in grouped_issues:
                lines.append(f"### {category}")
                # Sort violations within category by severity
                category_violations = sorted(
                    grouped_issues[category],
                    key=lambda x: self.severity_rank.get(x.severity.lower(), 99)
                )
                for v in category_violations:
                    lines.append(self._format_violation(v))
                lines.append("")  # Spacing between sections

        # Catch-all for any categories not in priority list
        for category, items in grouped_issues.items():
            if category not in priority_order:
                lines.append(f"### {category}")
                # Sort by severity within category
                sorted_items = sorted(
                    items,
                    key=lambda x: self.severity_rank.get(x.severity.lower(), 99)
                )
                for v in sorted_items:
                    lines.append(self._format_violation(v))
                lines.append("")

        return "\n".join(lines).strip()

    def _infer_category(self, parameter: str | None) -> str:
        """
        Infer functional category from parameter namespace.

        Architecture Decision: Prefix-Based Grouping (simple, no mapping needed)

        Args:
            parameter: Parameter name (e.g., 'amr.n_cell')

        Returns
        -------
            Category name for grouping
        """
        if not parameter:
            return "System & Resources"

        # Normalize to lowercase for matching
        param_lower = parameter.lower()

        # Check specific patterns BEFORE generic prefixes
        # I/O (check first - more specific than amr.*)
        if any(x in param_lower for x in ['plot', 'check', 'derived', 'plot_int', 'io.']):
            return "I/O"

        # Particles & EB
        if any(x in param_lower for x in ['particles.', 'eb2.', 'eb_', 'spray.']):
            return "Particles & EB"

        # Physics & Solver
        if any(x in param_lower for x in get_feedback_physics_prefixes()):
            return "Physics & Solver"

        # Grid & Geometry (check last for amr.* - catch-all for AMR params)
        if any(x in param_lower for x in ['amr.', 'geometry.', 'prob_lo', 'prob_hi', 'n_cell', 'coord_sys']):
            return "Grid & Geometry"

        return "General"

    def _format_violation(self, v: RuleViolation) -> str:
        """
        Format a single violation into a Markdown bullet point.

        Architecture Decision: Template-based (deterministic, uses violation.message directly)

        Args:
            v: RuleViolation object

        Returns
        -------
            Formatted markdown string
        """
        icon = icon_for_severity(v.severity, use_emoji=True)

        # Format: - [CRITICAL] **param**: Message.
        msg = f"- {icon} "

        if v.parameter:
            msg += f"**{v.parameter}**: "

        msg += f"{v.message}"

        # Add suggestion if available
        if v.suggested_fix:
            msg += f"  \n  *Suggestion:* `{v.suggested_fix}`"

        return msg
