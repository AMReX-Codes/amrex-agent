"""
Level 1 Index Tests - Indexing Engine: Level 1 (Documentation)

Validates unified documentation search via extensible config maps.
Implements PRD Section 5.3 (FR-3) with yt-project pattern extensibility.

Architecture:
- Configs define documentation_map (data-driven)
- Builder is generic (processes any map structure)
- Supports database/reports and code repo sources
- No hardcoded index names
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from database.configs import BaseAMReXConfig
from database.indexing.level1_builder import Level1Builder


class DummyEmbedder:
    def __init__(self, dimension=4):
        self.dimension = dimension
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[0.1] * self.dimension for _ in texts]


def _write_doc(tmp_path: Path, relative_path: str, content: str) -> Path:
    doc_path = tmp_path / relative_path
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(content)
    return doc_path


class TestLevel1SubindicesStructure:
    """Test 1: Verify config-driven index creation."""
    
    def test_level1_subindices_structure(self, tmp_path):
        """
        Given: Custom config with documentation_map
        When:  Building Level 1 indices
        Then:  Should create indices matching config keys exactly
        
        PRD: FR-3 (Unified Documentation Search)
        Extensibility: Config defines structure, not builder code
        """
        # Arrange: Create custom config with specific map
        class MockConfig(BaseAMReXConfig):
            code_name = "MockCode"
            documentation_map = {
                'custom_guide': ['custom.txt'],
                'api_reference': ['api_docs.md'],
            }
        
        # Create source files
        _write_doc(tmp_path / "docs", "custom.txt", "Custom guide content for testing")
        _write_doc(tmp_path / "docs", "api_docs.md", "# API Reference\nFunction details")
        
        embedder = DummyEmbedder()
        
        # Act: Build Level 1 indices
        builder = Level1Builder(config=MockConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=tmp_path / "docs", output_dir=output_dir)
        
        # Assert: Indices created matching config keys
        assert (output_dir / "mockcode_doc_custom_guide.faiss").exists(), \
            "Should create index matching config key 'custom_guide'"
        
        assert (output_dir / "mockcode_doc_api_reference.faiss").exists(), \
            "Should create index matching config key 'api_reference'"
        
        # Should NOT create indices for keys not in config
        assert not (output_dir / "mockcode_doc_problem_catalogs.faiss").exists(), \
            "Should not create indices not specified in config"
    
    
    def test_level1_content_indexed(self, tmp_path):
        """
        Given: Documentation files specified in config
        When:  Building indices
        Then:  Should actually read and embed file content
        
        Verifies: Files are not just discovered but actually indexed
        """
        class TestConfig(BaseAMReXConfig):
            code_name = "TestCode"
            documentation_map = {
                'user_guide': ['guide.md'],
            }
        
        # Create source file with known content
        _write_doc(tmp_path / "docs", "guide.md", "# User Guide\nThis is test content")
        
        embedder = DummyEmbedder()
        
        builder = Level1Builder(config=TestConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=tmp_path / "docs", output_dir=output_dir)
        
        # Assert: embedder was called with actual content
        assert embedder.calls, "Should call embedder"
        
        # Check metadata contains source info
        metadata_file = output_dir / "testcode_doc_user_guide_metadata.json"
        assert metadata_file.exists(), "Should save metadata"
        
        metadata = json.loads(metadata_file.read_text())
        assert len(metadata) > 0, "Should have metadata entries"
        assert any('guide.md' in str(m.get('source', '')) for m in metadata), \
            "Metadata should reference source file"


class TestLevel1CatalogIndexing:
    """Test 2: Validate problem catalog parsing and indexing."""
    
    def test_level1_catalog_indexing(self, tmp_path):
        """
        Given: Problem catalog file with markdown structure
        When:  Indexing catalogs
        Then:  Should parse sections and enable category search
        
        PRD: Section 5.3 (Problem Catalogs)
        Format: Markdown with headers defining categories
        """
        class CatalogConfig(BaseAMReXConfig):
            code_name = "PeleC"
            documentation_map = {
                'problem_catalogs': ['catalogs.md'],
            }
        
        # Create catalog file with structure
        catalog_content = """
# Problem Catalog

## Detonation Cases
- PMF: Premixed flame detonation
- Sod: Shock tube with chemical reactions

