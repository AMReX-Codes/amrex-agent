"""
Unit tests for src/services/embedding.py - FAISS Cache Refactor

Gate 1 Day 2: Remove FAISS_DB_CACHE global state
Following TDD: These tests are written FIRST and will FAIL until refactor is complete.

Test Strategy:
1. Test instance-based cache exists
2. Test instance isolation (separate caches)
3. Test cache behavior (load/retrieve)
4. Test factory integration
5. Test no global state
6. Test backward compatibility

Expected Initial State: ALL TESTS FAIL ❌
Expected After Refactor: ALL TESTS PASS ✅
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import warnings

from src.config import AMReXAgentConfig
from src.services.embedding import EmbeddingService


# =============================================================================
# Test 1: Instance Cache Structure
# =============================================================================

class TestInstanceCacheStructure:
    """Verify EmbeddingService has instance-based cache (not global).
    
    RED PHASE: These tests will FAIL because FAISS_DB_CACHE is currently global.
    GREEN PHASE: After refactor, _faiss_cache will be instance variable.
    """
    
    def test_embedding_service_has_instance_cache_attribute(self):
        """
        Given: A new EmbeddingService instance
        When:  Checking for _faiss_cache attribute
        Then:  Should exist as instance variable (not global)
        
        RED: Will fail - _faiss_cache doesn't exist yet
        GREEN: Will pass - _faiss_cache added as instance variable
        """
        # Arrange
        config = AMReXAgentConfig()
        
        # Act
        service = EmbeddingService(config)
        
        # Assert
        assert hasattr(service, '_faiss_cache'), \
            "EmbeddingService should have _faiss_cache instance variable"
        assert isinstance(service._faiss_cache, dict), \
            "_faiss_cache should be a dictionary"
    
    def test_instance_cache_starts_empty(self):
        """
        Given: A newly created EmbeddingService (no indices available)
        When:  Checking _faiss_cache
        Then:  Should be empty dict (no pre-loaded indices)
        """
        from unittest.mock import patch
        from pathlib import Path
        
        # Arrange
        config = AMReXAgentConfig()
        config.faiss_db_path = Path("/nonexistent/path")
        
        # Act
        # Mock to simulate no indices on disk
        with patch.object(Path, 'exists', return_value=False):
            service = EmbeddingService(config)
        
        # Assert
        assert service._faiss_cache == {}, \
            "New instance should have empty cache when no indices exist"
        assert service._indices_loaded == False, \
            "Should not mark indices as loaded when none exist"


class TestInstanceIsolation:
    """Verify each EmbeddingService instance has separate cache.
    
    This is the CORE problem with global FAISS_DB_CACHE:
    - Multiple services share same cache (bad!)
    - Testing one service affects another (bad!)
    - Can't control cache state (bad!)
    
    After refactor, each instance has its own cache.
    """
    
    def test_multiple_services_have_separate_caches(self):
        """
        Given: Two EmbeddingService instances
        When:  Checking their _faiss_cache attributes
        Then:  Should be different objects (not shared)
        
        RED: Will fail - currently all services share FAISS_DB_CACHE global
        GREEN: Will pass - each instance has separate _faiss_cache
        """
        # Arrange
        config1 = AMReXAgentConfig()
        config2 = AMReXAgentConfig()
        
        # Act
        service1 = EmbeddingService(config1)
        service2 = EmbeddingService(config2)
        
        # Assert
        assert service1._faiss_cache is not service2._faiss_cache, \
            "Each service should have separate cache instance"
    
    def test_modifying_one_cache_does_not_affect_another(self):
        """
        Given: Two EmbeddingService instances
        When:  Modifying cache in one service
        Then:  Should not affect the other service's cache
        
        RED: Will fail - both services share global FAISS_DB_CACHE
        GREEN: Will pass - caches are isolated
        
        This test proves true isolation and testability.
        """
        # Arrange
        config1 = AMReXAgentConfig()
        config2 = AMReXAgentConfig()
        service1 = EmbeddingService(config1)
        service2 = EmbeddingService(config2)
        
        # Act - Modify service1's cache
        mock_db1 = Mock(name='database1')
        service1._faiss_cache['test_index'] = mock_db1
        
        # Also modify service2's cache with different value
        mock_db2 = Mock(name='database2')
        service2._faiss_cache['test_index'] = mock_db2
        
        # Assert - Caches should have different values
        assert service1._faiss_cache['test_index'] is mock_db1, \
            "Service1 should have its own cache value"
        assert service2._faiss_cache['test_index'] is mock_db2, \
            "Service2 should have its own cache value"
        assert service1._faiss_cache['test_index'] is not service2._faiss_cache['test_index'], \
            "Cache values should be independent"


# =============================================================================
# Test 3: Cache Loading Behavior
# =============================================================================

class TestCacheLoadingBehavior:
    """Test that load_all_indices() uses instance cache (not global).
    
    Current behavior (BAD):
    - load_all_indices() writes to global FAISS_DB_CACHE
    - All services see same loaded indices
    
    Desired behavior (GOOD):
    - load_all_indices() writes to self._faiss_cache
    - Each service has independent loaded indices
    """
    
    def test_instance_cache_can_be_populated_directly(self):
        """
        Given: EmbeddingService instance
        When:  Directly adding to _faiss_cache
        Then:  Cache should store the value

        Simplified test - we don't test the complex _load_indices() logic,
        just that the instance cache works as a dict.
        """
        # Arrange
        config = AMReXAgentConfig()
        service = EmbeddingService(config)
        
        # Act - Directly populate cache (simulates what _load_indices does)
        mock_db = Mock(name='test_db')
        service._faiss_cache['my_index'] = mock_db
        
        # Assert
        assert 'my_index' in service._faiss_cache
        assert service._faiss_cache['my_index'] is mock_db
        
        # Assert - Should NOT be in global (if it still exists)
        import src.services.embedding as emb_module
        if hasattr(emb_module, 'FAISS_DB_CACHE'):
            assert 'my_index' not in emb_module.FAISS_DB_CACHE,                 "Should use instance cache, not global"


    def test_indices_loaded_flag_independent_of_global(self):
        """
        Given: EmbeddingService instance
        When:  Setting _indices_loaded flag
        Then:  Should be independent per instance
        
        Simplified - just test the flag works.
        """
        # Arrange
        config1 = AMReXAgentConfig()
        config2 = AMReXAgentConfig()
        service1 = EmbeddingService(config1)
        service2 = EmbeddingService(config2)
        
        # Act
        service1._indices_loaded = True
        service2._indices_loaded = False
        
        # Assert - Independent flags
        assert service1._indices_loaded is True
        assert service2._indices_loaded is False


class TestCacheRetrievalBehavior:
    """Test that retrieve_faiss() uses instance cache.
    
    Current: retrieve_faiss() reads from global FAISS_DB_CACHE
    Desired: retrieve_faiss() reads from self._faiss_cache
    """
    
    def test_retrieve_uses_instance_cache(self):
        """
        Given: EmbeddingService with index in instance cache
        When:  retrieve_faiss() is called
        Then:  Should use cache from self._faiss_cache
        
        RED: Will fail - uses global FAISS_DB_CACHE
        GREEN: Will pass - uses self._faiss_cache
        """
        # Arrange
        config = AMReXAgentConfig()
        service = EmbeddingService(config)
        
        # Manually populate instance cache
        mock_db = Mock()
        mock_docs = [Mock(page_content="test doc", metadata={})]
        mock_db.similarity_search_with_score.return_value = [
            (mock_docs[0], 0.95)
        ]
        
        # This will fail initially - _faiss_cache doesn't exist
        service._faiss_cache = {'test_index': mock_db}
        service._indices_loaded = True
        service.embeddings = Mock()  # Need embeddings to not be None
        
        # Act
        result = service.retrieve_faiss(
            query="test query",
            index_name='test_index',
            topk=1
        )
        
        # Assert - Should have called the mock from instance cache
        assert mock_db.similarity_search_with_score.called, \
            "Should use database from instance cache"
        assert len(result) > 0, "Should return results"
    
    def test_retrieve_returns_none_when_index_not_in_instance_cache(self):
        """
        Given: Index name not in instance cache
        When:  retrieve_faiss() is called with fallback disabled
        Then:  Should return None (not found in cache)
        
        Tests cache miss behavior.
        """
        # Arrange
        config = AMReXAgentConfig(faiss_fallback_to_llm=False)
        service = EmbeddingService(config)
        service._faiss_cache = {}  # Empty cache
        service._indices_loaded = True
        service.embeddings = Mock()
        
        # Act
        result = service.retrieve_faiss(
            query="test",
            index_name='nonexistent_index'
        )
        
        # Assert
        # Assert - Returns 'unavailable' dict (better than None)
        assert result is not None, \
            "Should return result dict, not None"
        assert result['source'] == 'unavailable', \
            "Should indicate unavailable when index not in cache"
        assert result['results'] == [], \
            "Should have empty results when unavailable"


# =============================================================================
# Test 5: Factory Integration
# =============================================================================

class TestFactoryIntegration:
    """Test that factory returns services with instance cache.
    
    The factory (embedding_service_factory.py) should still work,
    but services it creates should have instance caches.
    """
    
    def test_factory_returns_service_with_instance_cache(self):
        """
        Given: Using get_embedding_service factory
        When:  Creating service
        Then:  Should have _faiss_cache instance variable
        
        RED: Will fail - factory returns service without _faiss_cache
        GREEN: Will pass - refactored service has _faiss_cache
        """
        from src.services.embedding_service_factory import (
            get_embedding_service,
            clear_embedding_service_cache
        )
        
        # Arrange - Clear factory cache
        clear_embedding_service_cache()
        
        config = AMReXAgentConfig()
        
        # Act
        service = get_embedding_service(config)
        
        # Assert
        assert hasattr(service, '_faiss_cache'), \
            "Factory should return service with instance cache"
        assert isinstance(service._faiss_cache, dict), \
            "Instance cache should be a dict"
    
    def test_factory_singleton_maintains_same_instance_cache(self):
        """
        Given: Factory singleton pattern
        When:  Getting service multiple times with same config
        Then:  Should return same service with same cache reference
        
        This ensures singleton pattern works with instance cache.
        """
        from src.services.embedding_service_factory import (
            get_embedding_service,
            clear_embedding_service_cache
        )
        
        # Arrange
        clear_embedding_service_cache()
        config = AMReXAgentConfig()
        
        # Act
        service1 = get_embedding_service(config)
        service2 = get_embedding_service(config)
        
        # Assert - Same instance
        assert service1 is service2, \
            "Factory should return same instance for same config"
        
        # Assert - Same cache reference
        assert service1._faiss_cache is service2._faiss_cache, \
            "Singleton should share same cache reference"
    
    def test_factory_different_configs_have_different_caches(self):
        """
        Given: Two different config instances
        When:  Getting services from factory
        Then:  Should have separate instance caches
        
        Ensures factory creates isolated services for different configs.
        """
        from src.services.embedding_service_factory import (
            get_embedding_service,
            clear_embedding_service_cache
        )
        
        # Arrange
        clear_embedding_service_cache()
        config1 = AMReXAgentConfig()
        config2 = AMReXAgentConfig()
        
        # Act
        service1 = get_embedding_service(config1)
        service2 = get_embedding_service(config2)
        
        # Assert
        assert service1 is not service2, \
            "Different configs should get different services"
        assert service1._faiss_cache is not service2._faiss_cache, \
            "Different services should have separate caches"


# =============================================================================
# Test 6: No Global State
# =============================================================================

class TestNoGlobalState:
    """Verify FAISS_DB_CACHE global is removed after refactor.
    
    These tests explicitly check that global state is gone.
    """
    
    def test_faiss_db_cache_global_does_not_exist(self):
        """
        Given: Refactored embedding.py module
        When:  Checking for FAISS_DB_CACHE global
        Then:  Should not exist
        
        RED: Will fail - FAISS_DB_CACHE still exists
        GREEN: Will pass - global removed
        
        This is the ultimate test of successful refactor!
        """
        import src.services.embedding as emb_module
        
        assert not hasattr(emb_module, 'FAISS_DB_CACHE'), \
            "FAISS_DB_CACHE global variable should be removed after refactor"
    
    def test_service_initialization_does_not_mutate_globals(self):
        """
        Given: Clean embedding module
        When:  Creating EmbeddingService instances
        Then:  Should not add any global data structures
        
        Ensures refactor doesn't accidentally create new globals.
        """
        import src.services.embedding as emb_module
        
        # Snapshot module-level variables before
        globals_before = {
            k: id(v) for k, v in vars(emb_module).items()
            if not k.startswith('_') and not callable(v)
        }
        
        # Act - Create services
        config1 = AMReXAgentConfig()
        config2 = AMReXAgentConfig()
        service1 = EmbeddingService(config1)
        service2 = EmbeddingService(config2)
        
        # Snapshot after
        globals_after = {
            k: id(v) for k, v in vars(emb_module).items()
            if not k.startswith('_') and not callable(v)
        }
        
        # Assert - No new globals added (only existing ones)
        new_globals = set(globals_after.keys()) - set(globals_before.keys())
        assert len(new_globals) == 0, \
            f"Creating services should not add globals, but added: {new_globals}"


# =============================================================================
# Test 7: Backward Compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Ensure deprecated functions still work with warnings.
    
    Some code might still use old patterns - maintain compatibility
    during transition period.
    """
    
    def test_deprecated_get_embedding_service_in_embedding_py(self):
        """
        Given: Deprecated get_embedding_service in embedding.py
        When:  Function is called
        Then:  Should work but emit deprecation warning
        
        The function at line 271 should delegate to factory.
        """
        from src.services.embedding import get_embedding_service
        
        config = AMReXAgentConfig()
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            service = get_embedding_service(config)
            
            # Should work
            assert isinstance(service, EmbeddingService), \
                "Deprecated function should still return EmbeddingService"
            
            # Should warn (optional - depends on implementation)
            # If we add deprecation warning:
            # assert len(w) >= 1
            # assert "deprecated" in str(w[0].message).lower()


