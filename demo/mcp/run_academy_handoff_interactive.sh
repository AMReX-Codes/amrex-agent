#!/usr/bin/env bash
set -euo pipefail

# Interactive helper for Academy handoff validation.
# Usage:
#   demo/mcp/run_academy_handoff_interactive.sh agent
#   demo/mcp/run_academy_handoff_interactive.sh client --agent-id <agent_id>
#   demo/mcp/run_academy_handoff_interactive.sh extract-agent-id

MODE="${1:-}"
shift || true

EVIDENCE_DIR="${EVIDENCE_DIR:-output/handoff_runs/2026-02-20}"
mkdir -p "${EVIDENCE_DIR}"

export PYTHONPATH="${PYTHONPATH:-.}"
export HOME="${HOME:-/tmp/amrex_agent_home}"
mkdir -p "${HOME}"

AGENT_LOG="${EVIDENCE_DIR}/academy_agent.log"
CLIENT_LOG="${EVIDENCE_DIR}/academy_execute_workflow_smoke.log"

print_usage() {
  cat <<'EOF'
Usage:
  demo/mcp/run_academy_handoff_interactive.sh agent
  demo/mcp/run_academy_handoff_interactive.sh client --agent-id <agent_id>
  demo/mcp/run_academy_handoff_interactive.sh extract-agent-id

Notes:
  - Run `agent` in one terminal and keep it running.
  - Run `client --agent-id ...` in another terminal.
  - Both commands are interactive and may prompt for Globus auth.
EOF
}

extract_agent_id() {
  if [[ ! -f "${AGENT_LOG}" ]]; then
    echo "Agent log not found: ${AGENT_LOG}" >&2
    exit 1
  fi
  if grep -q 'AMReXMCPAgent uid:' "${AGENT_LOG}"; then
    grep -Eo 'AMReXMCPAgent uid: .*' "${AGENT_LOG}" | tail -n1 | sed 's/AMReXMCPAgent uid: //'
    return 0
  fi
  echo "No full UUID found in ${AGENT_LOG}." >&2
  echo "Restart agent with updated script and copy 'AMReXMCPAgent uid: <uuid>'." >&2
  exit 1
}

run_agent() {
  echo "Writing agent log to ${AGENT_LOG}"
  echo "Starting Academy agent (Ctrl+C to stop)..."
  python demo/mcp/academy_amrex_agent.py 2>&1 | tee "${AGENT_LOG}"
}

run_client() {
  local agent_id=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --agent-id)
        agent_id="${2:-}"
        shift 2
        ;;
      *)
        echo "Unknown option: $1" >&2
        print_usage
        exit 1
        ;;
    esac
  done

  if [[ -z "${agent_id}" ]]; then
    echo "--agent-id is required for client mode." >&2
    print_usage
    exit 1
  fi

  echo "Writing client log to ${CLIENT_LOG}"
  echo "Calling Academy actions against agent: ${agent_id}"
  python demo/mcp/academy_execute_workflow_smoke.py --agent-id "${agent_id}" 2>&1 | tee "${CLIENT_LOG}"
}

case "${MODE}" in
  agent)
    run_agent
    ;;
  client)
    run_client "$@"
    ;;
  extract-agent-id)
    extract_agent_id
    ;;
  *)
    print_usage
    exit 1
    ;;
esac
