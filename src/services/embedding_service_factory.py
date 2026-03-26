"""
Singleton factory for EmbeddingService initialization.

Provides consistent EmbeddingService initialization across all services
(knowledge.py, input_writer.py, architect.py) with graceful fallback handling.

Usage:
    from services.embedding_service_factory import get_embedding_service

    # In service __init__
    embedding_service = get_embedding_service(config)
    self.embeddings = embedding_service.embeddings  # May be None

    if self.embeddings:
        logger.debug(" [OK] FAISS embeddings available")
    else:
        logger.warning("[WARN] FAISS embeddings not available")
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .embedding import EmbeddingService

# Module-level cache for singleton pattern
_embedding_service_cache: dict[int, "EmbeddingService"] = {}


logger = logging.getLogger(__name__)

def get_embedding_service(config: object) -> "EmbeddingService":
    """
    Get (or create) EmbeddingService singleton instance.

    Uses singleton pattern to ensure each config instance gets exactly one
    EmbeddingService, avoiding redundant FAISS cache loading and initialization.

    Call context: Used by services to share an EmbeddingService instance.

    Parameters
    ----------
    config : object
        AMReXAgentConfig instance.

    Returns
    -------
    EmbeddingService
        EmbeddingService instance (never None).

    Caching Strategy:
        - Uses id(config) as cache key to identify unique config instances
        - Each unique config gets its own EmbeddingService
        - Subsequent calls with same config return cached instance

    Example:
        >>> from config import AMReXAgentConfig
        >>> config = AMReXAgentConfig()
        >>>
        >>> # First call creates instance
        >>> service1 = get_embedding_service(config)
        >>>
        >>> # Second call returns same instance
        >>> service2 = get_embedding_service(config)
        >>> assert service1 is service2  # Same object
        >>>
        >>> # Check if embeddings initialized successfully
        >>> if service1.embeddings:
        ...     logger.debug("Embeddings ready")
        ... else:
        ...     logger.debug("Embeddings failed to initialize")
    """
    global _embedding_service_cache

    config_id = id(config)

    # Return cached instance if available
    if config_id in _embedding_service_cache:
        return _embedding_service_cache[config_id]

    # Create new instance and cache it
    from .embedding import EmbeddingService
    service = EmbeddingService(config)
    _embedding_service_cache[config_id] = service

    return service


def clear_embedding_service_cache() -> None:
    """
    Clear the embedding service cache.

    Useful for testing or when config changes require reinitialization.

    Warning:
        This will force recreation of EmbeddingService on next call,
        which will reload all FAISS indices from disk.
    """
    global _embedding_service_cache
    _embedding_service_cache.clear()
