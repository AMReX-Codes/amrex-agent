import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from src.config import load_config
from src.services.architect import ArchitectService
from src.services.embedding_service_factory import get_embedding_service

config = load_config()
emb = get_embedding_service(config)
architect = ArchitectService(config, embedding_service=emb)

solver_config, _ = architect.select_solver("ERF ABL simulation")
baseline_result = architect.select_baseline("ERF ABL simulation", solver_config)

print(f" solver_config: {solver_config}")
print(f" Case: {baseline_result['selected_case']['case']}")
