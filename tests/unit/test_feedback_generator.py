"""
Reviewer Service: Feedback Generator: Feedback Generator Tests

TDD: RED → GREEN → Refactor
Tests markdown formatting for Architect feedback loop.
"""
import pytest

from src.services.feedback_generator import FeedbackGenerator
from src.services.rules.base import RuleViolation


class TestFeedbackGenerator:

    @pytest.fixture
    def generator(self):
        """Create feedback generator instance."""
        return FeedbackGenerator()

    def test_severity_sorting_within_categories(self, generator):
        """
        CRITICAL TEST 1: Verify severity ordering within categories
        
        GIVEN: Violations with mixed severities in same category
        WHEN: generate_feedback() is called
        THEN: Within each category, critical → error → warning order
        """
        violations = [
            # All in Grid & Geometry category
            RuleViolation("R1", "warning", "Low priority issue", "amr.v"),
            RuleViolation("R2", "critical", "Critical grid issue", "amr.max_level"),
            RuleViolation("R3", "error", "Invalid logic", "amr.n_cell"),
        ]
        
        feedback = generator.generate_feedback(violations)
        
        # All should be in Grid & Geometry section
        assert "### Grid & Geometry" in feedback
        
        # Extract just the Grid section
        grid_section = feedback.split("### Grid & Geometry")[1].split("###")[0]
        
        # Find indices within the grid section
        idx_crit = grid_section.find("Critical grid issue")
        idx_err = grid_section.find("Invalid logic")
        idx_warn = grid_section.find("Low priority issue")
        
        assert idx_crit != -1 and idx_err != -1 and idx_warn != -1, \
            "Not all messages found in Grid section"
        
        # Within the section: Critical < Error < Warning
        assert idx_crit < idx_err < idx_warn, \
            f"Wrong order in section: crit@{idx_crit}, err@{idx_err}, warn@{idx_warn}"

    def test_category_grouping_logic(self, generator):
        """
        CRITICAL TEST 2: Verify parameter grouping
        
        GIVEN: Violations from different functional areas
        WHEN: generate_feedback() is called
        THEN: Output has correct section headers and grouping
        """
        violations = [
            RuleViolation("R1", "error", "Grid error", "amr.n_cell"),
            RuleViolation("R2", "error", "Physics error", "amr.cfl"),
            RuleViolation("R3", "error", "Particle error", "particles.v"),
        ]
        
        feedback = generator.generate_feedback(violations)
        
        # Check headers exist
        assert "### Grid & Geometry" in feedback
        assert "### Physics & Solver" in feedback
        assert "### Particles & EB" in feedback
        
        # Verify content is under correct header
        grid_section = feedback.split("### Physics & Solver")
        assert "amr.n_cell" in grid_section[0], "Grid param not in Grid section"
        
        physics_section = feedback.split("### Grid & Geometry")
        assert "amr.cfl" in physics_section[1], "Physics param not in Physics section"

    def test_template_formatting_with_suggestion(self, generator):
        """
        CRITICAL TEST 3: Verify markdown template
        
        GIVEN: Violation with suggested_fix
        WHEN: generate_feedback() is called
        THEN: Output has icon, parameter, message, and suggestion
        """
        violation = RuleViolation(
            rule_name="TestRule",
            severity="error",
            message="Invalid value",
            parameter="amr.max_level",
            suggested_fix="Set to 2"
        )
        
        feedback = generator.generate_feedback([violation])
        
        # Check components
        assert "❌" in feedback, "Missing error icon"
        assert "**amr.max_level**" in feedback, "Missing bold parameter"
        assert "Invalid value" in feedback, "Missing message"
        assert "*Suggestion:*" in feedback, "Missing suggestion label"
        assert "Set to 2" in feedback, "Missing suggestion text"

    def test_system_error_handling_no_param(self, generator):
        """
        GIVEN: Global error with parameter=None
        WHEN: generate_feedback() is called
        THEN: Grouped under System & Resources, no bold parameter
        """
        violation = RuleViolation(
            rule_name="FileCheck",
            severity="critical",
            message="Executable not found",
            parameter=None
        )
        
        feedback = generator.generate_feedback([violation])
        
        assert "### System & Resources" in feedback
        assert "Executable not found" in feedback
        # Check that we don't have "**None**" or similar
        assert "**None**" not in feedback

    def test_no_deduplication(self, generator):
        """
        GIVEN: Multiple violations for same parameter
        WHEN: generate_feedback() is called
        THEN: All violations shown (no deduplication)
        """
        violations = [
            RuleViolation("R1", "error", "Msg 1", "amr.n_cell"),
            RuleViolation("R2", "error", "Msg 2", "amr.n_cell"),
        ]
        
        feedback = generator.generate_feedback(violations)
        
        assert "Msg 1" in feedback
        assert "Msg 2" in feedback
        assert feedback.count("amr.n_cell") == 2

    def test_empty_violations_list(self, generator):
        """
        GIVEN: Empty violations list
        WHEN: generate_feedback() is called
        THEN: Returns positive validation message
        """
        feedback = generator.generate_feedback([])
        
        assert "valid" in feedback.lower() or "no issues" in feedback.lower()
        assert len(feedback) > 0

    def test_markdown_formatting_valid(self, generator):
        """
        GIVEN: Standard violation
        WHEN: generate_feedback() is called
        THEN: Output is valid Markdown (headers, bullets, bold)
        """
        violation = RuleViolation(
            "Rule", "error", "Test message", "test.param", "Fix it"
        )
        
        feedback = generator.generate_feedback([violation])
        
        # Basic markdown elements
        assert feedback.startswith("##")  # Header
        assert "- " in feedback  # Bullet point
        assert "**" in feedback  # Bold text

    def test_error_fields_include_tier_category_and_normalized_severity(self, generator):
        """
        GIVEN: Violation with uppercase severity and no explicit taxonomy metadata
        WHEN: RuleViolation is created
        THEN: Severity is normalized and tier/category fields are auto-populated
        """
        violation = RuleViolation(
            "Rule",
            "ERROR",
            "Bad setting",
            "amr.n_cell",
        )

        assert violation.severity == "error"
        assert violation.tier == "tier1"
        assert violation.category == "Grid & Geometry"

        feedback = generator.generate_feedback([violation])
        assert "Bad setting" in feedback

    def test_error_fields_preserve_explicit_tier_and_category(self):
        """
        GIVEN: Violation with explicit taxonomy metadata
        WHEN: RuleViolation is created
        THEN: Explicit tier/category values are preserved
        """
        violation = RuleViolation(
            "Rule",
            "warning",
            "Needs review",
            "custom.param",
            tier="tier9",
            category="Custom Group",
        )

        assert violation.severity == "warning"
        assert violation.tier == "tier9"
        assert violation.category == "Custom Group"

    def test_multiple_categories_priority_order(self, generator):
        """
        GIVEN: Violations across all categories
        WHEN: generate_feedback() is called
        THEN: Categories appear in fixed priority order
        """
        violations = [
            RuleViolation("R1", "error", "I/O issue", "amr.plot_int"),
            RuleViolation("R2", "error", "Grid issue", "geometry.prob_lo"),
            RuleViolation("R3", "error", "Sys issue", None),
        ]
        
        feedback = generator.generate_feedback(violations)
        
        # Find section positions
        idx_system = feedback.find("### System & Resources")
        idx_grid = feedback.find("### Grid & Geometry")
        idx_io = feedback.find("### I/O")
        
        # All sections should exist
        assert idx_system != -1, "System section missing"
        assert idx_grid != -1, "Grid section missing"
        assert idx_io != -1, "I/O section missing"
        
        # System should appear before Grid, Grid before I/O
        assert idx_system < idx_grid < idx_io, \
            f"Wrong section order: sys@{idx_system}, grid@{idx_grid}, io@{idx_io}"
