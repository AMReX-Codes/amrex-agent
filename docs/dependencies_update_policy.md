# Dependencies Update Policy

## Purpose

This policy defines how to update dependency pins and associated index artifacts
without losing reproducibility. Dependency pins in `.dependencies.json` capture
the exact solver tip (repo, branch, commit) used to build schemas and FAISS
artifacts so benchmark and retrieval results can be reproduced.

## When to Update Pins

Update pins when one or more of these conditions are true:

- Paper milestone requires refreshed evidence artifacts.
- A major solver release changes baseline structure or behavior.
- Substantial `Exec` changes affect schemas, priority cases, or retrieval.

## Eight-Step Update Procedure

1. Pull solver tips.
   - Fetch the latest commits for each tracked solver repo and confirm target commits.
2. Run reconnaissance diff.
   - Compare previous pinned commit versus new candidate commit for `Exec`, inputs, and metadata changes.
3. Run schema rebuild or rename workflow where needed.
   - Rebuild composed schemas for changed repos; if case paths moved, apply rename-safe schema updates.
4. Apply L2 rebuild triggers.
   - Rebuild L2 structures when case topology, metadata, or retrieval-relevant content changed.
5. Update pins in `.dependencies.json`.
   - Write updated repo URL, branch, and commit values for each changed dependency.
6. Regenerate manifests via index build.
   - Rebuild indices and regenerate manifests (for example FAISS manifest) from the updated source state.
7. Update oracle benchmark paths if paths moved.
   - Adjust benchmark fixtures and expected case paths for any rename or relocation.
8. Confirm ERF squall-line end-to-end path.
   - Run ERF squall-line e2e confirmation to verify retrieval and benchmark wiring after updates.

## Always-Rebuild Triggers

Always run rebuild workflow when any of the following occurs:

- `Exec` directory add/remove.
- Priority case input changes.
- Embedding provider or embedding model changes.

## Related Documentation

- `docs/integration.md` for `.dependencies.json` usage during auto-compose and clone-missing flows.
- `docs/build_faiss_indices.md` for FAISS provider structure, embedding-provider options, and manifest generation.
- `docs/workflows.md` for environment and dependency-management conventions.
- `docs/standards.md` for reproducibility and traceability expectations.
