#!/usr/bin/env bash
set -euo pipefail

release_id="isc-llm4hpc-paper-v1"
snapshot_commit="2c2d60017707d48b63c5803fa0d80ffef43c6e3c"
snapshot_short="${snapshot_commit:0:7}"
remote_name="amrex-codes"
remote_repo="git@github.com:amrex-codes/amrex-agent"
outdir="artifacts/releases/${release_id}"
code_zip="${outdir}/${release_id}_code_${snapshot_short}.zip"
paper_zip="${outdir}/${release_id}_paper_assets.zip"
evidence_zip="${outdir}/${release_id}_benchmark_and_evidence.zip"
manifest="${outdir}/RELEASE_MANIFEST.md"
artifact_index="${outdir}/ARTIFACT_INDEX.md"
coverage_artifact=".coverage"
historical_cov_log="results/repo_validation_snapshot_20260313_102708/pytest_cov.log"
e2e_dt_repair_artifact=".pytest-e2e/test_cli_full_mode_short_refle0/runs_full_mode_short/run_20260514_131839_294108/workflow_history.json"
pelelmex_result_root="benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z"

evidence_paths=(
    "benchmark_crosscode/latest"
    "benchmark_v2/prompt_matrix.jsonl"
    "benchmark_v2/results/full_amsci2_20260429T160959Z/summary.json"
    "benchmark_v2/results/full_amsci2_20260429T160959Z/token_summary.txt"
    "benchmark_v2/results/full_cborg_20260427T202152Z/summary.json"
    "benchmark_v2/results/full_cborg_20260427T202152Z/token_summary.txt"
    "benchmark_pelelmex/prompt_matrix.jsonl"
    "benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/summary.json"
    "benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/explainability_calls.jsonl"
    "benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/simple/metrics.jsonl"
    "benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/hierarchical/metrics.jsonl"
    "benchmark_remora/prompt_matrix.jsonl"
    "benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/summary.json"
    "benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/results.jsonl"
    "artifacts/self_correction/march18_ekman_spiral_workflow_history.json"
    ".coverage"
    "${historical_cov_log}"
    "${e2e_dt_repair_artifact}"
)

while IFS= read -r path; do
    evidence_paths+=("${path}")
done < <(find "${pelelmex_result_root}" -path '*/run_*/metrics.jsonl' -type f | sort)

mkdir -p "${outdir}"
rm -f "${code_zip}" "${paper_zip}" "${evidence_zip}" "${manifest}" "${artifact_index}" "${outdir}/SHA256SUMS"

git archive --format=zip --output="${code_zip}" "${snapshot_commit}"

zip -r "${evidence_zip}" "${evidence_paths[@]}" >/dev/null

sha256sum "${code_zip}" > "${outdir}/SHA256SUMS"
sha256sum "${evidence_zip}" >> "${outdir}/SHA256SUMS"

coverage_total="$(coverage report | awk '/^TOTAL/{print $NF}')"
pelelmex_ratio="$(python - <<'PY'
import json
prompt = 0
completion = 0
import glob
paths = sorted(glob.glob('benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/**/metrics.jsonl', recursive=True))
for path in paths:
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            if row.get('type') != 'workflow_summary':
                continue
            data = row.get('data') or {}
            prompt += int(data.get('tokens_total_input') or 0)
            completion += int(data.get('tokens_total_output') or 0)
ratio = prompt / completion if completion else 0.0
print(f"{prompt} prompt / {completion} completion ({ratio:.2f}:1)")
PY
)"

cat > "${manifest}" <<EOF
# ${release_id}

