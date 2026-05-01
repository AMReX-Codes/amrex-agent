#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LATEST:-}" ]]; then
  echo "LATEST is not set. Example:"
  echo "  export LATEST=benchmark_remora/results/sanity_amsci2_20260430T141913Z"
  exit 2
fi

RESULTS="${LATEST%/}/results.jsonl"
if [[ ! -f "${RESULTS}" ]]; then
  echo "results.jsonl not found: ${RESULTS}"
  exit 2
fi

python3 - "${RESULTS}" <<'PY'
import json
import sys
from pathlib import Path

rows = []
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    rows.append(
        (
            str(r.get("strategy", "")),
            int(bool(r.get("case_match", 0))),
            str(r.get("target_case_relpath", "")),
            str(r.get("selected_case", "")),
        )
    )

for strategy, case_match, expected_case, selected_case in sorted(rows):
    print(
        strategy,
        case_match,
        expected_case[:45],
        "->",
        selected_case[:45],
    )
PY