## Diffusion Cases
- TaylorGreen: Vorticity decay
- BubbleRise: Buoyancy-driven flow
"""
        _write_doc(tmp_path / "docs", "catalogs.md", catalog_content)
        
        embedder = DummyEmbedder()
        
        builder = Level1Builder(config=CatalogConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=tmp_path / "docs", output_dir=output_dir)
        
        # Assert: Catalog index created
        assert (output_dir / "pelec_doc_problem_catalogs.faiss").exists()
        
        # Check metadata structure
        metadata_file = output_dir / "pelec_doc_problem_catalogs_metadata.json"
        metadata = json.loads(metadata_file.read_text())
        
        # Should have parsed sections
        categories = [m.get('category') for m in metadata if 'category' in m]
        assert 'Detonation Cases' in str(metadata) or len(categories) > 0, \
            "Should parse catalog categories"
    
    
    def test_level1_catalog_source_flexibility(self, tmp_path):
        """
        Given: Config points to non-standard catalog location
        When:  Building indices
        Then:  Should handle any file path in config
        
        Verifies: No hardcoded assumptions about file names/locations
        """
        class FlexConfig(BaseAMReXConfig):
            code_name = "FlexCode"
            documentation_map = {
                'problem_catalogs': ['nonstandard/my_catalog.txt'],
            }
        
        _write_doc(tmp_path / "docs", "nonstandard/my_catalog.txt", "Custom catalog structure")
        
        embedder = DummyEmbedder()
        
        builder = Level1Builder(config=FlexConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=tmp_path / "docs", output_dir=output_dir)
        
        # Should succeed (no hardcoded path checks)
        assert (output_dir / "flexcode_doc_problem_catalogs.faiss").exists()


class TestLevel1DocMapEdgeCases:
    """Test 2b: Validate edge cases in documentation map handling."""

    def test_level1_missing_files_skip_index(self, tmp_path):
        """
        Given: Config points to missing documentation file
        When:  Building Level 1 indices
        Then:  Should not create an index for missing sources
        """
        class MissingConfig(BaseAMReXConfig):
            code_name = "MissingDocs"
            documentation_map = {
                'missing_docs': ['nope.md'],
            }

        embedder = DummyEmbedder()
        builder = Level1Builder(config=MissingConfig, embedder=embedder)

        output_dir = tmp_path / "level1"
        builder.build(source_dir=tmp_path / "docs", output_dir=output_dir)

        assert not (output_dir / "missingdocs_doc_missing_docs.faiss").exists(), \
            "Should skip index creation when sources are missing"

    def test_level1_glob_matches_multiple_files(self, tmp_path):
        """
        Given: Glob pattern for documentation files
        When:  Building Level 1 indices
        Then:  Should index all matching files
        """
        class GlobConfig(BaseAMReXConfig):
            code_name = "GlobDocs"
            documentation_map = {
                'guides': ['*.md'],
            }

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide_a.md").write_text("Guide A content")
        (docs_dir / "guide_b.md").write_text("Guide B content")

        embedder = DummyEmbedder()
        builder = Level1Builder(config=GlobConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=docs_dir, output_dir=output_dir)

        metadata_file = output_dir / "globdocs_doc_guides_metadata.json"
        assert metadata_file.exists(), "Should write metadata for glob matches"

        metadata = json.loads(metadata_file.read_text())
        sources = {item.get('source') for item in metadata}
        assert {'guide_a.md', 'guide_b.md'} <= sources

    def test_level1_agent_relative_path(self, tmp_path):
        """
        Given: Documentation path relative to agent repo root
        When:  Building Level 1 indices
        Then:  Should resolve and index the agent-relative file
        """
        class AgentPathConfig(BaseAMReXConfig):
            code_name = "AgentPath"
            documentation_map = {
                'agent_doc': ['database/configs/amrex_config.py'],
            }

        embedder = DummyEmbedder()
        builder = Level1Builder(config=AgentPathConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=tmp_path / "docs", output_dir=output_dir)

        assert (output_dir / "agentpath_doc_agent_doc.faiss").exists(), \
            "Should create index from agent-relative source"

class TestLevel1RetrievalSpeed:
    """Test 3: Validate query performance (NFR-2)."""
    
    @pytest.mark.performance
    def test_level1_retrieval_speed(self):
        """
        Given: Level 1 indices for a solver
        When:  Executing simultaneous search across all doc indices
        Then:  Should complete in <2 seconds
        
        PRD: NFR-2 (Query Response Time)
        Note: Querying ~7 sub-indices simultaneously
        """
        import time
        from database.indexing.level1_searcher import Level1Searcher
        
        # Skip if indices don't exist
        index_dir = Path("database/indices/level1/pelec")
        if not index_dir.exists():
            pytest.skip("Level 1 indices not built")
        
        searcher = Level1Searcher(code="PeleC", index_dir=index_dir)
        
        # Act: Time the search across all indices
        start = time.time()
        results = searcher.search_all_docs("parameter configuration guide", top_k=3)
        elapsed = time.time() - start
        
        # Assert: <2 seconds for multi-index search
        assert elapsed < 2.0, \
            f"Multi-index search took {elapsed:.2f}s (requirement: <2s)"
        
        print(f"\n⚡ Level 1 search latency: {elapsed*1000:.1f}ms")
    
    
    def test_level1_searcher_combines_results(self, tmp_path):
        """
        Given: Multiple doc indices for a solver
        When:  Searching
        Then:  Should return combined ranked results
        
        Verifies: Searcher aggregates across sub-indices
        """
        from database.indexing.level1_searcher import Level1Searcher
        
        # Create dummy index files for discovery
        (tmp_path / "mockcode_doc_guide.faiss").write_text("dummy")
        (tmp_path / "mockcode_doc_api.faiss").write_text("dummy")
        
        # Initialize searcher
        searcher = Level1Searcher(code="MockCode", index_dir=tmp_path)
        
        # Verify indices discovered
        assert len(searcher.available_indices) == 2, "Should discover 2 indices"
        
        # Mock individual index searches
        with patch.object(searcher, '_search_single_index') as mock_search:
            mock_search.side_effect = [
                [{'text': 'Doc 1', 'score': 0.9, 'source': 'guide'}],
                [{'text': 'Doc 2', 'score': 0.8, 'source': 'api'}],
            ]
            
            results = searcher.search_all_docs("query", top_k=5)
            
            # Should combine and rank
            assert len(results) >= 1, "Should return combined results"
            # Higher scores first
            if len(results) > 1:
                assert results[0]['score'] >= results[1]['score'], \
                    "Should rank by score"
class TestLevel1Extensibility:
    """Test 4: Verify extensibility (new solver without code changes)."""
    
    def test_level1_extensibility(self, tmp_path):
        """
        Given: New solver config with non-standard doc map
        When:  Building indices
        Then:  Should create only specified indices (not assume 7 standard)
        
        Extensibility Proof: Adding solver requires only config change
        """
        # Simulate adding a completely new solver
        class HypotheticalSolver(BaseAMReXConfig):
            code_name = "HypotheticalSolver"
            github_org = "NewOrg"
            github_repo = "HypotheticalSolver"
            
            # Only 2 doc types (not 7!)
            documentation_map = {
                'readme': ['README.md'],
                'api_docs': ['docs/api.rst'],
            }
        
        # Create source files
        docs_dir = tmp_path / "hypo_docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# HypotheticalSolver\nOverview")
        api_dir = docs_dir / "docs"
        api_dir.mkdir()
        (api_dir / "api.rst").write_text("API Documentation")
        
        embedder = DummyEmbedder()
        
        # Act: Build with generic builder
        builder = Level1Builder(config=HypotheticalSolver, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=docs_dir, output_dir=output_dir)
        
        # Assert: Only specified indices created
        assert (output_dir / "hypotheticalsolver_doc_readme.faiss").exists(), \
            "Should create readme index"
        
        assert (output_dir / "hypotheticalsolver_doc_api_docs.faiss").exists(), \
            "Should create api_docs index"
        
        # Should NOT create standard indices not in config
        assert not (output_dir / "hypotheticalsolver_doc_problem_catalogs.faiss").exists(), \
            "Should not assume standard indices"
        
        assert not (output_dir / "hypotheticalsolver_doc_parameter_guides.faiss").exists(), \
            "Should only create what config specifies"
        
        print("\n✅ New solver added with ZERO builder code changes")
    
    
    def test_level1_config_override(self, tmp_path):
        """
        Given: Subclass config overrides documentation_map
        When:  Building
        Then:  Should use subclass map (polymorphism)
        
        Verifies: yt-project pattern works for Level 1
        """
        class ParentConfig(BaseAMReXConfig):
            code_name = "Parent"
            documentation_map = {
                'default_guide': ['guide.txt'],
            }
        
        class ChildConfig(ParentConfig):
            code_name = "Child"
            # Override
            documentation_map = {
                'custom_guide': ['custom.txt'],
                'extra_docs': ['extra.md'],
            }
        
        # Create files
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "custom.txt").write_text("Child-specific")
        (docs_dir / "extra.md").write_text("Extra docs")
        
        embedder = DummyEmbedder()
        
        builder = Level1Builder(config=ChildConfig, embedder=embedder)
        output_dir = tmp_path / "level1"
        builder.build(source_dir=docs_dir, output_dir=output_dir)
        
        # Should use child config map (not parent)
        assert (output_dir / "child_doc_custom_guide.faiss").exists(), \
            "Should use overridden map"
        
        assert (output_dir / "child_doc_extra_docs.faiss").exists(), \
            "Should process child-specific indices"
        
        assert not (output_dir / "child_doc_default_guide.faiss").exists(), \
            "Should NOT inherit parent map (override, not extend)"


class TestLevel1Integration:
    """Bonus: Integration with Metadata Schema schema."""
    
    def test_level1_integrates_with_config_schema(self, tmp_path):
        """
        Given: Real config from Metadata Schema
        When:  Building Level 1
        Then:  Should use config.code_name for index naming
        
        Verifies: Clean integration with Metadata Schema
        """
        from database.configs import PeleCConfig
        
        # Use real config
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        
        # Create minimal doc file
        (docs_dir / "readme.md").write_text("# PeleC")
        
        # Temporarily override map for test
        original_map = PeleCConfig.documentation_map
        PeleCConfig.documentation_map = {'readme': ['readme.md']}
        
        try:
            embedder = DummyEmbedder()
            
            builder = Level1Builder(config=PeleCConfig, embedder=embedder)
            output_dir = tmp_path / "level1"
            builder.build(source_dir=docs_dir, output_dir=output_dir)
            
            # Index name should use config.code_name
            expected_name = f"{PeleCConfig.code_name.lower()}_doc_readme.faiss"
            assert (output_dir / expected_name).exists(), \
                f"Should use config.code_name ({PeleCConfig.code_name})"
        finally:
            # Restore
            PeleCConfig.documentation_map = original_map
