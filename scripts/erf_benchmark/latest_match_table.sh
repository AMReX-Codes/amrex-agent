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
from collections import defaultdict
from pathlib import Path

rows = [json.loads(l) for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
by_strategy: dict[str, list[dict]] = defaultdict(list)
for row in rows:
    by_strategy[str(row.get("strategy", "unknown"))].append(row)


def group_subcase_key(row: dict) -> str:
    rel = str(row.get("target_case_relpath", "")).strip("/")
    parts = rel.split("/") if rel else []
    # Expected benchmark format: Exec/<group>/<subcase>
    if len(parts) >= 3 and parts[0] == "Exec":
        return f"{parts[1]}/{parts[2]}"
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    if parts:
        return parts[-1]
    return str(row.get("category", "unknown"))


for strategy, group in sorted(by_strategy.items()):
    total = len(group)
    case_match = sum(int(bool(r.get("case_match", 0))) for r in group)
    inputs_match = sum(int(bool(r.get("inputs_match", 0))) for r in group)
    print(
        f"{strategy}: case_match={case_match}/{total} ({100*case_match/total:.1f}%) "
        f"inputs_match={inputs_match}/{total} ({100*inputs_match/total:.1f}%)"
    )

    by_subcase: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in group:
        key = group_subcase_key(r)
        by_subcase[key][0] += int(bool(r.get("case_match", 0)))
        by_subcase[key][1] += int(bool(r.get("inputs_match", 0)))
        by_subcase[key][2] += 1

    for key, (case_hits, input_hits, n) in sorted(by_subcase.items()):
        print(
            f"  {key}: "
            f"case={case_hits}/{n} ({100*case_hits/n:.1f}%) "
            f"inputs={input_hits}/{n} ({100*input_hits/n:.1f}%)"
        )
PY
