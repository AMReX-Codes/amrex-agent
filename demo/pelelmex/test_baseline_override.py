"""
Simplest test: Diff baseline vs output with 0 modifications.
Should be identical (or nearly identical).
"""
import sys
from pathlib import Path
import logging
import difflib

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.services.architect import ArchitectService
from src.services.input_writer import InputWriterService
from src.services.embedding_service_factory import get_embedding_service

def test_baseline_diff():
    """Test that baseline override with 0 mods produces identical output."""
    
    # Setup
    config = load_config()
    config.indexing_strategy = "hierarchical"
    config.baseline_override = "PeleLMeX/Exec/Production/JetInCrossflow"
    
    architect = ArchitectService(config, embedding_service=get_embedding_service(config))
    writer = InputWriterService(config)
    
    # Generate plan with 0 modifications
    plan = architect.execute_planning("DNS jet in crossflow")
    
    assert len(plan.modifications) == 0, f"Expected 0 mods, got {len(plan.modifications)}"
    print(f"✓ Plan has 0 modifications")
    
    # Write output (using positional args like original test)
    output_dir = Path("/tmp/test_override_diff")
    output_dir.mkdir(exist_ok=True)
    
    result = writer.apply_plan(
        plan.selected_case,
        plan.modifications,
        plan.baseline or {},
        plan.reasoning,
        output_dir
    )
    
    # === DIFF ===
    baseline_inputs = Path(plan.baseline['local_path']) / "input.3d"
    output_inputs = Path(result['inputs_path'])
    
    print(f"\n=== DIFF ===")
    print(f"Baseline: {baseline_inputs}")
    print(f"Output:   {output_inputs}")
    
    # Read both files
    with open(baseline_inputs) as f:
        baseline_lines = f.readlines()
    
    with open(output_inputs) as f:
        output_lines = f.readlines()
    
    # Generate diff
    diff = list(difflib.unified_diff(
        baseline_lines, 
        output_lines,
        fromfile=str(baseline_inputs),
        tofile=str(output_inputs),
        lineterm=''
    ))
    
    if not diff:
        print("✓ Files are IDENTICAL")
    else:
        print(f"\n⚠️  Files differ ({len(diff)} lines changed):\n")
        for line in diff[:50]:  # Show first 50 diff lines
            print(line)
        
        if len(diff) > 50:
            print(f"\n... ({len(diff) - 50} more lines)")
        
        # Count removed lines (likely schema stripping)
        removed = [l for l in diff if l.startswith('-') and not l.startswith('---')]
        added = [l for l in diff if l.startswith('+') and not l.startswith('+++')]
        
        print(f"\nSummary: {len(removed)} lines removed, {len(added)} lines added")
        
        if len(removed) > len(added):
            print("⚠️  More lines removed than added - likely schema stripping bug")

if __name__ == "__main__":
    test_baseline_diff()
