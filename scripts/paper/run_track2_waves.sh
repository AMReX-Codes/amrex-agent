#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage:
  ./scripts/paper/run_track2_waves.sh [--wave2]

Default (no flags): run Wave 1 only, then stop for human tuning.
--wave2: run Wave 2, then auto-run Wave 3 if <10h elapsed since Wave 1 start.
USAGE
}

RUN_WAVE2=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --wave2)
      RUN_WAVE2=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TRACK2_DIR="results/track2"
RUN_LOG="$TRACK2_DIR/run.log"
BENCH_RUNNER="scripts/erf_benchmark/run_llm_compare_benchmark.py"
COMPARE_RUNS="scripts/erf_benchmark/compare_runs.py"

TRAIN_MATRIX="benchmark/erf_llm_compare/train.jsonl"
HOLDOUT_MATRIX="benchmark/erf_llm_compare/holdout.jsonl"
PARAPHRASE_MATRIX="benchmark/erf_llm_compare/paraphrase.jsonl"
TRAIN_SUBSAMPLE="benchmark/erf_llm_compare/train_subsample_s42.jsonl"

mkdir -p "$TRACK2_DIR"

iso_ts() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf '[%s] %s\n' "$(iso_ts)" "$*" | tee -a "$RUN_LOG"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    log "ERROR: missing required file: $path"
    exit 1
  fi
}

build_train_subsample() {
  require_file "$TRAIN_MATRIX"
  log "Wave 1 / Step 1: building deterministic 100-row train subsample (seed=42)"

  TRAIN_MATRIX="$TRAIN_MATRIX" TRAIN_SUBSAMPLE="$TRAIN_SUBSAMPLE" python - <<'PY'
import json
import os
import random
from pathlib import Path

train_path = Path(os.environ["TRAIN_MATRIX"])
out_path = Path(os.environ["TRAIN_SUBSAMPLE"])
rows = [json.loads(line) for line in train_path.read_text(encoding="utf-8").splitlines() if line.strip()]

sample_size = min(100, len(rows))
rng = random.Random(42)

strat_key = None
for candidate in ("solver", "code"):
    if any(isinstance(row.get(candidate), str) and row.get(candidate) for row in rows):
        strat_key = candidate
        break

if strat_key is None:
    sampled = rng.sample(rows, sample_size)
else:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        value = row.get(strat_key)
        if not isinstance(value, str) or not value:
            value = "__missing__"
        groups.setdefault(value, []).append(row)

    for group_rows in groups.values():
        group_rows.sort(key=lambda r: r.get("row_id", ""))

    keys = sorted(groups)
    base = sample_size // len(keys)
    remainder = sample_size % len(keys)
    targets = {k: base + (1 if i < remainder else 0) for i, k in enumerate(keys)}

    sampled = []
    leftovers = []
    for key in keys:
        group_rows = groups[key]
        need = min(targets[key], len(group_rows))
        if need:
            chosen = set(rng.sample(range(len(group_rows)), need))
            for idx, row in enumerate(group_rows):
                if idx in chosen:
                    sampled.append(row)
                else:
                    leftovers.append(row)
        else:
            leftovers.extend(group_rows)

    if len(sampled) < sample_size:
        missing = sample_size - len(sampled)
        leftovers = sorted(leftovers, key=lambda r: r.get("row_id", ""))
        sampled.extend(rng.sample(leftovers, missing))

sampled = sorted(sampled, key=lambda r: r.get("row_id", ""))
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in sampled) + "\n", encoding="utf-8")
print(f"subsample_rows={len(sampled)} stratify_key={strat_key}")
PY
}

launch_wave_pair() {
  local wave_name="$1"
  local matrix_path="$2"

  require_file "$matrix_path"

  local ts
  ts="$(date +%Y%m%d_%H%M%S)"
  local out_simple="$TRACK2_DIR/${wave_name}_simple_${ts}"
  local out_hier="$TRACK2_DIR/${wave_name}_hierarchical_${ts}"

  mkdir -p "$out_simple" "$out_hier"

  log "${wave_name}: launching simple strategy -> $out_simple"
  local simple_start
  simple_start="$(date +%s)"
  python "$BENCH_RUNNER" --strategy simple --prompt-matrix "$matrix_path" --out-dir "$out_simple" >"$out_simple/stdout.log" 2>&1 &
  local pid_simple=$!

  log "${wave_name}: launching hierarchical strategy -> $out_hier"
  local hier_start
  hier_start="$(date +%s)"
  python "$BENCH_RUNNER" --strategy hierarchical --prompt-matrix "$matrix_path" --out-dir "$out_hier" >"$out_hier/stdout.log" 2>&1 &
  local pid_hier=$!

  log "${wave_name}: PID simple=$pid_simple"
  log "${wave_name}: PID hierarchical=$pid_hier"

  local rc_simple=0
  local rc_hier=0

  set +e
  wait "$pid_simple"
  rc_simple=$?
  wait "$pid_hier"
  rc_hier=$?
  set -e

  local simple_end
  simple_end="$(date +%s)"
  local hier_end
  hier_end="$(date +%s)"

  local simple_elapsed=$(( simple_end - simple_start ))
  local hier_elapsed=$(( hier_end - hier_start ))

  log "${wave_name}: simple wall_time_sec=${simple_elapsed} exit_code=${rc_simple}"
  log "${wave_name}: hierarchical wall_time_sec=${hier_elapsed} exit_code=${rc_hier}"

  WAVE_SIMPLE_DIR="$out_simple"
  WAVE_HIER_DIR="$out_hier"

  if [[ "$rc_simple" -ne 0 || "$rc_hier" -ne 0 ]]; then
    log "ERROR: ${wave_name} strategy run failed (simple=${rc_simple}, hierarchical=${rc_hier})"
    return 1
  fi
  return 0
}

