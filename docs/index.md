# AMReXAgent Documentation

AMReXAgent is an AI workflow for configuring AMReX-based simulation codes from
natural language prompts.

## Build the docs locally

```bash
mkdocs serve
```

## Documentation layout

- `docs/workflows.md` holds design and workflow notes.
- `docs/standards.md` tracks C6 standards mapping and evidence.
- `docs/academy.md` documents Academy integration and launcher usage.
- `docs/api_keys.md` documents API key setup and OpenAI usage.
- `docs/sfapi.md` documents Superfacility API (SFAPI) usage.
- `docs/deployment_readiness.md` covers testing, deployment, and release gates.
- `docs/benchmark_erf_llm_compare.md` defines the ERF `llm_compare` benchmark design and artifact contract.
- `README.md` covers quick start and usage examples.
- `demo/README.md` contains example scenarios and configs.
- `docs/mcp.md` describes the MCP server and testing guidance.

## ERF Benchmark Scripts

- `scripts/erf_benchmark/generate_prompt_matrix.py`
- `scripts/erf_benchmark/make_splits.py`
- `scripts/erf_benchmark/make_sanity_prompt_set.py`
- `scripts/erf_benchmark/run_llm_compare_benchmark.py`
- `scripts/erf_benchmark/compare_runs.py`
