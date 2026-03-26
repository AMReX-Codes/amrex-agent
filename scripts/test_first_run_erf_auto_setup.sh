#!/usr/bin/env bash
set -euo pipefail

# Phase 14 command matrix runner
# Usage:
#   export CBORG_API_KEY=...
#   bash scripts/phase14_command_matrix.sh
# Optional overrides:
#   REPO_URL, BRANCH, ROOT, PROMPT, PHASE14_MODE, BUILD_SCENARIO, FORCE_BUILD_ALL, RUN_SCENARIOS, PHASE14_INTERACTIVE_MODE

export TS="${TS:-$(date +%Y%m%d_%H%M%S)}"
export ROOT="${ROOT:-$HOME/codes/worktree_sandbox/phase14_runs_$TS}"
export REPO_URL="${REPO_URL:-git@github.com:AMReX-Codes/amrex-agent.git}"
export BRANCH="${BRANCH:-preflight_layer_fix_stack_main_erf_test_visuals}"
export PROMPT="${PROMPT:-Run a 2D squall line simulation using a Straka-style/Kessler setup with open x boundaries and HO outflow aloft. Run the simulation for 10 steps and output simulation data every 1 step. Visualize the cloud water every 1 step from the simulation data.}"

export PHASE14_MODE="${PHASE14_MODE:-fast}"
export BUILD_SCENARIO="${BUILD_SCENARIO:-E}"
export FORCE_BUILD_ALL="${FORCE_BUILD_ALL:-0}"
export RUN_SCENARIOS="${RUN_SCENARIOS:-A,B,C,D,E}"
export PHASE14_INTERACTIVE_MODE="${PHASE14_INTERACTIVE_MODE:-auto}"
export SCENARIO_A_SELECTION="${SCENARIO_A_SELECTION:-4}"
export SCENARIO_B_SELECTION="${SCENARIO_B_SELECTION:-2}"
if [[ -z "${SKIP_BUILD_SCENARIOS:-}" ]]; then
  if [[ "$PHASE14_MODE" == "fast" ]]; then
    export SKIP_BUILD_SCENARIOS="A,B,C,D"
  else
    export SKIP_BUILD_SCENARIOS=""
  fi
fi
export SCENARIO_E_SELECTION="${SCENARIO_E_SELECTION:-4}"

: "${CBORG_API_KEY:?CBORG_API_KEY is required}"

mkdir -p "$ROOT"/{scenario_A,scenario_B,scenario_C,scenario_D,scenario_E,logs}

echo "[phase14] root: $ROOT"
echo "[phase14] mode=$PHASE14_MODE build_scenario=$BUILD_SCENARIO force_build_all=$FORCE_BUILD_ALL skip_build=$SKIP_BUILD_SCENARIOS"
echo "[phase14] run_scenarios=$RUN_SCENARIOS"
echo "[phase14] interactive_mode=$PHASE14_INTERACTIVE_MODE"

contains_csv_token() {
  local csv="$1"
  local token="$2"
  IFS=',' read -r -a parts <<< "$csv"
  for part in "${parts[@]}"; do
    if [[ "${part^^}" == "${token^^}" ]]; then
      return 0
    fi
  done
  return 1
}

should_run() {
  local scenario="$1"
  contains_csv_token "$RUN_SCENARIOS" "$scenario"
}

should_build() {
  local scenario="$1"
  if [[ "$FORCE_BUILD_ALL" == "1" ]]; then
    return 0
  fi
  if [[ "$PHASE14_MODE" == "full" ]]; then
    return 0
  fi
  if contains_csv_token "$SKIP_BUILD_SCENARIOS" "$scenario"; then
    return 1
  fi
  [[ "${scenario^^}" == "${BUILD_SCENARIO^^}" ]]
}

scenario_run_mode() {
  local scenario="$1"
  if should_build "$scenario"; then
    printf "full"
  else
    printf "dry"
  fi
}

extract_issue_codes() {
  local transcript="$1"
  if [[ ! -f "$transcript" ]]; then
    printf "none"
    return
  fi
  local codes
  codes="$(grep -oE 'ERF_[A-Z_]+' "$transcript" 2>/dev/null | sort -u | paste -sd ',' - || true)"
  printf "%s" "${codes:-none}"
}

