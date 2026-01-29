"""
Input Writer: Schema Scraper Enhancement: Critical Parameter Coverage

Validates that the generated schema contains all parameters
classified as high-priority in Amendment D (Hierarchy of Importance).

Architecture:
    Tier 1 (Physics)  → MUST be present
    Tier 2 (Stability) → SHOULD be present
    Tier 3 (Performance) → MAY be present
    
References:
    - Amendment D.2: Hierarchy of Importance
    - Architect Node: UQ sweep prioritization
"""

import pytest
import warnings
from pathlib import Path
from typing import Set, Dict

from database.scripts.build_schema import SchemaBuilder
from database.configs.pelec_config import PeleCConfig


class TestCriticalParameterCoverage:
    """Test coverage of critical parameters per Amendment D.2."""
    
    @pytest.fixture
    def full_pelec_schema(self) -> Dict:
        """
        Load real PeleC complete schema from database.
        
        Uses newest schema (matching 'newest' strategy in ConfigModelFactory).
        """
        import json
        
        schema_dir = Path("database/schemas")
        schemas = list(schema_dir.glob("pelec_complete_*.json"))
        
        if not schemas:
            pytest.skip("No PeleC complete schema found. Run: python database/scripts/build_schema.py ../PeleC --auto-compose")
        
        # Use newest (matching default strategy)
        latest = max(schemas, key=lambda p: p.stat().st_mtime)
        schema_data = json.load(open(latest))
        
        return schema_data.get('parameters', {})
    
    def test_tier1_physics_parameters_present(self, full_pelec_schema):
        """
        Given: Full PeleC schema
        When:  Checking Tier 1 (Physics Definition) parameters
        Then:  ALL must be present (hard requirement)
        
        Validates: Amendment D.2 - Physics parameters are non-negotiable
        """
        tier1_params = {
            "pelec.cfl",
            "pelec.do_react",  # Critical: Enable/disable reactions
            "amr.n_cell",
        }
        
        missing = tier1_params - set(full_pelec_schema.keys())
        
        assert not missing, (
            f"CRITICAL: Tier 1 physics parameters missing from schema: {missing}\n"
            f"These parameters define the simulation physics and are required for UQ."
        )
    
    def test_tier2_stability_parameters_present(self, full_pelec_schema):
        """
        Given: Full PeleC schema
        When:  Checking Tier 2 (Numerical Stability) parameters
        Then:  SHOULD be present (soft requirement, warn if missing)
        
        Validates: Amendment D.2 - Stability parameters important but not critical
        """
        tier2_params = {
            "pelec.do_react",
            "amr.max_level",
        }
        
        missing = tier2_params - set(full_pelec_schema.keys())
        
        if missing:
            warnings.warn(
                f"Important Tier 2 stability parameters missing: {missing}",
                UserWarning
            )
        
        # Soft assertion - test passes but logs warning
        assert len(missing) <= 1, \
            "Too many Tier 2 parameters missing - check source scan coverage"
    
    def test_tier3_performance_parameters_optional(self, full_pelec_schema):
        """
        Given: Full PeleC schema
        When:  Checking Tier 3 (Performance) parameters
        Then:  MAY be present (no requirement)
        
        Validates: Amendment D.2 - Performance params nice to have
        """
        tier3_params = {
            "amr.blocking_factor",
        }
        
        present = tier3_params & set(full_pelec_schema.keys())
        
        # No assertion - just informational
        if present:
            pytest.skip(f"Tier 3 performance parameters found: {present}")
    
    def test_schema_priority_tagging(self, full_pelec_schema):
        """
        Given: Schema with priority tags
        When:  Checking parameter metadata
        Then:  Critical params should be marked "tier1"
        
        Validates: Schema enhancement for UQ prioritization
        """
        # Tier 1 params should be tagged
        assert full_pelec_schema.get("pelec.cfl", {}).get("priority") == "tier1", \
            "CFL must be marked as Tier 1 for UQ sweep prioritization"
        
        assert full_pelec_schema.get("pelec.do_react", {}).get("priority") == "tier1", \
            "do_react must be marked as Tier 1 (critical physics switch)"
    
    def test_coverage_report_generation(self, full_pelec_schema):
        """
        Given: Full schema
        When:  Generating coverage report
        Then:  Should show percentage of critical params covered
        
        Validates: Quality metric for schema completeness
        """
        tier1_params = {"pelec.cfl", "pelec.do_react", "amr.n_cell"}
        tier2_params = {"amr.max_level", "amr.blocking_factor"}
        
        tier1_coverage = len(tier1_params & set(full_pelec_schema.keys())) / len(tier1_params)
        tier2_coverage = len(tier2_params & set(full_pelec_schema.keys())) / len(tier2_params)
        
        # Quality gates
        assert tier1_coverage == 1.0, "Tier 1 coverage must be 100%"
        assert tier2_coverage >= 0.8, "Tier 2 coverage should be at least 80%"
        
        # Log for monitoring
        print(f"\n=== Schema Coverage Report ===")
        print(f"Tier 1 (Physics):    {tier1_coverage:.1%}")
        print(f"Tier 2 (Stability):  {tier2_coverage:.1%}")


class TestMultiSolverCoverage:
    """Test coverage across different AMReX solvers."""
    
    @pytest.mark.parametrize("solver_config,required_params", [
        ("PeleCConfig", {"pelec.cfl", "geometry.is_periodic"}),
        ("ERFConfig", {"erf.cfl", "geometry.is_periodic"}),
        ("WarpXConfig", {"warpx.cfl", "geometry.is_periodic"}),
    ])
    def test_cross_solver_tier1_coverage(self, solver_config, required_params, tmp_path):
        """
        Given: Different AMReX solver configs
        When:  Building schema
        Then:  Each solver's Tier 1 params must be present
        
        Validates: Universal coverage across solver family
        """
        # This would be fully implemented with actual solver repos
        pytest.skip("Requires full solver repositories")
