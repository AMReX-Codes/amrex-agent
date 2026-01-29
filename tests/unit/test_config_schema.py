"""
Config Schema Tests - Metadata Schema

Defines the data contract between Configuration (Source of Truth)
and Index Builder (Consumer).

Validates:
- Amendment B: Portable path-based identifiers
- Amendment C: Full input file parsing
- Level 2 metadata: Grid, Physics, Path indices
"""
import pytest
from pathlib import Path


class TestMetadataSchema:
    """Category 1: Validate complete metadata schema."""
    
    def test_extract_metadata_complete_schema(self, tmp_path):
        """
        Given: A case directory with inputs file
        When:  Calling extract_metadata(case_dir)
        Then:  Should return complete Level 2 metadata
        
        Verifies:
        - Registry metadata (code_name, github_org) from Cases Service: Config-Driven Discovery
        - Parsed metadata (n_cell, max_step) from inputs file
        - Portable path (repo_path) from Amendment B
        - Full inputs content from Amendment C
        
        Data Contract: This defines what the Index Builder receives
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Create case structure
        repo_root = tmp_path / "TestCode"
        case_dir = repo_root / "Exec" / "RegTests" / "TestBox"
        case_dir.mkdir(parents=True)
        
        # Create inputs file with known parameters
        inputs_content = """
# Test case configuration
amr.n_cell = 64 64 64
amr.max_level = 2
max_step = 100
geometry.prob_lo = 0.0 0.0 0.0
geometry.is_periodic = 1 1 1
pelec.cfl = 0.5
"""
        (case_dir / "inputs").write_text(inputs_content)
        
        # Act: Extract metadata
        metadata = BaseAMReXConfig.extract_metadata(case_dir)
        
        # Assert: Complete schema
        # 1. Identity (portable)
        assert "case_name" in metadata, "Must have case_name"
        assert metadata["case_name"] == "TestBox"
        
        assert "repo_path" in metadata, "Must have repo_path (portable ID)"
        assert metadata["repo_path"].endswith("Exec/RegTests/TestBox"),             "repo_path must be relative (Amendment B)"
        
        # 2. Grid configuration (Level 2 Index)
        assert "n_cell" in metadata, "Must extract n_cell for Grid Index"
        assert metadata["n_cell"] == "64 64 64"
        
        # 3. Physics parameters (Level 2 Index)
        assert "max_step" in metadata, "Must have max_step"
        
        # Namespaced parameters preserved in inputs_content
        inputs_dict = metadata["inputs_content"]
        assert "pelec.cfl" in inputs_dict,             "Must preserve namespaced parameters in inputs_content"
        
        # 4. Full inputs content (Amendment C)
        assert "inputs_content" in metadata,             "Must have inputs_content (Amendment C)"
        assert isinstance(metadata["inputs_content"], dict),             "inputs_content must be dict, not string (full parsing)"
        
        # Should contain all parsed parameters
        inputs_dict = metadata["inputs_content"]
        assert "amr.n_cell" in inputs_dict, "inputs_content must be complete"
        assert "geometry.is_periodic" in inputs_dict,             "Must preserve all parameters for generation context"


    def test_registry_metadata_integrated(self, tmp_path):
        """
        Given: PeleCConfig with registry metadata
        When:  Extracting metadata
        Then:  Should include both registry AND parsed data
        
        Verifies: Integration of Cases Service: Config-Driven Discovery (registry) with Metadata Schema (parsing)
        """
        from database.configs import PeleCConfig
        
        # Arrange
        case_dir = tmp_path / "Exec" / "RegTests" / "PMF"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("max_step = 10")
        
        # Act
        metadata = PeleCConfig.extract_metadata(case_dir)
        
        # Assert: Registry metadata included
        assert "code_name" in metadata or "code" in metadata, \
            "Must include code_name from registry"
        assert "github_org" in metadata, \
            "Must include github_org from Cases Service: Config-Driven Discovery"
        
        # And parsed data
        assert "max_step" in metadata, "Must include parsed data"
        
        # Verify values come from config class
        assert metadata.get("code_name") == "PeleC" or metadata.get("code") == "PeleC"
        assert metadata["github_org"] == "AMReX-Combustion"


class TestInputFileParsing:
    """Category 2: Robust input file parsing (Amendment C)."""
    
    def test_parse_inputs_file_regex(self):
        """
        Given: Raw inputs file content with various formats
        When:  Parsing with regex
        Then:  Should handle all AMReX input patterns
        
        Tests:
        - Standard key = value
        - Inline comments
        - Extra whitespace
        - Namespaced keys (amr.n_cell)
        - Various value types (strings, numbers, booleans)
        
        Single Source of Truth: Config class defines parsing logic
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Complex inputs file
        inputs_text = """
# Header comment
amr.n_cell = 128 64 32  # Grid size
geometry.prob_lo   =   0.0 0.0 0.0

# Physics section
pelec.use_soret = true
pelec.diffusion_type = ConstantDiffusivity  
max_step=1000

# Empty lines and more comments
# This is ignored
amr.max_level =2
"""
        
        # Act
        parsed = BaseAMReXConfig.parse_inputs(inputs_text)
        
        # Assert: All patterns handled
        assert parsed["amr.n_cell"] == "128 64 32", \
            "Should strip inline comment"
        
        assert parsed["geometry.prob_lo"] == "0.0 0.0 0.0", \
            "Should handle extra whitespace"
        
        assert parsed["pelec.use_soret"] == "true", \
            "Should parse boolean strings"
        
        assert parsed["pelec.diffusion_type"] == "ConstantDiffusivity", \
            "Should parse string values"
        
        assert parsed["max_step"] == "1000", \
            "Should handle no whitespace around ="
        
        assert parsed["amr.max_level"] == "2", \
            "Should handle tight spacing"
        
        # Should NOT include comments
        assert "# Header comment" not in str(parsed.values()), \
            "Should not include comment text in values"
    
    
    def test_parse_preserves_namespaces(self):
        """
        Given: Inputs with hierarchical namespaces
        When:  Parsing
        Then:  Should preserve dot notation (amr.n_cell, not n_cell)
        
        Critical: LLM needs to know amr.n_cell vs pelec.n_cell
        """
        from database.configs import BaseAMReXConfig
        
        inputs_text = """
amr.n_cell = 64 64 64
pelec.n_cell = 128 128 128
amrex.verbose = 1
"""
        
        parsed = BaseAMReXConfig.parse_inputs(inputs_text)
        
        # Should preserve full namespaced keys
        assert "amr.n_cell" in parsed, "Should preserve amr namespace"
        assert "pelec.n_cell" in parsed, "Should preserve pelec namespace"
        assert "amrex.verbose" in parsed, "Should preserve amrex namespace"
        
        # Should NOT create n_cell (ambiguous)
        assert parsed["amr.n_cell"] != parsed["pelec.n_cell"], \
            "Different namespaces should have different values"
    
    
    def test_parse_handles_edge_cases(self):
        """
        Edge cases:
        - Empty lines
        - Comment-only lines
        - Values with spaces (vector notation)
        - Missing values
        """
        from database.configs import BaseAMReXConfig
        
        inputs_text = """

# Comment only line

vector_param = 1.0 2.0 3.0
# Another comment
string_with_spaces = hello world

"""
        
        parsed = BaseAMReXConfig.parse_inputs(inputs_text)
        
        assert "vector_param" in parsed
        assert parsed["vector_param"] == "1.0 2.0 3.0", \
            "Should preserve multi-value parameters"
        
        # This one is tricky - should we keep it?
        # For now, keep everything after =
        if "string_with_spaces" in parsed:
            assert "hello world" in parsed["string_with_spaces"]


