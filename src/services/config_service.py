"""Configuration initialization service.

Handles API key loading, environment setup, and LLM connection testing.
Extracted from AMReXAgentConfig to separate concerns (data model vs initialization).

Pattern: Matches other services (EmbeddingService, ArchitectService, etc.)
"""

import logging
import os
from pathlib import Path

from src.config import AMReXAgentConfig, resolve_alcf_base_url, wrap_llm_client_with_retry

logger = logging.getLogger(__name__)

class ConfigService:
    """Manages configuration initialization with side effects.

    Responsibilities:
    - Load API keys from files
    - Test LLM connections
    - Setup environment variables

    Separates initialization logic from data model (AMReXAgentConfig).
    """

    def __init__(self, verbose: bool = True):
        """Initialize config service.

        Args:
            verbose: Print status messages during initialization
        """
        self.verbose = verbose

    def _print(self, message: str):
        """Print message if verbose mode enabled."""
        if self.verbose:
            logger.info(message)

    def load_api_keys(self, config: AMReXAgentConfig) -> AMReXAgentConfig:
        """
        Load API keys from files if not already set.

        Call context: Used during configuration initialization before LLM access.

        Parameters
        ----------
        config : AMReXAgentConfig
            Base configuration.

        Returns
        -------
        AMReXAgentConfig
            Updated configuration with API keys loaded.
        """
        # If key already set, return as-is
        if config.llm_provider == "cborg" and config.cborg_api_key:
            logger.debug(" Using CBORG_API_KEY from environment")
            return config
        if config.llm_provider == "alcf" and config.alcf_api_key:
            logger.debug(" Using ALCF_API_KEY from environment")
            return config
        
        if config.llm_provider == "cborg":
            # Try loading from file
            key_file = Path.home() / ".nersc" / "cborg_api_key.txt"
            if key_file.exists():
                try:
                    api_key = key_file.read_text().strip()
                    logger.debug(f" Loaded CBORG_API_KEY from {key_file}")
                    # Return new config with updated key
                    return config.model_copy(update={'cborg_api_key': api_key})
                except Exception as e:
                    logger.warning(f"[WARN] Could not read {key_file}: {e}")
                    return config
            else:
                logger.warning("[WARN] CBORG_API_KEY not available")
                logger.debug("       Setup options:")
                logger.debug("         1. Set environment: export CBORG_API_KEY=your_key")
                logger.debug("         2. Create file: echo 'your_key' > ~/.nersc/cborg_api_key.txt")
                logger.debug("         3. Get key from: https://api.cborg.lbl.gov")
                return config

        if config.llm_provider == "alcf":
            # Optional hook: use inference_auth_token helper if available
            try:
                from inference_auth_token import get_access_token  # type: ignore
                api_key = get_access_token()
                if api_key:
                    logger.debug(" Loaded ALCF_API_KEY from inference_auth_token helper")
                    return config.model_copy(update={'alcf_api_key': api_key})
            except Exception as e:
                logger.debug(f" ALCF helper not available or failed: {e}")

            logger.warning("[WARN] ALCF_API_KEY not available")
            logger.debug("       Setup options:")
            logger.debug("         1. Set environment: export ALCF_API_KEY=$(python inference_auth_token.py get_access_token)")
            logger.debug("         2. Authenticate: python inference_auth_token.py authenticate")
            logger.debug("         3. Get helper: https://github.com/argonne-lcf/inference-endpoints")
            return config

        return config
    def auto_detect_model(self, config: AMReXAgentConfig) -> AMReXAgentConfig:
        """
        Auto-detect best available LLM model from CBORG.

        Call context: Used during configuration initialization after API keys load.

        Parameters
        ----------
        config : AMReXAgentConfig
            Configuration with API key set.

        Returns
        -------
        AMReXAgentConfig
            Updated configuration with llm_model selected.
        """
        # Only auto-detect for CBORG or ALCF providers
        if config.llm_provider not in {"cborg", "alcf"}:
            return config
        if config.llm_provider == "cborg" and not config.cborg_api_key:
            return config
        if config.llm_provider == "alcf" and not config.alcf_api_key:
            return config

        # Check if model already set in environment
        if config.llm_provider == "cborg":
            env_model = os.getenv("CBORG_MODEL")
            if env_model:
                logger.debug(f" Using CBORG_MODEL from environment: {env_model}")
                logger.info("Using LLM model: %s/%s", config.llm_provider, env_model)
                return config.model_copy(update={'llm_model': env_model})
        if config.llm_provider == "alcf":
            env_model = os.getenv("ALCF_MODEL")
            if env_model:
                logger.debug(f" Using ALCF_MODEL from environment: {env_model}")
                logger.info("Using LLM model: %s/%s", config.llm_provider, env_model)
                return config.model_copy(update={'llm_model': env_model})
        # If model already set, use it
        if config.llm_model:
            logger.info("Using LLM model: %s/%s", config.llm_provider, config.llm_model)
            return config

        # Discover and select best model
        try:
            from openai import OpenAI
            if config.llm_provider == "cborg":
                client = OpenAI(
                    api_key=config.cborg_api_key,
                    base_url=config.cborg_base_url
                )
            else:
                base_url = resolve_alcf_base_url(config)
                client = OpenAI(
                    api_key=config.alcf_api_key,
                    base_url=base_url
                )
            client = wrap_llm_client_with_retry(client, config)
            logger.debug(" Discovering available models...")
            models = client.models.list()
            available_models = [model.id for model in models]

            logger.debug(f"[ OK ] Found {len(available_models)} models")

            # Prefer LBL models > Llama > Claude > GPT
            if config.llm_provider == "cborg":
                preferred_models = [
                    'lbl/Llama-4-Scout-17B-16E-Instruct',  # Llama 4 Scout variant
                    'Llama-4-Scout-17B-16E-Instruct',      # Without lbl/ prefix
                    'lbl/llama',                            # LBL on-prem Llama
                    'lbl/cborg-chat',                       # LBL custom chat model
                    'llama-3.1-70b-instruct',               # Standard llama
                    'llama-3-70b-instruct',
                    'claude-sonnet-4',                      # Claude fallback
                    'openai/gpt-4o',                        # GPT-4o fallback
                ]
            else:
                preferred_models = [
                    'openai/gpt-oss-120b',
                    'gpt-oss-120b',
                    'meta-llama/Meta-Llama-3.1-70B-Instruct',
                    'Meta-Llama-3.1-70B-Instruct',
                    'meta-llama/Meta-Llama-3.1-8B-Instruct',
                    'Meta-Llama-3.1-8B-Instruct',
                ]
            selected_model = None
            for pref in preferred_models:
                for avail in available_models:
                    if pref.lower() in avail.lower():
                        selected_model = avail
                        break
                if selected_model:
                    break

            # Fall back to first model if no preference found
            if not selected_model and available_models:
                selected_model = available_models[0]

            if selected_model:
                logger.info("Using LLM model: %s/%s", config.llm_provider, selected_model)
                if config.llm_provider == "cborg":
                    logger.debug("       (Prefer LBL models > Anthropic > GPT)")
                else:
                    logger.debug("       (Prefer gpt-oss > Llama)")
                return config.model_copy(update={'llm_model': selected_model})
            else:
                logger.error("[ERROR] No suitable model found")
                return config

        except Exception as e:
            logger.error(f"[ERROR] Model auto-detection failed: {e}")
            logger.warning("[WARN] Will attempt to use default model on first query")
            return config

    def test_llm_connection(self, config: AMReXAgentConfig) -> bool:
        """
        Test LLM API connection.

        Call context: Used during configuration initialization to validate credentials.

        Parameters
        ----------
        config : AMReXAgentConfig
            Configuration with API key and model.

        Returns
        -------
        bool
            True if connection succeeded, otherwise False.
        """
        if config.llm_provider not in {"cborg", "alcf"}:
            return False
        if config.llm_provider == "cborg" and (not config.cborg_api_key or not config.llm_model):
            return False
        if config.llm_provider == "alcf" and (not config.alcf_api_key or not config.llm_model):
            return False

        try:
            from openai import OpenAI
            if config.llm_provider == "cborg":
                client = OpenAI(
                    api_key=config.cborg_api_key,
                    base_url=config.cborg_base_url
                )
            else:
                base_url = resolve_alcf_base_url(config)
                client = OpenAI(
                    api_key=config.alcf_api_key,
                    base_url=base_url
                )
            prompt = "Say 'OK' and nothing else."
            try:
                from database.configs.base_amrex_config import BaseAMReXConfig
                misc_prompts = BaseAMReXConfig.get_prompt_templates().get("misc", {})
                if isinstance(misc_prompts, dict):
                    prompt = misc_prompts.get("llm_connectivity_test", prompt)
            except Exception:
                prompt = prompt

            logger.debug(" Testing API connection...")
            response = client.chat.completions.create(
                model=config.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5
            )
            if config.llm_provider == "cborg":
                logger.debug("[ OK ] CBORG API connection successful")
            else:
                logger.debug("[ OK ] ALCF API connection successful")
            logger.debug(f"       Response: {response.choices[0].message.content}")
            return True

        except Exception as e:
            logger.error(f"[ERROR] CBORG API connection failed: {e}")
            return False

    def setup_environment_vars(self, config: AMReXAgentConfig) -> None:
        """
        Set up environment variables for utils.pele_tools.

        Call context: Used during configuration initialization before tools run.

        Parameters
        ----------
        config : AMReXAgentConfig
            Configuration to extract values from.

        Returns
        -------
        None
            Environment variables are updated in-place.
        """
        # Set PELE_REPORTS_DIR for utils.pele_tools
        if config.knowledge_base_path.exists():
            os.environ['PELE_REPORTS_DIR'] = str(config.knowledge_base_path.resolve())
            logger.debug(f" Set PELE_REPORTS_DIR={os.environ['PELE_REPORTS_DIR']}")

        # Set CBORG_API_KEY for utils.pele_tools (ask_pele_question uses it)
        if config.cborg_api_key:
            os.environ['CBORG_API_KEY'] = config.cborg_api_key
            logger.debug(" Set CBORG_API_KEY for pele_tools")

        if config.alcf_api_key:
            os.environ['ALCF_API_KEY'] = config.alcf_api_key
            logger.debug(" Set ALCF_API_KEY for pele_tools")

        if config.alcf_cluster:
            os.environ['ALCF_CLUSTER'] = config.alcf_cluster
            logger.debug(f" Set ALCF_CLUSTER={config.alcf_cluster}")

        if config.alcf_api_key or config.alcf_cluster or config.alcf_base_url:
            base_url = resolve_alcf_base_url(config)
            os.environ['ALCF_BASE_URL'] = base_url
            logger.debug(f" Set ALCF_BASE_URL={base_url}")
        # Set CBORG_MODEL if available
        if config.llm_model and config.llm_provider == "cborg":
            os.environ['CBORG_MODEL'] = config.llm_model
            logger.debug(f" Set CBORG_MODEL={config.llm_model}")
        if config.llm_model and config.llm_provider == "alcf":
            os.environ['ALCF_MODEL'] = config.llm_model
            logger.debug(f" Set ALCF_MODEL={config.llm_model}")
    def _load_config_file(self, config_path: Path) -> dict:
        """Load config overrides from JSON or YAML file."""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        suffix = config_path.suffix.lower()
        if suffix == ".json":
            import json
            return json.loads(config_path.read_text())
        if suffix in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:
                raise RuntimeError(
                    "PyYAML is required for YAML config files. "
                    "Install with `pip install pyyaml` or use JSON."
                ) from exc
            return yaml.safe_load(config_path.read_text()) or {}

        raise ValueError(f"Unsupported config file type: {config_path}")

    def _apply_overrides(self, config: AMReXAgentConfig, overrides: dict) -> AMReXAgentConfig:
        """Apply overrides from config file to AMReXAgentConfig."""
        if not overrides:
            return config
        allowed_keys = set(AMReXAgentConfig.model_fields.keys())
        # Support common aliases from config files.
        alias_map = {
            "AMREX_HOME": "amrex_repo_path",
            "AMReX_HOME": "amrex_repo_path",
            "AMREX_REPO_PATH": "amrex_repo_path",
            "amrex_home": "amrex_repo_path",
        }
        merged = dict(overrides)
        for alias_key, target_key in alias_map.items():
            if alias_key in merged and target_key not in merged:
                merged[target_key] = merged[alias_key]
        filtered = {k: v for k, v in merged.items() if k in allowed_keys}
        unknown = [k for k in merged if k not in allowed_keys]
        if unknown:
            logger.warning(f"Ignoring unknown config keys: {unknown}")
        return config.model_copy(update=filtered)

    def initialize(self, config_path: Path | None = None) -> AMReXAgentConfig:
        """
        Run the full configuration initialization flow.

        Call context: Primary entry point for building a ready-to-use config.

        Parameters
        ----------
        config_path : Path or None, optional
            Optional config file to apply as overrides.

        Returns
        -------
        AMReXAgentConfig
            Fully initialized configuration.
        """
        logger.debug("=== CBORG API Configuration ===\n")

        # Create base config
        config = AMReXAgentConfig()

        # Apply config file overrides (if provided)
        if config_path:
            overrides = self._load_config_file(Path(config_path))
            config = self._apply_overrides(config, overrides)
            config.model_post_init(None)

        # Load API keys
        config = self.load_api_keys(config)

        # Auto-detect model
        config = self.auto_detect_model(config)
        if config.llm_provider not in {"cborg", "alcf"} and config.llm_model:
            logger.info("Using LLM model: %s/%s", config.llm_provider, config.llm_model)

        # Test connection
        self.test_llm_connection(config)

        # Setup environment
        self.setup_environment_vars(config)

        logger.debug("\n" + "="*60 + "\n")

        return config
