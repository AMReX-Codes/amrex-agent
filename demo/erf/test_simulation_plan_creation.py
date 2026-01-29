import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.config import load_config
from src.services.architect import ArchitectService
from src.services.embedding_service_factory import get_embedding_service
import json

config = load_config()
config.indexing_strategy = "hierarchical"  # Set to hierarchical

emb = get_embedding_service(config)
architect = ArchitectService(config, embedding_service=emb)

# One call to get complete SimulationPlan
plan = architect.execute_planning("ERF ABL simulation with 128x128 grid")

print(plan.get_summary())

# Get as dict
plan_dict = plan.to_dict()

# Show just modifications
print("Modifications:")
print(json.dumps(plan_dict['modifications'], indent=2))

# Or show full plan as JSON
#print("\nFull Plan:")
#print(plan.to_json(indent=2))

# Or specific fields
#print(f"\nSolver: {plan_dict['selected_solver']}")
#print(f"Case: {plan_dict['selected_case']}")
#print(f"Modifications count: {len(plan_dict['modifications'])}")
