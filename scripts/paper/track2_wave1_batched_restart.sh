#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/paper/track2_wave1_batched_restart.sh [options]

Options:
  --matrix PATH                     Prompt matrix JSONL (default: benchmark/erf_llm_compare/train_subsample_s42.jsonl)
  --batch-size N                    Rows per batch (default: 20)
  --sleep-sec N                     Sleep seconds between batches (default: 15)
  --out-root PATH                   Root output directory (default: results/track2_recovery)
  --agent-config PATH               Optional config file passed to benchmark runner
  --inputs-file-strategy S          Inputs selection strategy (default: llm_compare)
  --max-rate-limit-retries N        429/rate-limit retries per row (default: 1)
  --max-unavailable-attempts N      llm_unavailable attempts per row (default: 1)
  --assessment-minutes N            Metadata only: planned partial assessment cadence (default: 5)
  --no-verbose-cli                  Disable --verbose-cli forwarding
  --enforce-gates                   Stop early if batch fails gate checks
  -h, --help                        Show help
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
MAX_RATE_LIMIT_RETRIES=1
MAX_UNAVAILABLE_ATTEMPTS=1
ASSESSMENT_MINUTES=5

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
    --max-rate-limit-retries)
      MAX_RATE_LIMIT_RETRIES="$2"; shift 2 ;;
    --max-unavailable-attempts)
      MAX_UNAVAILABLE_ATTEMPTS="$2"; shift 2 ;;
    --assessment-minutes)
      ASSESSMENT_MINUTES="$2"; shift 2 ;;
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
PHASE_STATUS_CSV="$RUN_ROOT/phase_status.csv"

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
  "phase_split": true,
  "python_unbuffered": true,
  "assessment_minutes": $ASSESSMENT_MINUTES,
  "max_rate_limit_retries": $MAX_RATE_LIMIT_RETRIES,
  "max_unavailable_attempts": $MAX_UNAVAILABLE_ATTEMPTS,
  "preserve_agent_artifacts": {
    "save_workflow": true,
    "save_transcript": true,
    "save_log": true
  }
}
EOF

echo "batch_idx,row_start,row_end,row_count,simple_score,hier_score,simple_failed_sentinel,hier_failed_sentinel,hier_non_erf_rows,gate_status,batch_dir" > "$STATUS_CSV"
echo "batch_idx,batch_name,strategy,start_utc,end_utc,duration_sec,weighted_score,failed_rows,phase_dir" > "$PHASE_STATUS_CSV"

run_phase() {
  local batch_idx="$1"
  local batch_name="$2"
  local batch_matrix="$3"
  local batch_dir="$4"
  local strategy="$5"

  local phase_dir="$batch_dir/${strategy}_phase"
  local phase_log="$batch_dir/benchmark_stdout_${strategy}.log"
  mkdir -p "$phase_dir"
  local start_epoch
  start_epoch="$(date +%s)"
  local start_utc
  start_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  log "Starting ${batch_name} strategy=${strategy}"

  local cmd=(python -u scripts/erf_benchmark/run_llm_compare_benchmark.py
    --prompt-matrix "$batch_matrix"
    --out-dir "$phase_dir"
    --strategy "$strategy"
    --inputs-file-strategy "$INPUTS_FILE_STRATEGY"
    --save-workflow
    --save-transcript
    --save-log
    --max-rate-limit-retries "$MAX_RATE_LIMIT_RETRIES"
    --max-unavailable-attempts "$MAX_UNAVAILABLE_ATTEMPTS"
    --flush-prints
  )
  if [[ "$VERBOSE_CLI" -eq 1 ]]; then
    cmd+=(--verbose-cli)
  fi
  if [[ -n "$AGENT_CONFIG" ]]; then
    cmd+=(--agent-config "$AGENT_CONFIG")
  fi

  PYTHONUNBUFFERED=1 "${cmd[@]}" | tee "$phase_log"
  cat "$phase_log" >> "$batch_dir/benchmark_stdout.log"

  local phase_summary="$phase_dir/summary.json"
  if [[ ! -f "$phase_summary" ]]; then
    log "ERROR: missing $phase_summary"
    exit 1
  fi
  cp "$phase_summary" "$batch_dir/summary.${strategy}.json"

  local end_epoch
  end_epoch="$(date +%s)"
  local end_utc
  end_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local duration_sec
  duration_sec=$((end_epoch - start_epoch))

  local score_key failed_key weighted_score failed_rows
  if [[ "$strategy" == "simple" ]]; then
    score_key="simple_weighted_score"
    failed_key="simple_failed_rows"
  else
    score_key="hierarchical_weighted_score"
    failed_key="hierarchical_failed_rows"
  fi
  weighted_score="$(jq -r ".${score_key}" "$phase_summary")"
  failed_rows="$(jq -r ".${failed_key}" "$phase_summary")"
  echo "${batch_idx},${batch_name},${strategy},${start_utc},${end_utc},${duration_sec},${weighted_score},${failed_rows},${phase_dir}" >> "$PHASE_STATUS_CSV"
  log "Completed ${batch_name} strategy=${strategy} score=${weighted_score} failed_rows=${failed_rows} duration_sec=${duration_sec}"
}

