"""
Canonical GraphState Schema for AMReX Agent

Implements:
- PRD Amendment A requirements [Source 781]
- yt-project naming standards [Source 4754]
- LangGraph Reducers Pattern [Source 2919]

Philosophy: "Digital Twin of Expert Workflow"
- Observability: Complete audit trail via workflow_history
- Standardization: Short, descriptive names (yt-project)
- Determinism: Immutable state updates (LangGraph)

Usage:
    from src.models.graph_state_canonical import GraphState

    state: GraphState = {
        "prompt": "Run 2D advection simulation",
        "config": config,
        "mode": "initial",
        ...
    }
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal
from src.config import AMReXAgentConfig


class GraphState(TypedDict, total=False):
    """
    Canonical State Object for AMReX Agent.

    Tracks the complete lifecycle from user prompt to visualization.

    Naming Convention (yt-project standard):
    - Short but descriptive variable names
    - Underscores for multi-word names (run_directory, not runDirectory)
    - Full words preferred over abbreviations (directory, not dir)

    State Management Pattern (LangGraph):
    - Nodes return updates dict, not modified state
    - History uses immutable append pattern
    - No in-place mutations

    Fields are organized by workflow phase for readability.
    """

    # ========================================
    # INPUTS (Set at initialization)
    # ========================================
    prompt: str                     # User's natural language request
    config: AMReXAgentConfig         # Runtime configuration (paths, API keys)

    # ========================================
    # PLANNING PHASE (Architect outputs)
    # ========================================
    selected_case: str              # Path relative to repo root
                                    # Example: "Exec/<problem_directory>"

    modifications: List[tuple]      # List of (parameter, value) tuples
                                    # Example: [("amr.n_cell", "128 128 128")]

    reasoning: str                  # Human-readable explanation
                                    # Example: "Selected baseline because it matches the physics."

    case_candidates: Optional[List[Dict[str, Any]]]  # FAISS search results
    baseline_confidence: Optional[float]             # Similarity score

    plan: Optional[Dict[str, Any]]              # Combined plan object from architect (Fix 6)
    # Structure:
    #   {
    #       "selected_case": str,
    #       "modifications": List[tuple],
    #       "reasoning": str,
    #       "case_candidates": List[Dict],
    #       "baseline_confidence": float
    #   }

    baseline: Optional[Dict[str, Any]]          # Baseline case metadata (for runner) (Fix 6)
    # Structure:
    #   {
    #       "code_name": str,       # AMReX application code name
    #       "repo_path": str,       # "/home/.../<repo_name>"
    #       "case_path": str,       # "Exec/<problem_directory>"
    #       "local_path": str       # "/home/.../<repo_name>/Exec/<problem_directory>"
    #   }

    # ========================================
    # VALIDATION PHASE (Reviewer outputs)
    # ========================================
    review_analysis: Optional[Dict[str, Any]]        # Pre-execution validation
    suggested_fixes: Optional[List[Dict[str, Any]]]  # Recommended changes
    resource_estimate: Optional[Dict[str, Any]]      # Memory, nodes, walltime
    retry_guidance: Optional[Dict[str, Any]]         # Inputs/baseline retry hints

    # ========================================
    # EXECUTION PHASE (Writer/Runner outputs)
    # ========================================
    run_directory: str              # Full path to simulation directory
                                    # Example: "/scratch/runs/run_20250101_120000"

    inputs_file_path: str           # Full path to inputs file
                                    # Example: "/scratch/runs/run_001/inputs"

    inputs_file: Optional[str]                  # Legacy alias for inputs_file_path (deprecated) (Fix 6)
    modifications_applied: Optional[int]        # Count of modifications applied by input_writer (Fix 6)
    ready_to_run: Optional[bool]                # Flag: input files ready for execution (Fix 6)

    executable_path: Optional[str]  # Full path to compiled executable
                                    # Example: "/path/to/solver.ex"

    job_id: Optional[str]           # SLURM job ID or process ID
                                    # Example: "12345678" or "local_pid_5432"

    job_submission_time: Optional[str]          # Job submission timestamp (ISO 8601) (Fix 6)

    job_status: str                 # Execution status (queued/running/completed/failed/cancelled/timeout/skipped)
                                    # Values: "queued", "running", "completed", "failed"

    script_path: Optional[str]      # Path to submit script
                                    # Example: "/scratch/runs/run_001/submit.sh"

    # ========================================
    # ANALYSIS PHASE (Analysis/Viz outputs)
    # ========================================
    analysis_report: Optional[Dict[str, Any]]  # Post-execution diagnostics
    # Structure:
    #   {
    #       "status": "success" | "failed" | "unstable",
    #       "total_steps": int,
    #       "final_time": float,
    #       "issues": List[str],
    #       "warnings": List[str],
    #       "metrics": Dict[str, Any],
    #       "suggestions": List[str]
    #   }

    visualization_images: Optional[List[str]]     # Paths to generated plots
    visualization_backend: str                    # Backend used (amrex_tools, yt, pyamrex, none)
    visualization_status: Optional[str]           # Status (success, failed, skipped)
    visualization_metadata: Optional[Dict[str, Any]]  # Plot metadata

    # ========================================
    # CONTROL FLOW & ERROR TRACKING
    # ========================================
    mode: Literal["initial", "proceed", "retry", "fail", "terminal"]
    # - initial: First execution attempt
    # - proceed: Continue to next node
    # - retry: Backtrack to earlier node (reflexion)
    # - fail: Terminal failure, exit workflow (deprecated - use terminal)
    # - terminal: Terminal state (max retries exceeded)

    iteration: int                  # Current attempt number (0-indexed)
    retry_count: int                # Number of retries performed
    max_retries: int                # Maximum allowed retries (default: 3)
    loop_count: Optional[int]                   # Legacy alias for iteration (deprecated) (Fix 6)

    errors_active: List[str]        # Current blocking errors
    errors_found: List[str]         # All errors discovered (historical)
    errors_fixed: List[str]         # Errors successfully resolved
    error_logs: List[str]           # Runtime error messages from execution/analysis
    preconfirm_action: Optional[str]            # "proceed" | "cancel"

    # ========================================
    # OBSERVABILITY (Immutable Audit Log)
    # ========================================
    workflow_history: List[Dict[str, Any]]
    # Immutable append-only log of all node executions (Fix 7 - canonical format).
    # Each entry structure:
    #   {
    #       "node": str,            # Node name (architect, reviewer, etc.)
    #       "timestamp": str,       # ISO 8601 timestamp with 'Z' suffix
    #       "action": str,          # Action taken (plan_created, approved, etc.)
    #       "iteration": int,       # Which retry iteration
    #       "details": Dict[str, Any]  # Node-specific metadata
    #   }
    #
    # All node-specific data should be stored in 'details' dict.
    #
    # Example:
    #   [
    #       {
    #           "node": "architect",
    #           "timestamp": "2025-01-01T12:00:00Z",
    #           "action": "plan_created",
    #           "iteration": 0,
    #           "details": {
    #               "case": "PMF",
    #               "modifications": [("param1", "val1"), ("param2", "val2")],
    #               "reasoning_snippet": "Selected PMF case because..."
    #           }
    #       },
    #       {
    #           "node": "reviewer",
    #           "timestamp": "2025-01-01T12:00:05Z",
    #           "action": "rejected",
    #           "iteration": 0,
    #           "details": {
    #               "errors": ["missing amr.max_level"],
    #               "retry_count": 1
    #           }
    #       }
    #   ]

    history: List[str]              # Human-readable log (legacy, deprecated)
    # Use workflow_history instead for structured data

    # ========================================
    # METADATA
    # ========================================
    phase: str                      # Current workflow phase
                                    # Values: "planning", "execution", "analysis", "complete"

    job_name: Optional[str]         # Custom job name (optional)
    timestamp_start: Optional[str]  # Workflow start time (ISO 8601)
    timestamp_end: Optional[str]    # Workflow end time (ISO 8601)
    timestamp_plan_created: Optional[str]       # Plan creation timestamp (ISO 8601) (Fix 6)
    timestamp_generated: Optional[str]          # Input generation timestamp (ISO 8601) (Fix 6)


# ========================================
# Schema Validation Helpers
# ========================================

def validate_required_fields(state: GraphState, phase: str) -> List[str]:
    """
    Validate that required fields are present for a given phase.

    Args:
        state: Current graph state
        phase: Workflow phase ("planning", "execution", "analysis")

    Returns:
        List of missing field names (empty if valid)

    Example:
        >>> errors = validate_required_fields(state, "planning")
        >>> if errors:
        ...     print(f"Missing fields: {errors}")
    """
    required_by_phase = {
        "planning": ["prompt", "config", "mode"],
        "execution": ["prompt", "config", "selected_case", "modifications", "run_directory"],
        "analysis": ["prompt", "config", "run_directory", "job_id"],
    }

    required = required_by_phase.get(phase, [])
    missing = [field for field in required if field not in state or state[field] is None]

    return missing


def get_workflow_summary(state: GraphState) -> str:
    """
    Generate human-readable summary of workflow execution.

    Args:
        state: Final graph state

    Returns:
        Multi-line summary string

    Example:
        >>> summary = get_workflow_summary(final_state)
        >>> print(summary)
        Workflow Summary:
        ----------------
        Prompt: Run 2D advection simulation
        Case: <repo_name>/Exec/<problem_directory>
        Modifications: 3
        Retries: 1
        Status: completed
        Nodes executed: 6
    """
    history = state.get("workflow_history", [])
    nodes_executed = list(dict.fromkeys([e["node"] for e in history]))  # Unique, preserve order

    lines = [
        "Workflow Summary:",
        "----------------",
        f"Prompt: {state.get('prompt', 'N/A')[:60]}...",
        f"Case: {state.get('selected_case', 'N/A')}",
        f"Modifications: {len(state.get('modifications', []))}",
        f"Retries: {state.get('retry_count', 0)}",
        f"Status: {state.get('job_status', 'unknown')}",
        f"Nodes executed: {len(nodes_executed)} ({', '.join(nodes_executed)})",
        f"Total events: {len(history)}",
    ]

    return "\n".join(lines)
