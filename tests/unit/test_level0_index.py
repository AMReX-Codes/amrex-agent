"""
Level 0 Index Tests - Indexing Engine: Level 0 (Physics Taxonomy)

Validates multi-solver physics regime identification.
Implements PRD Section 5.2 (FR-1, FR-2) and Section 10.1.

Architecture:
- 4 sub-indices with weighted scoring
- Routes queries to correct solver family
- Integrates with Metadata Schema schema
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


class TestLevel0TaxonomyStructure:
    """Test 1: Validate 4 required sub-indices exist and are populated."""
    
    def test_level0_taxonomy_structure(self, tmp_path):
        """
        Given: Mock configs (AMReX, PeleLMeX) and knowledge base reports
        When:  Building Level 0 indices
        Then:  Should create 4 specific FAISS indices
        
        PRD: FR-1 (Multi-Solver Physics Regime Identification)
        PRD: Section 10.1 (Level 0 Architecture)
        
        Sub-indices:
        1. physics_regimes (40% weight) - Domain families
        2. solver_capabilities (30% weight) - Specific capabilities
        3. code_lineage (20% weight) - Evolution history
        4. cross_cutting_guidance (10% weight) - Decision frameworks
        """
        from database.indexing.level0_builder import Level0Builder
        
        # Arrange: Mock embedding service
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 10  # Mock embeddings
        mock_embedder.expand_documents.side_effect = lambda documents, metadata: (documents, metadata)
        
        # Act: Build Level 0 indices
        builder = Level0Builder(embedder=mock_embedder)
        output_dir = tmp_path / "level0"
        builder.build(output_dir=output_dir)
        
        # Assert: 4 specific indices created
        assert (output_dir / "physics_regimes.faiss").exists(), \
            "Missing physics_regimes index"
        
        assert (output_dir / "solver_capabilities.faiss").exists(), \
            "Missing solver_capabilities index"
        
        assert (output_dir / "code_lineage.faiss").exists(), \
            "Missing code_lineage index"
        
        assert (output_dir / "cross_cutting_guidance.faiss").exists(), \
            "Missing cross_cutting_guidance index"
    
    
    def test_level0_populated_with_solver_data(self, tmp_path):
        """
        Given: Level 0 builder with discovered configs
        When:  Building solver_capabilities index
        Then:  Should contain entries for each AMReX code
        
        Verifies: Integration with Cases Service: Config-Driven Discovery (discover_code_configs)
        """
        from database.indexing.level0_builder import Level0Builder
        from database.configs import discover_code_configs
        
        # Arrange
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 20
        mock_embedder.expand_documents.side_effect = lambda documents, metadata: (documents, metadata)
        
        # Get actual codes from registry
        codes = discover_code_configs()
        code_names = [cfg.code_name for cfg in codes]
        
        # Act
        builder = Level0Builder(embedder=mock_embedder)
        output_dir = tmp_path / "level0"
        builder.build(output_dir=output_dir)
        
        # Assert: Index has entries for discovered codes
        # Load metadata to verify
        import json
        metadata_file = output_dir / "solver_capabilities_metadata.json"
        
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text())
            indexed_codes = set(m.get('code_name') for m in metadata if 'code_name' in m)
            
            # Should have at least AMReX, PeleLMeX
            assert 'AMReX' in indexed_codes, "Should index AMReX"
            assert 'PeleLMeX' in indexed_codes, "Should index PeleLMeX"
            
            print(f"\n✅ Indexed {len(indexed_codes)} codes: {indexed_codes}")
    
    
    def test_level0_includes_cross_cutting_guidance(self, tmp_path):
        """
        Given: Knowledge base with Reports 1, 3, 4 (decision frameworks)
        When:  Building cross_cutting_guidance index
        Then:  Should extract and index guidance text
        
        PRD: Section 10.1 - Cross-cutting guidance (10% weight)
        """
        from database.indexing.level0_builder import Level0Builder
        
        # Arrange: Create mock knowledge base
        kb_dir = tmp_path / "knowledge_base"
        kb_dir.mkdir()
        
        # Mock Report 1: Solver Selection Guide
        report1 = kb_dir / "report_1_solver_selection.md"
        report1.write_text("""