pinned_erf_commit() {
  local repo_dir="$1"
  (
    cd "$repo_dir"
    python - <<'PY'
import json
from pathlib import Path
path = Path('.dependencies.json')
data = json.loads(path.read_text(encoding='utf-8'))
commit = None
if isinstance(data.get('repos'), dict):
    commit = ((data.get('repos') or {}).get('erf') or {}).get('commit')
if not commit and isinstance(data.get('repositories'), dict):
    commit = ((data.get('repositories') or {}).get('ERF') or {}).get('commit')
if not commit:
    raise SystemExit('Could not locate ERF commit in .dependencies.json')
print(commit)
PY
  )
}

run_agent_tty() {
  local transcript="$1"
  local run_mode="$2"
  local erf_path="${3:-}"
  local input_text="${4:-}"

  local cmd="python amrex_agent.py --run-mode $run_mode --indexing-strategy simple --inputs-file-strategy llm_compare --json --verbose --prompt \"$PROMPT\""
  if [[ -n "$erf_path" ]]; then
    cmd="ERF_REPO_PATH=$erf_path $cmd"
  fi
  if [[ -n "$input_text" ]]; then
    printf '%b' "$input_text" | script -q -c "$cmd" "$transcript" || true
    return
  fi
  script -q -c "$cmd" "$transcript" || true
}

selection_input() {
  local scenario="$1"
  if [[ "$PHASE14_INTERACTIVE_MODE" != "scripted" ]]; then
    printf ""
    return
  fi
  case "${scenario^^}" in
    A) printf "%s\n" "$SCENARIO_A_SELECTION" ;;
    B) printf "%s\n" "$SCENARIO_B_SELECTION" ;;
    E) printf "%s\n" "$SCENARIO_E_SELECTION" ;;
    *) printf "" ;;
  esac
}

run_agent_non_tty() {
  local transcript="$1"
  local run_mode="$2"
  local erf_path="${3:-}"

  if [[ -n "$erf_path" ]]; then
    ERF_REPO_PATH="$erf_path" python amrex_agent.py --run-mode "$run_mode" --indexing-strategy simple --inputs-file-strategy llm_compare --json --verbose --prompt "$PROMPT" >"$transcript" 2>&1 || true
  else
    python amrex_agent.py --run-mode "$run_mode" --indexing-strategy simple --inputs-file-strategy llm_compare --json --verbose --prompt "$PROMPT" >"$transcript" 2>&1 || true
  fi
}

if should_run A; then
  # ========= Scenario A: isolated clone (no sibling repos) =========
  cd "$ROOT/scenario_A"
  git clone "$REPO_URL" amrex-agent
  cd amrex-agent
  git checkout "$BRANCH"
  A_MODE="$(scenario_run_mode A)"
  run_agent_tty "$ROOT/logs/scenario_A_transcript.txt" "$A_MODE" "" "$(selection_input A)"
fi

if should_run B; then
  # ========= Scenario B: clone + mock sibling ERF mismatch =========
  cd "$ROOT/scenario_B"
  git clone "$REPO_URL" amrex-agent
  cd amrex-agent
  git checkout "$BRANCH"

  cd ..
  git clone git@github.com:erf-model/ERF.git ERF
  cd ERF
  git submodule update --init --recursive
  git checkout HEAD~1
  cd ../amrex-agent

  B_MODE="$(scenario_run_mode B)"
  run_agent_tty "$ROOT/logs/scenario_B_transcript.txt" "$B_MODE" "$ROOT/scenario_B/ERF" "$(selection_input B)"
fi

if should_run C; then
  # ========= Scenario C: clone + aligned ERF state =========
  cd "$ROOT/scenario_C"
  git clone "$REPO_URL" amrex-agent
  cd amrex-agent
  git checkout "$BRANCH"
  PINNED_ERF_COMMIT="$(pinned_erf_commit "$PWD")"

  cd ..
  git clone git@github.com:erf-model/ERF.git ERF
  cd ERF
  git submodule update --init --recursive
  git checkout "$PINNED_ERF_COMMIT"
  cd ../amrex-agent

  C_MODE="$(scenario_run_mode C)"
  run_agent_tty "$ROOT/logs/scenario_C_transcript.txt" "$C_MODE" "$ROOT/scenario_C/ERF"

  find "$PWD/output" -name "qc_slice.png" -print | tee "$ROOT/logs/scenario_C_qc_slice_paths.txt"
