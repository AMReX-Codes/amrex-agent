#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/erf_benchmark/tune_cborg_deepthought_safe.sh [options]

Options:
  --matrix PATH            Prompt matrix JSONL (default: results/track2_recovery/validation_first10.jsonl)
  --rows N                 Number of rows to run sequentially (default: 5)
  --start-offset N         Starting row offset in matrix (default: 0)
  --config PATH            Agent config YAML (default: results/track2_recovery/model_sweep/configs/lbl__cborg-deepthought.yaml)
  --out-root PATH          Output root (default: results/track2_recovery/model_sweep/runs)
  --pace-sec N             Sleep between rows in seconds (default: 65)
  --max-429-retries N      Runner 429 retries (default: 1)
  --max-unavail N          Runner llm_unavailable attempts (default: 2)
  --skip-preflight         Skip CBORG preflight curl checks
  -h, --help               Show help
USAGE
}

MATRIX="results/track2_recovery/validation_first10.jsonl"
ROWS=5
START_OFFSET=0
CONFIG_PATH="results/track2_recovery/model_sweep/configs/lbl__cborg-deepthought.yaml"
OUT_ROOT="results/track2_recovery/model_sweep/runs"
PACE_SEC=65
MAX_429_RETRIES=1
MAX_UNAVAIL=2
SKIP_PREFLIGHT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix)
      MATRIX="$2"; shift 2 ;;
    --rows)
      ROWS="$2"; shift 2 ;;
    --start-offset)
      START_OFFSET="$2"; shift 2 ;;
    --config)
      CONFIG_PATH="$2"; shift 2 ;;
    --out-root)
      OUT_ROOT="$2"; shift 2 ;;
    --pace-sec)
      PACE_SEC="$2"; shift 2 ;;
    --max-429-retries)
      MAX_429_RETRIES="$2"; shift 2 ;;
    --max-unavail)
      MAX_UNAVAIL="$2"; shift 2 ;;
    --skip-preflight)
      SKIP_PREFLIGHT=1; shift ;;
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
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Missing config: $CONFIG_PATH" >&2
  exit 1
fi
if ! command -v python >/dev/null 2>&1; then
  echo "python not found in PATH" >&2
  exit 1
fi

mkdir -p "$OUT_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="$OUT_ROOT/deepthought_safe_${STAMP}"
mkdir -p "$RUN_ROOT/rows"
STATUS_CSV="$RUN_ROOT/row_status.csv"

echo "row_offset,row_dir,simple_score,simple_failed_rows,total_failed_rows,rate_limit_retries_unavailable" > "$STATUS_CSV"

echo "run_root=$RUN_ROOT"
echo "matrix=$MATRIX rows=$ROWS start_offset=$START_OFFSET pace_sec=$PACE_SEC"
echo "config=$CONFIG_PATH max_429_retries=$MAX_429_RETRIES max_unavail=$MAX_UNAVAIL"

if [[ "$SKIP_PREFLIGHT" -eq 0 ]]; then
  if [[ -z "${CBORG_API_KEY:-}" ]]; then
    echo "CBORG_API_KEY is missing; set it or pass --skip-preflight" >&2
    exit 1
  fi
  echo "Preflight: /v1/models"
  curl -sS -o /dev/null -w "models_status=%{http_code} connect=%{time_connect}s total=%{time_total}s\n" \
    -H "Authorization: Bearer ${CBORG_API_KEY}" \
    https://api.cborg.lbl.gov/v1/models
fi

for ((i=0; i<ROWS; i++)); do
  row_offset=$((START_OFFSET + i))
  row_dir="$RUN_ROOT/rows/row_$(printf '%04d' "$row_offset")"
  mkdir -p "$row_dir"

  echo
  echo "== row_offset=${row_offset} =="
  python -u scripts/erf_benchmark/run_llm_compare_benchmark.py \
    --prompt-matrix "$MATRIX" \
    --out-dir "$row_dir" \
    --strategy simple \
    --max-rows 1 \
    --row-offset "$row_offset" \
    --agent-config "$CONFIG_PATH" \
    --max-rate-limit-retries "$MAX_429_RETRIES" \
    --max-unavailable-attempts "$MAX_UNAVAIL" \
    --save-workflow --save-transcript --save-log --verbose-cli --flush-prints

  summary_json="$row_dir/summary.json"
  if [[ ! -f "$summary_json" ]]; then
    echo "missing summary: $summary_json" >&2
    exit 1
  fi
  simple_score="$(jq -r '.simple_weighted_score' "$summary_json")"
  simple_failed_rows="$(jq -r '.simple_failed_rows' "$summary_json")"
  total_failed_rows="$(jq -r '.total_failed_rows' "$summary_json")"
  rate_limit_retries_unavailable="$(jq -r '.max_rate_limit_retries|tostring + \"/\" + . as $r | $r' "$summary_json" 2>/dev/null || echo "${MAX_429_RETRIES}/${MAX_UNAVAIL}")"
  echo "${row_offset},${row_dir},${simple_score},${simple_failed_rows},${total_failed_rows},${rate_limit_retries_unavailable}" >> "$STATUS_CSV"

  if [[ "$i" -lt $((ROWS - 1)) ]]; then
    echo "Sleeping ${PACE_SEC}s before next row to avoid 429 bursts..."
    sleep "$PACE_SEC"
  fi
done

echo
echo "Completed. Status CSV: $STATUS_CSV"
echo "Summary table:"
column -s, -t "$STATUS_CSV" || cat "$STATUS_CSV"
