#!/bin/bash
# Demo Example Generation - Progressive Complexity
# Base case: Premixed flame (PMF) with hierarchy progression
# Complexity dimensions:
#   Ex00: Simple indexing (direct case retrieval)
#   Ex01: Hierarchical indexing (Level 0 + Level 2 routing)
#   Ex02: Add AMR (2 levels of refinement)
#   Ex03: Add timesteps (1000) + complex parameters
#   Ex04: Cross-code (ERF - different domain entirely)

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f "amrex_agent.py" ]]; then
  echo "Error: amrex_agent.py not found. Run from project root."
  exit 1
fi

mkdir -p examples
mkdir -p examples/{00_simple_indexing,01_hierarchical_indexing,02_hierarchical_with_amr,03_complex_params,04_cross_code_erf}
PIDS=()

echo "===================================================="
echo "AMReXAgent Demo: Progressive Complexity"
echo "===================================================="
echo ""
echo "Base case: Premixed flame (PMF)"
echo "Hierarchy + complexity progression:"
echo "  Ex00: Simple indexing (direct CBR)"
echo "  Ex01: Hierarchical indexing (Level 0+2)"
echo "  Ex02: + AMR (2 levels refinement)"
echo "  Ex03: + parameters (timesteps, CFL, etc)"
echo "  Ex04: Cross-code (ERF ABL)"
echo ""
echo "Monitor: tail -f examples/*/generation.log"
echo ""

# ============================================
# EXAMPLE 00: Simple indexing (minimal prompt)
# ============================================
echo "[0/5] Simple indexing - Premixed flame"
(
  # ALT: --prompt "premixed flame"  # minimal - may lack context
  # ALT: --prompt "PeleC premixed methane flame"
  python amrex_agent.py \
    --prompt "premixed methane flame PMF case" \
    --output-dir examples/00_simple_indexing/run \
    --indexing-strategy simple \
    --save-workflow \
    --save-transcript \
    --verbose
) > examples/00_simple_indexing/generation.log 2>&1 &
PIDS+=($!)

# ============================================
# EXAMPLE 01: Hierarchical indexing (Level 0+2)
# ============================================
echo "[1/5] Hierarchical indexing - Premixed flame with solver"
(
  # ALT: --prompt "premixed methane flame"  # more generic
  # ALT: --prompt "combustion simulation PeleC"
  python amrex_agent.py \
    --prompt "PeleC premixed methane flame simulation" \
    --output-dir examples/01_hierarchical_indexing/run \
    --indexing-strategy hierarchical \
    --save-workflow \
    --save-transcript \
    --verbose
) > examples/01_hierarchical_indexing/generation.log 2>&1 &
PIDS+=($!)

# ============================================
# EXAMPLE 02: Add AMR (grid complexity)
# ============================================
echo "[2/5] Hierarchical + AMR - Premixed flame with refinement"
(
  # ALT: --prompt "PeleC combustion with adaptive refinement"
  # ALT: --prompt "methane flame 2-level AMR grid"
  python amrex_agent.py \
    --prompt "Premixed methane flame simulation
AMR: 2 levels of refinement" \
    --output-dir examples/02_hierarchical_with_amr/run \
    --indexing-strategy hierarchical \
    --save-workflow \
    --save-transcript \
    --verbose
) > examples/02_hierarchical_with_amr/generation.log 2>&1 &
PIDS+=($!)

# ============================================
# EXAMPLE 03: Add timesteps + parameters
# ============================================
echo "[3/5] Complex parameters - AMR + timesteps + CFL"
(
  # ALT: --prompt "PeleC AMR 512x512 1000 steps 0.3 CFL"
  # ALT: --prompt "methane combustion high resolution long-time simulation"
  python amrex_agent.py \
    --prompt "Premixed methane flame simulation
AMR: 2 levels of refinement
Grid: 512x512 cells
Run for 1000 timesteps
CFL: 0.3
Enable chemistry tracking" \
    --output-dir examples/03_complex_params/run \
    --indexing-strategy hierarchical \
    --save-workflow \
    --save-transcript \
    --verbose
) > examples/03_complex_params/generation.log 2>&1 &
PIDS+=($!)

# ============================================
# EXAMPLE 04: Cross-code routing (ERF)
# ============================================
echo "[4/5] Cross-code - Atmospheric boundary layer (ERF)"
(
  # ALT: --prompt "Atmospheric boundary layer simulation"  # too generic
  # ALT: --prompt "atmospheric stable boundary layer with wind"
  python amrex_agent.py \
    --prompt "ERF ABL simulation" \
    --output-dir examples/04_cross_code_erf/run \
    --indexing-strategy hierarchical \
    --save-workflow \
    --save-transcript \
    --verbose
) > examples/04_cross_code_erf/generation.log 2>&1 &
PIDS+=($!)

echo ""
echo "All examples spawned. Waiting for completion..."
echo ""

# Wait for all processes
FAILED=0
for i in "${!PIDS[@]}"; do
  pid=${PIDS[$i]}
  if wait $pid 2>/dev/null; then
    echo "✅ Example $i complete"
  else
    echo "❌ Example $i FAILED"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "Validating artifacts..."
EXAMPLES=("00_simple_indexing" "01_hierarchical_indexing" "02_hierarchical_with_amr" "03_complex_params" "04_cross_code_erf")
for ex_name in "${EXAMPLES[@]}"; do
  workflow_file="examples/$ex_name/run/*/workflow_history.json"
  # Use shell expansion to check if any matching files exist
  if ls $workflow_file 1>/dev/null 2>&1; then
    echo "  ✓ $ex_name"
  else
    echo "  ✗ $ex_name (missing workflow_history.json)"
  fi
done

echo ""
echo "===================================================="
if [[ $FAILED -eq 0 ]]; then
  echo "✅ All 5 examples complete!"
  echo ""
  echo "Demo Narrative:"
  echo ""
  echo "  Ex00 (Simple):"
  echo "    - Uses single FAISS index"
  echo "    - Fastest path: direct case retrieval"
  echo "    - Minimal modifications"
  echo ""
  echo "  Ex01 (Hierarchical):"
  echo "    - Uses Level 0 physics routing"
  echo "    - Shows solver selection (PeleC for combustion)"
  echo "    - Shows Level 2 CBR cascade"
  echo ""
  echo "  Ex02 (Hierarchical + AMR):"
  echo "    - Same routing as Ex01"
  echo "    - Added complexity: AMR parameters"
  echo "    - Shows schema handling of grid refinement"
  echo ""
  echo "  Ex03 (Complex Parameters):"
  echo "    - Full parameter spec (timesteps, CFL, chemistry)"
  echo "    - Tests Pydantic validation"
  echo "    - Shows potential Reflexion loop if validation fails"
  echo ""
  echo "  Ex04 (Cross-Code):"
  echo "    - Different domain (atmospheric)"
  echo "    - Level 0 routing to ERF (not PeleC)"
  echo "    - May fail due to ERF integration status"
  echo "    - Documents honest failure vs fake success"
  echo ""
else
  echo "⚠️  $FAILED failed - check logs"
fi
echo "===================================================="
echo ""
echo "Compare workflows:"
echo "  jq -r '.workflow_history[] | \"\(.node): \(.action)\"' examples/*/run/*/workflow_history.json"
echo ""
echo "Compare timings:"
echo "  grep 'elapsed' examples/*/generation.log"
echo ""

exit $FAILED
