"""Configuration for AMReXAgent."""

import os
import random
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Literal, List, Any
from pydantic import BaseModel, Field, ConfigDict


import logging

logger = logging.getLogger(__name__)
TRANSIENT_API_RECOVERY_TARGET = 0.95


def compute_transient_api_recovery_rate(outcomes: list[bool]) -> float | None:
    """Return recovery rate for transient retry events."""
    if not outcomes:
        return None
    recovered = sum(1 for outcome in outcomes if outcome)
    return recovered / len(outcomes)


def evaluate_transient_api_recovery_target(
    outcomes: list[bool],
    target: float = TRANSIENT_API_RECOVERY_TARGET,
) -> dict[str, Any]:
    """Evaluate whether transient API retries meet the configured recovery target."""
    try:
        target_value = float(target)
    except (TypeError, ValueError):
        target_value = TRANSIENT_API_RECOVERY_TARGET
    if not (0.0 < target_value <= 1.0):
        target_value = TRANSIENT_API_RECOVERY_TARGET

    recovery_rate = compute_transient_api_recovery_rate(outcomes)
    return {
        "transient_recovery_target": target_value,
        "transient_recovery_observations": len(outcomes),
        "transient_recovery_successes": sum(1 for outcome in outcomes if outcome),
        "transient_recovery_rate": recovery_rate,
        "transient_recovery_target_met": recovery_rate is not None and recovery_rate >= target_value,
    }

def should_stage_run(target_env: str | None, detected_env: str | None) -> bool:
    """Decide if runs need remote staging based on target vs detected environment."""
    if target_env is not None:
        target_env = target_env.strip().lower()
    if detected_env is not None:
        detected_env = detected_env.strip().lower()
    if target_env != "perlmutter":
        return False
    if detected_env is None:
        return False
    return detected_env != "perlmutter"
def _default_superfacility_account() -> str:
    return (
        os.getenv("SBATCH_ACCOUNT")
        or "amsc014"
    )

def detect_environment(env: dict = None) -> str:
    """Detect if running on Perlmutter, locally, or as MCP.
    
    Args:
        env: Environment variables dict. If None, uses os.environ.
             Allows dependency injection for testing.
    
    Returns:
        'perlmutter', 'mcp', or 'local'
    
    Examples:
        >>> detect_environment()  # Uses os.environ
        'local'
        >>> detect_environment({'NERSC_HOST': 'perlmutter'})
        'perlmutter'
    """
    if env is None:
        env = dict(os.environ)
    
    if env.get('NERSC_HOST'):
        return 'perlmutter'
    elif env.get('MCP_SERVER'):
        return 'mcp'
    else:
        return 'local'


def detect_hpc_system() -> tuple[str, str]:
    """Detect HPC site/system using environment and hostname hints."""
    import socket

    nersc_host = os.environ.get("NERSC_HOST")
    if nersc_host and nersc_host in ["perlmutter", "alvarez", "muller"]:
        return "nersc", "perlmutter"

    if os.environ.get("LMOD_SITE_NAME") == "OLCF":
        host_name = socket.getfqdn()
        if "frontier" in host_name:
            return "olcf", "frontier"
        if "crusher" in host_name:
            return "olcf", "crusher"

    fqdn = socket.getfqdn()
    if "alcf.anl.gov" in fqdn and "polaris" in fqdn:
        return "alcf", "polaris"

    return "unknown", "unknown"


def resolve_database_path(relative_path: str) -> Path:
    """Resolve database paths for different environments.

    Enables flexible deployment across Perlmutter, local development, and MCP server.
    Pattern inspired by foam-agent's multi-environment support.

    Priority:
    1. Environment variable override (AMREX_DATABASE_PATH, fallback PELE_DATABASE_PATH)
    2. Perlmutter: Absolute path to CFS directory
    3. Local: Relative to repo root (./database)
    4. MCP: User's home directory (~/.amrex_agent/database)

    Args:
        relative_path: Path relative to database root (e.g., 'faiss', 'reports')

    Returns:
        Resolved absolute Path

    Example:
        >>> resolve_database_path('faiss')  # Local
        PosixPath('/home/user/amrex_agent/database/faiss')

        >>> os.environ['AMREX_DATABASE_PATH'] = '/custom/path/database'
        >>> resolve_database_path('reports')
        PosixPath('/custom/path/database/reports')
    """
    # Priority 1: Allow override
    if override := os.getenv('AMREX_DATABASE_PATH') or os.getenv('PELE_DATABASE_PATH'):
        return Path(override) / relative_path

    env = detect_environment()

    if env == 'perlmutter':
        # Perlmutter-specific path (CFS filesystem)
        base = Path('/global/cfs/cdirs/amsc014/superfacility/amrex-agent/database')
        return base / relative_path

    elif env == 'mcp':
        # MCP: Use user's home directory
        return Path.home() / '.amrex_agent' / 'database' / relative_path

    else:  # local
        # Local development: relative to repo root
        repo_root = Path(__file__).parent.parent
        return repo_root / 'database' / relative_path


def _has_flat_faiss_artifacts(faiss_root: Path) -> bool:
    if not faiss_root.exists() or not faiss_root.is_dir():
        return False
    for child in faiss_root.iterdir():
        if child.name in {"cborg", "amsc"}:
            continue
        return True
    return False