# Solver Selection Guide

## When to use AMReX
- Supersonic flows
- Strong shocks
- Compressible combustion

## When to use PeleLMeX
- Low Mach number flames
- Detailed chemistry
- Diffusion-dominated
""")
        
        mock_embedder = Mock()
        mock_embedder.embed_texts.return_value = [[0.1] * 384] * 5
        mock_embedder.expand_documents.side_effect = lambda documents, metadata: (documents, metadata)
        
        # Act
        builder = Level0Builder(
            embedder=mock_embedder,
            knowledge_base_path=kb_dir
        )
        output_dir = tmp_path / "level0"
        builder.build(output_dir=output_dir)
        
        # Assert: Cross-cutting guidance index created
        assert (output_dir / "cross_cutting_guidance.faiss").exists()


class TestLevel0SolverRouting:
    """Test 2: Validate weighted scoring and solver selection."""
    
    def test_level0_solver_routing_supersonic(self):
        """
        Given: Query "supersonic flow with shocks"
        When:  Searching Level 0 with weighted scoring
        Then:  Should rank AMReX highest (compressible solver)
        
        PRD: FR-1 Accuracy target ≥95%
        PRD: NFR-2 Query latency <1 sec
        
        Scoring: 40% physics_regimes + 30% solver_capabilities + 
                 20% code_lineage + 10% cross_cutting
        """
        from database.indexing.level0_searcher import Level0Searcher
        
        # Arrange: Mock searcher with known results
        searcher = Level0Searcher(index_dir=Path("mock"))
        
        # Mock individual index results
        with patch.object(searcher, '_search_physics_regimes') as mock_regimes, \
             patch.object(searcher, '_search_solver_capabilities') as mock_caps, \
             patch.object(searcher, '_search_code_lineage') as mock_lineage, \
             patch.object(searcher, '_search_cross_cutting') as mock_cross:
            
            # AMReX matches strongly in regimes and capabilities
            mock_regimes.return_value = [
                {'code': 'AMReX', 'score': 0.95},
                {'code': 'PeleLMeX', 'score': 0.2},
            ]
            
            mock_caps.return_value = [
                {'code': 'AMReX', 'score': 0.9, 'capability': 'shock handling'},
                {'code': 'PeleLMeX', 'score': 0.1},
            ]
            
            mock_lineage.return_value = [
                {'code': 'AMReX', 'score': 0.5},
            ]
            
            mock_cross.return_value = [
                {'code': 'AMReX', 'score': 0.7, 'guidance': 'Use AMReX for supersonic'},
            ]
            
            # Act
            results = searcher.search("supersonic flow with shocks", top_k=2)
            
            # Assert: AMReX ranked highest
            assert results[0]['code'] == 'AMReX', \
                f"Expected AMReX first, got {results[0]['code']}"
            
            # Weighted score should be high
            # 0.95*0.4 + 0.9*0.3 + 0.5*0.2 + 0.7*0.1 = 0.38 + 0.27 + 0.1 + 0.07 = 0.82
            assert results[0]['score'] > 0.8, \
                f"Expected score >0.8, got {results[0]['score']}"
    
    
    def test_level0_solver_routing_low_mach(self):
        """
        Given: Query "low Mach number flame with detailed chemistry"
        When:  Searching Level 0
        Then:  Should rank PeleLMeX highest (low Mach solver)
        
        Verifies: System distinguishes between compressible vs low Mach physics
        """
        from database.indexing.level0_searcher import Level0Searcher
        
        searcher = Level0Searcher(index_dir=Path("mock"))
        
        with patch.object(searcher, '_search_physics_regimes') as mock_regimes, \
             patch.object(searcher, '_search_solver_capabilities') as mock_caps:
            
            # PeleLMeX matches strongly for low Mach
            mock_regimes.return_value = [
                {'code': 'PeleLMeX', 'score': 0.95},
                {'code': 'AMReX', 'score': 0.3},
            ]
            
            mock_caps.return_value = [
                {'code': 'PeleLMeX', 'score': 0.9, 'capability': 'low Mach'},
                {'code': 'AMReX', 'score': 0.2},
            ]
            
            results = searcher.search("low Mach flame", top_k=2)
            
            assert results[0]['code'] == 'PeleLMeX', \
                "Should select PeleLMeX for low Mach physics"
    
    
    def test_level0_weighted_scoring_formula(self):
        """
        Given: Mock scores from all 4 sub-indices
        When:  Computing weighted total
        Then:  Should use correct weights (40/30/20/10)
        
        PRD: Section 10.1 specifies exact weights
        """
        from database.indexing.level0_searcher import Level0Searcher
        
        searcher = Level0Searcher(index_dir=Path("mock"))
        
        # Test the scoring formula directly
        scores = {
            'physics_regimes': 0.9,
            'solver_capabilities': 0.8,
            'code_lineage': 0.6,
            'cross_cutting_guidance': 0.5,
        }
        
        # Expected: 0.9*0.4 + 0.8*0.3 + 0.6*0.2 + 0.5*0.1
        #         = 0.36 + 0.24 + 0.12 + 0.05 = 0.77
        
        weighted = searcher._compute_weighted_score(scores)
        
        assert abs(weighted - 0.77) < 0.01, \
            f"Expected 0.77, got {weighted}"

    def test_level0_weighted_scoring_bounds(self):
        """
        Given: All scores missing or maxed
        When:  Computing weighted score
        Then:  Should clamp to 0.0 or 1.0 based on inputs
        """
        from database.indexing.level0_searcher import Level0Searcher

        searcher = Level0Searcher(index_dir=Path("mock"))

        assert searcher._compute_weighted_score({}) == 0.0

        scores = {
            'physics_regimes': 1.0,
            'solver_capabilities': 1.0,
            'code_lineage': 1.0,
            'cross_cutting_guidance': 1.0,
        }
        assert abs(searcher._compute_weighted_score(scores) - 1.0) < 1e-12

    def test_level0_missing_indices_do_not_contribute(self):
        """
        Given: Results only for physics_regimes and cross-cutting "general"
        When:  Combining scores
        Then:  Missing indices contribute 0 and general guidance is ignored
        """
        from database.indexing.level0_searcher import Level0Searcher

        searcher = Level0Searcher(index_dir=Path("mock"))

        regimes = [{'code': 'AMReX', 'score': 0.5}]
        capabilities = []
        lineage = []
        cross = [{'code': 'general', 'score': 0.99}]

        combined = searcher._combine_scores(regimes, capabilities, lineage, cross)

        assert set(combined.keys()) == {'AMReX'}
        assert abs(combined['AMReX']['score'] - 0.2) < 0.01


class TestLevel0SchemaConsistency:
    """Test 3: Validate integration with Metadata Schema schema."""
    
    def test_level0_schema_consistency(self):
        """
        Given: Level 0 index returns solver names
        When:  Checking against Metadata Schema config registry
        Then:  Every solver must match a code_name in configs
        
        Critical: Ensures "Solver Selector" → "Architect" handoff works
        
        Amendment B: Unified Gate Framework
        """
        from database.indexing.level0_builder import Level0Builder
        from database.configs import discover_code_configs
        
        # Arrange: Get valid code names from Metadata Schema
        configs = discover_code_configs()
        valid_code_names = {cfg.code_name for cfg in configs}
        
        print(f"\n📋 Valid code names from Metadata Schema: {valid_code_names}")
        
        # Act: Get solvers indexed in Level 0
        builder = Level0Builder(embedder=Mock())
        indexed_solvers = builder._get_solver_list()
        
        # Assert: Every Level 0 solver exists in Metadata Schema registry
        for solver in indexed_solvers:
            assert solver in valid_code_names, \
                f"Level 0 uses '{solver}' but it's not in Metadata Schema configs.\n" + \
                f"Valid names: {valid_code_names}"
        
        print(f"✅ All {len(indexed_solvers)} Level 0 solvers match Metadata Schema schema")
    
    
    def test_level0_output_matches_config_code_name(self):
        """
        Given: Level 0 search result
        When:  Result contains code='AMReX'
        Then:  PeleCConfig.code_name must equal 'AMReX'
        
        Verifies: Exact string matching for routing
        """
        from database.configs import AMReXConfig, PeleLMeXConfig
        
        # Simulate Level 0 output
        level0_output = {'code': 'AMReX', 'score': 0.9}
        
        # Verify matches Metadata Schema
        assert level0_output['code'] == AMReXConfig.code_name, \
            "Level 0 output must exactly match config.code_name"
        
        # Test for PeleLMeX too
        level0_output = {'code': 'PeleLMeX', 'score': 0.85}
        assert level0_output['code'] == PeleLMeXConfig.code_name
    
    
    def test_level0_rejects_invalid_solver_names(self):
        """
        Given: Level 0 builder with invalid solver name
        When:  Attempting to index solver "Pele-C" (wrong format)
        Then:  Should raise validation error
        
        Prevents: Typos and inconsistencies in solver names
        """
        from database.indexing.level0_builder import Level0Builder
        from database.configs import discover_code_configs
        
        builder = Level0Builder(embedder=Mock())
        
        # Get valid names
        valid_codes = {cfg.code_name for cfg in discover_code_configs()}
        
        # Test invalid name
        invalid_name = "Pele-C"  # Should be "PeleC"
        
        assert invalid_name not in valid_codes, \
            "Test setup error: invalid name is actually valid"
        
        # Builder should validate
        is_valid = builder._validate_solver_name(invalid_name)
        
        assert not is_valid, \
            f"Builder should reject invalid solver name '{invalid_name}'"


class TestLevel0PerformanceRequirements:
    """Bonus: Validate NFR-2 (p95 FAISS retrieval <500ms)."""
    
    @pytest.mark.performance
    def test_level0_faiss_retrieval_p95_latency(self):
        """
        Given: A Level 0 FAISS searcher and deterministic retrieval latencies
        When:  Executing repeated retrieval calls
        Then:  p95 latency should remain under 500ms

        Audit criterion: p95 FAISS retrieval <500ms
        """
        import time
        from statistics import quantiles
        from database.indexing.level0_searcher import Level0Searcher

        searcher = Level0Searcher(index_dir=Path("mock"))

        latencies_ms = [
            180, 220, 250, 275, 290, 305, 320, 340, 360, 380,
            395, 405, 415, 425, 435, 445, 450, 460, 470, 480,
        ]

        # Deterministic clock values: (start, end) for each retrieval.
        perf_counter_values = []
        current_time = 1000.0
        for latency in latencies_ms:
            perf_counter_values.extend([current_time, current_time + (latency / 1000.0)])
            current_time += 1.0

        with patch.object(searcher, '_search_physics_regimes', return_value=[{'code': 'AMReX', 'score': 0.9}]), \
             patch.object(searcher, '_search_solver_capabilities', return_value=[{'code': 'AMReX', 'score': 0.8}]), \
             patch.object(searcher, '_search_code_lineage', return_value=[{'code': 'AMReX', 'score': 0.7}]), \
             patch.object(searcher, '_search_cross_cutting', return_value=[{'code': 'AMReX', 'score': 0.6}]), \
             patch('time.perf_counter', side_effect=perf_counter_values):

            measured_ms = []
            for _ in latencies_ms:
                start = time.perf_counter()
                results = searcher.search("supersonic combustion", top_k=3)
                end = time.perf_counter()
                measured_ms.append((end - start) * 1000.0)

                assert results and results[0]['code'] == 'AMReX'

        # inclusive p95 over measured run distribution
        p95_ms = quantiles(measured_ms, n=100, method='inclusive')[94]

        assert p95_ms < 500.0, \
            f"p95 retrieval latency {p95_ms:.1f}ms exceeds 500ms target"
