"""
Input Writer: Schema Scraper: Schema Quality Tests

Regression tests for Issue 1:
1. Invalid parameter names (e.g., ".")
2. Required parameter count inflation (get vs query)
3. Malformed namespace structures

Reference: Amendment D, Input Writer: Schema Scraper
"""

import pytest
from pathlib import Path
import sys

# Add paths for imports
sys.path.insert(0, 'database/scripts')
from build_schema import SchemaBuilder


class TestSchemaQuality:
    
    @pytest.fixture
    def dirty_source_file(self, tmp_path):
        """Creates a C++ file with known problematic ParmParse calls."""
        content = """
        void BadParams() {
            ParmParse pp("amr");
            
            // 1. The "." bug (SprayJet.cpp regression)
            int val;
            pp.get(".", val); 
            
            // 2. Trailing dot
            pp.query("bad_param.", val);
            
            // 3. Valid parameters
            pp.get("viscosity", val);      // Required
            pp.query("diffusivity", val);  // Optional
            
            // 4. Nested namespace (Valid)
            pp.query("chem.rate", val);
            
            // 5. Empty string
            pp.get("", val);
        }
        """
        source_dir = tmp_path / "Source"
        source_dir.mkdir()
        f = source_dir / "SprayJet.cpp"
        f.write_text(content)
        return f

    def test_no_invalid_parameter_names(self, tmp_path, dirty_source_file):
        """
        Verify schema rejects invalid parameter names like '.', empty strings, or trailing dots.
        """
        builder = SchemaBuilder(tmp_path)
        builder.scan_source_code(['Source'])
        
        schema = builder.schema
        
        # Should NOT contain invalid names
        assert "amr.." not in schema, "Double dots should be rejected"
        assert "amr." not in schema, "Bare dot should be rejected"
        assert "." not in schema, "Just '.' should be rejected"
        assert "amr.bad_param." not in schema, "Trailing dot should be rejected"
        
        # Should contain valid names
        assert "amr.viscosity" in schema, "Valid parameter missing"
        assert "amr.diffusivity" in schema, "Valid parameter missing"
        assert "amr.chem.rate" in schema, "Nested namespace missing"

    def test_required_count_accuracy(self, tmp_path, dirty_source_file):
        """
        Verify 'pp.get' maps to required=True and 'pp.query' to required=False.
        Prevents regression where all params become required.
        """
        builder = SchemaBuilder(tmp_path)
        builder.scan_source_code(['Source'])
        
        schema = builder.schema
        
        # Check required (pp.get)
        if "amr.viscosity" in schema:
            assert schema["amr.viscosity"]["required"] is True, "pp.get should be required"
        
        # Check optional (pp.query)
        if "amr.diffusivity" in schema:
            assert schema["amr.diffusivity"]["required"] is False, "pp.query should be optional"
        
        # Count check (only 1 valid required param in fixture)
        required_params = [k for k, v in schema.items() if v.get('required', False)]
        assert len(required_params) == 1, f"Expected 1 required param, found {len(required_params)}: {required_params}"

    def test_dot_notation_validity(self, tmp_path):
        """
        Verify nested namespaces are structured correctly and valid.
        """
        content = """
        void Setup() {
            ParmParse pp("amr");
            int n_cell;
            pp.query("n_cell", n_cell); // amr.n_cell
            
            ParmParse pp_geom("geometry");
            Real lo;
            pp_geom.get("prob_lo", lo); // geometry.prob_lo
        }
        """
        source_dir = tmp_path / "Source"
        source_dir.mkdir()
        f = source_dir / "Valid.cpp"
        f.write_text(content)
        
        builder = SchemaBuilder(tmp_path)
        builder.scan_source_code(['Source'])
        
        schema = builder.schema
        
        assert "amr.n_cell" in schema, "Namespace parameter missing"
        assert "geometry.prob_lo" in schema, "Namespace parameter missing"
        
        # Regex validation for all keys
        import re
        valid_pattern = re.compile(r'^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$')
        
        for param in schema.keys():
            assert valid_pattern.match(param), f"Invalid parameter format: {param}"
    
    def test_empty_string_parameter_rejected(self, tmp_path):
        """Empty parameter names should be rejected."""
        content = """
        void test() {
            ParmParse pp("test");
            int val;
            pp.get("", val);  // Invalid
        }
        """
        source_dir = tmp_path / "Source"
        source_dir.mkdir()
        f = source_dir / "test.cpp"
        f.write_text(content)
        
        builder = SchemaBuilder(tmp_path)
        builder.scan_source_code(['Source'])
        
        # Should not have empty or "test." in schema
        assert "" not in builder.schema
        assert "test." not in builder.schema


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
