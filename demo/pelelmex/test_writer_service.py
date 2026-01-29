import sys
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,  # Use DEBUG for more detail
    format='%(levelname)s - %(name)s - %(message)s'
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.services.architect import ArchitectService
from src.services.input_writer import InputWriterService
from src.services.embedding_service_factory import get_embedding_service

# Test prompts: Jet-in-crossflow variations
prompts = [
    "DNS of a nonreacting jet in crossflow where the jet issues into a ducted flow of vitiated combustion products at atmospheric pressure. The jet has a mole-basis composition of 70% H2, 18% N2 and 12% HE at 300 K, a bulk inlet velocity of 42.2 m/s with a uniform profile, and a diameter of 3.175 mm. The domain has a cross section of 24d_j in the spanwise direction by 40d_j in the streamwise direction from 30d_j upstream to 50d_j downstream of the jet. Adiabatic walls. The cross flow has a bulk velocity of 19.1 m/s with a uniform profile and a composition of 12.91% O2, 76.11% N2, 3.66% CO2, 7.32% H2O and 0.0019629% OH at 1236 K.",
    
    "LES of a reacting jet in crossflow where the jet issues into a channel flow of vitiated combustion products at atmospheric pressure. The jet has a mole-basis composition of 70% H2, 18% N2 and 12% HE at 300 K, a bulk inlet velocity of 42.2 m/s with turbulent fluctuations at an intensity of 5%, and a diameter of 3.175 mm. The domain has a cross section of 24d_j spanwise by 40d_j streamwise from 30d_j upstream to 50d_j downstream. Adiabatic walls. The cross flow has a bulk velocity of 19.1 m/s with turbulent fluctuations at 5% intensity and a composition of 12.91% O2, 76.11% N2, 3.66% CO2, 7.32% H2O and 0.0019629% OH at 1236 K. Output jet trajectory z(x) on mean streamline from jet center.",
    
    "LES of a reacting jet in crossflow with momentum ratio 25.32 (adjust jet velocity to 94.4 m/s from baseline 42.2 m/s). Jet: 70% H2, 18% N2, 12% HE at 300 K with 5% turbulent fluctuations, diameter 3.175 mm. Domain: 24d_j x 40d_j, 30d_j upstream to 50d_j downstream. Isothermal walls. Crossflow: 19.1 m/s with 5% turbulence, composition 12.91% O2, 76.11% N2, 3.66% CO2, 7.32% H2O, 0.0019629% OH at 1236 K. Determine jet trajectory.",
    
    "DNS of nonreacting H2 jet in crossflow. Adjust domain to 30d_j spanwise by 60d_j streamwise (increased from 40d_j). Increase crossflow velocity to 25 m/s (from 19.1 m/s). Jet: 70% H2, 18% N2, 12% HE at 300 K, 42.2 m/s uniform profile, 3.175 mm diameter. Adiabatic walls. Crossflow composition: 12.91% O2, 76.11% N2, 3.66% CO2, 7.32% H2O, 0.0019629% OH at 1236 K."
]

# Setup
config = load_config()
config.indexing_strategy = "hierarchical"
config.baseline_override = "PeleLMeX/Exec/Production/JetInCrossflow"  # Force this baseline
config.llm_model = "claude-sonnet-4-5"
architect = ArchitectService(config, embedding_service=get_embedding_service(config))
writer = InputWriterService(config)

# Run comparison
for i, prompt in enumerate(prompts, 1):
    plan = architect.execute_planning(prompt)

    # Normalize baseline - use plan.solver_name (handles overrides correctly)
    baseline = plan.baseline or {}
    if baseline:
        code_name = plan.selected_solver  # Use plan's solver (handles overrides)
        repo_path = baseline.get('repo_path', config.repositories.get(code_name) if hasattr(config, 'repositories') else None)
        case_path = baseline.get('path', baseline.get('case_path', ''))
    
        baseline = {
            'code_name': code_name,
            'repo_path': str(repo_path) if repo_path else '',
            'case_path': case_path,
            'local_path': str(Path(repo_path) / case_path) if repo_path and case_path else ''
        }

        result = writer.apply_plan(
            selected_case=plan.selected_case,
            modifications=plan.modifications,
            baseline=plan.baseline or {},
            reasoning=plan.reasoning,
            output_dir=Path(f"/tmp/jicf_case_{i}")
        )

    print(f"\nCase {i}: {'DNS' if 'DNS' in prompt else 'LES'} | {'Reacting' if 'reacting' in prompt else 'Nonreacting'} | MR={25.32 if '25.32' in prompt else 5.08}")
    print(f"  Baseline: {plan.selected_case}")
    print(f"  Modifications: {result['modifications_applied']} | Confidence: {plan.get_overall_confidence():.1%}")
    print(f"  File: {result['inputs_path']} ({Path(result['inputs_path']).stat().st_size if Path(result['inputs_path']).exists() else 0} bytes)")
    exit()
