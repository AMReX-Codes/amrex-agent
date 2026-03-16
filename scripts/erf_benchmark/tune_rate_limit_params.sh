#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/erf_benchmark/tune_rate_limit_params.sh [options]

Options:
  --matrix PATH             Prompt matrix JSONL (default: results/track2_recovery/model_sweep/validation_first5.jsonl)
  --rows N                  Row cap for each trial via --max-rows (default: 5)
  --model-config PATH       Base model config YAML (default: results/track2_recovery/model_sweep/configs/claude-sonnet.yaml)
  --out-root PATH           Output root (default: results/track2_recovery/model_sweep/runs)
  --llm-retries LIST        Comma list for llm_retry_max_attempts (default: 1,2,3)
  --embed-retries LIST      Comma list for embedding_retry_max_attempts (default: 1,2,3)
  --embed-rpm LIST          Comma list for embedding_rate_limit_rpm (default: 6,10,15)
  --runner-429 N            Runner max-rate-limit-retries (default: 1)
  --runner-unavail N        Runner max-unavailable-attempts (default: 2)
  -h, --help                Show help
USAGE
}

MATRIX="results/track2_recovery/model_sweep/validation_first5.jsonl"
ROWS=5
MODEL_CONFIG="results/track2_recovery/model_sweep/configs/claude-sonnet.yaml"
OUT_ROOT="results/track2_recovery/model_sweep/runs"
LLM_RETRIES_CSV="1,2,3"
EMBED_RETRIES_CSV="1,2,3"
EMBED_RPM_CSV="6,10,15"
RUNNER_429=1
RUNNER_UNAVAIL=2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix)
      MATRIX="$2"; shift 2 ;;
    --rows)
      ROWS="$2"; shift 2 ;;
    --model-config)
      MODEL_CONFIG="$2"; shift 2 ;;
    --out-root)
      OUT_ROOT="$2"; shift 2 ;;
    --llm-retries)
      LLM_RETRIES_CSV="$2"; shift 2 ;;
    --embed-retries)
      EMBED_RETRIES_CSV="$2"; shift 2 ;;
    --embed-rpm)
      EMBED_RPM_CSV="$2"; shift 2 ;;
    --runner-429)
      RUNNER_429="$2"; shift 2 ;;
    --runner-unavail)
      RUNNER_UNAVAIL="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ ! -f "$MATRIX" ]]; then
  echo "Missing matrix: $MATRIX" >&2
  exit 1
fi
if [[ ! -f "$MODEL_CONFIG" ]]; then
  echo "Missing model config: $MODEL_CONFIG" >&2
  exit 1
fi

mkdir -p "$OUT_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="$OUT_ROOT/rate_limit_tune_${STAMP}"
mkdir -p "$RUN_ROOT/configs" "$RUN_ROOT/trials"

RESULTS_CSV="$RUN_ROOT/tuning_results.csv"
echo "trial_id,llm_retry_max_attempts,embedding_retry_max_attempts,embedding_rate_limit_rpm,simple_score,simple_failed_rows,total_retry_events,total_retry_count,llm_unavailable_events,elapsed_sec,trial_dir" > "$RESULTS_CSV"

IFS=',' read -r -a LLM_RETRIES <<< "$LLM_RETRIES_CSV"
IFS=',' read -r -a EMBED_RETRIES <<< "$EMBED_RETRIES_CSV"
IFS=',' read -r -a EMBED_RPMS <<< "$EMBED_RPM_CSV"

echo "run_root=$RUN_ROOT"
echo "matrix=$MATRIX rows=$ROWS model_config=$MODEL_CONFIG"
echo "grid llm_retries=$LLM_RETRIES_CSV embed_retries=$EMBED_RETRIES_CSV embed_rpm=$EMBED_RPM_CSV"

