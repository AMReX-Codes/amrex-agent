"""
Phase-1 RED Tests v3: State-Aware Preflight — ERF Commit Mismatch
=================================================================
All patch targets and return shapes confirmed from seam map.

Corrections applied from v2 codex review:
  [C-1] check_dependency_commit_alignment returns {"issues": [...]} not list[dict].
        _find_mismatch_issues extracts from result["issues"].
  [C-2] Commit control: expected commit via expected_dependencies= kwarg (confirmed
        accepted); actual commit via patch of src.first_run._get_git_head_sha
        (confirmed call site: first_run.py:366).
  [C-3] erf_repo_path must satisfy Path.exists(). Tests use tmp_path fixture.
  [C-4] TestMismatchIssuePayloadFields is module-level, not nested in another class.
  [C-5] _collect_indexed_commits(repo_root, repo_name) -> set[str] EXISTS at
        first_run.py:177 but is NOT consulted in mismatch severity logic today.
        Fixture patches are future-facing Phase 2 seams — labeled explicitly.
  [C-6] check_dependency_commit_alignment does NOT accept pinned_commit/actual_commit
        kwargs. Removed. Commit values enter only via expected_dependencies and
        _get_git_head_sha.

VERIFY items (all that remain after seam map)
---------------------------------------------
V-1. expected_dependencies kwarg format fed into check_dependency_commit_alignment.
     Assumed: {"erf": {"commit": SHA_STRING}}.
     If _read_dependencies returns a different structure (e.g. a list), update
     _make_expected_deps() to match the real return shape.

V-2. erf_repo_path kwarg type: str vs Path.
     Tests pass str(erf_path). If the function expects a Path object, remove str().
     Conversely if _erf_path resolution inside the function requires a string, keep str().

V-3. _get_git_head_sha called as _get_git_head_sha(erf_repo_path) — single positional.
     Confirmed from seam map (first_run.py:366). If signature adds extra args, update
     the lambda in actual_sha_differs / actual_sha_matches fixtures.

V-4. _collect_readiness_issues minimum required kwargs beyond repo_root and erf_repo_path.
     Relevant only for the matrix sweep at the bottom of this file. Add stub kwargs
     (provider=, config=MagicMock(), etc.) if the function raises on missing kwargs.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.first_run import (
    check_dependency_commit_alignment,   # primary unit seam (first_run.py:359)
    _collect_readiness_issues,           # used in decision matrix sweep only
)

# ─── SHA constants ────────────────────────────────────────────────────────────

PINNED_SHA = "abc123000000pinned"
ACTUAL_SHA  = "def456000000actual"   # differs from pin → mismatch path
SAME_SHA    = "abc123000000same"     # pin == actual → no mismatch


# ─── expected_dependencies factory ───────────────────────────────────────────

def _make_expected_deps(sha: str) -> dict:
    """
    Minimal expected_dependencies value that causes check_dependency_commit_alignment
    to use sha as the expected (pinned) ERF commit.
    VERIFY: V-1 — update structure if _read_dependencies returns a different shape.
    """
    return {"repos": {"erf": {"commit": sha}}}


# ─── Issue extraction helpers ─────────────────────────────────────────────────

def _find_mismatch_issues(result: dict) -> list:
    """
    [C-1] result is {"issues": [...]}.
    Extracts ERF_COMMIT_MISMATCH entries from the issues list.
    Uses issue["code"] — confirmed field name from seam map.
    """
    return [
        i for i in result.get("issues", [])
        if i.get("code") == "ERF_COMMIT_MISMATCH"
    ]


def _is_blocking(issue: dict) -> bool:
    return issue.get("severity") == "error"


def _is_warning(issue: dict) -> bool:
    return issue.get("severity") == "warning"


# ─── Path fixture ─────────────────────────────────────────────────────────────

@pytest.fixture()
def erf_path(tmp_path) -> Path:
    """
    [C-3] Real directory so erf_repo_path satisfies Path.exists() inside
    check_dependency_commit_alignment. tmp_path is isolated per test.
    """
    p = tmp_path / "erf"
    p.mkdir()
    return p


# ─── Commit control fixtures ──────────────────────────────────────────────────

@pytest.fixture()
def actual_sha_differs(monkeypatch):
    """
    [C-2] Patches _get_git_head_sha to return ACTUAL_SHA (differs from PINNED_SHA).
    Confirmed call site: first_run.py:366 — _get_git_head_sha(erf_repo_path).
    VERIFY: V-3 if signature has changed.
    """
    monkeypatch.setattr(
        "src.first_run._get_git_head_sha",
        lambda *a, **kw: ACTUAL_SHA,
    )


@pytest.fixture()
def actual_sha_matches(monkeypatch):
    """_get_git_head_sha returns SAME_SHA — used for pin-match (no mismatch) cases."""
    monkeypatch.setattr(
        "src.first_run._get_git_head_sha",
        lambda *a, **kw: SAME_SHA,
    )


# ─── Phase 2 future seam fixtures ─────────────────────────────────────────────
# [C-5] _collect_indexed_commits EXISTS (first_run.py:177) but is NOT consulted
# in mismatch severity logic today. These patches are correct and will activate
# once Phase 2 wires _collect_indexed_commits into check_dependency_commit_alignment.

@pytest.fixture()
def indexed_for_actual(monkeypatch):
    """
    FAISS manifests include ACTUAL_SHA. Compatible: index built for current commit.
    PHASE 2 SEAM — currently has no effect on mismatch severity.
    Signature confirmed: _collect_indexed_commits(repo_root: Path, repo_name: str)
    """
    monkeypatch.setattr(
        "src.first_run._collect_indexed_commits",
        lambda *a, **kw: {ACTUAL_SHA},
    )


@pytest.fixture()
def indexed_for_pinned_only(monkeypatch):
    """
    FAISS index exists but built for PINNED_SHA, not ACTUAL_SHA.
    PHASE 2 SEAM — currently has no effect on mismatch severity.
    """
    monkeypatch.setattr(
        "src.first_run._collect_indexed_commits",
        lambda *a, **kw: {PINNED_SHA},
    )


@pytest.fixture()
def no_manifests(monkeypatch):
    """
    No FAISS manifests — provenance unverifiable.
    PHASE 2 SEAM — currently has no effect on mismatch severity.
    """
    monkeypatch.setattr(
        "src.first_run._collect_indexed_commits",
        lambda *a, **kw: set(),
    )


@pytest.fixture()
def schema_fresh(monkeypatch):
    """
    check_schema_staleness returns non-stale report.
    PHASE 2 SEAM — not currently consulted by check_dependency_commit_alignment.
    Patch target assumes: from src.services.schema_staleness import check_schema_staleness
    in first_run.py. VERIFY if imported differently.
    """
    report = MagicMock()
    report.is_stale = False
    monkeypatch.setattr(
        "src.first_run.check_schema_staleness",
        lambda *a, **kw: report,
    )


@pytest.fixture()
def schema_stale(monkeypatch):
    """
    check_schema_staleness returns stale report.
    PHASE 2 SEAM — not currently consulted by check_dependency_commit_alignment.
    """
    report = MagicMock()
    report.is_stale = True
    monkeypatch.setattr(
        "src.first_run.check_schema_staleness",
        lambda *a, **kw: report,
    )


# ─── subprocess guard ─────────────────────────────────────────────────────────

@pytest.fixture()
def no_real_subprocess(monkeypatch):
    monkeypatch.setattr(
        "subprocess.run",
        MagicMock(side_effect=RuntimeError("subprocess.run blocked in unit tests")),
    )


# ─── Primary call wrapper ─────────────────────────────────────────────────────

def _run_alignment_check(erf_path: Path, pinned_sha: str) -> list:
    """
    Calls check_dependency_commit_alignment with controlled expected_dependencies
    and an erf_repo_path that exists. Actual SHA is controlled by the
    actual_sha_differs / actual_sha_matches fixture (patches _get_git_head_sha).

    Returns the issues list extracted from {"issues": [...]}.
    VERIFY: V-2 if erf_repo_path type needs to be Path not str.
    """
    result = check_dependency_commit_alignment(
        erf_repo_path=str(erf_path),                   # VERIFY: V-2
        expected_dependencies=_make_expected_deps(pinned_sha),  # VERIFY: V-1
    )
    return result.get("issues", [])


# ═══════════════════════════════════════════════════════════════════════════════
# 5-case decision contract tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMismatchDecisionContract:

    # ── Case 1 ── RED ──────────────────────────────────────────────────────────

    def test_mismatch_with_compatible_artifacts_is_warning(
        self, erf_path, no_real_subprocess, actual_sha_differs,
        schema_fresh, indexed_for_actual
    ):
        """
        STATUS: RED
        WHY RED: check_dependency_commit_alignment emits severity="error"
        unconditionally for any SHA mismatch (current impl, first_run.py:359).
        It does not consult _collect_indexed_commits or check_schema_staleness.
        After Phase 2: must emit severity="warning" when both seams confirm
        compatibility.

        schema_fresh and indexed_for_actual are Phase 2 seams — currently inert.
        The RED reason is unconditional "error" not the missing seam calls.
        """
        issues = _run_alignment_check(erf_path, PINNED_SHA)
        mismatch = _find_mismatch_issues({"issues": issues})

        assert len(mismatch) == 1, (
            f"Expected exactly one ERF_COMMIT_MISMATCH issue, got {len(mismatch)}.\n"
            f"All issues: {issues}"
        )
        assert _is_warning(mismatch[0]), (
            f"Expected severity='warning' for compatible local state. "
            f"Got severity={mismatch[0].get('severity')!r}.\n"
            f"Full issue: {mismatch[0]}"
        )

    # ── Case 2 ── likely GREEN (regression lock) ───────────────────────────────

    def test_mismatch_with_missing_provenance_is_blocking(
        self, erf_path, no_real_subprocess, actual_sha_differs,
        schema_fresh, no_manifests
    ):
        """
        STATUS: likely GREEN — current impl blocks for all mismatches.
        ROLE: regression lock. Must remain blocking after Phase 2 refactor.
        The reason must be: provenance unverifiable (no manifests).
        If this goes RED during Phase 3 refactor, implementation over-relaxed.
        """
        issues = _run_alignment_check(erf_path, PINNED_SHA)
        mismatch = _find_mismatch_issues({"issues": issues})

        assert len(mismatch) == 1
        assert _is_blocking(mismatch[0]), (
            f"Expected severity='error' when no manifest provenance. "
            f"Got severity={mismatch[0].get('severity')!r}."
        )

    # ── Case 3 ── likely GREEN (regression lock) ───────────────────────────────

    def test_mismatch_with_stale_schema_is_blocking(
        self, erf_path, no_real_subprocess, actual_sha_differs,
        schema_stale, indexed_for_actual
    ):
        """
        STATUS: likely GREEN — current impl blocks unconditionally.
        ROLE: regression lock. Stale schema must override manifest compatibility.
        Must remain blocking through Phase 3 refactor.
        """
        issues = _run_alignment_check(erf_path, PINNED_SHA)
        mismatch = _find_mismatch_issues({"issues": issues})

        assert len(mismatch) == 1
        assert _is_blocking(mismatch[0]), (
            f"Expected severity='error' when schema is stale. "
            f"Got severity={mismatch[0].get('severity')!r}."
        )

    # ── Case 4 ── likely GREEN (regression lock) ───────────────────────────────

    def test_pinned_match_emits_no_mismatch_issue(
        self, erf_path, no_real_subprocess, actual_sha_matches,
        schema_fresh, indexed_for_actual
    ):
        """
        STATUS: likely GREEN.
        ROLE: regression lock. SHA match must produce zero mismatch issues.
        actual_sha_matches patches _get_git_head_sha to return SAME_SHA which
        matches the SAME_SHA passed as expected_dependencies.
        """
        issues = _run_alignment_check(erf_path, SAME_SHA)
        mismatch = _find_mismatch_issues({"issues": issues})

        assert len(mismatch) == 0, (
            f"Expected zero ERF_COMMIT_MISMATCH issues when SHAs match. "
            f"Got: {mismatch}"
        )

    # ── Case 5 ── RED (post Phase 2) ──────────────────────────────────────────

    def test_mismatch_with_faiss_not_indexed_for_actual_sha_is_blocking(
        self, erf_path, no_real_subprocess, actual_sha_differs,
        schema_fresh, indexed_for_pinned_only
    ):
        """
        STATUS: GREEN now (unconditional blocking), RED contract post-Phase-2.
        ROLE: locks the post-refactor invariant. After Phase 2, blocking here
        must be specifically because FAISS index was built for PINNED_SHA not
        ACTUAL_SHA. Having an index is insufficient — must be indexed FOR the
        current commit. If Phase 3 refactor causes this to return 'warning',
        the refactor broke the indexed-commit compatibility requirement.
        """
        issues = _run_alignment_check(erf_path, PINNED_SHA)
        mismatch = _find_mismatch_issues({"issues": issues})

        assert len(mismatch) == 1
        assert _is_blocking(mismatch[0]), (
            f"Expected severity='error' when index not built for actual SHA. "
            f"Got severity={mismatch[0].get('severity')!r}."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Payload field tests — module-level [C-4]
# ═══════════════════════════════════════════════════════════════════════════════

class TestMismatchIssuePayloadFields:
    """
    [C-4] Module-level class — pytest collects nested classes unreliably.
    All three new diagnostic fields are RED: current issue dict keys are:
      code, severity, suggested_action, expected_commit, actual_commit,
      repo_name, repo_path   (confirmed from seam map)
    compatibility_verified, indexed_for_actual_commit, schema_stale are absent.
    These become GREEN when Phase 2 adds them in the issue construction site
    inside check_dependency_commit_alignment.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, erf_path, no_real_subprocess, actual_sha_differs,
               schema_fresh, indexed_for_actual, request):
        """
        Put system in compatible-mismatch state to produce exactly one issue.
        Stores result on the instance so test methods can access it.
        """
        issues = _run_alignment_check(erf_path, PINNED_SHA)
        self._mismatch_issues = _find_mismatch_issues({"issues": issues})

    def _get_single_mismatch(self) -> dict:
        assert len(self._mismatch_issues) == 1, (
            f"Fixture produced {len(self._mismatch_issues)} mismatch issues, "
            "expected 1. Check _setup fixture state or V-1/V-2."
        )
        return self._mismatch_issues[0]

    # ── Case 6 ── RED ──────────────────────────────────────────────────────────

    def test_compatibility_verified_field_present(self):
        """RED: field absent from current issue dict."""
        issue = self._get_single_mismatch()
        assert "compatibility_verified" in issue, (
            f"Issue payload missing 'compatibility_verified'.\n"
            f"Present keys: {sorted(issue.keys())}"
        )
        assert isinstance(issue["compatibility_verified"], bool), (
            f"Expected bool, got {type(issue['compatibility_verified'])!r}"
        )

    # ── Case 7 ── RED ──────────────────────────────────────────────────────────

    def test_indexed_for_actual_commit_field_present(self):
        """RED: field absent from current issue dict."""
        issue = self._get_single_mismatch()
        assert "indexed_for_actual_commit" in issue, (
            f"Issue payload missing 'indexed_for_actual_commit'.\n"
            f"Present keys: {sorted(issue.keys())}"
        )
        assert isinstance(issue["indexed_for_actual_commit"], bool)

    # ── Case 8 ── RED ──────────────────────────────────────────────────────────

    def test_schema_stale_field_present(self):
        """RED: field absent from current issue dict."""
        issue = self._get_single_mismatch()
        assert "schema_stale" in issue, (
            f"Issue payload missing 'schema_stale'.\n"
            f"Present keys: {sorted(issue.keys())}"
        )
        assert isinstance(issue["schema_stale"], bool)

    def test_confirmed_existing_fields_preserved(self):
        """
        Regression lock on the confirmed existing issue dict shape.
        If any of these fail, the seam map is stale — update before proceeding.
        """
        issue = self._get_single_mismatch()
        for field in ("code", "severity", "suggested_action",
                      "expected_commit", "actual_commit", "repo_name", "repo_path"):
            assert field in issue, (
                f"Confirmed existing field {field!r} missing from issue dict. "
                f"Seam map may be stale. Present keys: {sorted(issue.keys())}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Parametrized decision matrix
# ═══════════════════════════════════════════════════════════════════════════════

_MATRIX = [
    # sha_match  idx_actual  stale   expected_sev  status        case_id
    (True,  True,  False,  None,       "GREEN-lock",  "pin-match-clean"),
    (True,  False, False,  None,       "GREEN-lock",  "pin-match-not-indexed"),
    (True,  True,  True,   None,       "GREEN-lock",  "pin-match-stale"),
    (False, True,  False,  "warning",  "RED",         "mismatch-fully-compatible"),
    (False, True,  True,   "error",    "GREEN-lock",  "mismatch-stale-schema-overrides"),
    (False, False, False,  "error",    "GREEN-lock",  "mismatch-not-indexed-for-actual"),
    (False, False, True,   "error",    "GREEN-lock",  "mismatch-not-indexed-and-stale"),
]

@pytest.mark.parametrize(
    "sha_match,idx_actual,stale,expected_sev,status,case_id",
    _MATRIX,
    ids=[row[5] for row in _MATRIX],
)
def test_mismatch_decision_matrix(
    sha_match, idx_actual, stale, expected_sev, status, case_id,
    erf_path, no_real_subprocess, monkeypatch,
):
    """
    Exhaustive parametrized matrix over check_dependency_commit_alignment.
    Only "mismatch-fully-compatible" is expected RED against current impl.
    GREEN-lock rows must survive Phase 2 and Phase 3 without regression.

    [C-5] _collect_indexed_commits and check_schema_staleness patches are
    future-facing — they have no effect on severity today, but wire in
    correctly once Phase 2 implementation is complete.

    VERIFY: V-4 if _collect_readiness_issues version of this matrix is needed.
    """
    # Phase 2 seam: schema staleness
    report = MagicMock()
    report.is_stale = stale
    monkeypatch.setattr("src.first_run.check_schema_staleness", lambda *a, **kw: report)

    # Phase 2 seam: indexed commits
    indexed = {ACTUAL_SHA} if idx_actual else {PINNED_SHA}
    monkeypatch.setattr("src.first_run._collect_indexed_commits", lambda *a, **kw: indexed)

    # Commit state
    if sha_match:
        monkeypatch.setattr("src.first_run._get_git_head_sha", lambda *a, **kw: SAME_SHA)
        pinned = SAME_SHA
    else:
        monkeypatch.setattr("src.first_run._get_git_head_sha", lambda *a, **kw: ACTUAL_SHA)
        pinned = PINNED_SHA

    result = check_dependency_commit_alignment(
        erf_repo_path=str(erf_path),                   # VERIFY: V-2
        expected_dependencies=_make_expected_deps(pinned),  # VERIFY: V-1
    )
    mismatch = _find_mismatch_issues(result)

    if expected_sev is None:
        assert len(mismatch) == 0, (
            f"[{case_id}|{status}] Expected zero mismatch issues. Got: {mismatch}"
        )
    else:
        assert len(mismatch) == 1, (
            f"[{case_id}|{status}] Expected one mismatch issue, got {len(mismatch)}."
        )
        got_sev = mismatch[0].get("severity")
        assert got_sev == expected_sev, (
            f"[{case_id}|{status}] Expected severity={expected_sev!r}, "
            f"got={got_sev!r}.\nFull issue: {mismatch[0]}"
        )
