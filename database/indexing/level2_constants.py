"""
Shared constants for Level 2 indexing.
"""

LEVEL2_WEIGHTS = {
    "physics_parameters": 0.30,        # Physics parameters and descriptions
    "grid_specifications": 0.20,       # AMR settings and geometry
    "development_activity": 0.10,      # Development signals
    "configuration_complexity": 0.10,  # Parameter customization depth
    "path_hierarchy": 0.15,            # Organizational structure
    "domain_models": 0.10,             # Domain-specific knobs
    "resource_requirements": 0.05,     # Runtime/resource heuristics
}

LEVEL2_BASE_KEYS = list(LEVEL2_WEIGHTS.keys())
