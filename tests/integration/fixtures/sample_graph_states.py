'''
Canonical GraphState templates for Integration Levels 1-4.
Reference: src/models.py (GraphState definition)
'''
from typing import Dict, Any
from unittest.mock import Mock

def get_base_config():
    '''Returns a mock configuration object.'''
    config = Mock()
    config.max_iterations = 3
    config.output_dir = "/tmp/test_output"
    config.disabled_validators = []
    return config

def get_l1_state() -> Dict[str, Any]:
    '''
    Level 1 State: Initial Input.
    Used for testing Architect -> Reviewer transitions.

    Matches GraphState schema from src/models.py
    '''
    return {
        "config": get_base_config(),
        "user_requirement": "Simulate a 2D premixed flame with methane",
        "mode": "initial",
        "iteration": 0,
        "max_iterations": 3,
        "workflow_history": [],
        "errors_active": [],
        "errors_found": [],
        "errors_fixed": [],
        "phase": "planning",
        # Empty fields that will be populated
        "plan": None,
        "baseline": None,
        "requirements": None,
    }

def get_l2_state(tmp_path) -> Dict[str, Any]:
    '''
    Level 2 State: Post-Planning.
    Used for testing InputWriter file generation.
    '''
    state = get_l1_state()
    state["config"].output_dir = str(tmp_path)

    # Simulate Architect output
    state["plan"] = {
        "baseline": {
            "code": "AMReX",
            "path": "Tests/Amr/Advection_AmrCore",
            "name": "AMReX/Tests/Amr/Advection_AmrCore",
        },
        "modifications": [
            {
                "section": "amr",
                "parameter": "n_cell",
                "value": "64 64 64",
                "reason": "Test resolution"
            }
        ],
    }
    state["baseline"] = state["plan"]["baseline"]
    state["mode"] = "initial"
    state["phase"] = "execution"
    return state

def get_l3_state(run_dir) -> Dict[str, Any]:
    '''
    Level 3 State: Post-Execution.
    Used for testing Analysis/Viz log parsing.
    '''
    from pathlib import Path
    state = get_l2_state(Path(run_dir).parent)
    state["run_directory"] = str(run_dir)
    state["inputs_path"] = str(run_dir / "inputs")
    state["executable"] = str(run_dir / "AMReX.ex")
    state["job_id"] = "FAKE_JOB_123"
    state["phase"] = "analysis"
    return state

def get_l4_state(tmp_path) -> Dict[str, Any]:
    '''
    Level 4 State: Pre-Execution.
    Used for testing Runner with real executable.
    '''
    state = get_l2_state(tmp_path)
    # L4 starts same as L2 but will execute
    return state
