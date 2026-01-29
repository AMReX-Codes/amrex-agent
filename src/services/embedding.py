"""
FAISS Embedding Service with CBORG and Hybrid LLM Fallback.

Provides semantic search capabilities using FAISS vector indices.
Pattern inspired by foam-agent's global FAISS_DB_CACHE.

Features:
- CBORG embeddings (with OpenAI fallback)
- Global index caching for performance
- Hybrid fallback to LLM when indices unavailable
- Hierarchical retrieval support
"""

import logging
from typing import Any

from langchain_community.vectorstores import FAISS

from .faiss_artifacts import ensure_faiss_indices
from .vector_store_backends import OpenAIVectorStoreBackend

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    FAISS embedding service with CBORG and hybrid LLM fallback.

    Manages FAISS vector indices for semantic search across AMReX code knowledge bases.
    Implements foam-agent's global cache pattern for performance.
    """

    def __init__(self, config):
        """
        Initialize embedding service.

        Args:
            config: Agent configuration instance with FAISS settings
        """
        self.config = config
        self.embeddings = None
        self._indices_loaded = False
        self._vector_backend = self._init_vector_backend()
        self._use_faiss_local = self._vector_backend is None
        self._faiss_download_enabled = self._should_download_faiss()

        # Instance-based FAISS cache (replaces global)
        self._faiss_cache: dict[str, FAISS] = {}

        # Initialize embedding model
        self._init_embeddings()

        if self._use_faiss_local and self._faiss_download_enabled:
            self._download_faiss_indices()

        # Load FAISS indices if caching enabled
        if self._use_faiss_local and self.config.faiss_cache_enabled:
            self._load_indices()

    def _init_vector_backend(self):
        """
        Initialize vector store backend selection.

        Returns
        -------
            Backend instance or None (defaults to local FAISS)
        """
        backend = getattr(self.config, "vector_store_backend", "auto")
        backend = backend.lower() if isinstance(backend, str) else "auto"

        if backend == "openai":
            try:
                return OpenAIVectorStoreBackend(self.config)
            except Exception as e:
                logger.debug(f"Warning: Failed to initialize OpenAI vector store backend: {e}")
                return None

        if backend == "auto" and (
            getattr(self.config, "openai_vector_store_id", None)
            or getattr(self.config, "openai_vector_store_ids", None)
        ):
            try:
                return OpenAIVectorStoreBackend(self.config)
            except Exception as e:
                logger.debug(f"Warning: OpenAI vector store backend unavailable: {e}")
                return None

        return None

    def _should_download_faiss(self) -> bool:
        backend = getattr(self.config, "vector_store_backend", "auto")
        backend = backend.lower() if isinstance(backend, str) else "auto"

        if backend == "faiss_download":
            return True

        if backend == "auto":
            base_url = getattr(self.config, "vector_store_base_url", None)
            manifest_url = getattr(self.config, "vector_store_manifest_url", None)
            if base_url or manifest_url:
                return True

        return False

    def _download_faiss_indices(self) -> None:
        base_url = getattr(self.config, "vector_store_base_url", None)
        manifest_url = getattr(self.config, "vector_store_manifest_url", None)
        if not base_url and not manifest_url:
            logger.debug("No FAISS download URL configured; skipping download.")
            return
        try:
            downloaded = ensure_faiss_indices(
                faiss_root=self.config.faiss_db_path,
                base_url=base_url,
                manifest_url=manifest_url,
            )
            logger.info(f"Downloaded {downloaded} FAISS artifact files")
        except Exception as e:
            logger.debug(f"Warning: Failed to download FAISS artifacts: {e}")

    def _init_embeddings(self):
        """
        Initialize embedding model using shared factory.

        Uses embedding_factory for consistent initialization across all services.
        This eliminates duplication with build_index.py.

        Priority (handled by factory):
        1. CBORG embeddings (LBNL Nomic via OpenAI SDK)
        2. OpenAI embeddings (fallback)
        3. HuggingFace embeddings (local fallback)
        """
        from .embedding_factory import create_embeddings

        self.embeddings = create_embeddings(
            provider=self.config.embedding_provider,
            config=self.config,
            enable_cache=True
        )

        if self.embeddings is None:
            logger.debug(f"Warning: Failed to initialize {self.config.embedding_provider} embeddings")
            logger.debug("         FAISS retrieval will be unavailable")

    def _load_indices(self):
        """
        Load all FAISS indices into global cache.

        Implements foam-agent's pattern: load once at startup, reuse for all queries.
        Discovers and loads indices for all registered code configs.
        """
        # Using instance cache instead of global

        if self.embeddings is None:
            logger.debug("Warning: No embeddings initialized. Cannot load FAISS indices.")
            return

        # Discover code configs
        try:
            from database.configs import discover_code_configs

            code_configs = discover_code_configs()

        except ImportError:
            logger.debug("Warning: Could not import code configs. Skipping FAISS index loading.")
            return

        # Load indices for each code
        indices_loaded = 0
        for code_config in code_configs:
            for index_name in code_config.get_faiss_indices():
                index_path = self.config.faiss_db_path / index_name

                if index_path.exists():
                    try:
                        self._faiss_cache[index_name] = FAISS.load_local(
                            str(index_path),
                            self.embeddings,
                            allow_dangerous_deserialization=True
                        )
                        indices_loaded += 1
                        logger.debug(f"Loaded FAISS index: {index_name}")

                    except Exception as e:
                        logger.debug(f"Warning: Failed to load FAISS index '{index_name}': {e}")

        self._indices_loaded = indices_loaded > 0
        logger.debug(f"FAISS cache initialized with {indices_loaded} indices")

    def indices_available(self) -> bool:
        """
        Check if any FAISS indices are available.

        Returns
        -------
            True if indices loaded, False otherwise
        """
        if self._vector_backend:
            return self._vector_backend.available()
        return self._indices_loaded and len(self._faiss_cache) > 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts using the underlying LangChain embeddings.

        This delegates to the LangChain embeddings.embed_documents() method.
        Provided for compatibility with Level0Builder.

        Parameters
        ----------
        texts : list of str
            Text strings to embed.

        Returns
        -------
        list of list of float
            Embedding vectors (one per input text).
        """
        if self.embeddings is None:
            raise RuntimeError("No embeddings initialized. Cannot embed texts.")
        return self.embeddings.embed_documents(texts)

    def retrieve_faiss(
        self,
        query: str,
        index_name: str,
        topk: int | None = None
    ) -> dict[str, Any]:
        """
        Retrieve similar documents from FAISS index.

        Implements hierarchical retrieval and hybrid LLM fallback.

        Parameters
        ----------
        query : str
            Search query string.
        index_name : str
            Name of FAISS index to query.
        topk : int or None, optional
            Number of top results to return (uses config default if None).

        Returns
        -------
        dict
            Retrieval payload with results, confidence, and source.
        """
        if topk is None:
            topk = self.config.faiss_topk

        if self._vector_backend:
            try:
                return self._vector_backend.query(index_name=index_name, query=query, topk=topk)
            except Exception as e:
                logger.debug(f"Error retrieving from vector store backend: {e}")
                if self.config.faiss_fallback_to_llm:
                    return self._llm_fallback(query)
                return {
                    'results': [],
                    'confidence': 0.0,
                    'source': 'error'
                }

        # Check if index available
        if index_name not in self._faiss_cache:
            if self.config.faiss_fallback_to_llm:
                return self._llm_fallback(query)
            else:
                return {
                    'results': [],
                    'confidence': 0.0,
                    'source': 'unavailable'
                }

        # Retrieve from FAISS
        try:
            vectordb = self._faiss_cache[index_name]
            docs_and_scores = vectordb.similarity_search_with_score(query, k=topk)

            results = []
            for doc, score in docs_and_scores:
                results.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'score': float(score),  # Distance score (lower is better)
                })

            return {
                'results': results,
                'confidence': 1.0,
                'source': 'faiss'
            }

        except Exception as e:
            logger.debug(f"Error retrieving from FAISS index '{index_name}': {e}")

            if self.config.faiss_fallback_to_llm:
                return self._llm_fallback(query)
            else:
                return {
                    'results': [],
                    'confidence': 0.0,
                    'source': 'error'
                }

    def retrieve_hierarchical(
        self,
        queries: list[dict[str, str]],
        topk: int | None = None
    ) -> dict[str, Any]:
        """
        Hierarchical retrieval across multiple FAISS indices.

        Implements foam-agent's 3-level pattern:
        1. Structure index (broad matching)
        2. Details index (detailed documentation)
        3. Templates/execution index (specific patterns)

        Parameters
        ----------
        queries : list of dict
            List of dicts with "index" and "query" keys.
        topk : int or None, optional
            Number of results per query.

        Returns
        -------
        dict
            Aggregated results from all levels.
        """
        all_results = []
        combined_confidence = 1.0

        for query_spec in queries:
            index_name = query_spec['index']
            query = query_spec['query']

            result = self.retrieve_faiss(index_name, query, topk=topk)

            all_results.extend(result['results'])
            combined_confidence *= result['confidence']

        return {
            'results': all_results,
            'confidence': combined_confidence,
            'source': 'hierarchical_faiss'
        }

    def _llm_fallback(self, query: str) -> dict[str, Any]:
        """
        Fallback to LLM-based query when FAISS unavailable.

        Args:
            query: Search query

        Returns
        -------
            Empty results with fallback indicator
        """
        # TODO: Integrate with existing knowledge service's ask_pele_question
        # For now, return empty results
        logger.debug(f"FAISS index unavailable. Falling back to LLM for query: {query}")

        return {
            'results': [],
            'confidence': 0.0,
            'source': 'llm_fallback'
        }


def get_embedding_service(config) -> EmbeddingService:
    """
    Get embedding service instance.

    Call context: Used by services to obtain an embedding client.

    Parameters
    ----------
    config : object
        Agent configuration instance.

    Returns
    -------
    EmbeddingService
        Embedding service instance.
    """
    return EmbeddingService(config)
