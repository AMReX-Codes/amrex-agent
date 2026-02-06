# Extending to Your AMReX Code

This guide turns the slide outline into an actionable integration path. It
assumes you already have a working AMReX code with a test suite.

## Step 1 (30 min): Register the code

Add a configuration entry that points to your repo and test suite. You can
follow the existing config patterns in `database/configs`. If you create a new
config class, register it in `database/configs/__init__.py` so
`discover_code_configs()` can find it.

Minimal config template:

```python
{%
  include "snippets/new_config.py"
%}
```

Register the class:

```python
from .mycode_config import MyCodeConfig

__all__ = [
    "MyCodeConfig",
]
```

Checklist:
- Repo path (local or environment variable)
- GitHub search paths (`github_search_paths`) for baseline discovery
- Physics domains (used for routing)
- Solver/code name and GitHub repo name

## Step 2 (1-2 hours): Define a config template and validation rules

Start from an existing template (for example `database/configs/pelec_config.py`)
and tailor:
- Default inputs and baseline locations
- Input schema rules (AMR constraints, solver-specific limits)
- Optional validation hooks for custom fields

The goal is to reuse the existing validation framework while encoding your
solver-specific constraints.

## Step 3: Index existing test cases

Run the indexing scripts against your repo to build the searchable baseline
library. This reuses the same test suite you already trust:

```bash
bash demo/setup_demo_database.sh --code <your_code>
```

## Why this works

- Minimal effort: leverage your production tests instead of writing new docs.
- No workflow change: you keep building and running the same cases.
- Shared infrastructure: validation improvements benefit the whole ecosystem.

## Next steps

If you want help wiring up a new code, open an issue with:
- Repo URL and local path
- Test suite locations
- A few representative baseline cases