trial_idx=0
for llm_r in "${LLM_RETRIES[@]}"; do
  for emb_r in "${EMBED_RETRIES[@]}"; do
    for rpm in "${EMBED_RPMS[@]}"; do
      trial_idx=$((trial_idx + 1))
      trial_id="$(printf 'trial_%03d' "$trial_idx")"
      trial_dir="$RUN_ROOT/trials/$trial_id"
      cfg_path="$RUN_ROOT/configs/${trial_id}.yaml"

      cat "$MODEL_CONFIG" > "$cfg_path"
      {
        echo ""
        echo "# rate-limit tuning override"
        echo "llm_retry_max_attempts: $llm_r"
        echo "embedding_retry_max_attempts: $emb_r"
        echo "embedding_rate_limit_rpm: $rpm"
      } >> "$cfg_path"

      echo
      echo "== $trial_id (llm=$llm_r embed_retries=$emb_r rpm=$rpm) =="
      start_epoch="$(date +%s)"
      python -u scripts/erf_benchmark/run_llm_compare_benchmark.py \
        --prompt-matrix "$MATRIX" \
        --out-dir "$trial_dir" \
        --strategy simple \
        --max-rows "$ROWS" \
        --agent-config "$cfg_path" \
        --max-rate-limit-retries "$RUNNER_429" \
        --max-unavailable-attempts "$RUNNER_UNAVAIL" \
        --save-workflow --save-transcript --save-log --verbose-cli --flush-prints
      end_epoch="$(date +%s)"
      elapsed_sec=$((end_epoch - start_epoch))

      python - "$trial_id" "$llm_r" "$emb_r" "$rpm" "$elapsed_sec" "$trial_dir" "$RESULTS_CSV" <<'PY'
import csv
import json
import sys
from pathlib import Path

trial_id, llm_r, emb_r, rpm, elapsed_sec, trial_dir, results_csv = sys.argv[1:]
trial_path = Path(trial_dir)
summary = json.loads((trial_path / "summary.json").read_text(encoding="utf-8"))

retry_events = 0
retry_count = 0
console_path = trial_path / "console_logs.jsonl"
if console_path.exists():
    for line in console_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rc = int(row.get("rate_limit_retries", 0) or 0)
        if rc > 0:
            retry_events += 1
            retry_count += rc

llm_unavailable_events = 0
events_path = trial_path / "catastrophic_events.jsonl"
if events_path.exists():
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("reason") == "llm_unavailable":
            llm_unavailable_events += 1

with Path(results_csv).open("a", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow([
        trial_id,
        llm_r,
        emb_r,
        rpm,
        summary.get("simple_weighted_score"),
        summary.get("simple_failed_rows"),
        retry_events,
        retry_count,
        llm_unavailable_events,
        elapsed_sec,
        trial_dir,
    ])
PY
    done
  done
done

echo
echo "Raw results: $RESULTS_CSV"
echo "Ranked (best first: fewer unavailable, fewer retries, shorter runtime):"
python - "$RESULTS_CSV" <<'PY'
import csv
import sys
from pathlib import Path

rows = []
with Path(sys.argv[1]).open("r", encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        row["_llm_unavail"] = int(row["llm_unavailable_events"])
        row["_retry_count"] = int(row["total_retry_count"])
        row["_elapsed"] = int(row["elapsed_sec"])
        row["_score"] = float(row["simple_score"])
        rows.append(row)

rows.sort(key=lambda r: (r["_llm_unavail"], r["_retry_count"], r["_elapsed"], -r["_score"]))
print("trial_id llm_retry embed_retry embed_rpm score failed unavailable retry_count elapsed_sec")
for r in rows:
    print(
        f"{r['trial_id']} {r['llm_retry_max_attempts']} {r['embedding_retry_max_attempts']} "
        f"{r['embedding_rate_limit_rpm']} {r['simple_score']} {r['simple_failed_rows']} "
        f"{r['llm_unavailable_events']} {r['total_retry_count']} {r['elapsed_sec']}"
    )
PY
