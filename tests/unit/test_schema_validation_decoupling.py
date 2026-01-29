"""
Input Writer: Schema Metadata vs Validation Decoupling

Tests for Issue 2:
1. Schema correctly marks pp.get() as required (Metadata)
2. Pydantic model allows missing fields (Permissive Load)
3. Rule Engine enforces required fields (Strict Validation)

Reference: Amendment C, Amendment D
"""

import pytest
from typing import Dict, Any
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, 'database/scripts')
sys.path.insert(0, 'src')

from build_schema import SchemaBuilder
from services.config_model_factory import ConfigModelFactory


class TestSchemaValidationDecoupling:

    @pytest.fixture
    def cpp_source(self, tmp_path):
        """Creates C++ source with mix of required and optional params."""
        content = """
        void Setup() {
            ParmParse pp("amr");
            
            // Required (pp.get)
            int viscosity;
            pp.get("viscosity", viscosity);
            
            // Optional (pp.query)
            Real cfl = 0.8;
            pp.query("cfl", cfl);
        }
        """
        source_dir = tmp_path / "Source"
        source_dir.mkdir()
        f = source_dir / "Setup.cpp"
        f.write_text(content)
        return tmp_path

    def test_schema_required_semantics(self, cpp_source):
        """
        Verify schema accurately reflects C++ source truth (metadata).
        """
        builder = SchemaBuilder(cpp_source)
        builder.scan_source_code(['Source'])
        schema = builder.schema

        # Metadata should be strict
        assert "amr.viscosity" in schema, "Missing viscosity parameter"
        assert "amr.cfl" in schema, "Missing cfl parameter"
        
        assert schema["amr.viscosity"]["required"] is True, "pp.get should be required in schema"
        assert schema["amr.cfl"]["required"] is False, "pp.query should be optional in schema"

    def test_sparse_config_compatibility(self, cpp_source):
        """
        Verify Pydantic model loads sparse config without error.
        
        This is the CRITICAL test for Issue #2:
        - Schema says viscosity is required
        - But Pydantic should allow it to be missing
        - Validation happens later in Rule Engine
        """
        # 1. Build Schema
        builder = SchemaBuilder(cpp_source)
        builder.scan_source_code(['Source'])
        schema = builder.schema

        # 2. Create Model
        Model = ConfigModelFactory.create_from_schema(schema, build_config={})

        # 3. Load Sparse Config (missing 'viscosity' which is marked required!)
        sparse_input = "amr.cfl = 0.5"
        
        # Should NOT raise ValidationError (this is the key test)
        try:
            model = ConfigModelFactory.hydrate(Model, sparse_input)
        except Exception as e:
            pytest.fail(f"Sparse config hydration failed (Pydantic too strict): {e}")

        # Check values
        assert model.amr_cfl == 0.5, "Should load provided value"
        assert model.amr_viscosity is None, "Should default to None, not raise error"

    def test_all_fields_optional_in_pydantic(self, cpp_source):
        """
        Verify ALL Pydantic fields are Optional, regardless of schema metadata.
        """
        builder = SchemaBuilder(cpp_source)
        builder.scan_source_code(['Source'])
        schema = builder.schema
        
        Model = ConfigModelFactory.create_from_schema(schema, {})
        
        # Check field definitions
        for field_name, field_info in Model.model_fields.items():
            # All fields should allow None
            assert not field_info.is_required(), f"Field {field_name} should be Optional"
            
        # Should be able to create completely empty instance
        empty_model = Model()
        assert empty_model is not None, "Should create empty model"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
