#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage:
  $(basename "$0") --wave <N> [--agent <bin>] [--dry-run] [--resume]

Launches wt-1..wt-5 in parallel with isolated logs.
Each worker runs scripts/run_wave_worktree.sh inside its own worktree.
USAGE
}

WAVE=""
AGENT_BIN="${AGENT_BIN:-codex}"
DRY_RUN=0
RESUME=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wave)
      WAVE="${2:-}"
      shift 2
      ;;
    --agent)
      AGENT_BIN="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --resume)
      RESUME=1
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

if [[ -z "$WAVE" || ! "$WAVE" =~ ^[0-9]+$ ]]; then
  echo "--wave must be an integer" >&2
  usage
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
BASE_PARENT="$(dirname "$ROOT")"
BASE_NAME="$(basename "$ROOT")"
STATE_DIR="$ROOT/.wave_runs"
mkdir -p "$STATE_DIR"

pids=()
for wt in 1 2 3 4 5; do
  worktree_path="$BASE_PARENT/${BASE_NAME}_wt-${wt}"
  if [[ ! -d "$worktree_path" ]]; then
    echo "[warn] missing worktree path: $worktree_path (skipping wt-$wt)"
    continue
  fi

  cmd=("$ROOT/scripts/run_wave_worktree.sh" --wt "$wt" --wave "$WAVE" --agent "$AGENT_BIN")
  if [[ "$DRY_RUN" -eq 1 ]]; then cmd+=(--dry-run); fi
  if [[ "$RESUME" -eq 1 ]]; then cmd+=(--resume); fi

  launcher_log="$STATE_DIR/launcher_wave${WAVE}_wt${wt}.log"
  echo "[launch] wt-$wt in $worktree_path"
  (
    cd "$worktree_path"
    "${cmd[@]}"
  ) >"$launcher_log" 2>&1 &
  pids+=("$!")
done

if [[ ${#pids[@]} -eq 0 ]]; then
  echo "No worktrees launched."
  exit 1
fi

rc=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    rc=1
  fi
done

if [[ $rc -ne 0 ]]; then
  echo "At least one worktree run failed. Check .wave_runs/launcher_wave${WAVE}_wt*.log"
  exit $rc
fi

echo "Wave ${WAVE} launch complete across all available worktrees."
