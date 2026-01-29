"""
Reviewer Service: Resource Validator: External Resource Validator Tests (DEFERRED)

NOTE: Most tests marked as skipped - functionality deferred to Runner Node.
Tests document expected behavior but are not blocking for MVP.
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from src.services.validators.resource_validator import ResourceValidator
from src.services.rules.base import RuleViolation
from src.config import AMReXAgentConfig


class TestResourceValidator:

    @pytest.fixture
    def validator(self):
        """Create validator with mock config."""
        config = AMReXAgentConfig()
        return ResourceValidator(config)

    def test_chemistry_file_exists_in_search_path(self, validator):
        """
        GIVEN: Plan references chemistry mechanism (e.g., 'drm19')
        WHEN: mechanism.yaml exists in PelePhysics/Mechanisms
        THEN: No violations
        """
        plan = {
            "selected_solver": "PeleC",
            "modifications": [("pelec.chem_file", "drm19")]
        }
        
        # Mock file exists in one search path
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            violations = validator.validate(plan)
        
        assert len(violations) == 0

    def test_chemistry_file_not_found(self, validator):
        """
        GIVEN: Plan references non-existent chemistry mechanism
        WHEN: File not in any search path
        THEN: Returns critical violation
        """
        plan = {
            "selected_solver": "PeleC",
            "modifications": [("pelec.chem_file", "fake_mechanism")]
        }
        
        # Mock file doesn't exist anywhere
        with patch("pathlib.Path.exists", return_value=False):
            violations = validator.validate(plan)
        
        assert len(violations) >= 1
        assert violations[0].severity == "critical"
        assert "fake_mechanism" in violations[0].message

    def test_geometry_file_check_stl(self, validator):
        """
        GIVEN: EB geometry with STL file
        WHEN: File doesn't exist
        THEN: Returns critical violation
        """
        plan = {
            "modifications": [
                ("eb2.geom_type", "stl"),
                ("eb2.geom_file", "sphere.stl")
            ]
        }
        
        with patch("pathlib.Path.exists", return_value=False):
            violations = validator.validate(plan)
        
        assert any(
            v.parameter == "eb2.geom_file" and v.severity == "critical"
            for v in violations
        )

    def test_memory_estimation_warning(self, validator):
        """
        GIVEN: Extremely large grid (2048^3)
        WHEN: Estimated memory > 1TB
        THEN: Returns warning violation
        """
        plan = {
            "modifications": [("amr.n_cell", "2048 2048 2048")]
        }
        
        violations = validator.validate(plan)
        
        assert any(
            v.rule_name == "ResourceLimit" and v.severity == "warning"
            for v in violations
        )

    def test_reasonable_grid_size_passes(self, validator):
        """
        GIVEN: Normal grid size (128^3)
        WHEN: validate() called
        THEN: No memory warnings
        """
        plan = {
            "modifications": [("amr.n_cell", "128 128 128")]
        }
        
        violations = validator.validate(plan)
        
        # Should not have memory warnings
        assert not any(v.rule_name == "ResourceLimit" for v in violations)

    # === DEFERRED TESTS (Document Expected Behavior) ===

    @pytest.mark.skip(reason="Deferred to Runner Node (Runner)")
    def test_executable_presence_check(self, validator):
        """
        DEFERRED: Executable validation moved to Runner.
        
        GIVEN: Plan specifies custom executable
        WHEN: Executable not found in PATH
        THEN: Should return critical violation
        
        NOTE: Runner Node handles compilation/finding executables
        """
        plan = {
            "modifications": [("executable", "CustomAMReX.ex")]
        }
        
        with patch("shutil.which", return_value=None), \
             patch("pathlib.Path.exists", return_value=False):
            violations = validator.validate(plan)
            assert any("Executable" in v.message for v in violations)

    @pytest.mark.skip(reason="Deferred to Runner Node (Runner)")
    def test_restart_file_validation(self, validator):
        """
        DEFERRED: Restart validation at execution time.
        
        GIVEN: Plan specifies amr.restart checkpoint
        WHEN: Directory doesn't exist yet
        THEN: Runner will handle creating/finding it
        """
        plan = {
            "modifications": [("amr.restart", "chk00100")]
        }
        pass

    @pytest.mark.skip(reason="Deferred to Runner Node (Runner)")
    def test_run_directory_permissions(self, validator):
        """
        DEFERRED: Permission checks at job submission time.
        
        Container environments have different permission models.
        Runner validates actual execution environment.
        """
        plan = {"modifications": []}
        pass

    @pytest.mark.skip(reason="Deferred to Runner Node (Runner)")
    def test_disk_quota_check(self, validator):
        """
        DEFERRED: Quota checks expensive and flaky.
        
        Should be done by Runner immediately before job submission,
        not during plan validation.
        """
        plan = {"modifications": []}
        pass
