"""
Shared embedding provider initialization factory.

Centralizes CBORG, OpenAI, and HuggingFace embedding provider logic
to eliminate duplication between embedding.py and build_index.py.

Usage:
    from services.embedding_factory import create_embeddings

    # Using config
    embeddings = create_embeddings(provider="cborg", config=config)

    # Using direct API key
    embeddings = create_embeddings(provider="openai", api_key="sk-...")

    # With custom model
    embeddings = create_embeddings(
        provider="openai",
        model_name="text-embedding-3-large",
        config=config
    )
"""

import logging
import os

logger = logging.getLogger(__name__)

def _resolve_api_key(provider: str, config: object | None = None) -> str | None:
    """
    Resolve API key from config or environment.

    Priority:
        1. config.<provider>_api_key attribute
        2. Environment variable (CBORG_API_KEY, ALCF_API_KEY, OPENAI_API_KEY)

    Args:
        provider: 'cborg', 'alcf', 'openai', or 'huggingface'
        config: AMReXAgentConfig object with API keys

    Returns
    -------
        API key string or None
    """
    provider = provider.lower()

    # Try config first
    if config:
        key_attr = f'{provider}_api_key'
        if hasattr(config, key_attr):
            key = getattr(config, key_attr)
            if key:
                return key

    # Try environment variable
    env_var_map = {
        'cborg': 'CBORG_API_KEY',
        'alcf': 'ALCF_API_KEY',
        'openai': 'OPENAI_API_KEY'
    }

    env_var = env_var_map.get(provider)
    if env_var:
        return os.getenv(env_var)

    return None


def _resolve_model_name(
    provider: str,
    model_name: str | None = None,
    config: object | None = None
) -> str | None:
    """
    Resolve embedding model name based on provider and config.

    Args:
        provider: 'cborg', 'alcf', 'openai', or 'huggingface'
        model_name: Optional override model name
        config: AMReXAgentConfig object with embedding settings

    Returns
    -------
        Resolved model name or None
    """
    provider = provider.lower()

    if provider not in {"openai", "alcf"}:
        return model_name

    if model_name:
        return model_name

    if provider == "alcf":
        if config and hasattr(config, "alcf_embedding_model"):
            config_model = getattr(config, "alcf_embedding_model")
            if config_model:
                return config_model
        if config and hasattr(config, "faiss_embedding_model"):
            config_model = getattr(config, "faiss_embedding_model")
            if config_model and config_model != "text-embedding-3-small":
                return config_model
        return "mistralai/Mistral-7B-Instruct-v0.3-embed"

    if config and hasattr(config, "faiss_embedding_model"):
        config_model = config.faiss_embedding_model
        if config_model:
            return config_model

    return "text-embedding-3-small"


