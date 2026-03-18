"""
Data models for AMReXAgent state management.

Following foamagent's pattern but adapted for AMReX/combustion workflows.

The GraphState flows through the agent graph, with each node adding its outputs:
- Architect: plan, baseline, requirements
- Reviewer: review_analysis, suggested_fixes (Phase 4)
- Input Writer: inputs_path, config_dict
- Runner: run_dir, executable, submit_script
- Analysis: analysis_report (Phase 4)
- Visualization: visualization_images (Phase 4)
"""

from typing import TypedDict, Optional, Dict, List, Any

import logging

logger = logging.getLogger(__name__)

class GraphState(TypedDict, total=False):
    """
    State that flows through the AMReXAgent graph.
    
    Similar to: foamagent/src/utils.py GraphState
    
    total=False means all fields are optional (can be added incrementally)
    """
    
    # ========================================
    # User Inputs
    # ========================================
    user_requirement: str  # Natural language prompt
    config: Any  # AMReXAgentConfig instance
    
    # ========================================
    # Architect Outputs
    # ========================================
    plan: Optional[Dict[str, Any]]  # Full plan from architect
    baseline: Optional[Dict[str, Any]]  # Selected baseline case
    requirements: Optional[Dict[str, Any]]  # Extracted parameters
    
    # ========================================
    # Input Writer Outputs
    # ========================================
    inputs_path: Optional[str]  # Path to generated inputs file
    config_dict: Optional[Dict[str, Any]]  # Full configuration dict
    
    # ========================================
    # Runner Outputs
    # ========================================
    run_dir: Optional[str]  # Job/run directory
    executable: Optional[str]  # Path to compiled executable
    submit_script: Optional[str]  # Path to SLURM script
    job_id: Optional[str]  # Job ID if submitted
    
    # ========================================
    # Reviewer Outputs (Phase 4 - Pre-execution validation)
    # ========================================
    review_analysis: Optional[Dict[str, Any]]  # Pre-execution review results
    suggested_fixes: Optional[List[Dict[str, Any]]]  # Recommended parameter changes

    # ========================================
    # Analysis Outputs (Phase 4 - Post-execution)
    # ========================================
    analysis_report: Optional[Dict[str, Any]]  # Post-execution analysis
    # Contains: status, issues, warnings, metrics, timesteps, cfl_history

    # ========================================
    # Visualization Outputs (Phase 4/5)
    # ========================================
    execution_intent: Optional[Dict[str, Any]]  # Canonical pre-run execution intent
    visualization_intent: Optional[Dict[str, Any]]  # Canonical pre-run visualization intent
    visualization_images: Optional[List[str]]  # Paths to generated images

    # Phase 5 Workflow Integration - Visualization metadata
    visualization_backend: Optional[str]  # Backend used: 'AMReXToolsBackend', 'YtBackend', etc.
    visualization_status: Optional[str]  # Status: 'success', 'failed', 'skipped'
    visualization_metadata: Optional[Dict[str, Any]]  # Plotfile count, fields plotted, errors

    # ========================================
    # Error Tracking & Control Flow
    # ========================================
    error_logs: Optional[List[str]]  # Errors encountered
    loop_count: int  # Number of retry loops (legacy - kept for compatibility)
    mode: str  # 'initial', 'retry', 'final'
    iteration: int         # Current attempt (0, 1, 2, ...)
    max_iterations: int    # Usually 3
    
    # Phase 2: Enhanced Error Tracking
    phase: str                      # Current workflow phase: "planning" | "execution" | "analysis" | "complete"
    errors_found: List[str]         # All unique errors discovered across all iterations
    errors_fixed: List[str]         # Errors that were successfully addressed
    errors_active: List[str]        # Current issues that need fixing
    
    # Phase 2: Workflow History (rich event log for debugging/demo)
    workflow_history: List[Dict[str, Any]]  # [{iteration, node, action, timestamp, metadata}, ...]

    # ========================================
    # History & Metadata
    # ========================================
    history: List[str]  # Human-readable execution log
    job_name: Optional[str]  # Custom job name
