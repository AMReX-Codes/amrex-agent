# Standards and Compliance

This page tracks documentation standards and maps evidence to the repository.
It is intended to be short, explicit, and easy to audit.

## Scope

- Standards and API documentation are current and referenced.
- Evidence/checklists are visible and link to source artifacts.

## Standards and API documentation

Coverage notes:
- API key setup + OpenAI usage: `docs/api_keys.md`
- Superfacility API usage: `docs/sfapi.md`
- MCP tool surface + testing guidance: `docs/mcp.md`
- Indexing + embedding guidance: `docs/BUILD_FAISS_INDICES.md`
- Integration workflow: `docs/integration.md`

Evidence (paths):
- `docs/api_keys.md`
- `docs/sfapi.md`
- `docs/mcp.md`
- `docs/BUILD_FAISS_INDICES.md`
- `docs/integration.md`

## Standards checklist and evidence mapping

| Standard | Evidence | Notes |
| --- | --- | --- |
| Reproducibility | `docs/BUILD_FAISS_INDICES.md` | Deterministic index builds and pinned embedding flows |
| Traceability | `docs/coverage_map.md` | Maps tests, contracts, and graph state fields |
| Safety and control | `docs/mcp.md` | Tool schemas + explicit interfaces for external calls |
| Verification | `tests/quality/test_contract_schema_alignment.py` | Schema alignment and contract checks |
| Transparency | `docs/workflow_visualization.md` | Documented outputs and traceable artifacts |
| Interoperability | `docs/mcp.md` | MCP tool surface for external orchestration |

## Capability coverage (Agents4Science-aligned)

| Capability | Coverage status | References |
| --- | --- | --- |
| Planning | implemented | `src/services/architect.py`, `docs/workflow_visualization.md` |
| Retrieval | implemented | `docs/BUILD_FAISS_INDICES.md`, `docs/api_keys.md` |
| Validation | implemented | `docs/coverage_map.md`, `tests/contracts/` |
| Execution | implemented | `docs/sfapi.md`, `demo/superfacility/README.md` |
| Analysis | implemented | `docs/workflow_visualization.md` |
| Visualization | implemented | `docs/workflow_visualization.md` |
| Collaboration | partial | `docs/mcp.md` (tool surface; orchestration external) |

## Agents4Science capability stages (reference)

Source: https://agents4science.github.io/Capabilities/

| Stage | Capability | Status | Notes |
| --- | --- | --- | --- |
| 1 | Local agent execution | partial | Single-process workflow with tool calling |
| 2 | Federated agent execution | not implemented | No federated identity or cross-institution agent fabric |
| 3 | Parallel agent inference | not implemented | No large-scale fan-out inference |
| 4 | Governed tool use | partial | Gating exists, but no shared policy/budget ledger |
| 5 | Multi-agent coordination | not implemented | No shared state/policy/budget across agents |
| 6 | Long-lived agents | not implemented | No persistent autonomous agent lifecycle |
| 7 | Agent workflows | partial | Workflow orchestration exists, not dynamic DAG construction |

Note: dynamic DAG construction means the workflow graph can be built or pruned
at runtime based on context, instead of following a fixed node sequence.

## Collaboration expectations (Agents4Science)

Agents4Science collaboration emphasizes:
- Shared state, policy, and budget controls for multi-agent coordination.
- Federated identity and cross-institution agent collaboration.
- Capability discovery across agents or institutions.
- Audit logging for cross-institution operations.

Current alignment:
- MCP provides a tool surface and schema definitions for external orchestration.
- No built-in federated identity, shared policy/budget ledger, or cross-agent
  coordination hub in this repo.

## Gaps and risk notes

- Capability mapping needs periodic review when new nodes or external tools are added.
- Collaboration is external to this repo; document orchestration changes if added.
- Agents4Science stages 2-6 are not implemented; track if integration is planned.

## Evidence and checklists

Checklist:
- [ ] API provider support matrix is up to date.
- [ ] Env var and config field lists are complete.
- [ ] Examples reference the latest demo READMEs.
- [ ] Standards references link to their source in the repo.
- [ ] Capability mapping table reviewed for new services.
- [ ] ADRs are added for significant architectural decisions.

Evidence (paths):
- `docs/index.md` (entry points)
- `docs/coverage_map.md` (tests-to-contracts mapping)
- `tests/contracts/` (node contracts)
- `src/models/graph_state_canonical.py` (canonical state schema)
- `docs/adr/README.md` (decision records and template)

ADRs provide a durable record of major architectural decisions and tradeoffs.
They help explain why we chose a path when the implementation evolves.

## Maintenance notes

- Keep this page ASCII and link to concrete file paths.
- When adding a new provider or API surface, update `docs/api_keys.md` and
  add a bullet in the coverage notes above.
