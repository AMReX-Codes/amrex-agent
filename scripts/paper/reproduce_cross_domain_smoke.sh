#!/usr/bin/env bash
# Reproduce core Track-1 evidence used in the manuscript.
# Requires: amrex-agent-dev environment, CBORG/API credentials, repo root cwd.
# Evidence anchor commit for flat-score routing patch: e95b3d8 (in wt-erf branch history).

set -euo pipefail

RESULTS_DIR="results/track1_reproduce_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${CONFIG_DIR:-$SCRIPT_DIR/configs}"

echo "Results dir: $RESULTS_DIR"

echo "=== Step 1 (optional): README registry audit ===" | tee "$RESULTS_DIR/run.log"
pytest tests/e2e/test_readme_command_registry.py -v \
  2>&1 | tee "$RESULTS_DIR/readme_registry.log" || true

echo "=== Step 2: Cross-domain smoke ===" | tee -a "$RESULTS_DIR/run.log"
pytest tests/e2e/test_demo_smoke.py -v --tb=short \
  2>&1 | tee "$RESULTS_DIR/smoke.log"

echo "=== Step 3: Indexing strategies (JICF) ===" | tee -a "$RESULTS_DIR/run.log"
if pytest tests/integration/test_jicf_indexing_strategies.py -v --tb=short \
  2>&1 | tee "$RESULTS_DIR/indexing_strategies.log"; then
  echo "Step 3 status: PASS" | tee -a "$RESULTS_DIR/run.log"
else
  echo "Step 3 status: FAIL (continuing for pilot and artifact collection)" | tee -a "$RESULTS_DIR/run.log"
fi

echo "=== Step 3b (optional): Hierarchical-only verbose diagnostics ===" | tee -a "$RESULTS_DIR/run.log"
pytest tests/integration/test_jicf_indexing_strategies.py -k hierarchical -v --tb=short -s \
  2>&1 | tee "$RESULTS_DIR/hierarchical_verbose.log" || true

echo "=== Step 4 (optional): Direct ERF dry-run probes with persisted workflow/log artifacts ===" | tee -a "$RESULTS_DIR/run.log"
PROMPT="${PROMPT:-Run a supercell 2D squall line simulation}"
if compgen -G "$CONFIG_DIR/*.yaml" > /dev/null; then
  mapfile -t MODEL_CONFIGS < <(ls "$CONFIG_DIR"/*.yaml | sort)
else
  MODEL_CONFIGS=()
fi

if [[ ${#MODEL_CONFIGS[@]} -eq 0 ]]; then
  echo "No pilot configs found in $CONFIG_DIR; skipping Step 4." | tee -a "$RESULTS_DIR/run.log"
else
  echo "Pilot config dir: $CONFIG_DIR" | tee -a "$RESULTS_DIR/run.log"
  printf '%s\n' "${MODEL_CONFIGS[@]}" | sed 's/^/  - /' | tee -a "$RESULTS_DIR/run.log"
  for CFG in "${MODEL_CONFIGS[@]}"; do
    MODEL_ID="$(basename "$CFG" .yaml)"
    for STRAT in simple hierarchical override_static; do
      OUT_SUBDIR="$RESULTS_DIR/pilot_${MODEL_ID}_${STRAT}"
      mkdir -p "$OUT_SUBDIR"
      python amrex_agent.py \
        --config "$CFG" \
        --indexing-strategy "$STRAT" \
        --inputs-file-strategy newest \
        --run-mode dry \
        --json \
        --save-workflow \
        --save-log \
        --save-transcript \
        --output-dir "$OUT_SUBDIR" \
        --prompt "$PROMPT" \
        > "$OUT_SUBDIR/result.json" 2> "$OUT_SUBDIR/stderr.log" || true
    done
  done
fi

echo "=== Step 5 (optional): Minimal benchmark summary regeneration ===" | tee -a "$RESULTS_DIR/run.log"
# Run from repo root with module path to avoid relative import issues.
python -m scripts.erf_benchmark.run_llm_compare_benchmark \
  --inputs-file-strategy llm_compare \
  --out-dir benchmark/erf_llm_compare/runs/track1_reproduce_minimal \
  2>&1 | tee "$RESULTS_DIR/erf_benchmark.log" || true

echo "=== Summary ===" | tee -a "$RESULTS_DIR/run.log"
rg -n "passed|failed|AssertionError|short test summary|in [0-9]+\\.[0-9]+s" \
  "$RESULTS_DIR/smoke.log" \
  "$RESULTS_DIR/indexing_strategies.log" \
  "$RESULTS_DIR/hierarchical_verbose.log" \
  2>/dev/null | tee -a "$RESULTS_DIR/run.log" || true

if compgen -G "$RESULTS_DIR/pilot_*/*result.json" > /dev/null; then
  echo "=== Pilot matrix outputs ===" | tee -a "$RESULTS_DIR/run.log"
  find "$RESULTS_DIR" -type f -path "*/pilot_*/*result.json" | sort | sed 's/^/  - /' | tee -a "$RESULTS_DIR/run.log"
fi

echo "Done. Results written to $RESULTS_DIR"
