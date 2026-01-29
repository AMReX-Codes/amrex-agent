import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.services.architect import ArchitectService
from src.services.embedding_service_factory import get_embedding_service

# Setup with override
config = load_config()
config.indexing_strategy = "hierarchical"
config.baseline_override = "PeleLMeX/Exec/RegTests/TaylorGreen"  # Force this baseline

architect = ArchitectService(config, embedding_service=get_embedding_service(config))

# Test prompt
prompt = "LES of reacting H2 jet in crossflow with 5% turbulence"

# Should use PeleLMeX/TaylorGreen regardless of prompt
plan = architect.execute_planning(prompt)

print(f"Selected solver: {plan.selected_solver}")
print(f"Selected case: {plan.selected_case}")
print(f"Baseline confidence: {plan.baseline_confidence}")  # Should be 1.0
print(f"Override: {plan.baseline.get('override', False)}")  # Should be True