fi

if should_run D; then
  # ========= Scenario D: explicit ERF_REPO_PATH override =========
  cd "$ROOT/scenario_D"
  git clone "$REPO_URL" amrex-agent
  cd amrex-agent
  git checkout "$BRANCH"

  D_MODE="$(scenario_run_mode D)"
  run_agent_tty "$ROOT/logs/scenario_D_transcript.txt" "$D_MODE" "$ROOT/scenario_C/ERF"
fi

if should_run E; then
  # ========= Scenario E: mismatch + interactive development rebuild =========
  cd "$ROOT/scenario_E"
  git clone "$REPO_URL" amrex-agent
  cd amrex-agent
  git checkout "$BRANCH"

  cd ..
  git clone git@github.com:erf-model/ERF.git ERF
  cd ERF
  git submodule update --init --recursive
  git checkout development || git checkout HEAD~1
  cd ../amrex-agent

  cat > "$ROOT/logs/scenario_E_rebuild_commands.txt" <<CMDS
python -u database/scripts/build_schema.py "\$ERF_PATH" --output database/schemas --auto-compose
python -u scripts/rename_schema_after_build.py --repo-root . --schemas-dir database/schemas --singleton-rename
python -u database/scripts/build_all_indices.py --level 1 --repo "\$ERF_PATH" --output database/faiss --provider cborg
python -u database/scripts/build_all_indices.py --level 2 --repo "\$ERF_PATH" --output database/faiss --provider cborg
python -u database/scripts/build_index.py --config erf --type case_structure --source "\$ERF_PATH" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg
python -u database/scripts/build_index.py --config erf --type case_details --source "\$ERF_PATH" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg
python -u database/scripts/build_index.py --config erf --type input_templates --source "\$ERF_PATH" --embedding cborg --embedding-model lbl/nomic-embed-text --provider cborg
python -u database/scripts/build_all_indices.py --check --output database/faiss --provider cborg
CMDS

  run_agent_non_tty "$ROOT/logs/scenario_E_pre_transcript.txt" "dry" "$ROOT/scenario_E/ERF"

  E_MODE="$(scenario_run_mode E)"
  run_agent_tty "$ROOT/logs/scenario_E_rebuild_transcript.txt" "$E_MODE" "$ROOT/scenario_E/ERF" "$(selection_input E)"

  run_agent_non_tty "$ROOT/logs/scenario_E_post_transcript.txt" "dry" "$ROOT/scenario_E/ERF"
fi

# ========= Summary =========
printf "scenario\tmode\tinteractive_action\tbuild_attempted\trebuild_commands_run\tpreflight_issue_codes\ttranscript\tqc_slice\texit_status\n" > "$ROOT/logs/summary.tsv"
for s in A B C D; do
  if ! should_run "$s"; then
    continue
  fi
  T="$ROOT/logs/scenario_${s}_transcript.txt"
  Q="$(grep -R --line-number "qc_slice.png" "$ROOT/scenario_${s}/amrex-agent/output" 2>/dev/null | head -n1 || true)"
  MODE="$(scenario_run_mode "$s")"
  BUILD="no"
  if should_build "$s"; then
    BUILD="yes"
  fi
  CODES="$(extract_issue_codes "$T")"
  printf "scenario_%s\t%s\tn/a\t%s\tno\t%s\t%s\t%s\tunknown\n" "$s" "$MODE" "$BUILD" "$CODES" "$T" "${Q:-none}" >> "$ROOT/logs/summary.tsv"
done

if should_run E; then
  E_Q="$(grep -R --line-number "qc_slice.png" "$ROOT/scenario_E/amrex-agent/output" 2>/dev/null | head -n1 || true)"
  E_BUILD="no"
  if should_build E; then
    E_BUILD="yes"
  fi
  E_CODES="$(extract_issue_codes "$ROOT/logs/scenario_E_rebuild_transcript.txt")"
  printf "scenario_E\t%s\tdevelopment_rebuild\t%s\tyes\t%s\t%s\t%s\tunknown\n" "$(scenario_run_mode E)" "$E_BUILD" "$E_CODES" "$ROOT/logs/scenario_E_rebuild_transcript.txt" "${E_Q:-none}" >> "$ROOT/logs/summary.tsv"
fi

echo
cat "$ROOT/logs/summary.tsv"
echo
echo "[phase14] complete"