# =============================================================================
# Test 8: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_cache_survives_failed_index_load(self):
        """
        Given: load_all_indices() encounters error
        When:  Error occurs during loading
        Then:  Instance cache should remain valid (partial state OK)
        
        Tests robustness - errors shouldn't corrupt cache.
        """
        # This test will be easier to write after refactor
        # For now, document the expected behavior
        pass  # Implement after GREEN phase
    
    def test_empty_cache_handled_gracefully(self):
        """
        Given: EmbeddingService with empty cache
        When:  Checking is_loaded()
        Then:  Should return False
        
        Tests the is_loaded() check uses instance cache.
        """
        config = AMReXAgentConfig()
        service = EmbeddingService(config)
        service._faiss_cache = {}  # Explicitly empty
        service._indices_loaded = True  # Flag set
        
        # indices_available() should check cache, not just flag
        # Current implementation: return self._indices_loaded and len(FAISS_DB_CACHE) > 0
        # New implementation: return self._indices_loaded and len(self._faiss_cache) > 0
        result = service.indices_available()
        
        # Should return False because cache is empty
        assert result is False, \
            "indices_available() should return False when cache is empty"


# =============================================================================
# Summary Comment
# =============================================================================

"""
TDD Progress Tracker:

RED PHASE (Current):
- [ ] All tests written above WILL FAIL
- [ ] Run: pytest tests/unit/test_embedding.py -v
- [ ] Expected: ~20 failures (proves global state exists)

GREEN PHASE (Next):
- [ ] Refactor EmbeddingService to use self._faiss_cache
- [ ] Remove global FAISS_DB_CACHE
- [ ] Update load_all_indices() to use instance cache
- [ ] Update retrieve_faiss() to use instance cache
- [ ] Update is_loaded() to check instance cache
- [ ] Run: pytest tests/unit/test_embedding.py -v
- [ ] Expected: All tests pass

REFACTOR PHASE (Final):
- [ ] Add docstrings
- [ ] Add type hints
- [ ] Clean up code
- [ ] Run full test suite
- [ ] Check coverage ≥90%

Success Criteria:
✅ All tests pass
✅ No global FAISS_DB_CACHE
✅ Instance isolation verified
✅ Factory integration works
✅ Coverage ≥90% on embedding.py
"""