def _create_cborg_embeddings(
    api_key: str | None = None,
    enable_cache: bool = True,
    config: object | None = None
):
    """
    Initialize CBORG embeddings using official OpenAI SDK pattern.

    Uses LBNL's Nomic embeddings via OpenAI-compatible API.

    Args:
        api_key: CBORG API key (if None, will try to resolve)
        enable_cache: Enable caching (uses CBORGEmbeddings class)
        config: AMReXAgentConfig object

    Returns
    -------
        Embeddings instance or None on failure
    """
    try:
        # Resolve API key if not provided
        if not api_key:
            api_key = _resolve_api_key('cborg', config)

        if not api_key:
            logger.debug("Error: CBORG_API_KEY not found")
            logger.debug("       Config: Check config.cborg_api_key")
            logger.debug("       Env: export CBORG_API_KEY=your_key")
            logger.debug("       Get your key from: https://api.cborg.lbl.gov")
            return None

        # Use custom CBOR embeddings class with caching if available
        if enable_cache:
            try:
                # Try to import custom CBORG class from database scripts
                import sys
                from pathlib import Path
                db_scripts_path = Path(__file__).parent.parent.parent / 'database' / 'scripts'
                if str(db_scripts_path) not in sys.path:
                    sys.path.insert(0, str(db_scripts_path))

                from cborg_embeddings import CBORGEmbeddings

                embeddings = CBORGEmbeddings(
                    model="lbl/nomic-embed-text",
                    api_key=api_key,
                    enable_cache=True
                )
                logger.debug("Initialized CBORG embeddings (with caching)")
                logger.debug("  Model: lbl/nomic-embed-text")
                logger.debug("  Dimensions: 768")
                logger.debug("  Context: 8192 tokens")
                logger.debug("  Cost: FREE at LBNL")
                logger.debug("  Cache: Enabled (1-hour TTL)")
                return embeddings

            except ImportError:
                # Fall back to standard OpenAI embeddings class
                pass

        # Standard LangChain OpenAI embeddings (no custom caching)
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            model="lbl/nomic-embed-text",
            openai_api_key=api_key,
            openai_api_base="https://api.cborg.lbl.gov",
            base_url="https://api.cborg.lbl.gov",
        )

        logger.debug("Initialized CBORG embeddings (LBNL Nomic)")
        logger.debug("  Model: lbl/nomic-embed-text")
        logger.debug("  Dimensions: 768")
        logger.debug("  Context: 8192 tokens")
        logger.debug("  Cost: FREE at LBNL")

        return embeddings

    except ImportError as e:
        logger.debug("Error: langchain-openai not installed for CBORG")
        logger.debug("       Install: pip install langchain-openai")
        logger.debug(f"       {e}")
        return None
    except Exception as e:
        logger.debug(f"Error initializing CBORG embeddings: {e}")
        return None


def _create_openai_embeddings(
    api_key: str | None = None,
    model_name: str = "text-embedding-3-small",
    config: object | None = None,
    base_url: str | None = None,
):
    """
    Initialize OpenAI embeddings.

    Args:
        api_key: OpenAI API key (if None, uses environment/config)
        model_name: Model name (default: text-embedding-3-small)
        config: AMReXAgentConfig object

    Returns
    -------
        Embeddings instance or None on failure
    """
    try:
        from langchain_openai import OpenAIEmbeddings

        # Resolve API key if needed
        if not api_key:
            api_key = _resolve_api_key('openai', config)

        # Resolve base URL if needed
        if base_url is None and config and hasattr(config, "openai_base_url"):
            base_url = config.openai_base_url

        # Create embeddings (langchain will use OPENAI_API_KEY env if api_key is None)
        if api_key:
            embeddings = OpenAIEmbeddings(
                model=model_name,
                openai_api_key=api_key,
                base_url=base_url
            )
        else:
            embeddings = OpenAIEmbeddings(
                model=model_name,
                base_url=base_url
            )

        logger.debug(f"Initialized OpenAI embeddings: {model_name}")
        return embeddings

    except ImportError:
        logger.debug("Error: langchain-openai not installed. Cannot initialize embeddings.")
        logger.debug("       Install: pip install langchain-openai")
        return None
    except Exception as e:
        logger.debug(f"Error initializing OpenAI embeddings: {e}")
        return None


def _resolve_alcf_base_url(
    config: Optional[object] = None,
    base_url: Optional[str] = None,
) -> Optional[str]:
    if base_url:
        return base_url
    if config and hasattr(config, "alcf_base_url"):
        value = getattr(config, "alcf_base_url")
        if value:
            return value
    if os.getenv("ALCF_BASE_URL"):
        return os.getenv("ALCF_BASE_URL")
    try:
        from src.config import resolve_alcf_base_url, AMReXAgentConfig
        if isinstance(config, AMReXAgentConfig):
            return resolve_alcf_base_url(config)
    except Exception:
        pass
    cluster = (os.getenv("ALCF_CLUSTER") or "").strip().lower()
    if cluster == "metis":
        return "https://inference-api.alcf.anl.gov/resource_server/metis/api/v1"
    return "https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"