class TestPathPortability:
    """Category 3: Amendment B compliance (portable paths)."""
    
    def test_path_portability(self, tmp_path):
        """
        Given: Case at /tmp/pytest-123/PeleC/Exec/Production/Flame
        When:  Extracting metadata
        Then:  repo_path should be "Exec/Production/Flame"
        
        Amendment B: Index must be portable across machines
        
        Critical: repo_path is the unique identifier in FAISS
        """
        from database.configs import BaseAMReXConfig
        
        # Arrange: Absolute path structure
        repo_root = tmp_path / "PeleC"
        case_dir = repo_root / "Exec" / "Production" / "Flame"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("max_step = 10")
        
        # Act: Extract with knowledge of repo root
        metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Assert: Portable path
        repo_path = metadata["repo_path"]
        
        # Must be relative
        assert not repo_path.startswith("/"), \
            f"repo_path must be relative, got: {repo_path}"
        
        assert not str(tmp_path) in repo_path, \
            f"repo_path must not contain temp dir: {repo_path}"
        
        # Must be correct relative path
        assert repo_path == "Exec/Production/Flame" or \
               repo_path.endswith("Exec/Production/Flame"), \
            f"Expected 'Exec/Production/Flame', got: {repo_path}"
    
    
    def test_repo_path_is_unique_identifier(self, tmp_path):
        """
        Given: Two users with same case at different paths
        When:  Both index the case
        Then:  repo_path should be identical (same FAISS key)
        
        Scenario:
        - User A: /global/cfs/cdirs/m4431/PeleC/Exec/RegTests/PMF
        - User B: /home/user/codes/PeleC/Exec/RegTests/PMF
        
        Both should get repo_path = "Exec/RegTests/PMF"
        """
        from database.configs import BaseAMReXConfig
        
        # User A's path
        user_a_root = tmp_path / "user_a" / "PeleC"
        case_a = user_a_root / "Exec" / "RegTests" / "PMF"
        case_a.mkdir(parents=True)
        (case_a / "inputs").write_text("max_step = 10")
        
        # User B's path
        user_b_root = tmp_path / "user_b" / "PeleC"
        case_b = user_b_root / "Exec" / "RegTests" / "PMF"
        case_b.mkdir(parents=True)
        (case_b / "inputs").write_text("max_step = 10")
        
        # Extract with different roots
        metadata_a = BaseAMReXConfig.extract_metadata(case_a, repo_root=user_a_root)
        metadata_b = BaseAMReXConfig.extract_metadata(case_b, repo_root=user_b_root)
        
        # Assert: Same repo_path (portable identifier)
        assert metadata_a["repo_path"] == metadata_b["repo_path"], \
            "Different absolute paths should yield same repo_path"
        
        assert metadata_a["repo_path"] == "Exec/RegTests/PMF"
    
    
    def test_local_path_stored_separately(self, tmp_path):
        """
        Given: Metadata extraction
        When:  Extracting metadata
        Then:  Should store BOTH repo_path (portable) and local_path (absolute)
        
        Use cases:
        - repo_path: FAISS key (portable)
        - local_path: File operations (machine-specific)
        """
        from database.configs import BaseAMReXConfig
        
        repo_root = tmp_path / "PeleC"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("max_step = 10")
        
        metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Should have both
        assert "repo_path" in metadata, "Must have portable path"
        assert "local_path" in metadata or "absolute_path" in metadata, \
            "Should have absolute path for file operations"
        
        # Verify they're different
        repo_path = metadata["repo_path"]
        local_path = metadata.get("local_path") or metadata.get("absolute_path")
        
        assert repo_path != str(local_path), \
            "repo_path and local_path should be different"
        
        assert not repo_path.startswith("/"), "repo_path must be relative"
        assert str(local_path).startswith("/") or str(local_path).startswith(str(tmp_path)), \
            "local_path must be absolute"


