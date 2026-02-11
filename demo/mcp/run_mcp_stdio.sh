#!/usr/bin/env bash
set -euo pipefail

if command -v module >/dev/null 2>&1; then
  module use /soft/modulefiles
  module load conda
  conda activate base
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

CONDA_NAME=$(echo "${CONDA_PREFIX}" | tr '\/' '\t' | sed -E 's/mconda3|\/base//g' | awk '{print $NF}')
VENV_DIR="${REPO_ROOT}/venvs/${CONDA_NAME}"

if [[ -d "${VENV_DIR}" ]]; then
  # shellcheck disable=SC1090
  source "${VENV_DIR}/bin/activate"
elif [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
  echo "Using active conda env: ${CONDA_DEFAULT_ENV}" >&2
else
  echo "Missing venv at ${VENV_DIR}. Create it first or activate a conda env." >&2
  exit 1
fi

python -u mcp_server.py
