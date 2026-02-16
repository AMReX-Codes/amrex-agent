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
import random
import time
from typing import Any

from langchain_community.vectorstores import FAISS

from .faiss_artifacts import ensure_faiss_indices
from .vector_store_backends import OpenAIVectorStoreBackend

logger = logging.getLogger(__name__)


class _CountingEmbeddings:
    def __init__(self, embeddings, record_call) -> None:
        self._embeddings = embeddings
        self._record_call = record_call

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._record_call("embed_documents")
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self._record_call("embed_query")
        return self._embeddings.embed_query(text)

    def __getattr__(self, name: str):
        return getattr(self._embeddings, name)


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
        self._disabled = bool(getattr(config, "disable_embeddings", False))
        self.embeddings = None
        self._indices_loaded = False
        self._vector_backend = self._init_vector_backend()
        self._use_faiss_local = self._vector_backend is None
        self._faiss_download_enabled = self._should_download_faiss()
        self._last_embed_request_ts: float | None = None
        self._embedding_call_counts = {
            "total": 0,
            "embed_documents": 0,
            "embed_query": 0,
        }

        # Instance-based FAISS cache (replaces global)
        self._faiss_cache: dict[str, FAISS] = {}

        if self._disabled:
            logger.debug("[Config] Embeddings disabled via disable_embeddings")
            return

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
            logger.debug(f"Downloaded {downloaded} FAISS artifact files")
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

        raw_embeddings = create_embeddings(
            provider=self.config.embedding_provider,
            config=self.config,
            enable_cache=True
        )

        if raw_embeddings is None:
            logger.debug(f"Warning: Failed to initialize {self.config.embedding_provider} embeddings")
            logger.debug("         FAISS retrieval will be unavailable")
            return

        self.embeddings = _CountingEmbeddings(raw_embeddings, self._record_embedding_call)

    def _record_embedding_call(self, call_type: str) -> None:
        if call_type in self._embedding_call_counts:
            self._embedding_call_counts[call_type] += 1
        self._embedding_call_counts["total"] += 1

    def get_embedding_call_counts(self) -> dict[str, int]:
        return dict(self._embedding_call_counts)

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
        if not texts:
            return []

        rate_limit_rpm = getattr(self.config, "embedding_rate_limit_rpm", 0) or 0
        max_attempts = getattr(self.config, "embedding_retry_max_attempts", 1) or 1

        return self._embed_documents_with_policy(
            texts,
            rate_limit_rpm=rate_limit_rpm,
            max_attempts=max_attempts
        )

    def expand_documents(
        self,
        documents: list[str],
        metadata: list[dict[str, Any]] | None = None
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """
        Expand documents via chunking while keeping metadata aligned.
        """
        chunk_size = getattr(self.config, "embedding_chunk_size_chars", 0) or 0
        if chunk_size <= 0 or not documents:
            return documents, metadata or []

        chunked_docs: list[str] = []
        parent_indices: list[int] = []
        logged = 0
        for idx, text in enumerate(documents):
            if len(text) <= chunk_size:
                chunked_docs.append(text)
                parent_indices.append(idx)
                if logged < 5:
                    logger.debug(
                        "Embedding chunk (doc %s): 1 chunk, size=%s",
                        idx,
                        len(text),
                    )
                    logged += 1
                continue
            start = 0
            text_len = len(text)
            chunk_count = 0
            while start < text_len:
                end = min(start + chunk_size, text_len)
                chunked_docs.append(text[start:end])
                parent_indices.append(idx)
                chunk_count += 1
                if end >= text_len:
                    break
                start = end
            if logged < 5:
                logger.debug(
                    "Embedding chunk (doc %s): %s chunks, size=%s",
                    idx,
                    chunk_count,
                    chunk_size,
                )
                logged += 1

        if not parent_indices:
            return documents, metadata or []

        base_meta = metadata or [{} for _ in documents]
        expanded_meta: list[dict[str, Any]] = []
        for chunk_idx, parent_idx in enumerate(parent_indices):
            parent = base_meta[parent_idx] if parent_idx < len(base_meta) else {}
            meta = dict(parent) if isinstance(parent, dict) else {}
            meta["chunk_parent"] = parent_idx
            meta["chunk_index"] = chunk_idx
            expanded_meta.append(meta)
        return chunked_docs, expanded_meta

    def _embed_documents_with_policy(
        self,
        texts: list[str],
        rate_limit_rpm: int,
        max_attempts: int,
    ) -> list[list[float]]:
        batch_size = 64  # conservative default to avoid oversized requests
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_idx = (i // batch_size) + 1
            batch_total = (len(texts) + batch_size - 1) // batch_size
            sample = (batch[0][:10] if batch and isinstance(batch[0], str) else "")
            if rate_limit_rpm > 0:
                min_interval = 60.0 / rate_limit_rpm
                now = time.monotonic()
                if self._last_embed_request_ts is not None:
                    elapsed = now - self._last_embed_request_ts
                    if elapsed < min_interval:
                        time.sleep(min_interval - elapsed)
                self._last_embed_request_ts = time.monotonic()

            attempt = 0
            while True:
                attempt += 1
                try:
                    all_embeddings.extend(self.embeddings.embed_documents(batch))
                    if attempt > 1:
                        logger.info(
                            "Embedding batch %s/%s recovered after %s attempt(s) (sample='%s')",
                            batch_idx,
                            batch_total,
                            attempt,
                            sample,
                        )
                    break
                except Exception as e:
                    status_code = self._get_http_status(e)
                    retryable = status_code in {429, 500, 502, 503}
                    if not retryable or attempt >= max_attempts:
                        raise
                    base_delay = 1.0
                    max_delay = 20.0
                    backoff = 2.0
                    delay = min(max_delay, base_delay * (backoff ** (attempt - 1)))
                    delay += random.uniform(0.0, delay * 0.1)
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    logger.warning(
                        "[%s] Embedding batch %s/%s failed (attempt %s/%s, status %s, sample='%s'): %s",
                        timestamp,
                        batch_idx,
                        batch_total,
                        attempt,
                        max_attempts,
                        status_code,
                        sample,
                        e,
                    )
                    time.sleep(delay)
        return all_embeddings

    @staticmethod
    def _get_http_status(error: Exception) -> int | None:
        for attr in ("status_code", "http_status"):
            value = getattr(error, attr, None)
            if isinstance(value, int):
                return value
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
        return None

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