merge_phase_artifacts() {
  local batch_dir="$1"
  python - "$batch_dir" "$MAX_RATE_LIMIT_RETRIES" "$MAX_UNAVAILABLE_ATTEMPTS" <<'PY'
import csv
import json
import sys
from pathlib import Path

try:
    from scripts.erf_benchmark.lib.explainability_scoring import summarize_explainability
except ModuleNotFoundError:
    from lib.explainability_scoring import summarize_explainability

batch_dir = Path(sys.argv[1])
max_rate_limit_retries = int(sys.argv[2])
max_unavailable_attempts = int(sys.argv[3])

simple_dir = batch_dir / "simple_phase"
hier_dir = batch_dir / "hierarchical_phase"
summary_simple = json.loads((batch_dir / "summary.simple.json").read_text(encoding="utf-8"))
summary_hier = json.loads((batch_dir / "summary.hierarchical.json").read_text(encoding="utf-8"))

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def concat_jsonl(output_path: Path, inputs: list[Path]) -> list[dict]:
    merged: list[dict] = []
    for path in inputs:
        merged.extend(load_jsonl(path))
    text = "\n".join(json.dumps(row, sort_keys=True) for row in merged)
    if text:
        text += "\n"
    output_path.write_text(text, encoding="utf-8")
    return merged

def concat_csv(output_path: Path, inputs: list[Path]) -> list[dict]:
    rows: list[dict] = []
    fieldnames: list[str] = []
    for path in inputs:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames and not fieldnames:
                fieldnames = list(reader.fieldnames)
            for row in reader:
                rows.append(row)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        if not fieldnames:
            return rows
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return rows

results_rows = concat_jsonl(batch_dir / "results.jsonl", [simple_dir / "results.jsonl", hier_dir / "results.jsonl"])
console_rows = concat_jsonl(batch_dir / "console_logs.jsonl", [simple_dir / "console_logs.jsonl", hier_dir / "console_logs.jsonl"])
events_rows = concat_jsonl(batch_dir / "catastrophic_events.jsonl", [simple_dir / "catastrophic_events.jsonl", hier_dir / "catastrophic_events.jsonl"])
explainability_rows = concat_jsonl(batch_dir / "explainability_calls.jsonl", [simple_dir / "explainability_calls.jsonl", hier_dir / "explainability_calls.jsonl"])
concat_csv(batch_dir / "category_report.csv", [simple_dir / "category_report.csv", hier_dir / "category_report.csv"])
concat_csv(batch_dir / "failures.csv", [simple_dir / "failures.csv", hier_dir / "failures.csv"])
concat_csv(
    batch_dir / "explainability_failures.csv",
    [simple_dir / "explainability_failures.csv", hier_dir / "explainability_failures.csv"],
)

category_rows = []
with (batch_dir / "category_report.csv").open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        try:
            category_rows.append(float(row.get("weighted_score", 0.0)))
        except (TypeError, ValueError):
            category_rows.append(0.0)

summary = {
    "simple_weighted_score": summary_simple.get("simple_weighted_score", 0.0),
    "hierarchical_weighted_score": summary_hier.get("hierarchical_weighted_score", 0.0),
    "simple_failed_rows": summary_simple.get("simple_failed_rows", 0),
    "hierarchical_failed_rows": summary_hier.get("hierarchical_failed_rows", 0),
}
summary["total_failed_rows"] = int(summary["simple_failed_rows"]) + int(summary["hierarchical_failed_rows"])
summary["holdout_weighted_score"] = round((float(summary["simple_weighted_score"]) + float(summary["hierarchical_weighted_score"])) / 2.0, 6)
summary["paraphrase_weighted_score"] = summary["holdout_weighted_score"]
summary["category_min_weighted_score"] = min(category_rows) if category_rows else 0.0
summary["non_erf_sanity_weighted_score"] = summary["holdout_weighted_score"]
summary.update(summarize_explainability(explainability_rows, threshold=0.9))
summary["max_rate_limit_retries"] = max_rate_limit_retries
summary["max_unavailable_attempts"] = max_unavailable_attempts
summary["checkpoint_every_row"] = True
summary["checkpoint_prefix"] = "partial"
summary["merged_from_phase_runs"] = True
summary["rows_merged"] = len(results_rows)
summary["console_rows_merged"] = len(console_rows)
summary["events_merged"] = len(events_rows)
summary["explainability_rows_merged"] = len(explainability_rows)

(batch_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
PY
}

log "Wave1 restart run root: $RUN_ROOT"
log "Rows=$TOTAL_ROWS batch_size=$BATCH_SIZE max_rate_limit_retries=$MAX_RATE_LIMIT_RETRIES max_unavailable_attempts=$MAX_UNAVAILABLE_ATTEMPTS"

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
  : > "$batch_dir/benchmark_stdout.log"

  run_phase "$batch_idx" "$batch_name" "$batch_matrix" "$batch_dir" "simple"
  simple_phase_summary="$batch_dir/summary.simple.json"
  simple_phase_score="$(jq -r '.simple_weighted_score' "$simple_phase_summary")"
  log "Immediate simple signal $batch_name simple_score=$simple_phase_score"

  run_phase "$batch_idx" "$batch_name" "$batch_matrix" "$batch_dir" "hierarchical"
  merge_phase_artifacts "$batch_dir"

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
log "Phase status CSV: $PHASE_STATUS_CSV"