- Remote: \`${remote_name}\`
- Repository: \`${remote_repo}\`
- Snapshot commit: \`${snapshot_commit}\`
- Code asset: \`$(basename "${code_zip}")\`
- Paper asset: omitted from committed release branch; manuscript binary remains local-only
- Benchmark/evidence asset: \`$(basename "${evidence_zip}")\`
- Artifact index: \`$(basename "${artifact_index}")\`

## Suggested Release Title

\`${release_id}\`

## Suggested Release Notes

Repository release bundle for the ISC LLM4HPC paper artifacts and benchmark evidence.

- Code snapshot is archived from commit \`${snapshot_short}\`.
- The manuscript binary is intentionally excluded from the committed release branch to avoid adding an actively edited \`.docx\` to repository history.
- Benchmark evidence and claim-to-artifact mapping are packaged separately so paper numbers can be audited without browsing the whole repository.

## Upload Assets

- \`$(basename "${code_zip}")\`
- \`$(basename "${evidence_zip}")\`
- \`$(basename "${artifact_index}")\`
- \`SHA256SUMS\`
EOF

cat > "${artifact_index}" <<EOF
# ${release_id} Artifact Index

## Bundle Scope

- Paper bundle name: \`${release_id}\`
- Code snapshot commit: \`${snapshot_commit}\`
- Code zip: \`$(basename "${code_zip}")\`
- Benchmark/evidence zip: \`$(basename "${evidence_zip}")\`
- Manuscript binary: excluded from the committed release branch; retained as a local-only working document

## Numeric Claims Mapped To Saved Artifacts

- \`0.922\` weighted ERF score for \`claude-sonnet-4-5\`: matched by \`benchmark_v2/results/full_amsci2_20260429T160959Z/summary.json\` (\`simple_weighted_score=0.922794\`, \`hierarchical_weighted_score=0.922794\`), with release-facing summary in \`benchmark_crosscode/latest/benchmark_summary.md\`.
- \`0.441\` weighted ERF score for \`lbl/cborg-deepthought\`: matched by \`benchmark_v2/results/full_cborg_20260427T202152Z/summary.json\` (\`simple_weighted_score=0.441912\`), with release-facing summary in \`benchmark_crosscode/latest/benchmark_summary.md\`.
- \`136-item\` ERF frozen prompt set: matched by \`benchmark_v2/prompt_matrix.jsonl\` and summarized in \`benchmark_crosscode/latest/benchmark_summary.md\`.
- ERF case-match percentages \`100%\`, \`47.1%\`, and \`50.7%\`: matched by \`benchmark_crosscode/latest/benchmark_summary.csv\` and \`benchmark_crosscode/latest/benchmark_summary.md\` (source values \`100.00\`, \`47.06\`, and \`50.74\`).
- ERF token totals \`3.47M\` prompt and \`50.8K\` completion with about \`68:1\`: matched by \`benchmark_v2/results/full_amsci2_20260429T160959Z/token_summary.txt\` (\`3,469,128\` prompt, \`50,823\` completion, ratio about \`68.26:1\`).
- ERF open-weight token totals \`1.92M\` prompt and \`647K\` completion with about \`3:1\`: matched by \`benchmark_v2/results/full_cborg_20260427T202152Z/token_summary.txt\` (\`1,916,931\` prompt, \`647,618\` completion, ratio about \`2.96:1\`).
- PeleLMeX token ratio \`about 23:1\`: matched as a rounded workflow-summary aggregate across all \`metrics.jsonl\` files under \`${pelelmex_result_root}/\`, including the strategy-level rollups and per-run \`run_*/metrics.jsonl\` records, which together yield \`${pelelmex_ratio}\`.
- Table 3 missing-parameter recovery claim: matched by \`artifacts/self_correction/march18_ekman_spiral_workflow_history.json\`, which records the Ekman Spiral recovery path referenced in the manuscript.
- Table 4 post-execution correction claim for \`erf.fixed_dt\`: matched by the generated e2e reproducibility artifact \`${e2e_dt_repair_artifact}\`, which records a post-execution stability-consistency repair path from a user-requested \`dt=20\` to reviewer-guided \`erf.fixed_dt=5\` via \`reason_code=postexec_stability_consistency\`.

## External Or Non-Matching Claims

- Figure 1 provenance: external SIAM-talk reference. No local repository artifact was identified for the exact figure asset, so it is intentionally not claimed as part of the saved benchmark bundle.
- \`57.91%\` line coverage: matched by the historical repository validation snapshot \`${historical_cov_log}\`, which records \`TOTAL 20648 8066 8560 1049 57.91%\`. This should be treated as a March 13, 2026 validation artifact, distinct from the current packaged local \`${coverage_artifact}\` file, which reports \`${coverage_total}\` under the present worktree state.
- \`11.0%\` of CBORG hierarchical selections outside the ERF catalog: supported as a documented derivation from investigation material. Row-level inspection identified \`30\` selections across both CBORG strategy runs landing outside the ERF case catalog, out of \`272\` total CBORG selections (\`136\` rows times \`2\` strategies), yielding \`30/272 = 11.03%\`, rounded to \`11.0%\`. Because the numerator is recovered from investigation output rather than emitted as a single packaged summary field, this claim should be treated as a derived computation.

## Directory Pointers

- Cross-code benchmark rollup: \`benchmark_crosscode/latest/\`
- ERF benchmark prompt set and saved summaries: \`benchmark_v2/\` and \`benchmark_v2/results/full_amsci2_20260429T160959Z/\`
- ERF open-weight comparison run: \`benchmark_v2/results/full_cborg_20260427T202152Z/\`
- PeleLMeX benchmark evidence: \`benchmark_pelelmex/\` and \`benchmark_pelelmex/results/full_amsci2_faiss0_20260430T191652Z/\`
- REMORA benchmark evidence: \`benchmark_remora/\` and \`benchmark_remora/results/full_amsci2_faiss0_20260430T180635Z/\`
- Self-correction workflow artifact: \`artifacts/self_correction/\`
EOF

printf 'Built release assets in %s\n' "${outdir}"
ls -1 "${outdir}"
