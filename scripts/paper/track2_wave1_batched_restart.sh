#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/paper/track2_wave1_batched_restart.sh [options]

Options:
  --matrix PATH            Prompt matrix JSONL (default: benchmark/erf_llm_compare/train_subsample_s42.jsonl)
  --batch-size N           Rows per batch (default: 20)
  --sleep-sec N            Sleep seconds between batches (default: 15)
  --out-root PATH          Root output directory (default: results/track2_recovery)
  --agent-config PATH      Optional config file passed to benchmark runner
  --inputs-file-strategy S Inputs selection strategy (default: llm_compare)
  --no-verbose-cli         Disable --verbose-cli forwarding
  --enforce-gates          Stop early if batch fails gate checks
  -h, --help               Show help
USAGE
}

MATRIX="benchmark/erf_llm_compare/train_subsample_s42.jsonl"
BATCH_SIZE=20
SLEEP_SEC=15
OUT_ROOT="results/track2_recovery"
AGENT_CONFIG=""
INPUTS_FILE_STRATEGY="llm_compare"
VERBOSE_CLI=1
ENFORCE_GATES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix)
      MATRIX="$2"; shift 2 ;;
    --batch-size)
      BATCH_SIZE="$2"; shift 2 ;;
    --sleep-sec)
      SLEEP_SEC="$2"; shift 2 ;;
    --out-root)
      OUT_ROOT="$2"; shift 2 ;;
    --agent-config)
      AGENT_CONFIG="$2"; shift 2 ;;
    --inputs-file-strategy)
      INPUTS_FILE_STRATEGY="$2"; shift 2 ;;
    --no-verbose-cli)
      VERBOSE_CLI=0; shift ;;
    --enforce-gates)
      ENFORCE_GATES=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2 ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ ! -f "$MATRIX" ]]; then
  echo "Missing matrix: $MATRIX" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="$OUT_ROOT/wave1_batched_restart_${STAMP}"
mkdir -p "$RUN_ROOT/batches"

RUN_LOG="$RUN_ROOT/run.log"
STATUS_CSV="$RUN_ROOT/batch_status.csv"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$RUN_LOG"
}

TOTAL_ROWS="$(wc -l < "$MATRIX" | tr -d ' ')"
if [[ "$TOTAL_ROWS" -eq 0 ]]; then
  echo "Matrix has no rows: $MATRIX" >&2
  exit 1
fi

cat > "$RUN_ROOT/restart_config.json" <<EOF
{
  "matrix": "$MATRIX",
  "total_rows": $TOTAL_ROWS,
  "batch_size": $BATCH_SIZE,
  "sleep_sec": $SLEEP_SEC,
  "inputs_file_strategy": "$INPUTS_FILE_STRATEGY",
  "verbose_cli": $VERBOSE_CLI,
  "enforce_gates": $ENFORCE_GATES,
  "preserve_agent_artifacts": {
    "save_workflow": true,
    "save_transcript": true,
    "save_log": true
  }
}
EOF

echo "batch_idx,row_start,row_end,row_count,simple_score,hier_score,simple_failed_sentinel,hier_failed_sentinel,hier_non_erf_rows,gate_status,batch_dir" > "$STATUS_CSV"

log "Wave1 restart run root: $RUN_ROOT"
log "Rows=$TOTAL_ROWS batch_size=$BATCH_SIZE"

batch_idx=0
row_start=0
while [[ "$row_start" -lt "$TOTAL_ROWS" ]]; do
  batch_idx=$((batch_idx + 1))
  row_end=$((row_start + BATCH_SIZE))
  if [[ "$row_end" -gt "$TOTAL_ROWS" ]]; then
    row_end="$TOTAL_ROWS"
  fi
  row_count=$((row_end - row_start))

  batch_name="$(printf "batch_%03d_rows_%04d_%04d" "$batch_idx" "$row_start" "$row_end")"
  batch_dir="$RUN_ROOT/batches/$batch_name"
  mkdir -p "$batch_dir"

  batch_matrix="$batch_dir/prompt_matrix.batch.jsonl"
  sed -n "$((row_start + 1)),$row_end"p "$MATRIX" > "$batch_matrix"

  log "Starting $batch_name count=$row_count"

  cmd=(python scripts/erf_benchmark/run_llm_compare_benchmark.py
    --prompt-matrix "$batch_matrix"
    --out-dir "$batch_dir"
    --inputs-file-strategy "$INPUTS_FILE_STRATEGY"
    --save-workflow
    --save-transcript
    --save-log
  )
  if [[ "$VERBOSE_CLI" -eq 1 ]]; then
    cmd+=(--verbose-cli)
  fi
  if [[ -n "$AGENT_CONFIG" ]]; then
    cmd+=(--agent-config "$AGENT_CONFIG")
  fi

  "${cmd[@]}" | tee "$batch_dir/benchmark_stdout.log"

  summary_json="$batch_dir/summary.json"
  if [[ ! -f "$summary_json" ]]; then
    log "ERROR: missing $summary_json"
    exit 1
  fi

  simple_score="$(jq -r '.simple_weighted_score' "$summary_json")"
  hier_score="$(jq -r '.hierarchical_weighted_score' "$summary_json")"
  simple_failed_sentinel="$(jq -r '.simple_failed_rows' "$summary_json")"
  hier_failed_sentinel="$(jq -r '.hierarchical_failed_rows' "$summary_json")"

  hier_non_erf_rows="$(jq -s '
    map(select(.strategy=="hierarchical" and .purpose=="solver_baseline_selection")) as $rows
    | ($rows | map({row_id, solver:(.observed.selected_solver // "")}) | group_by(.row_id))
    | map({row_id: .[0].row_id, has_erf: any(.[]; .solver=="ERF")})
    | map(select(.has_erf | not))
    | length
  ' "$batch_dir/explainability_calls.jsonl")"

  gate_status="pass"
  if [[ "$hier_non_erf_rows" -gt 0 ]]; then
    gate_status="fail:hier_non_erf"
  fi

  echo "$batch_idx,$row_start,$row_end,$row_count,$simple_score,$hier_score,$simple_failed_sentinel,$hier_failed_sentinel,$hier_non_erf_rows,$gate_status,$batch_dir" >> "$STATUS_CSV"

  log "Completed $batch_name simple_score=$simple_score hier_score=$hier_score simple_failed_sentinel=$simple_failed_sentinel hier_failed_sentinel=$hier_failed_sentinel hier_non_erf_rows=$hier_non_erf_rows gate=$gate_status"

  if [[ "$ENFORCE_GATES" -eq 1 && "$gate_status" != "pass" ]]; then
    log "Stopping early due to gate failure in $batch_name"
    break
  fi

  row_start="$row_end"
  if [[ "$row_start" -lt "$TOTAL_ROWS" ]]; then
    log "Sleeping ${SLEEP_SEC}s before next batch"
    sleep "$SLEEP_SEC"
  fi
done

log "Batch run complete. Status CSV: $STATUS_CSV"
