#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage:
  $(basename "$0") --wt <1-5> --wave <N> [--agent <bin>] [--plan-root <path>] [--dry-run] [--resume]

Options:
  --wt <1-5>      Worktree slot number.
  --wave <N>      Wave number from docs/audits/semantic/wave_plan.md.
  --agent <bin>   Agent CLI binary (default: codex).
  --plan-root     Root containing docs/audits/semantic/{wave_plan,session_plan}.md.
  --dry-run       Print planned actions without invoking agent.
  --resume        Skip sessions already recorded as complete.
USAGE
}

WT=""
WAVE=""
AGENT_BIN="${AGENT_BIN:-codex}"
PLAN_ROOT=""
DRY_RUN=0
RESUME=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wt)
      WT="${2:-}"
      shift 2
      ;;
    --wave)
      WAVE="${2:-}"
      shift 2
      ;;
    --agent)
      AGENT_BIN="${2:-}"
      shift 2
      ;;
    --plan-root)
      PLAN_ROOT="${2:-}"
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

if [[ -z "$WT" || -z "$WAVE" ]]; then
  usage
  exit 2
fi

if ! [[ "$WT" =~ ^[1-5]$ ]]; then
  echo "--wt must be 1..5" >&2
  exit 2
fi
if ! [[ "$WAVE" =~ ^[0-9]+$ ]]; then
  echo "--wave must be an integer" >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -z "$PLAN_ROOT" ]]; then
  PLAN_ROOT="$REPO_ROOT"
  if [[ ! -f "$PLAN_ROOT/docs/audits/semantic/wave_plan.md" || ! -f "$PLAN_ROOT/docs/audits/semantic/session_plan.md" ]]; then
    PLAN_ROOT="$SCRIPT_REPO_ROOT"
  fi
fi

WAVE_PLAN="$PLAN_ROOT/docs/audits/semantic/wave_plan.md"
SESSION_PLAN="$PLAN_ROOT/docs/audits/semantic/session_plan.md"
STATE_DIR="$REPO_ROOT/.wave_runs"
LOG_DIR="$STATE_DIR/logs"
RUN_TAG="wave${WAVE}_wt${WT}"
COMPLETE_FILE="$STATE_DIR/${RUN_TAG}.complete"
FAILED_FILE="$STATE_DIR/${RUN_TAG}.failed"
SESSION_LIST_FILE="$STATE_DIR/${RUN_TAG}.sessions"

mkdir -p "$STATE_DIR" "$LOG_DIR"
: > "$SESSION_LIST_FILE"

if [[ ! -f "$WAVE_PLAN" || ! -f "$SESSION_PLAN" ]]; then
  echo "Missing plan file(s): $WAVE_PLAN or $SESSION_PLAN" >&2
  exit 1
fi

extract_sessions() {
  awk -v wave="$WAVE" -v wt="$WT" '
    $0 ~ "^Wave "wave" " {in_wave=1; next}
    $0 ~ "^Wave " && in_wave {exit}
    in_wave && $0 ~ "^[[:space:]]*wt-"wt":" {
      while (match($0, /Session[[:space:]]+[0-9]+/)) {
        s = substr($0, RSTART, RLENGTH)
        gsub(/[^0-9]/, "", s)
        print s
        $0 = substr($0, RSTART + RLENGTH)
      }
    }
  ' "$WAVE_PLAN"
}

session_title() {
  local sn="$1"
  awk -v n="$sn" '
    $0 ~ "^Session "n" — " {
      line=$0
      sub(/^Session [0-9]+ — \[[^]]+\] /, "", line)
      print line
      exit
    }
  ' "$SESSION_PLAN"
}

already_completed() {
  local sn="$1"
  [[ -f "$COMPLETE_FILE" ]] && grep -qx "$sn" "$COMPLETE_FILE"
}

mapfile -t SESSIONS < <(extract_sessions)
if [[ ${#SESSIONS[@]} -eq 0 ]]; then
  echo "No sessions found for wave ${WAVE}, wt-${WT}." >&2
  exit 1
fi

printf '%s\n' "${SESSIONS[@]}" > "$SESSION_LIST_FILE"
echo "Run tag: $RUN_TAG"
echo "Repo root: $REPO_ROOT"
echo "Plan root: $PLAN_ROOT"
echo "Sessions (${#SESSIONS[@]}): ${SESSIONS[*]}"

for sn in "${SESSIONS[@]}"; do
  if [[ "$RESUME" -eq 1 ]] && already_completed "$sn"; then
    echo "[skip] Session $sn already completed"
    continue
  fi

  title="$(session_title "$sn")"
  if [[ -z "$title" ]]; then
    title="(title not found)"
  fi

  session_log="$LOG_DIR/${RUN_TAG}_session${sn}.log"
  echo "[start] Session $sn | $title"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] $AGENT_BIN for Session $sn" | tee -a "$session_log"
    continue
  fi

  {
    "$AGENT_BIN" <<PROMPT
Read docs/audits/semantic/session_plan.md.
Find Session ${sn}.
Execute only Session ${sn}.
Implement the changes, run that session's CI verify command, and commit.
Commit message format: Session ${sn}: ${title}
Stop after that commit. Do not execute any other session.
PROMPT
  } 2>&1 | tee "$session_log"

  status=${PIPESTATUS[0]}
  if [[ $status -ne 0 ]]; then
    echo "$sn" >> "$FAILED_FILE"
    echo "[fail] Session $sn failed (see $session_log)"
    exit $status
  fi

  echo "$sn" >> "$COMPLETE_FILE"
  echo "[done] Session $sn"
done

echo "All assigned sessions finished for $RUN_TAG"
