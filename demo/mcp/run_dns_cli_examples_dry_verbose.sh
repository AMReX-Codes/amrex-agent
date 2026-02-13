#!/usr/bin/env bash
# CLI examples for DNS prompts (dry-run + verbose).
set -euo pipefail

python amrex_agent.py \
  --config demo/pelelmex/config_JICF.yaml \
  --prompt-path demo/pelelmex/user_requirements_DNS_isothermal.txt \
  --run-mode dry \
  --save-workflow \
  --save-transcript \
  --save-log \
  --color-logs always \
  --verbose

python amrex_agent.py \
  --config demo/pelelmex/config_JICF.yaml \
  --prompt-path demo/pelelmex/user_requirements_test_DNS.txt \
  --run-mode dry \
  --save-workflow \
  --save-transcript \
  --save-log \
  --color-logs always \
  --verbose
