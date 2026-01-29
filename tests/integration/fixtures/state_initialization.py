"""
Centralized state initialization for integration tests.

Ensures both old and new history fields are present.
"""

from typing import Dict, Any
from src.models.state_compatibility import ensure_history_fields


def initialize_l1_state(
    prompt: str = "Run a test simulation",
    config: Any = None,
    mode: str = "initial",
    iteration: int = 0
) -> Dict[str, Any]:
    """
    Initialize state for L1 (Architect/Reviewer) tests.
    
    Includes both legacy and canonical fields for compatibility.
    """
    state = {
        "prompt": prompt,
        "user_requirement": prompt,
        "config": config,
        "mode": mode,
        "iteration": iteration,
        "max_iterations": 3,
        "retry_count": 0,
        
        # Error tracking
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
        
        # Phase tracking
        "phase": "planning",
        
        # Architect fields
        "plan": None,
        "selected_case": None,
        "baseline": None,
        "modifications": [],
        "reasoning": None,
        "case_candidates": [],
        "baseline_confidence": None,
        
        # Reviewer fields
        "review_analysis": None,
        "suggested_fixes": None,
    }
    
    # Initialize both history fields
    state = ensure_history_fields(state)
    
    return state


def initialize_l2_state(**kwargs) -> Dict[str, Any]:
    """Initialize state for L2 (InputWriter) tests"""
    state = initialize_l1_state(**kwargs)
    
    state.update({
        "run_directory": None,
        "inputs_file_path": None,
        "input_files": [],
        "work_dir": None,
    })
    
    return state


def initialize_l3_state(**kwargs) -> Dict[str, Any]:
    """Initialize state for L3 (Analysis/Viz) tests"""
    state = initialize_l2_state(**kwargs)
    
    state.update({
        "simulation_output": None,
        "job_status": None,
        "analysis_report": None,
        "visualization_images": None,
        "visualization_backend": None,
        "visualization_status": None,
    })
    
    return state


def initialize_l4_state(**kwargs) -> Dict[str, Any]:
    """Initialize state for L4 (Runner) tests"""
    state = initialize_l3_state(**kwargs)
    
    state.update({
        "executable_path": None,
        "job_id": None,
        "run_status": None,
        "execution_log": None,
        "script_path": None,
    })
    
    return state