def _create_alcf_embeddings(
    api_key: Optional[str] = None,
    model_name: str = "text-embedding-3-small",
    config: Optional[object] = None,
    base_url: Optional[str] = None,
):
    """
    Initialize ALCF embeddings (OpenAI-compatible via ALCF base URL).

    Args:
        api_key: ALCF access token (if None, uses environment/config)
        model_name: Model name (default: text-embedding-3-small)
        config: AMReXAgentConfig object

    Returns:
        Embeddings instance or None on failure
    """
    return _create_openai_embeddings(
        api_key=api_key or _resolve_api_key("alcf", config),
        model_name=model_name,
        config=config,
        base_url=_resolve_alcf_base_url(config, base_url),
    )


def _create_huggingface_embeddings():
    """
    Initialize HuggingFace embeddings (local, no API key required).

    WARNING: Requires sentence-transformers package which may not be installed.

    Returns
    -------
        Embeddings instance or None on failure
    """
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        logger.debug("Loading HuggingFace model (first run may download ~90MB)...")
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        logger.debug("Initialized HuggingFace embeddings (local)")
        logger.debug("  Model: all-MiniLM-L6-v2")
        logger.debug("  Dimensions: 384")
        logger.debug("  Context: 512 tokens ([WARN]  SHORT)")
        logger.debug("  Cost: FREE (local)")

        return embeddings

    except ImportError:
        logger.debug("Error: HuggingFace embeddings not available")
        logger.debug("       Missing package: langchain-huggingface or sentence-transformers")
        logger.debug("       Install: conda install -c conda-forge sentence-transformers")
        logger.debug("       Or: pip install sentence-transformers langchain-huggingface")
        return None
    except Exception as e:
        logger.debug(f"Error initializing HuggingFace embeddings: {e}")
        return None


def create_embeddings(
    provider: str,
    api_key: str | None = None,
    model_name: str | None = None,
    config: object | None = None,
    enable_cache: bool = True,
    base_url: str | None = None,
):
    """
    Create embeddings for any provider.

    This is the single source of truth for embedding provider initialization,
    replacing duplicated logic in embedding.py and build_index.py.

    Parameters
    ----------
    provider : str
        "cborg", "alcf", "openai", or "huggingface".
    api_key : str or None, optional
        Direct API key (overrides config/env).
    model_name : str or None, optional
        Model name (provider-specific defaults).
    config : object or None, optional
        AMReXAgentConfig object with API keys/settings.
    enable_cache : bool, optional
        Enable caching for CBORG.
    base_url : str or None, optional
        Optional base URL for the embedding provider.

    Returns
    -------
    object or None
        LangChain Embeddings instance or None on failure.

    Priority for API key resolution:
        1. Direct api_key parameter
        2. config.<provider>_api_key attribute
        3. Environment variable (CBORG_API_KEY, ALCF_API_KEY, OPENAI_API_KEY)
        4. None (will print error and return None)

    Examples
    --------
        >>> # Using config
        >>> embeddings = create_embeddings(provider="cborg", config=config)

        >>> # Using direct API key
        >>> embeddings = create_embeddings(provider="openai", api_key="sk-...")

        >>> # With custom model
        >>> embeddings = create_embeddings(
        ...     provider="openai",
        ...     model_name="text-embedding-3-large"
        ... )
    """
    provider = provider.lower()

    if provider == "cborg":
        return _create_cborg_embeddings(
            api_key=api_key,
            enable_cache=enable_cache,
            config=config
        )

    elif provider == "alcf":
        model = _resolve_model_name(provider, model_name=model_name, config=config)
        return _create_alcf_embeddings(
            api_key=api_key,
            model_name=model or "text-embedding-3-small",
            config=config,
            base_url=base_url,
        )

    elif provider == "openai":
        model = _resolve_model_name(provider, model_name=model_name, config=config)
        return _create_openai_embeddings(
            api_key=api_key,
            model_name=model or "text-embedding-3-small",
            config=config,
            base_url=base_url,
        )

    elif provider == "huggingface":
        return _create_huggingface_embeddings()

    else:
        logger.debug(f"Warning: Unknown embedding provider '{provider}'")
        logger.debug(f"         Supported providers: 'cborg', 'alcf', 'openai', 'huggingface'")
        return None