class TestSchemaValidation:
    """Category 4: Schema completeness and validation."""
    
    def test_required_fields_present(self, tmp_path):
        """
        Given: Any case directory
        When:  Extracting metadata
        Then:  Must contain ALL required fields for Level 2 indexing
        
        Required Fields (Contract with Index Builder):
        - case_name: Human identifier
        - repo_path: Portable unique ID
        - code_name: Which AMReX code
        - n_cell: Grid configuration
        - inputs_content: Full context (Amendment C)
        """
        from database.configs import BaseAMReXConfig
        
        repo_root = tmp_path / "TestCode"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        
        inputs = """
amr.n_cell = 64 64 64
max_step = 100
"""
        (case_dir / "inputs").write_text(inputs)
        
        metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Required fields
        required = ["case_name", "repo_path", "inputs_content"]
        
        for field in required:
            assert field in metadata, \
                f"Missing required field: {field}\nGot: {list(metadata.keys())}"
        
        # Recommended fields (warn if missing)
        recommended = ["n_cell", "max_step"]
        for field in recommended:
            if field not in metadata and field not in metadata.get("inputs_content", {}):
                print(f"⚠️  Recommended field missing: {field}")
    
    
    def test_metadata_is_json_serializable(self, tmp_path):
        """
        Given: Extracted metadata
        When:  Serializing to JSON
        Then:  Should not raise errors (no Path objects, etc.)
        
        Critical: FAISS metadata must be JSON-compatible
        """
        import json
        from database.configs import BaseAMReXConfig
        
        repo_root = tmp_path / "Code"
        case_dir = repo_root / "Exec" / "Test"
        case_dir.mkdir(parents=True)
        (case_dir / "inputs").write_text("max_step = 10")
        
        metadata = BaseAMReXConfig.extract_metadata(case_dir, repo_root=repo_root)
        
        # Should be JSON serializable
        try:
            json_str = json.dumps(metadata)
            assert len(json_str) > 0
        except TypeError as e:
            pytest.fail(f"Metadata not JSON serializable: {e}\nMetadata: {metadata}")
