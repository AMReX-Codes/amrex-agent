# Demo Quickstart

This page mirrors the quickstart and demo READMEs directly so the docs stay in sync.

## Startup readiness preflight prerequisites

Phase-3 prerequisite coverage for demos:

- Zero-manual-setup path: sibling solver repos + `bash demo/setup_demo_database.sh` + run from repo root.
- Sibling repo autodetect: default lookup uses sibling repos (for example `../ERF`).
- Auto-clone fallback: `--clone-missing` uses `.dependencies.json` pins when repos are absent.
- Rebuild/index repair: rerun setup (or `--code <code>`) when schema/FAISS artifacts are stale or mismatched.
- Non-interactive fail-fast: headless startup checks should exit non-zero on blocking readiness issues.
- Build defaults/fallbacks are code-specific; do not assume one policy applies to all solvers.
- ERF-specific build defaults/fallbacks are documented in `demo/erf/README.md`.

Detailed runnable commands are maintained in:

- `demo/README.md`
- `demo/erf/README.md`

```markdown
{%
  include "../README.md"
  start="## Quick start"
  end="## Tests"
%}
```

```markdown
{%
  include "../demo/README.md"
%}
```

```markdown
{%
  include "../demo/amrex/README.md"
%}
```
