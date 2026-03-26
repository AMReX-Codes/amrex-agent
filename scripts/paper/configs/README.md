# Pilot Configs for `track1_reproduce.sh`

This directory is used by `scripts/paper/track1_reproduce.sh` Step 4.

The script runs a pilot matrix over every `*.yaml` in this folder across
`simple`, `hierarchical`, and `override_static` indexing strategies.

Included config:
- `ab_simple_sonnet.yaml` (copied from `/tmp/ab_simple_sonnet.yaml`)

To run cross-model pilot comparisons, add additional YAML configs here with
identical non-model settings and different model endpoints.
