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

| Standard | Evidence | Tests | Notes |
| --- | --- | --- | --- |
| Reproducibility | `docs/BUILD_FAISS_INDICES.md` | `tests/unit/test_faiss_artifacts.py` | Deterministic index builds and pinned embedding flows |
| Traceability | `docs/coverage_map.md` | `tests/unit/test_architect_node_history.py` | Maps tests, contracts, and graph state fields |
| Safety and control | `docs/mcp.md` | `tests/unit/test_architect_node_safety.py` | Tool schemas + explicit interfaces for external calls |
| Verification | `tests/quality/test_contract_schema_alignment.py` | `tests/quality/test_contract_schema_alignment.py` | Schema alignment and contract checks |
| Transparency | `docs/workflow_visualization.md` | `tests/integration/l3_postprocessing/test_analysis_parsing.py` | Documented outputs and traceable artifacts |
| Interoperability | `docs/mcp.md` | `tests/unit/test_mcp_tools.py`, `tests/integration/l1_mcp/test_mcp_stdio.py` | MCP tool surface for external orchestration |

## Standards to feature/test mapping

| Gap | Impact | Status | Next step | Evidence | Tests |
| --- | --- | --- | --- | --- | --- |
| Reproducibility coverage | Deterministic runs for indices and embeddings | Documented | Tie to benchmark and validation tests | `docs/BUILD_FAISS_INDICES.md` | `tests/unit/test_faiss_artifacts.py` |
| Traceability coverage | Decision trail for outputs | Documented | Map to workflow history fields | `docs/coverage_map.md` | `tests/unit/test_architect_node_history.py` |
| Safety and control coverage | Guardrails for costly actions | Documented | Tie to gating tests and policies | `docs/mcp.md` | `tests/unit/test_architect_node_safety.py` |
| Verification coverage | Schema and contract alignment | Documented | Map to quality tests | `tests/quality/test_contract_schema_alignment.py` | `tests/quality/test_contract_schema_alignment.py` |
| Transparency coverage | Evidence links for outputs | Documented | Map to analysis/report artifacts | `docs/workflow_visualization.md` | `tests/integration/l3_postprocessing/test_analysis_parsing.py` |
| Interoperability coverage | External tool schemas and hooks | Documented | Map to MCP tool inventory tests | `docs/mcp.md` | `tests/unit/test_mcp_tools.py`, `tests/integration/l1_mcp/test_mcp_stdio.py` |

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

## Structured gap log

| Gap | Impact | Status | Next step | Evidence | Tests |
| --- | --- | --- | --- | --- | --- |
| Federated identity for collaboration | Limits cross-institution workflows | Open | Evaluate Academy/Globus integration | `docs/mcp.md` | - |
| Shared policy/budget ledger for coordinated agents | No multi-agent governance | Open | Define governance layer requirements | `docs/standards.md` | - |
| Dynamic DAG construction | Workflow is mostly fixed per run | Open | Add prompt-conditional routing and optional nodes | `docs/standards.md` | - |

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
