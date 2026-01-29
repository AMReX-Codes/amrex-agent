"""
Vector store backends for retrieval.

Provides a small abstraction so EmbeddingService can swap between
local FAISS and hosted vector stores without changing callers.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from src.services.embedding_factory import _resolve_api_key

logger = logging.getLogger(__name__)


class VectorStoreBackend:
    """Minimal interface for vector store retrieval backends."""

    def available(self) -> bool:
        """
        Check whether the backend is usable.

        Returns
        -------
        bool
            True if the backend is available.
        """
        raise NotImplementedError

    def query(self, index_name: str, query: str, topk: int) -> dict[str, Any]:
        """
        Query the backend for similar content.

        Parameters
        ----------
        index_name : str
            Index or collection name.
        query : str
            Query string.
        topk : int
            Number of results to return.

        Returns
        -------
        dict
            Retrieval payload with results, confidence, and source.
        """
        raise NotImplementedError


@dataclass
class OpenAIVectorStoreBackend(VectorStoreBackend):
    """Hosted OpenAI vector store backend for retrieval."""

    config: object

    def __post_init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            logger.debug("OpenAI SDK not installed; cannot use hosted vector store.")
            raise RuntimeError("openai package not installed") from exc

        api_key = _resolve_api_key("openai", self.config)
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")

        base_url = getattr(self.config, "openai_base_url", None) or os.getenv("OPENAI_BASE_URL")
        base_url = base_url or os.getenv("OPENAI_API_BASE")

        if base_url:
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self._client = OpenAI(api_key=api_key)

        return self._client

    def _resolve_store_id(self, index_name: str) -> str | None:
        store_map = getattr(self.config, "openai_vector_store_ids", {}) or {}
        if isinstance(store_map, dict) and index_name in store_map:
            return store_map[index_name]
        return getattr(self.config, "openai_vector_store_id", None)

    def available(self) -> bool:
        """
        Check whether the OpenAI vector store backend is usable.

        Returns
        -------
        bool
            True if the backend is available.
        """
        try:
            _ = self._get_client()
        except Exception:
            return False
        return bool(getattr(self.config, "openai_vector_store_id", None) or getattr(self.config, "openai_vector_store_ids", None))

    def _extract_text(self, item: Any) -> str:
        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", None)

        if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
            parts = []
            for part in content:
                text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                if text:
                    parts.append(text)
            return "\n".join(parts).strip()

        if isinstance(content, str):
            return content

        text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        return text or ""

    def _extract_metadata(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item.get("metadata") or item.get("attributes") or {}
        return getattr(item, "metadata", None) or getattr(item, "attributes", None) or {}

    def _extract_score(self, item: Any) -> float:
        if isinstance(item, dict):
            score = item.get("score") or item.get("similarity")
        else:
            score = getattr(item, "score", None) or getattr(item, "similarity", None)
        return float(score) if score is not None else 0.0

    def _normalize_score(self, similarity: float) -> float:
        # OpenAI returns similarity (higher is better); convert to distance-like (lower is better).
        return 1.0 - similarity

    def query(self, index_name: str, query: str, topk: int) -> dict[str, Any]:
        """
        Query the OpenAI vector store.

        Parameters
        ----------
        index_name : str
            Index or collection name.
        query : str
            Query string.
        topk : int
            Number of results to return.

        Returns
        -------
        dict
            Retrieval payload with results, confidence, and source.
        """
        store_id = self._resolve_store_id(index_name)
        if not store_id:
            raise RuntimeError("OpenAI vector store ID not configured")

        store_map = getattr(self.config, "openai_vector_store_ids", None) or {}
        if not store_map and getattr(self.config, "openai_vector_store_id", None):
            logger.debug("OpenAI vector store uses a single store; results are not filtered by index_name.")

        client = self._get_client()

        # Avoid relying on API-specific params; fetch and slice results locally.
        response = client.vector_stores.search(
            vector_store_id=store_id,
            query=query,
        )

        data = response.get("data") if isinstance(response, dict) else getattr(response, "data", None)
        if not data:
            return {"results": [], "confidence": 0.0, "source": "openai_vector_store"}

        results = []
        for item in list(data)[:topk]:
            results.append(
                {
                    "content": self._extract_text(item),
                    "metadata": self._extract_metadata(item),
                    "score": self._normalize_score(self._extract_score(item)),
                }
            )

        return {"results": results, "confidence": 1.0 if results else 0.0, "source": "openai_vector_store"}
