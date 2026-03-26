# Intent Runtime Routing

This page documents how runtime intent is interpreted and applied without
mixing it into inputs-file modifications.

## Scope Boundary

- `inputs/baseline` domain:
  - architect `modifications`
  - input writer remap/apply paths
  - solver inputs content
- `runtime intent` domain:
  - execution environment and submission behavior
  - MPI/task count
  - walltime/qos/constraint/system/account
  - visualization intent

Runtime intent is consumed by runner and visualization paths. It is not passed
into `ConfigModelFactory.apply_modifications`.

## Visualization Mapping Contract

Visualization field resolution is code-gated and tiered:

1. Tier 1 semantic intents: canonical tokens extracted from prompt text (for
   example `cloud_water`, `temperature`, `velocity`).
2. Tier 2 solver candidates: live solver-code catalog candidates resolved from
   `build_viz_tier2_candidates(repo_root)`.
3. Tier 3 executable selection: final `requested_fields` consumed by input
   writing/visualization, selected only from Tier 2 candidates.

Policy:

- Missing solver code/catalog during visualization mapping is a hard runtime
  failure with remediation guidance.
- No blind fallback to unresolved generic semantic tokens in final
  `requested_fields`.
- Ambiguity or no-match is routed to clarification with candidate-constrained
  question payloads.

## Precedence

Effective runtime values are resolved in this order:

1. CLI flags
2. config overrides
3. `execution_intent`
4. defaults

Example:

- Prompt: `run with 4 procs`
- CLI: `--run-ntasks 8`
- Effective local launch: `mpirun -np 8 ...`

## Prompt Runtime Fields

Prompt can request:

- `environment`: `local`, `perlmutter`, `mcp`
- `run_mode`: `dry`, `stage`, `submit`, `full`
- `total_procs`
- `walltime`
- `qos`, `constraint`, `system`
- `account` and remote path selectors (audited and gate-aware)

Never prompt-controlled:

- credentials/tokens/secrets
- write-policy controls
- auth/security material

## Perlmutter Reachability Fallback

If runtime intent requests `perlmutter`, runner performs a read-only probe of
the remote filesystem root. When unreachable, effective environment falls back
to `local` and records:

- `environment_fallback_perlmutter_unreachable`
- probe reason (`missing_path`, `not_readable`, or probe error)

This fallback does not elevate permissions and is logged in
`workflow_history.details`.

## Noninteractive Permissions

Noninteractive calls do not get extra approval power:

- critical tools still require explicit approval token or trusted approval source
- `gate_approved=true` without trusted source does not bypass critical gates
- demo-only bypass behavior is unchanged

## Troubleshooting

### Prompt requested 4 procs but run is serial

Check:

1. Effective runtime in runner `workflow_history.details.runtime_effective`.
2. Whether CLI/config overrode prompt (`CLI > config > intent`).
3. Whether fallback changed environment due unreachable Perlmutter.

### Prompt requested Perlmutter but ran local

Check:

1. `runtime_adjustments` for fallback markers.
2. Remote path readability from the current host/session.