summarize_wave() {
  local wave_name="$1"
  local matrix_path="$2"
  local simple_dir="$3"
  local hier_dir="$4"
  local out_json="$5"

  WAVE_NAME="$wave_name" MATRIX_PATH="$matrix_path" SIMPLE_DIR="$simple_dir" HIER_DIR="$hier_dir" OUT_JSON="$out_json" python - <<'PY' | tee -a "$RUN_LOG"
import csv
import json
import os
from pathlib import Path

wave = os.environ["WAVE_NAME"]
matrix_path = Path(os.environ["MATRIX_PATH"])
simple_dir = Path(os.environ["SIMPLE_DIR"])
hier_dir = Path(os.environ["HIER_DIR"])
out_json = Path(os.environ["OUT_JSON"])

matrix_rows = [json.loads(line) for line in matrix_path.read_text(encoding="utf-8").splitlines() if line.strip()]
row_lookup = {str(row.get("row_id", "")): row for row in matrix_rows}

def solver_for(row_id: str):
    row = row_lookup.get(row_id, {})
    target_case_relpath = row.get("target_case_relpath")
    if isinstance(target_case_relpath, str) and target_case_relpath:
        solver = target_case_relpath.split("/", 1)[0].strip()
        if solver:
            return solver
    for key in ("solver", "code", "expected_solver", "target_solver"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None

def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def summarize_strategy(strategy: str, out_dir: Path):
    results_rows = read_jsonl(out_dir / "results.jsonl")
    filtered = [row for row in results_rows if row.get("strategy") == strategy]

    if not filtered and results_rows:
        filtered = results_rows

    total = len(filtered)
    case_correct = sum(1 for row in filtered if int(row.get("case_match", 0)) == 1)
    failed = [row for row in filtered if int(row.get("case_match", 0)) == 0 or int(row.get("inputs_match", 0)) == 0]

    per_solver_failure_counts = {}
    per_solver_accuracy = {}
    solver_totals = {}
    solver_correct = {}

    for row in filtered:
        row_id = str(row.get("row_id", ""))
        solver = solver_for(row_id)
        if not solver:
            continue
        solver_totals[solver] = solver_totals.get(solver, 0) + 1
        if int(row.get("case_match", 0)) == 1:
            solver_correct[solver] = solver_correct.get(solver, 0) + 1

    for row in failed:
        row_id = str(row.get("row_id", ""))
        solver = solver_for(row_id) or "__unknown__"
        per_solver_failure_counts[solver] = per_solver_failure_counts.get(solver, 0) + 1

    for solver, total_count in sorted(solver_totals.items()):
        correct = solver_correct.get(solver, 0)
        per_solver_accuracy[solver] = {
            "correct": correct,
            "total": total_count,
            "accuracy": round(correct / total_count, 6) if total_count else 0.0,
        }

    return {
        "strategy": strategy,
        "output_dir": str(out_dir),
        "total_rows": total,
        "case_correct": case_correct,
        "case_accuracy": round(case_correct / total, 6) if total else 0.0,
        "failed_rows": len(failed),
        "per_solver_failure_counts": per_solver_failure_counts,
        "per_solver_accuracy": per_solver_accuracy,
    }

simple_summary = summarize_strategy("simple", simple_dir)
hier_summary = summarize_strategy("hierarchical", hier_dir)

payload = {
    "wave": wave,
    "matrix_path": str(matrix_path),
    "strategies": {
        "simple": simple_summary,
        "hierarchical": hier_summary,
    },
}
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

print(f"{wave}: simple case_accuracy={simple_summary['case_accuracy']:.6f} failed_rows={simple_summary['failed_rows']}")
print(f"{wave}: simple per-solver failure counts={json.dumps(simple_summary['per_solver_failure_counts'], sort_keys=True)}")
print(f"{wave}: hierarchical case_accuracy={hier_summary['case_accuracy']:.6f} failed_rows={hier_summary['failed_rows']}")
print(f"{wave}: hierarchical per-solver failure counts={json.dumps(hier_summary['per_solver_failure_counts'], sort_keys=True)}")
print(f"{wave}: wrote summary={out_json}")
PY
}

wave1_start_epoch_from_log() {
  if [[ ! -f "$RUN_LOG" ]]; then
    return 1
  fi
  local line
  line="$(grep -E 'WAVE1_START_EPOCH=' "$RUN_LOG" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return 1
  fi
  echo "$line" | sed -E 's/.*WAVE1_START_EPOCH=([0-9]+).*/\1/'
}

write_final_summary() {
  local ts
  ts="$(date +%Y%m%d_%H%M%S)"
  local out_path="$TRACK2_DIR/summary_${ts}.json"

  TRACK2_DIR="$TRACK2_DIR" OUT_PATH="$out_path" python - <<'PY' | tee -a "$RUN_LOG"
import json
import os
from pathlib import Path

track2 = Path(os.environ["TRACK2_DIR"])
out_path = Path(os.environ["OUT_PATH"])

wave_files = [
    ("wave1", track2 / "wave1_summary.json"),
    ("wave2", track2 / "wave2_summary.json"),
    ("wave3", track2 / "wave3_summary.json"),
]

waves = {}
for name, path in wave_files:
    if path.exists():
        waves[name] = json.loads(path.read_text(encoding="utf-8"))

compare_path = track2 / "compare_wave2.json"
compare_payload = None
if compare_path.exists():
    compare_payload = json.loads(compare_path.read_text(encoding="utf-8"))

payload = {
    "completed_waves": sorted(waves.keys()),
    "waves": waves,
    "compare_wave2": compare_payload,
}
out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

print("Final accuracy table (wave x strategy):")
for wave_name in sorted(waves):
    strategies = waves[wave_name].get("strategies", {})
    for strategy in ("simple", "hierarchical"):
        info = strategies.get(strategy, {})
        acc = float(info.get("case_accuracy", 0.0))
        failed = int(info.get("failed_rows", 0))
        print(f"  {wave_name:>5} | {strategy:<12} | case_accuracy={acc:.6f} | failed_rows={failed}")
print(f"Wrote final summary: {out_path}")
PY
}

run_wave1_only() {
  log "Wave 1 start"
  local start_epoch
  start_epoch="$(date +%s)"
  log "WAVE1_START_EPOCH=${start_epoch}"
  log "WAVE1_START_ISO=$(iso_ts)"

  build_train_subsample | tee -a "$RUN_LOG"

  log "Wave 1 / Step 2: launching simple and hierarchical in parallel"
  launch_wave_pair "wave1" "$TRAIN_SUBSAMPLE"

  log "Wave 1 / Step 3: summarizing wave outputs"
  summarize_wave "wave1" "$TRAIN_SUBSAMPLE" "$WAVE_SIMPLE_DIR" "$WAVE_HIER_DIR" "$TRACK2_DIR/wave1_summary.json"

  log "Wave 1 / Step 4: stopping for human tuning checkpoint"
  cat <<'MSG' | tee -a "$RUN_LOG"
Wave 1 complete. Review results/track2/wave1_summary.json.
Adjust L2 weights in config based on observed failure patterns.
When ready, run: ./run_track2_waves.sh --wave2
MSG
}

run_wave2_and_optional_wave3() {
  require_file "$HOLDOUT_MATRIX"

  log "Wave 2 start"
  launch_wave_pair "wave2" "$HOLDOUT_MATRIX"
  summarize_wave "wave2" "$HOLDOUT_MATRIX" "$WAVE_SIMPLE_DIR" "$WAVE_HIER_DIR" "$TRACK2_DIR/wave2_summary.json"

  log "Wave 2 post-step: running compare_runs.py (non-gating for Wave 3)"
  local compare_rc=0
  set +e
  python "$COMPARE_RUNS" \
    --baseline "$WAVE_SIMPLE_DIR/summary.json" \
    --candidate "$WAVE_HIER_DIR/summary.json" \
    --out "$TRACK2_DIR/compare_wave2.json"
  compare_rc=$?
  set -e
  log "compare_runs exit_code=${compare_rc} out=$TRACK2_DIR/compare_wave2.json"

  local wave1_epoch
  if ! wave1_epoch="$(wave1_start_epoch_from_log)"; then
    log "ERROR: could not find WAVE1_START_EPOCH in $RUN_LOG"
    exit 1
  fi

  local now_epoch
  now_epoch="$(date +%s)"
  local elapsed_sec=$(( now_epoch - wave1_epoch ))
  local limit_sec=$(( 10 * 3600 ))
  log "Wave 3 gate: elapsed_since_wave1_sec=${elapsed_sec} threshold_sec=${limit_sec}"

  if (( elapsed_sec < limit_sec )); then
    require_file "$PARAPHRASE_MATRIX"
    log "Wave 3 start (elapsed time under 10h)"
    launch_wave_pair "wave3" "$PARAPHRASE_MATRIX"
    summarize_wave "wave3" "$PARAPHRASE_MATRIX" "$WAVE_SIMPLE_DIR" "$WAVE_HIER_DIR" "$TRACK2_DIR/wave3_summary.json"
  else
    log "Wave 3 skipped: elapsed time since Wave 1 start exceeded 10 hours"
  fi

  write_final_summary
}

log "Track 2 wave orchestration entrypoint (wave2_mode=${RUN_WAVE2})"
if [[ "$RUN_WAVE2" -eq 1 ]]; then
  run_wave2_and_optional_wave3
else
  run_wave1_only
fi

log "Track 2 wave orchestration complete"
