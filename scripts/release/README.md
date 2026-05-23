# Release Bundle Builder

Use `scripts/release/build_isc_llm4hpc_paper_release.sh` to prepare a GitHub-release-style bundle for the paper artifacts and benchmark evidence without committing manuscript binaries into git history.

The script produces:

- A code zip archived from commit `2c2d60017707d48b63c5803fa0d80ffef43c6e3c`
- A separate paper-assets zip containing `amrex_agent_sexton_isc_llm4hpc_camera_submit.docx` when present
- A benchmark/evidence zip containing the benchmark summaries, prompt matrices, self-correction workflow artifact, and local coverage artifact
- `ARTIFACT_INDEX.md`, `SHA256SUMS`, and `RELEASE_MANIFEST.md` under `artifacts/releases/isc-llm4hpc-paper-v1/`

Publishing to GitHub is intentionally left as a separate step so the bundle can be inspected before uploading it to the `amrex-codes/amrex-agent` repository.
