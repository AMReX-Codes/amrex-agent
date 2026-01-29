#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python "${ROOT_DIR}/database/scripts/upload_openai_vector_store.py" "$@"