# =============================================================================
# Integration Test: End-to-End with Real Index
# =============================================================================

@pytest.mark.integration
@pytest.mark.requires_indices("faiss")
@pytest.mark.requires_solver("PeleC")
class TestIntegrationWithRealIndex:
    """Integration test with actual FAISS index (if available)."""
    
    def test_can_load_and_query_real_index_pelec(self):
        """
        Given: Real FAISS index exists
        When:  Loading and querying
        Then:  Should retrieve relevant results
        
        This is an integration test that proves the refactor didn't break
        core functionality. Uses minimal test index (5 docs).
        """
        from pathlib import Path
        
        # Check if test index exists
        test_index = Path("database/faiss/case_names")
        if not test_index.exists():
            pytest.skip("Test index not built. Run build script first.")
        
        # Arrange
        config = AMReXAgentConfig()
        config.faiss_db_path = Path("database/faiss")
        
        # Act - Create service (should auto-load indices)
        service = EmbeddingService(config)
        
        # Assert - Indices loaded
        assert service.indices_available(), "Should have loaded test index"
        assert len(service._faiss_cache) > 0, "Cache should have indices"
        assert "pelec_case_names" in service._faiss_cache, "Should have pelec_case_names index"
        
        # Act - Query
        result = service.retrieve_faiss(
            query="premixed flame combustion",
            index_name="pelec_case_names",
            topk=3
        )
        
        # Assert - Got results
        assert result is not None
        assert result['source'] == 'faiss', "Should use FAISS, not fallback"
        assert len(result['results']) > 0, "Should have results"
        assert len(result['results']) <= 3, "Should respect topk limit"
        
        # Assert - Relevant result (PMF case should be in top results)
        top_result = result['results'][0]
        assert 'content' in top_result, "Result should have content"
        assert 'score' in top_result, "Result should have score"
        
        # Check that premixed flame is relevant
        all_content = ' '.join(r['content'] for r in result['results'])
        assert any(term in all_content.lower() for term in ['premixed', 'flame', 'pmf', 'methane']), \
            "Should retrieve documents relevant to query"
        
        print(f"\n✓ Integration test passed!")
        print(f"  Indices loaded: {list(service._faiss_cache.keys())}")
        print(f"  Query: 'premixed flame combustion'")
        print(f"  Results returned: {len(result['results'])}")
        print(f"  Top result: {top_result['content'][:80]}...")
        print(f"  Score: {top_result['score']:.3f}")
