#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LATEST:-}" ]]; then
  echo "LATEST is not set. Example:"
  echo "  export LATEST=benchmark_remora/results/sanity_amsci2_20260430T141913Z"
  exit 2
fi

if [[ ! -d "${LATEST}" ]]; then
  echo "LATEST directory not found: ${LATEST}"
  exit 2
fi

python3 - "${LATEST}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = [
    root / "partial_simple_console_logs.jsonl",
    root / "partial_hierarchical_console_logs.jsonl",
    root / "console_logs.jsonl",
]
keywords = ["error", "embedding", "faiss", "unavailable", "403", "401", "traceback"]
max_hits = 20
found_file = False

for path in files:
    if not path.exists():
        continue
    found_file = True
    print(f"[scan] {path}")
    hits = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        stderr = str(row.get("stderr_tail", ""))
        stdout = str(row.get("stdout_tail", ""))
        blob = (stderr + "\n" + stdout).lower()
        if any(k in blob for k in keywords):
            hits += 1
            print("--- row", str(row.get("row_id", "?"))[:8])
            tail = stderr if stderr.strip() else stdout
            print(tail[-400:])
            if hits >= max_hits:
                break
    if hits == 0:
        print("no keyword hits")

if not found_file:
    print(f"no console log jsonl files found under {root}")
PY
