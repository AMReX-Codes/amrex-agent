#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/jmsexton/codes/worktree_sandbox/amrex-agent_wt-erf"
OUT_DIR="${1:-results/track2_recovery/model_sweep/probes/phase2_canary_repro_$(date +%Y%m%dT%H%M%SZ)}"

cd "$REPO_ROOT"

if [[ -z "${CBORG_API_KEY:-}" ]]; then
  echo "CBORG_API_KEY is not set. Export it before running this script." >&2
  exit 1
fi

python -u scripts/erf_benchmark/run_llm_compare_benchmark.py \
  --prompt-matrix benchmark/erf_llm_compare/recovery_prompt_matrix/erf_wave_phase2_canary_8rows.jsonl \
  --out-dir "$OUT_DIR" \
  --strategy simple \
  --agent-config results/track2_recovery/model_sweep/configs/lbl__llama4-scout_tuned_weights_retune_20260316.yaml \
  --max-rate-limit-retries 1 \
  --max-unavailable-attempts 2 \
  --continue-on-catastrophic \
  --save-workflow \
  --save-transcript \
  --save-log \
  --verbose-cli \
  --flush-prints

echo "Reproduction run written under: $OUT_DIR"
