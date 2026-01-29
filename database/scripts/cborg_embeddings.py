"""
CBORG Embeddings with automatic caching.

Properly inherits from LangChain's Embeddings base class for full compatibility.
"""

import logging

import openai
from langchain_core.embeddings import Embeddings

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


logger = logging.getLogger(__name__)

class CBORGEmbeddings(Embeddings):
    """
    CBORG embeddings with token counting and automatic caching.

    Features:
    - Inherits from LangChain Embeddings (full compatibility)
    - Sends raw text (not token IDs) to API
    - Automatic caching for repeated texts (~40% speedup)
    - Token counting to avoid context limit
    - Automatic chunking for long texts
    - Compatible with FAISS and all LangChain vector stores
    """

    def __init__(
        self,
        api_key: str,
        model: str = "lbl/nomic-embed-text",
        max_tokens: int = 8192,  # Nomic's context length
        enable_cache: bool = True,  # Enable caching by default
        cache_ttl: int = 3600  # Cache for 1 hour
    ):
        """
        Initialize CBORG embeddings.

        Args:
            api_key: CBORG API key
            model: Model name
            max_tokens: Maximum tokens per text
            enable_cache: Enable litellm caching (default: True)
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl

        # Configure OpenAI SDK for CBORG
        openai.api_key = api_key
        openai.base_url = "https://api.cborg.lbl.gov"

        # Initialize tokenizer for counting
        if TIKTOKEN_AVAILABLE:
            try:
                self.encoding = tiktoken.get_encoding("cl100k_base")
            except Exception:
                self.encoding = None
        else:
            self.encoding = None

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.encoding is None:
            return len(text) // 4  # Rough estimate
        return len(self.encoding.encode(text))

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into chunks that fit within token limit."""
        token_count = self._count_tokens(text)

        if token_count <= self.max_tokens:
            return [text]

        # Chunk by sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            if current_tokens + sentence_tokens > self.max_tokens:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _get_extra_body(self) -> dict:
        """Get extra_body parameters for caching."""
        if not self.enable_cache:
            return {}

        return {
            "caching": True,
            "ttl": self.cache_ttl
        }

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of documents with automatic chunking and caching.

        Parameters
        ----------
        texts : List[str]
            Document texts.

        Returns
        -------
        List[List[float]]
            Embedding vectors.
        """
        if not texts:
            return []

        all_embeddings = []

        for text in texts:
            chunks = self._chunk_text(text)

            if len(chunks) > 1:
                logger.info(f" Splitting {self._count_tokens(text)} tokens "
                      f"into {len(chunks)} chunks")

            chunk_embeddings = []

            # TODO: Batch chunks into a single embeddings request (API accepts list input).
            for chunk in chunks:
                # Send raw text with caching enabled
                response = openai.embeddings.create(
                    model=self.model,
                    input=chunk,  # STRING, not token IDs
                    extra_body=self._get_extra_body()  # Enable caching
                )
                chunk_embeddings.append(response.data[0].embedding)

            # Average chunks if needed
            if len(chunk_embeddings) > 1:
                import numpy as np
                avg_embedding = np.mean(chunk_embeddings, axis=0).tolist()
                all_embeddings.append(avg_embedding)
            else:
                all_embeddings.append(chunk_embeddings[0])

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a single query with chunking and caching.

        Parameters
        ----------
        text : str
            Query text.

        Returns
        -------
        List[float]
            Embedding vector.
        """
        chunks = self._chunk_text(text)

        if len(chunks) > 1:
            logger.info(f" Splitting query ({self._count_tokens(text)} tokens) "
                  f"into {len(chunks)} chunks")

            import numpy as np
            chunk_embeddings = []

            for chunk in chunks:
                response = openai.embeddings.create(
                    model=self.model,
                    input=chunk,
                    extra_body=self._get_extra_body()
                )
                chunk_embeddings.append(response.data[0].embedding)

            return np.mean(chunk_embeddings, axis=0).tolist()

        # Single chunk
        response = openai.embeddings.create(
            model=self.model,
            input=text,
            extra_body=self._get_extra_body()  # Enable caching
        )

        return response.data[0].embedding
