"""
AMReXAgent workflow nodes.

Similar to: foamagent/src/nodes/__init__.py

Each node is a function that:
- Takes GraphState as input
- Performs one workflow step (architect, write, run, review)
- Returns updated GraphState with new fields added

Node execution order:
1. architect_node: Select baseline, plan modifications
2. input_writer_node: Generate input files
3. runner_node: Setup job directory, prepare submission
4. reviewer_node: Analyze results, suggest fixes (future)
"""

# Import will fail until we create the actual node files in steps D-G
# For now, we'll use try/except to allow gradual implementation

try:
    from .architect_node import architect_node
except ImportError:
    architect_node = None

try:
    from .input_writer_node import input_writer_node
except ImportError:
    input_writer_node = None

try:
    from .runner_node import runner_node
except ImportError:
    runner_node = None

try:
    from .reviewer_node import reviewer_node
except ImportError:
    reviewer_node = None

try:
    from .analysis_node import analysis_node
except ImportError:
    analysis_node = None

try:
    from .visualization_node import visualization_node
except ImportError:
    visualization_node = None

try:
    from .router_gate_node import router_gate_node
except ImportError:
    router_gate_node = None

__all__ = [
    'architect_node',
    'input_writer_node',
    'runner_node',
    'reviewer_node',
    'analysis_node',
    'visualization_node',
    'router_gate_node',
]