def _move_path(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if not dst.exists():
        src.rename(dst)
        return
    if src.is_file():
        if not dst.exists():
            src.rename(dst)
        return

    for child in src.iterdir():
        target = dst / child.name
        if target.exists():
            continue
        shutil.move(str(child), str(target))
    try:
        src.rmdir()
    except OSError:
        pass


def migrate_flat_faiss_to_provider(
    faiss_root: Path,
    provider: str = "cborg",
) -> bool:
    if provider != "cborg":
        return False
    if not faiss_root.exists() or not faiss_root.is_dir():
        return False

    provider_root = faiss_root / provider
    provider_root.mkdir(parents=True, exist_ok=True)

    moved_static = _migrate_static_faiss_paths(faiss_root, provider_root)
    moved_solver_dirs = _migrate_solver_faiss_dirs(faiss_root, provider_root)
    return moved_static or moved_solver_dirs


def _migrate_static_faiss_paths(faiss_root: Path, provider_root: Path) -> bool:
    moved_any = False
    for name in ("level0", "level1", "level2", "build_session_manifest.json"):
        src = faiss_root / name
        if not src.exists():
            continue
        _move_path(src, provider_root / name)
        moved_any = True
    return moved_any


def _migrate_solver_faiss_dirs(faiss_root: Path, provider_root: Path) -> bool:
    moved_any = False
    for child in faiss_root.iterdir():
        if child.name in {"cborg", "amsc"}:
            continue
        if not child.is_dir() or "_" not in child.name:
            continue
        _move_path(child, provider_root / child.name)
        moved_any = True
    return moved_any


def resolve_faiss_db_path_for_provider(
    faiss_root: Path,
    provider: str | None,
) -> Path:
    provider_slug = (provider or "").strip().lower()
    if not provider_slug:
        return faiss_root

    provider_root = faiss_root / provider_slug
    if provider_root.exists():
        return provider_root

    if provider_slug == "cborg":
        migrate_flat_faiss_to_provider(faiss_root, provider_slug)
        if provider_root.exists():
            return provider_root

    if _has_flat_faiss_artifacts(faiss_root):
        return faiss_root
    return provider_root



ALCF_SOPHIA_BASE_URL = "https://inference-api.alcf.anl.gov/resource_server/sophia/vllm/v1"
ALCF_METIS_BASE_URL = "https://inference-api.alcf.anl.gov/resource_server/metis/api/v1"

def _resolve_alcf_base_url(cluster: Optional[str], explicit_base_url: Optional[str]) -> str:
    """Resolve ALCF base URL from explicit override or cluster selection."""
    if explicit_base_url:
        return explicit_base_url
    cluster_value = (cluster or os.getenv("ALCF_CLUSTER") or "").strip().lower()
    if cluster_value in {"metis", "meti"}:
        return ALCF_METIS_BASE_URL
    return ALCF_SOPHIA_BASE_URL

def _default_repo_root() -> Path:
    """Get default repository root for repo path defaults."""
    return Path(__file__).parent.parent.parent


def _repo_path_from_env(env_var: str, repo_name: str) -> Path:
    """Resolve repo path from env var with default fallback."""
    if env_var == "AMREX_REPO_PATH":
        env_value = (
            os.getenv(env_var)
            or os.getenv("AMReX_HOME")
            or os.getenv("AMREX_HOME")
        )
    else:
        env_value = os.getenv(env_var)
    default_path = str(_default_repo_root() / repo_name)
    return Path(env_value or default_path)


def resolve_benchmark_lockfile_path(
    lockfile: str | Path | None,
    *,
    repo_root: Path | None = None,
) -> Path:
    """Resolve benchmark lockfile path with repo-root fallback for relative inputs."""
    if lockfile is None:
        lockfile = Path("utils/environment-frozen.yaml")
    lockfile_path = Path(lockfile)
    if lockfile_path.is_absolute():
        return lockfile_path
    base = repo_root if repo_root is not None else Path(__file__).resolve().parents[1]
    return base / lockfile_path

class AMReXAgentConfig(BaseModel):
    """Central configuration for AMReXAgent.

    Manages AMReX solver paths, CBORG API, and Superfacility API.
    """
    
    # === LLM Configuration ===
    llm_provider: Literal["cborg", "alcf", "openai", "anthropic", "pnnl", "litellm"] = Field(
        default="cborg",
        description="LLM provider to use"
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Model name (auto-detected for CBORG)"
    )
    llm_fast_onprem_model: Optional[str] = Field(
        default="lbl/cborg-mini",
        description="Model name (auto-detected for CBORG)"
    )
    llm_fast_model: Optional[str] = Field(
        default="gcp/gpt-oss-120b-high",
        description="Model name (auto-detected for CBORG)"
    )
    llm_thinking_model: Optional[str] = Field(
        default="claude-sonnet-4-5",
        description="Model name (auto-detected for CBORG)"
    )
    llm_temperature: float = Field(
        default=0.1,
        description="Temperature for LLM generation"
    )
    llm_max_tokens: int = Field(
        default=4000,
        description="Max tokens for LLM responses"
    )
    
    # === CBORG API (LBL's LLM endpoint) ===
    cborg_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("CBORG_API_KEY"),
        description="CBORG API key (from env or ~/.nersc/cborg_api_key.txt)"
    )
    cborg_base_url: str = Field(
        default="https://api.cborg.lbl.gov/v1",
        description="CBORG API base URL"
    )

    # === ALCF Inference Endpoints (OpenAI-compatible) ===
    alcf_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ALCF_API_KEY"),
        description="ALCF access token (from env or inference_auth_token helper)"
    )
    alcf_cluster: Optional[str] = Field(
        default_factory=lambda: os.getenv("ALCF_CLUSTER"),
        description="ALCF cluster selector (sophia or metis)"
    )
    alcf_base_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("ALCF_BASE_URL"),
        description="ALCF API base URL override (optional; defaults by cluster)"
    )
    
    # === OpenAI/Anthropic API (fallback) ===
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY"),
        description="OpenAI API key"
    )
    anthropic_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"),
        description="Anthropic API key"
    )

    # === LiteLLM Proxy (OpenAI-compatible) ===
    litellm_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("LITELLM_API_KEY"),
        description="LiteLLM API key (optional; depends on proxy configuration)"
    )
    litellm_base_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("LITELLM_BASE_URL"),
        description="LiteLLM proxy base URL (OpenAI-compatible)"
    )
    
    # === PNNL AI API ===
    pnnl_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("LLM_API_KEY"),
        description="PNNL AI API key (from LLM_API_KEY env var)"
    )
    pnnl_base_url: str = Field(
        default="https://ai-incubator-api.pnnl.gov",
        description="PNNL AI API base URL"
    )
    pnnl_default_model: str = Field(
        default="claude-haiku-4-5-20251001-v1-birthright",
        description="Default model for PNNL AI API"
    )
    
    pelec_executable: Optional[Path] = Field(
        default_factory=lambda: Path(os.getenv("PELEC_EXECUTABLE", "")),
        description="Path to PeleC executable"
    )

    # === AMReX Code Paths (priority codes with well-documented inputs) ===

    # Combustion (primary)
    pelec_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("PELEC_REPO_PATH", "PeleC"),
        description="Path to PeleC repository"
    )
    pelelmex_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("PELELMEX_REPO_PATH", "PeleLMeX"),
        description="Path to PeleLMeX repository"
    )
    # Atmospheric (excellent docs)
    erf_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("ERF_REPO_PATH", "ERF"),
        description="Path to ERF repository (Energy Research and Forecasting)"
    )
    erf_executable_path: Optional[Path] = Field(
        default=None,
        description=(
            "Optional explicit ERF executable path. "
            "When unset, runners fall back to case-local search first, then "
            "derive a central ERF build directory (Exec/<group>)."
        ),
    )
    erf_central_build_dir: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("ERF_CENTRAL_BUILD_DIR", "ERF/Exec/RegTests"),
        description=(
            "Optional ERF central build directory used for executable lookup/compile "
            "fallbacks (for example: ERF/Exec/CanonicalFlows). "
            "Defaults to ERF/Exec/RegTests unless overridden by ERF_CENTRAL_BUILD_DIR."
        ),
    )

    # Plasma/Accelerator (very well documented)
    warpx_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("WARPX_REPO_PATH", "warpx"),
        description="Path to WarpX repository (laser-plasma accelerator)"
    )

    # Fluids (clean inputs)
    incflo_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("INCFLO_REPO_PATH", "incflo"),
        description="Path to incflo repository (incompressible flow)"
    )

    # Ocean modeling
    remora_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("REMORA_REPO_PATH", "REMORA"),
        description="Path to REMORA repository (Regional Ocean Modeling with AMReX)"
    )

    # Tutorials (best for learning)
    amrex_tutorials_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("AMREX_TUTORIALS_REPO_PATH", "amrex-tutorials"),
        description="Path to amrex-tutorials repository"
    )

    # AMReX Core (for native tools - Phase 5)
    amrex_repo_path: Optional[Path] = Field(
        default_factory=lambda: _repo_path_from_env("AMREX_REPO_PATH", "amrex"),
        description="Path to AMReX core repository (for native tools like fextract, fextrema, fsnapshot)"
    )


    # Generic repository map (AMReX generalization)
    repositories: Dict[str, Path] = Field(default_factory=dict)

    # === Knowledge Base ===
    knowledge_base_path: Path = Field(
        default_factory=lambda: resolve_database_path('reports'),
        description="Path to knowledge base (reports directory) - environment-aware"
    )

    pele_tools_path: Path = Field(
        default=Path("./utils/pele_tools.py"),
        description="Path to Pele-specific tools module"
    )

    # === FAISS Embeddings Configuration ===
    faiss_db_path: Path = Field(
        default_factory=lambda: resolve_database_path('faiss'),
        description="Path to FAISS vector indices directory - environment-aware"
    )

    database_mismatch_policy: Literal[
        "auto_rebuild",
        "warn_continue",
        "fail",
    ] = Field(
        default="warn_continue",
        description=(
            "Policy when solver schema repo_commits do not match sibling repo HEADs. "
            "warn_continue: log and proceed. "
            "fail: raise with rebuild command. "
            "auto_rebuild: trigger rebuild and proceed."
        ),
    )

    environment: str = Field(
        default_factory=detect_environment,
        description="Deployment environment (perlmutter, local, mcp)"
    )

    embedding_provider: str = Field(
        default="cborg",
        description="Embedding model provider (cborg, alcf, openai, huggingface)"
    )

    vector_store_backend: Literal["auto", "faiss_local", "faiss_download", "openai"] = Field(
        default="auto",
        description="Vector store backend for retrieval: auto (prefer hosted if configured), "
                    "faiss_local (local indices), faiss_download (download published FAISS artifacts), "
                    "openai (hosted vector store)."
    )

    faiss_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model name (for OpenAI fallback if CBORG unavailable)"
    )

    alcf_embedding_model: Optional[str] = Field(
        default_factory=lambda: os.getenv("ALCF_EMBEDDING_MODEL"),
        description="Embedding model name for ALCF (optional override)"
    )

    openai_vector_store_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_VECTOR_STORE_ID"),
        description="OpenAI hosted vector store ID (single-store mode)"
    )

    openai_vector_store_ids: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-index OpenAI vector store IDs (index_name -> vector store ID)"
    )

    openai_base_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE"),
        description="OpenAI API base URL override (optional)"
    )

    vector_store_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for published FAISS artifacts (used with faiss_download)"
    )

    vector_store_manifest_url: Optional[str] = Field(
        default=None,
        description="Manifest URL for published FAISS artifacts (overrides base URL)"
    )

    faiss_topk: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of top results to retrieve from FAISS"
    )

    faiss_cache_enabled: bool = Field(
        default=True,
        description="Cache loaded FAISS indices in memory (foam-agent pattern)"
    )

    faiss_fallback_to_llm: bool = Field(
        default=True,
        description="Fall back to LLM queries if FAISS indices unavailable (hybrid approach). "
                    "NOTE: With FAISS-first architecture, LLM reports are optional enhancement. "
                    "Set to False to require FAISS indices (fail if unavailable)."
    )

    embedding_chunk_size_chars: int = Field(
        default=2000,
        ge=0,
        description="Chunk size in characters for embedding documents (0 disables chunking)."
    )

    embedding_rate_limit_rpm: int = Field(
        default=20,
        ge=0,
        description="Rate limit for embedding batches in requests per minute (0 disables)."
    )

    embedding_retry_max_attempts: int = Field(
        default=50,
        ge=1,
        description="Max retry attempts for embedding batches (1 disables retries)."
    )

    llm_retry_max_attempts: int = Field(
        default=3,
        ge=1,
        description="Max retry attempts for LLM chat completions (1 disables retries)."
    )

    faiss_semantic_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for FAISS semantic scoring in architect service (co-primary with metrics). "
                    "Was 0.20 (hybrid), now 0.5 (FAISS-first architecture)."
    )

    # === Baseline Selection Weights (Benchmark Tuning) ===
    simple_weight_kb_relevance: float = Field(
        default=0.40,
        ge=0.0,
        description="Simple strategy baseline weight: knowledge-base relevance bucket."
    )
    simple_weight_metrics: float = Field(
        default=0.25,
        ge=0.0,
        description="Simple strategy baseline weight: case metrics bucket."
    )
    simple_weight_path_heuristics: float = Field(
        default=0.10,
        ge=0.0,
        description="Simple strategy baseline weight: path heuristics bucket."
    )
    simple_weight_domain_specific: float = Field(
        default=0.25,
        ge=0.0,
        description="Simple strategy baseline weight: domain-specific bucket."
    )
    simple_weight_faiss_semantic: float = Field(
        default=0.50,
        ge=0.0,
        description="Simple strategy baseline weight: FAISS semantic bucket."
    )
    simple_case_hint_min_total: float = Field(
        default=0.00,
        ge=0.0,
        description=(
            "Simple strategy threshold gate for LLM-selected case promotion: "
            "minimum total score required for the hinted case."
        ),
    )
    simple_case_hint_max_gap: float = Field(
        default=0.14,
        ge=0.0,
        description=(
            "Simple strategy threshold gate for LLM-selected case promotion: "
            "maximum allowed score gap between top candidate and hinted case."
        ),
    )
    simple_case_hint_score_boost: float = Field(
        default=0.20,
        ge=0.0,
        description=(
            "Simple strategy score boost applied to the LLM-selected case hint "
            "before threshold comparison."
        ),
    )

    hierarchical_weight_physics_parameters: float = Field(
        default=0.30,
        ge=0.0,
        description="Hierarchical strategy baseline weight: physics_parameters index."
    )
    hierarchical_weight_grid_specifications: float = Field(
        default=0.20,
        ge=0.0,
        description="Hierarchical strategy baseline weight: grid_specifications index."
    )
    hierarchical_weight_development_activity: float = Field(
        default=0.10,
        ge=0.0,
        description="Hierarchical strategy baseline weight: development_activity index."
    )
    hierarchical_weight_configuration_complexity: float = Field(
        default=0.10,
        ge=0.0,
        description="Hierarchical strategy baseline weight: configuration_complexity index."
    )
    hierarchical_weight_path_hierarchy: float = Field(
        default=0.15,
        ge=0.0,
        description="Hierarchical strategy baseline weight: path_hierarchy index."
    )
    hierarchical_weight_domain_models: float = Field(
        default=0.10,
        ge=0.0,
        description="Hierarchical strategy baseline weight: domain_models index."
    )
    hierarchical_weight_resource_requirements: float = Field(
        default=0.05,
        ge=0.0,
        description="Hierarchical strategy baseline weight: resource_requirements index."
    )

    # === Indexing Strategy Configuration ===
    indexing_strategy: Literal["simple", "hierarchical", "override_static"] = Field(
        default="simple",
        description="Indexing strategy for baseline selection. "
                    "'simple' uses development's working single FAISS search (proven e2e). "
                    "'hierarchical' uses integration_ladder's L0/L1/L2 multi-index approach (experimental). "
                    "'override_static' skips L0/L1/L2 and uses raw docs/inputs (requires baseline_override)."
    )

    level2_override_enabled: bool = Field(
        default=True,
        description="Enable Level-2 case-name override of Level-0 solver selection for low-confidence L0 matches."
    )
    level2_override_l0_threshold: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Apply Level-2 case-name override only when Level-0 solver confidence is below this threshold."
    )
    level2_override_case_match_threshold: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Minimum normalized case-name match confidence required for Level-2 override."
    )
    level2_override_min_metadata_hits: int = Field(
        default=3,
        ge=1,
        description="Minimum number of Level-2 metadata files that must contain the matched case."
    )
    
    inputs_file_strategy: Literal["oldest", "newest", "smallest", "llm_compare", "override"] = Field(
        default="newest",
        description="Inputs file selection strategy. "
                    "'oldest' selects most mature file (by git age). "
                    "'newest' selects latest file (most up-to-date). "
                    "'smallest' selects simplest file (by file size). "
                    "'llm_compare' asks the LLM to choose between candidates. "
                    "'override' uses inputs_file_override or falls back to 'inputs' if present."
    )

    remap_strategy: Literal["last_write", "append"] = Field(
        default="last_write",
        description="Duplicate array merge strategy during parameter remap/apply. "
                    "'last_write' keeps the latest value (default). "
                    "'append' concatenates array values when duplicates appear."
    )

    inputs_file_override: Optional[str] = Field(
        default=None,
        description="Explicit inputs file to use (absolute path or relative to case directory). "
                    "When set, bypasses inputs file selection."
    )

    inputs_default_precedence: Literal["default_first", "strategy_first"] = Field(
        default="strategy_first",
        description="Precedence between config default inputs and strategy selection. "
                    "'default_first' uses default_inputs_path before strategy selection; "
                    "'strategy_first' tries strategy first and only falls back to defaults."
    )

    retry_guidance_use_llm: bool = Field(
        default=False,
        description="If True, use LLM assistance to refine retry guidance for inputs/baseline switching."
    )
    enable_intent_extraction: bool = Field(
        default=False,
        description="Enable Intent Extraction node LLM parsing of prompt into structured simulation config."
    )
    enable_sweep_orchestration: bool = Field(
        default=False,
        description="Enable sweep fan-out orchestration for parameter studies."
    )
    enable_clarification_subgraph: bool = Field(
        default=False,
        description="Enable clarification subgraph decision checks before input writing."
    )

    llm_gate_strategy: Literal[
        "off",
        "default",
        "feedback",
        "gate-major",
        "gate-all",
        "gate-major-prompt",
        "gate-all-prompt",
    ] = Field(
        default="off",
        description="LLM prompt gate strategy: off, default, feedback, gate-major, gate-all."
    )
    llm_gate_auto_approve: bool = Field(
        default=False,
        description="Auto-approve LLM prompt gates without prompting."
    )

    disable_embeddings: bool = Field(
        default=False,
        description="Disable embedding initialization and FAISS usage (forces non-embedding paths)."
    )

    baseline_switch_after_retries: int = Field(
        default=3,
        ge=1,
        description="Number of retry cycles to attempt fixing inputs/mods before switching baseline directory."
    )
    
    baseline_override: Optional[str] = Field(
        default=None,
        description="Force specific baseline case (overrides automatic selection). "
                    "Format: 'Code/Exec/Path/Case' or 'Exec/Path/Case'. "
                    "Example: 'PeleLMeX/Exec/Production/JetInCrossflow' or 'Exec/Production/JetFlame'. "
                    "When set, skips L2 baseline selection and uses this case directly."
    )

    dry_run: bool = Field(
        default=False,
        description="If True, generate scripts without executing external runs."
    )

    preconfirm_gate: bool = Field(
        default=False,
        description="If True, pause in terminal for a pre-confirmation gate before validation."
    )
    preconfirm_gate_auto_approve: bool = Field(
        default=False,
        description="Auto-approve pre-confirmation gates without prompting."
    )

    run_mode: Literal["dry", "stage", "submit", "full"] = Field(
        default="full",
        description="Run execution strategy: dry (scripts only), stage (stage inputs only), "
                    "submit (submit job only), full (stage + submit)."
    )

    # === Phase 4: Container and Analysis Configuration ===
    container_mode: bool = Field(
        default_factory=lambda: bool(os.getenv('PODMAN_HPC') or os.getenv('SHIFTER')),
        description="Enable container-aware mode for headless extraction/rendering split. "
                    "Auto-detected from PODMAN_HPC or SHIFTER env variables. "
                    "When True, visualization uses extraction (headless) + rendering (local) workflow."
    )

    analysis_always_enabled: bool = Field(
        default=True,
        description="Always run analysis after simulation completion (Phase 4 user decision). "
                    "Analysis detects CFL violations, NaN, convergence issues."
    )
    allow_make_introspection: bool = Field(
        default=False,
        description="Allow running make commands to extract build variables for analysis heuristics."
    )
    make_introspection_command: Optional[List[str]] = Field(
        default=None,
        description="Optional command (argv) to run for make introspection. "
                    "When None, analysis falls back to 'make help' with inferred flags."
    )

    visualization_backend: str = Field(
        default='auto',
        description="Visualization backend: 'auto' (Phase 5: AMReX tools → pyamrex → yt), "
                    "'amrex_tools', 'pyamrex', 'yt'. "
                    "Phase 4: yt-only. Phase 5: Multi-backend with auto-selection."
    )

    amrex_tools_path: Optional[Path] = Field(
        default=None,
        description="Path to AMReX tools directory (overrides auto-detection from amrex_repo_path). "
                    "When None, tools are auto-detected from config.amrex_repo_path/Tools/Plotfile."
    )

    # === Superfacility API ===
    # Superfacility
    superfacility_account: str = Field(
        default_factory=_default_superfacility_account,
        description="Default NERSC account to use for submission."
    )
    
    superfacility_client_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPERFACILITY_CLIENT_ID"),
        description="NERSC Superfacility API client ID"
    )
    superfacility_secret: Optional[str] = Field(
        default_factory=lambda: os.getenv("SUPERFACILITY_SECRET"),
        description="NERSC Superfacility API secret"
    )
    superfacility_endpoint: str = Field(
        default="https://api.nersc.gov/api/v1.2",
        description="Superfacility API endpoint"
    )

    remote_output_dir: Optional[Path] = Field(
        default=None,
        description="Remote output directory for staged runs (defaults to output_dir)."
    )
    remote_run_dir: Optional[Path] = Field(
        default=None,
        description="Optional fixed remote run directory (overrides remote_output_dir/run_name)."
    )
    remote_executable_path: Optional[Path] = Field(
        default=None,
        description="Absolute path to a prebuilt executable on the remote system."
    )
    remote_executable_template: Optional[str] = Field(
        default=None,
        description=(
            "Template for remote executable path "
            "(supports {case_dir}, {case_dir_name}, {repo_name}, {solver_name})."
        )
    )
    remote_executable_find: bool = Field(
        default=True,
        description="If True, attempt to discover a remote executable when template/path are not set."
    )
    remote_staging_method: str = Field(
        default="auto",
        description="Remote staging method: auto (sfapi_client then REST upload), "
                    "sfapi_client, or rest_upload."
    )
    monitor_job: bool = Field(
        default=True,
        description="Monitor remote submissions until completion."
    )
    stage_out_outputs: bool = Field(
        default=True,
        description="Stage back output logs and plotfiles after remote completion."
    )

    workflow_store_path: Path = Field(
        default_factory=lambda: Path.home() / ".amrex_agent" / "workflow_store.db",
        description="SQLite path for MCP workflow session persistence."
    )
    
    # === Workflow Settings ===
    max_iterations: int = Field(
        default=3,
        description="Max error correction iterations"
    )
    allow_local_run: bool = Field(
        default=True,
        description="Allow local execution if Superfacility unavailable"
    )
    use_mpi: bool = Field(
        default=True,
        description="Use MPI for local runs when available."
    )
    mpi_ranks: int = Field(
        default=1,
        ge=1,
        description="Number of MPI ranks for local runs (mpirun -np)."
    )
    
    # === Output Settings ===
    output_dir: Path = Field(
        default=Path("./output"),
        description="Base output directory for simulations"
    )
    metrics_output_dir: Optional[Path] = Field(
        default=None,
        description="Directory for metrics.jsonl when run_directory is unavailable (defaults to output_dir)."
    )
    metrics_filename: str = Field(
        default="metrics.jsonl",
        description="Metrics JSONL filename for workflow summaries."
    )
    privacy_mode: Literal["off", "shared", "strict"] = Field(
        default="off",
        description="Privacy mode for prompt/log persistence: off, shared, or strict."
    )
    privacy_scrubber: Literal["builtin", "scrubadub", "presidio"] = Field(
        default="builtin",
        description="Scrubber backend for privacy modes: builtin, scrubadub, or presidio."
    )
    privacy_hash_salt: Optional[str] = Field(
        default_factory=lambda: os.getenv("AMREX_PRIVACY_SALT"),
        description="Optional salt for prompt hashing in privacy modes."
    )
    write_policy_mode: str = Field(
        default="warn",
        description="Filesystem write policy mode: off, warn, or deny."
    )
    allow_write_paths: List[Path] = Field(
        default=[],
        description="Optional allowlist of writable path roots."
    )
    require_run_dir_prefix: bool = Field(
        default=False,
        description="Require run directories to start with run_dir_prefix."
    )
    run_dir_prefix: str = Field(
        default="run_",
        description="Prefix required for run directories when require_run_dir_prefix is true."
    )
    save_intermediate: bool = Field(
        default=True,
        description="Save intermediate results (plans, configs, etc.)"
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection and JSONL output"
    )
    benchmark_environment_lockfile: Path = Field(
        default=Path("utils/environment-frozen.yaml"),
        description="Benchmark environment lockfile path (relative to repo root or absolute).",
    )
    benchmark_require_lockfile: bool = Field(
        default=True,
        description="Require benchmark environment lockfile to exist.",
    )

    # === Validator Configuration ===
    disabled_validators: List[str] = Field(
        default=[],
        description="List of validator names to disable"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def available_solvers(self) -> List[str]:
        """Get list of all configured solver names from registry"""
        from database.configs import discover_code_configs
        return [c.code_name for c in discover_code_configs()]

    @property
    def default_solver(self) -> Optional[str]:
        """First available solver (for fallback only - prefer explicit selection)"""
        solvers = self.available_solvers
        return solvers[0] if solvers else None

    def get_code_registry(self) -> Dict[str, Any]:
        """Get dict mapping code_name -> config class"""
        from database.configs import discover_code_configs
        return {c.code_name: c for c in discover_code_configs()}

    def detect_hpc_system(self) -> tuple[str, str]:
        """Detect HPC site/system using shared config helper."""
        return detect_hpc_system()

    def should_stage_run(self, detected_env: str | None = None) -> bool:
        """Decide if a run should be staged based on target vs detected environment."""
        if detected_env is None:
            detected_env = detect_environment()
        return should_stage_run(getattr(self, "environment", None), detected_env)

    @property
    def amrex_agent_root(self) -> Path:
        """Root directory of amrex_agent (where src/ is).
        
        Finds project root by looking for marker files (pyproject.toml, setup.py)
        to be robust to file location changes.
        """
        current = Path(__file__).resolve()
        # Look for project markers
        for parent in [current.parent, current.parent.parent, current.parent.parent.parent]:
            if (parent / 'pyproject.toml').exists() or (parent / 'setup.py').exists():
                return parent
        # Fallback: assume config.py is in src/
        return Path(__file__).parent.parent

    def model_post_init(self, __context: Any) -> None:
        """Populate repositories dict from individual paths."""
        fields_set = getattr(self, "model_fields_set", set())
        if self.indexing_strategy == "override_static":
            if "disable_embeddings" not in fields_set and not self.disable_embeddings:
                self.disable_embeddings = True
                logger.info("[Config] override_static sets disable_embeddings=True by default")
            elif "disable_embeddings" in fields_set and not self.disable_embeddings:
                logger.warning(
                    "[Config] override_static with disable_embeddings=False; embeddings may initialize unexpectedly"
                )
        elif "disable_embeddings" in fields_set and self.disable_embeddings:
            logger.warning(
                "[Config] disable_embeddings=True while indexing_strategy=%s; embeddings will be disabled",
                self.indexing_strategy,
            )

        allowed_run_modes = {"dry", "stage", "submit", "full"}
        run_mode = getattr(self, "run_mode", "full")
        if run_mode not in allowed_run_modes:
            raise ValueError(f"Invalid run_mode: {run_mode}")
        run_mode_set = "run_mode" in fields_set
        dry_run_set = "dry_run" in fields_set
        if run_mode_set:
            if run_mode == "dry" and not self.dry_run:
                self.dry_run = True
            elif run_mode != "dry" and self.dry_run:
                if dry_run_set:
                    logger.warning(
                        "[Config] dry_run=True ignored because run_mode=%s",
                        run_mode,
                    )
                self.dry_run = False
        elif self.dry_run:
            self.run_mode = "dry"

        repo_root = Path(__file__).resolve().parents[1]
        resolved_lockfile = resolve_benchmark_lockfile_path(
            self.benchmark_environment_lockfile,
            repo_root=repo_root,
        )
        self.benchmark_environment_lockfile = resolved_lockfile
        if self.benchmark_require_lockfile and not resolved_lockfile.exists():
            raise ValueError(f"benchmark_environment_lockfile_missing: {resolved_lockfile}")

        if "faiss_db_path" not in fields_set:
            faiss_root = resolve_database_path("faiss")
            self.faiss_db_path = resolve_faiss_db_path_for_provider(
                faiss_root=faiss_root,
                provider=self.embedding_provider,
            )

        self.repositories = {
            'PeleC': self.pelec_repo_path,
            'PeleLMeX': self.pelelmex_repo_path,
            'ERF': self.erf_repo_path,
            'WarpX': self.warpx_repo_path,
            'incflo': self.incflo_repo_path,
            'REMORA': self.remora_repo_path,
            'amrex-tutorials': self.amrex_tutorials_repo_path,
            'AMReX': self.amrex_repo_path,
        }
        # Remove None values
        self.repositories = {k: v for k, v in self.repositories.items() if v}

    def get_benchmark_environment_contract(self) -> dict[str, Any]:
        """Return benchmark reproducibility contract metadata."""
        lockfile_path = resolve_benchmark_lockfile_path(self.benchmark_environment_lockfile)
        lockfile_exists = lockfile_path.exists()
        return {
            "isolation_mode": "container",
            "reproducible_by_default": True,
            "lockfile_path": str(lockfile_path),
            "lockfile_exists": lockfile_exists,
            "lockfile_required": bool(self.benchmark_require_lockfile),
        }

    def test_connection(self) -> None:
        """DEPRECATED: Use ConfigService.initialize() instead.
        
        This method has side effects (mutates self, makes API calls, modifies os.environ).
        It is maintained for backward compatibility only.
        
        New pattern:
            from src.services.config_service import ConfigService
            service = ConfigService()
            config = service.initialize()
        """
        import warnings
        warnings.warn(
            "AMReXAgentConfig.test_connection() is deprecated. "
            "Use ConfigService().initialize() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        from src.services.config_service import ConfigService
        service = ConfigService(verbose=True)
        
        # Mutate self (legacy behavior)
        updated = service.load_api_keys(self)
        self.cborg_api_key = updated.cborg_api_key
        
        updated = service.auto_detect_model(updated)
        self.llm_model = updated.llm_model
        
        service.test_llm_connection(updated)
    
    def setup_environment(self) -> None:
        """DEPRECATED: Use ConfigService.setup_environment_vars() instead.
        
        This method has side effects (modifies os.environ).
        It is maintained for backward compatibility only.
        
        New pattern:
            from src.services.config_service import ConfigService
            service = ConfigService()
            service.setup_environment_vars(config)
        """
        import warnings
        warnings.warn(
            "AMReXAgentConfig.setup_environment() is deprecated. "
            "Use ConfigService().setup_environment_vars() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        from src.services.config_service import ConfigService
        service = ConfigService(verbose=True)
        service.setup_environment_vars(self)
    
def load_config(config_path: Optional[Path] = None) -> AMReXAgentConfig:
    """Load configuration with auto-detection and validation.
    
    DEPRECATED: Use ConfigService().initialize() instead.
    
    This function is maintained for backward compatibility but will be
    removed in a future version. The new pattern separates config data
    from initialization logic.
    
    Old pattern:
        config = load_config()  # Side effects hidden
    
    New pattern:
        from src.services.config_service import ConfigService
        service = ConfigService()
        config = service.initialize()  # Side effects explicit
    
    For tests (no side effects):
        config = AMReXAgentConfig(cborg_api_key="test", llm_model="test")
    
    Config loading with CBORG auto-setup.
    """
    import warnings
    warnings.warn(
        "load_config() is deprecated. Use ConfigService().initialize() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    from src.services.config_service import ConfigService
    service = ConfigService()
    return service.initialize(config_path=config_path)

def resolve_alcf_base_url(config: AMReXAgentConfig) -> str:
    """Resolve ALCF base URL using config and environment."""
    return _resolve_alcf_base_url(config.alcf_cluster, config.alcf_base_url)


def _provider_fallback_order(primary_provider: str) -> list[str]:
    """Return deterministic provider order beginning with the configured provider."""
    providers = ["cborg", "alcf", "openai", "pnnl", "litellm", "amsc-i2", "anthropic"]
    if primary_provider not in providers:
        raise ValueError(f"Unknown LLM provider: {primary_provider}")
    order = [primary_provider]
    for provider in providers:
        if provider != primary_provider:
            order.append(provider)
    return order


def _missing_provider_dependency_reason(config: AMReXAgentConfig, provider: str) -> str | None:
    """Return missing dependency reason for provider, or None when ready to initialize."""
    if provider == "cborg":
        return None if config.cborg_api_key else "CBORG_API_KEY not set"
    if provider == "alcf":
        return None if config.alcf_api_key else "ALCF_API_KEY not set"
    if provider == "openai":
        return None if config.openai_api_key else "OPENAI_API_KEY not set"
    if provider == "anthropic":
        return "Anthropic provider not yet implemented"
    if provider == "pnnl":
        return None if config.pnnl_api_key else "LLM_API_KEY environment variable not set for PNNL AI API"
    if provider == "litellm":
        if not config.litellm_base_url:
            return "LITELLM_BASE_URL not set"
        if config.llm_model or os.getenv("LITELLM_MODEL"):
            return None
        return "llm_model not set for LiteLLM provider"
    if provider == "amsc-i2":
        base_url = config.litellm_base_url or os.getenv("AMSC_I2_BASE_URL")
        if not base_url:
            return "LITELLM_BASE_URL or AMSC_I2_BASE_URL not set for amsc-i2 provider"
        api_key = config.litellm_api_key or os.getenv("AMSC_I2_API_KEY")
        if not api_key:
            return "LITELLM_API_KEY or AMSC_I2_API_KEY not set for amsc-i2 provider"
        return None
    return f"Unknown LLM provider: {provider}"


def _build_llm_client_for_provider(config: AMReXAgentConfig, provider: str, openai_client_cls):
    """Build client for a specific provider once dependencies are satisfied."""
    if provider == "cborg":
        client = openai_client_cls(
            api_key=config.cborg_api_key,
            base_url=config.cborg_base_url
        )

        # Auto-detect model if not set
        if not config.llm_model:
            models = client.models.list()
            available = [m.id for m in models]

            # Prefer LBL models > Llama > Claude > GPT
            preferred = [
                'lbl/Llama-4-Scout-17B-16E-Instruct',
                'Llama-4-Scout-17B-16E-Instruct',
                'lbl/llama',
                'llama-3.1-70b-instruct',
                'claude-sonnet-4',
            ]

            for pref in preferred:
                for avail in available:
                    if pref.lower() in avail.lower():
                        config.llm_model = avail
                        logger.info(f" Auto-selected model: {avail}")
                        break
                if config.llm_model:
                    break

            if not config.llm_model and available:
                config.llm_model = available[0]
                logger.info(f" Using first available model: {config.llm_model}")

        return client

    if provider == "alcf":
        base_url = resolve_alcf_base_url(config)
        return openai_client_cls(
            api_key=config.alcf_api_key,
            base_url=base_url,
        )

    if provider == "openai":
        return openai_client_cls(api_key=config.openai_api_key)

    if provider == "anthropic":
        raise NotImplementedError("Anthropic provider not yet implemented")

    if provider == "pnnl":
        # Use default model if not explicitly set
        if not config.llm_model:
            config.llm_model = config.pnnl_default_model
            logger.info(f" Using PNNL default model: {config.llm_model}")
        return openai_client_cls(
            api_key=config.pnnl_api_key,
            base_url=config.pnnl_base_url
        )

    if provider == "litellm":
        if not config.llm_model:
            env_model = os.getenv("LITELLM_MODEL")
            if env_model:
                config.llm_model = env_model
        api_key = config.litellm_api_key or "litellm"
        return openai_client_cls(
            api_key=api_key,
            base_url=config.litellm_base_url
        )

    if provider == "amsc-i2":
        if not config.llm_model:
            config.llm_model = (
                os.getenv("AMSC_I2_MODEL")
                or os.getenv("LITELLM_MODEL")
                or "claude-sonnet-4-5"
            )
        api_key = config.litellm_api_key or os.getenv("AMSC_I2_API_KEY") or "litellm"
        base_url = config.litellm_base_url or os.getenv("AMSC_I2_BASE_URL")
        return openai_client_cls(
            api_key=api_key,
            base_url=base_url,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


def get_llm_client(config: AMReXAgentConfig) -> Any:
    """Get LLM client based on config
    
    Returns OpenAI-compatible client (CBORG, ALCF, OpenAI, or Anthropic)
    """
    from openai import OpenAI
    configured_provider = config.llm_provider
    primary_error: Exception | None = None

    for provider in _provider_fallback_order(configured_provider):
        reason = _missing_provider_dependency_reason(config, provider)
        if reason:
            error = NotImplementedError(reason) if provider == "anthropic" else ValueError(reason)
            if provider == configured_provider:
                # Compatibility policy:
                # - Anthropic without explicit Anthropic credentials may fallback.
                # - CBORG missing key may fallback to other configured providers.
                # - Explicit LiteLLM misconfiguration should fail fast.
                if provider == "anthropic" and not bool(getattr(config, "anthropic_api_key", None)):
                    primary_error = error
                    continue
                if provider == "cborg" and "CBORG_API_KEY not set" in reason:
                    primary_error = error
                    continue
                raise error
            continue

        try:
            client = _build_llm_client_for_provider(config, provider, OpenAI)
            if provider != configured_provider:
                logger.warning(
                    "[Config] Falling back LLM provider from %s to %s",
                    configured_provider,
                    provider,
                )
                config.llm_provider = provider
            return _wrap_llm_client_if_needed(client, config)
        except Exception as error:
            if provider == configured_provider:
                raise error
            logger.warning(
                "[Config] LLM provider %s initialization failed: %s",
                provider,
                error,
            )

    if primary_error:
        raise primary_error
    raise ValueError(f"Unknown LLM provider: {configured_provider}")


def _wrap_llm_client_if_needed(client, config: AMReXAgentConfig):
    client = _wrap_llm_client_with_retry(client, config)
    client = _wrap_llm_client_with_metrics(client, config)
    strategy = getattr(config, "llm_gate_strategy", "off") or "off"
    if strategy == "off":
        return client
    auto_approve = getattr(config, "llm_gate_auto_approve", False) is True
    return _LLMGateClient(client, strategy, auto_approve)


def _wrap_llm_client_with_retry(client, config: AMReXAgentConfig):
    raw_attempts = getattr(config, "llm_retry_max_attempts", 1)
    try:
        max_attempts = int(raw_attempts)
    except (TypeError, ValueError):
        max_attempts = 1
    if max_attempts <= 1:
        return client
    if isinstance(client, _LLMRetryClient):
        return client
    return _LLMRetryClient(client, max_attempts)


def _wrap_llm_client_with_metrics(client, config: AMReXAgentConfig):
    if getattr(config, "metrics_enabled", True) is False:
        return client
    if not getattr(client, "chat", None):
        return client
    if not getattr(getattr(client, "chat", None), "completions", None):
        return client
    if isinstance(client, _LLMMetricsClient):
        return client
    return _LLMMetricsClient(client, config)


def wrap_llm_client(client: Any, config: AMReXAgentConfig) -> Any:
    """Public helper to apply LLM gating to an existing client instance."""
    return _wrap_llm_client_if_needed(client, config)


def wrap_llm_client_with_retry(client: Any, config: AMReXAgentConfig) -> Any:
    """Public helper to apply retry behavior without LLM gating."""
    return _wrap_llm_client_with_retry(client, config)


def unwrap_llm_client(client: Any) -> Any:
    """Return the underlying client if wrapped by the LLM gate."""
    wrapped_types = (_LLMGateClient, _LLMRetryClient, _LLMMetricsClient)
    current = client
    while isinstance(current, wrapped_types):
        current = current._client
    return current


class _LLMRetryClient:
    def __init__(self, client, max_attempts: int) -> None:
        self._client = client
        self._max_attempts = max_attempts
        self.chat = _LLMRetryChat(client.chat, max_attempts)

    def __getattr__(self, name: str):
        return getattr(self._client, name)


class _LLMMetricsClient:
    def __init__(self, client, config: AMReXAgentConfig) -> None:
        self._client = client
        self._config = config
        self.chat = _LLMMetricsChat(client.chat, config)

    def __getattr__(self, name: str):
        return getattr(self._client, name)


class _LLMMetricsChat:
    def __init__(self, chat_resource, config: AMReXAgentConfig) -> None:
        self._chat = chat_resource
        self._config = config
        self.completions = _LLMMetricsCompletions(chat_resource.completions, config)

    def __getattr__(self, name: str):
        return getattr(self._chat, name)


class _LLMMetricsCompletions:
    def __init__(self, completions_resource, config: AMReXAgentConfig) -> None:
        self._completions = completions_resource
        self._config = config

    def create(self, *args: Any, **kwargs: Any) -> Any:
        response = self._completions.create(*args, **kwargs)
        try:
            from src.utils.metrics import metrics_collector

            metrics_collector.record_llm_usage(
                response,
                model=kwargs.get("model"),
                provider=getattr(self._config, "llm_provider", None),
            )
        except Exception:
            pass
        return response


class _LLMRetryChat:
    def __init__(self, chat_resource, max_attempts: int) -> None:
        self._chat = chat_resource
        self._max_attempts = max_attempts
        self.completions = _LLMRetryCompletions(chat_resource.completions, max_attempts)

    def __getattr__(self, name: str):
        return getattr(self._chat, name)


class _LLMRetryCompletions:
    def __init__(self, completions_resource, max_attempts: int) -> None:
        self._completions = completions_resource
        self._max_attempts = max_attempts
        self._retryable_statuses = {429, 500, 502, 503}
        self._transient_recovery_outcomes: list[bool] = []

    def get_transient_recovery_target_status(
        self,
        target: float = TRANSIENT_API_RECOVERY_TARGET,
    ) -> dict[str, Any]:
        """Return benchmark-style recovery metrics for transient retries."""
        return evaluate_transient_api_recovery_target(self._transient_recovery_outcomes, target=target)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        attempt = 0
        saw_transient_failure = False
        rate_limit_delay = 2.0
        while True:
            attempt += 1
            try:
                response = self._completions.create(*args, **kwargs)
                if saw_transient_failure:
                    self._transient_recovery_outcomes.append(True)
                return response
            except Exception as exc:
                status_code = _get_http_status(exc)
                retryable = _is_retryable_exception(exc, self._retryable_statuses)
                if not retryable:
                    raise
                saw_transient_failure = True
                if attempt >= self._max_attempts:
                    self._transient_recovery_outcomes.append(False)
                    raise
                if status_code == 429:
                    delay = rate_limit_delay
                    rate_limit_delay = min(60.0, (rate_limit_delay * 2.0) + random.uniform(0.0, 1.0))
                else:
                    base_delay = 1.0
                    max_delay = 20.0
                    backoff = 2.0
                    delay = min(max_delay, base_delay * (backoff ** (attempt - 1)))
                    delay += random.uniform(0.0, delay * 0.1)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(
                    "[%s] LLM request failed (attempt %s/%s, status %s): %s",
                    timestamp,
                    attempt,
                    self._max_attempts,
                    status_code,
                    exc,
                )
                time.sleep(delay)


def _is_retryable_exception(error: Exception, retryable_statuses: set[int]) -> bool:
    status_code = _get_http_status(error)
    if status_code in retryable_statuses:
        return True

    if getattr(error, "should_retry", False):
        return True

    if isinstance(error, (TimeoutError, ConnectionError)):
        return True

    err_name = error.__class__.__name__.lower()
    if "timeout" in err_name or "connection" in err_name:
        return True

    cause = getattr(error, "__cause__", None)
    if isinstance(cause, (TimeoutError, ConnectionError)):
        return True

    text = str(error).lower()
    transient_hints = (
        "timeout",
        "timed out",
        "connection error",
        "connection reset",
        "connection aborted",
        "temporarily unavailable",
        "service unavailable",
        "too many requests",
        "rate limit",
    )
    return any(hint in text for hint in transient_hints)


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


class _LLMGateClient:
    def __init__(self, client, strategy: str, auto_approve: bool):
        self._client = client
        self._strategy = strategy
        self._auto_approve = auto_approve
        self.chat = _LLMGateChat(client.chat, strategy, auto_approve)

    def __getattr__(self, name: str):
        return getattr(self._client, name)


class _LLMGateChat:
    def __init__(self, chat_resource, strategy: str, auto_approve: bool):
        self._chat = chat_resource
        self._strategy = strategy
        self._auto_approve = auto_approve
        self.completions = _LLMGateCompletions(
            chat_resource.completions,
            strategy,
            auto_approve,
        )

    def __getattr__(self, name: str):
        return getattr(self._chat, name)


class _LLMGateCompletions:
    def __init__(self, completions_resource, strategy: str, auto_approve: bool) -> None:
        self._completions = completions_resource
        self._strategy = strategy
        self._auto_approve = auto_approve

    def create(self, *args: Any, **kwargs: Any) -> Any:
        from src.utils.gate import run_llm_post_gate, run_llm_pre_gate

        prompt_text = _extract_prompt_text(kwargs.get("messages"))
        if self._strategy in {"default"}:
            strategy = "feedback"
        else:
            strategy = self._strategy

        if prompt_text and not run_llm_pre_gate(prompt_text, strategy, auto_approve=self._auto_approve):
            raise RuntimeError("LLM call canceled by user at prompt gate.")

        response = self._completions.create(*args, **kwargs)

        output_text = _extract_response_text(response)
        if output_text:
            run_llm_post_gate(output_text, strategy, auto_approve=self._auto_approve)

        return response


def _extract_prompt_text(messages: list[dict[str, str]] | None) -> str:
    if not messages:
        return ""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def _extract_response_text(response) -> str:
    try:
        choices = getattr(response, "choices", None)
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        if message and getattr(message, "content", None):
            return message.content
        return ""
    except Exception:
        return ""


# Example usage
if __name__ == "__main__":
    import sys

    # Ensure "src" is importable when running this file directly.
    sys.path.insert(0, str(Path(__file__).parent.parent))
    config = load_config()
    print(config.model_dump_json(indent=2))
    
    # Test LLM client
    try:
        client = get_llm_client(config)
        logger.debug(f"\n[OK] LLM client initialized: {config.llm_provider}/{config.llm_model}")
    except Exception as e:
        logger.debug(f"\n[ERROR] Failed to initialize LLM client: {e}")
