#!/usr/bin/env bash
# Capture commit-scoped repository validation snapshot for manuscript metrics.
# Intended outputs:
#   - pytest tests/unit summary
#   - full pytest summary
#   - pytest --cov=. --cov-report=term TOTAL line
#   - known failing tests list (if any)

set -euo pipefail

RESULTS_DIR="results/repo_validation_snapshot_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "Results dir: $RESULTS_DIR"
echo "Commit: $(git rev-parse --short HEAD)" | tee "$RESULTS_DIR/commit.txt"

run_pytest_step() {
  local label="$1"
  local log_file="$2"
  shift 2

  echo "=== $label ===" | tee -a "$RESULTS_DIR/run.log"
  if pytest "$@" 2>&1 | tee "$log_file"; then
    echo "$label status: PASS" | tee -a "$RESULTS_DIR/run.log"
    return 0
  fi

  echo "$label status: FAIL (continuing to collect full snapshot)" | tee -a "$RESULTS_DIR/run.log"
  return 1
}

UNIT_LOG="$RESULTS_DIR/pytest_unit.log"
FULL_LOG="$RESULTS_DIR/pytest_full.log"
COV_LOG="$RESULTS_DIR/pytest_cov.log"

unit_rc=0
full_rc=0
cov_rc=0

run_pytest_step "Step 1: Unit tests" "$UNIT_LOG" tests/unit || unit_rc=$?
run_pytest_step "Step 2: Full test suite" "$FULL_LOG" || full_rc=$?
run_pytest_step "Step 3: Coverage snapshot" "$COV_LOG" --cov=. --cov-report=term || cov_rc=$?

extract_summary_line() {
  local log_file="$1"
  rg -n "={3,} .* in [0-9]+\\.[0-9]+s ={3,}" "$log_file" | tail -n 1 || true
}

extract_failed_tests() {
  local log_file="$1"
  rg -n "^(FAILED|ERROR) " "$log_file" || true
}

cov_total_line="$(rg -n '^TOTAL\\s+' "$COV_LOG" | tail -n 1 || true)"

echo "=== Summary ===" | tee -a "$RESULTS_DIR/run.log"
{
  echo "commit: $(git rev-parse --short HEAD)"
  echo "unit_exit_code: $unit_rc"
  echo "full_exit_code: $full_rc"
  echo "cov_exit_code: $cov_rc"
  echo "unit_summary: $(extract_summary_line "$UNIT_LOG" | sed 's/^.*://')"
  echo "full_summary: $(extract_summary_line "$FULL_LOG" | sed 's/^.*://')"
  echo "coverage_total: ${cov_total_line#*:}"
} | tee "$RESULTS_DIR/summary.txt" | tee -a "$RESULTS_DIR/run.log"

echo "=== Known failing tests (full suite) ===" | tee -a "$RESULTS_DIR/run.log"
extract_failed_tests "$FULL_LOG" | tee "$RESULTS_DIR/known_failing_tests.txt" | tee -a "$RESULTS_DIR/run.log" || true

echo "Done. Results written to $RESULTS_DIR"
