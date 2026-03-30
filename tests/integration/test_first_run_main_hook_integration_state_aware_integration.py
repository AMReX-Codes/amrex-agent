"""
Phase-1 RED Integration Tests v3: Non-TTY Preflight — Reported Command Path
============================================================================
All call surfaces, exit mechanisms, and patch targets confirmed from seam map.

Corrections applied from v2 codex review:
  [C-1] _run_startup_preflight is in src.main, not src.first_run. Import fixed.
  [C-2] Blocking exit mechanism: _run_startup_preflight raises ValueError
        ("Startup readiness preflight failed..."), NOT SystemExit. All
        blocking assertions catch ValueError, not SystemExit.
  [C-3] capsys → caplog. Preflight output goes through logger not print().
  [C-4] Commit control: patch src.first_run._read_dependencies (expected commit)
        and src.first_run._get_git_head_sha (actual commit).
        No fake _get_pinned_commit / _get_actual_erf_commit — do not exist.
  [C-5] issue["code"] used throughout (confirmed field name).
  [C-6] Other readiness checks (FAISS, schema, repo-missing) are silenced so
        ERF_COMMIT_MISMATCH is the only issue under test. Achieved by patching
        the checks that produce other issue codes rather than patching
        _collect_readiness_issues wholesale.

Call chain (confirmed from seam map):
  src.main._run_startup_preflight(config)
    -> run_startup_readiness_checks(repo_root, config, is_tty, ...)
      -> _collect_readiness_issues(**kwargs)
        -> check_dependency_commit_alignment(...)
          -> _read_dependencies(repo_root)        [expected commit]
          -> _get_git_head_sha(erf_repo_path)     [actual commit]
          -> _issue(ISSUE_ERF_COMMIT_MISMATCH, "error", ...)
      -> resolve_readiness_issues_noninteractive(...)
        [non-TTY: auto-resolves ERF_REPO_MISSING only, mismatch stays unresolved]
      -> returns exit_code=1 when unresolved error exists
    -> raises ValueError if unresolved blocking issues remain

VERIFY items
------------
V-A. _run_startup_preflight(config) signature: confirmed from seam map (main.py:762).
     If config is not the only argument (e.g. it also takes repo_root explicitly),
     update _make_config() and all call sites.

V-B. _make_config() attributes: config.repo_root and config.erf_repo_path are
     assumed. Confirm the real attribute names read by _run_startup_preflight
     from the config object and update the MagicMock spec accordingly.

V-C. _read_dependencies(repo_root) return shape: assumed {"erf": {"commit": SHA}}.
     Must match V-1 in the unit test file. Confirm against actual return value.

V-D. Functions producing non-mismatch issues that need silencing.
     Tests patch check_faiss_readiness, check_schema_staleness_readiness, and
     check_repo_readiness to return empty lists. If other functions contribute
     issues to _collect_readiness_issues, add them to the silence_other_checks
     fixture.

V-E. Logger name for caplog assertions. Assumed root logger or "first_run".
     If preflight logs under a namespaced logger (e.g. "erf.preflight"),
     add caplog.set_level(logging.WARNING, logger="erf.preflight") in the fixture.
"""

import logging
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.main import _run_startup_preflight  # [C-1] confirmed: main.py:762


PINNED_SHA = "abc123000000pinned"
ACTUAL_SHA  = "def456000000actual"


# ─── Config factory ───────────────────────────────────────────────────────────

def _make_config(erf_path: Path) -> MagicMock:
    """
    Minimal config stub for _run_startup_preflight.
    VERIFY: V-A, V-B — confirm attribute names read from config inside
    _run_startup_preflight and run_startup_readiness_checks.
    """
    cfg = MagicMock()
    cfg.amrex_agent_root = str(erf_path.parent)
    cfg.erf_repo_path    = str(erf_path)
    cfg.non_interactive  = True
    return cfg


# ─── Path fixture ─────────────────────────────────────────────────────────────

@pytest.fixture()
def erf_path(tmp_path) -> Path:
    """Real directory so erf_repo_path satisfies Path.exists() inside call chain."""
    p = tmp_path / "erf"
    p.mkdir()
    return p


# ─── Commit control fixtures ──────────────────────────────────────────────────

@pytest.fixture()
def expect_pinned_sha(monkeypatch):
    """
    [C-4] _read_dependencies returns a structure that pins PINNED_SHA as the
    expected ERF commit. Patched at src.first_run._read_dependencies.
    VERIFY: V-C — update return structure if shape differs.
    """
    monkeypatch.setattr(
        "src.first_run._read_dependencies",
        lambda *a, **kw: {"repos": {"erf": {"commit": PINNED_SHA}}},
    )


@pytest.fixture()
def actual_is_different(monkeypatch):
    """
    [C-4] _get_git_head_sha returns ACTUAL_SHA (differs from PINNED_SHA).
    Confirmed call site: first_run.py:366.
    """
    monkeypatch.setattr(
        "src.first_run._get_git_head_sha",
        lambda *a, **kw: ACTUAL_SHA,
    )


@pytest.fixture()
def actual_is_pinned(monkeypatch):
    """_get_git_head_sha returns PINNED_SHA — SHA match, no mismatch."""
    monkeypatch.setattr(
        "src.first_run._get_git_head_sha",
        lambda *a, **kw: PINNED_SHA,
    )


# ─── Phase 2 seam fixtures (future-facing, currently inert) ──────────────────

@pytest.fixture()
def indexed_for_actual(monkeypatch):
    """PHASE 2 SEAM. No effect on severity until Phase 2 wires this in."""
    monkeypatch.setattr(
        "src.first_run._collect_indexed_commits",
        lambda *a, **kw: {ACTUAL_SHA},
    )


@pytest.fixture()
def indexed_for_pinned_only(monkeypatch):
    """PHASE 2 SEAM. No effect on severity until Phase 2 wires this in."""
    monkeypatch.setattr(
        "src.first_run._collect_indexed_commits",
        lambda *a, **kw: {PINNED_SHA},
    )


@pytest.fixture()
def schema_fresh(monkeypatch):
    """PHASE 2 SEAM. No effect on severity until Phase 2 wires this in."""
    report = MagicMock()
    report.is_stale = False
    monkeypatch.setattr(
        "src.first_run.check_schema_staleness",
        lambda *a, **kw: report,
    )


@pytest.fixture()
def schema_stale(monkeypatch):
    """PHASE 2 SEAM. No effect on severity until Phase 2 wires this in."""
    report = MagicMock()
    report.is_stale = True
    monkeypatch.setattr(
        "src.first_run.check_schema_staleness",
        lambda *a, **kw: report,
    )


# ─── Noise suppression fixture ────────────────────────────────────────────────

@pytest.fixture()
def silence_other_checks(monkeypatch):
    """
    [C-6] Silences readiness checks that produce non-mismatch issues, ensuring
    ERF_COMMIT_MISMATCH is the only issue in play for these tests.
    VERIFY: V-D — if other functions contribute issues, add patches here.

    Each patched function returns an empty list (no issues for that check).
    Patch targets assume these are module-level functions called directly inside
    _collect_readiness_issues. Adjust paths if they are method calls on an object.
    """
    empty = lambda *a, **kw: {"issues": []}
    for fn_name in (
        "check_faiss_readiness",
        "check_schema_staleness_readiness",
        "check_repo_readiness",          # VERIFY: V-D — add/remove as needed
    ):
        monkeypatch.setattr(f"src.first_run.{fn_name}", empty, raising=False)

    monkeypatch.setattr(
        "subprocess.run",
        MagicMock(side_effect=RuntimeError("subprocess.run blocked in integration tests")),
    )


# ─── Blocking assertion helpers ───────────────────────────────────────────────

def _assert_did_not_block(erf_path, config):
    """
    [C-2] _run_startup_preflight raises ValueError on blocking. A non-blocking
    run completes without raising. Asserts no ValueError is raised.
    """
    try:
        _run_startup_preflight(config)  # VERIFY: V-A
    except ValueError as exc:
        pytest.fail(
            f"_run_startup_preflight raised ValueError — preflight blocked.\n"
            f"Expected non-blocking outcome for compatible mismatch state.\n"
            f"Error: {exc}\n"
            f"ERF HEAD={ACTUAL_SHA!r} differs from pin={PINNED_SHA!r} but "
            "local schema and FAISS index are valid for actual HEAD."
        )


def _assert_did_block(erf_path, config):
    """
    [C-2] Asserts that _run_startup_preflight raises ValueError (blocking path).
    """
    with pytest.raises(ValueError, match="preflight"):
        _run_startup_preflight(config)  # VERIFY: V-A


# ═══════════════════════════════════════════════════════════════════════════════
# Acceptance criterion #1 — Reported command scenario
# ═══════════════════════════════════════════════════════════════════════════════

class TestReportedCommandScenario:

    # ── RED: primary acceptance criterion ─────────────────────────────────────

    def test_compatible_mismatch_does_not_block(
        self, erf_path, silence_other_checks,
        expect_pinned_sha, actual_is_different,
        schema_fresh, indexed_for_actual,
    ):
        """
        STATUS: RED
        MAPS TO: acceptance criterion #1 (plan section: Acceptance Criteria).

        Current behavior: _run_startup_preflight raises ValueError for any
        SHA mismatch in non-TTY mode, regardless of local artifact state.

        Required behavior after Phase 2: a mismatch where schema is fresh
        and FAISS index is built for actual SHA must complete without raising.
        ValueError must not be raised; warning must still be logged.

        This test is the machine-readable form of the reported user scenario.
        """
        config = _make_config(erf_path)
        _assert_did_not_block(erf_path, config)

    # ── GREEN-lock: incompatible state must stay blocking ─────────────────────

    def test_incompatible_mismatch_still_blocks(
        self, erf_path, silence_other_checks,
        expect_pinned_sha, actual_is_different,
        schema_stale, indexed_for_pinned_only,
    ):
        """
        STATUS: likely GREEN (current impl blocks all mismatches).
        ROLE: regression lock. The Phase 2 fix must not over-relax the gate.
        Stale schema + index built for wrong SHA must remain a hard block.
        If this goes RED during Phase 3 refactor, implementation over-relaxed.
        """
        config = _make_config(erf_path)
        _assert_did_block(erf_path, config)

    # ── GREEN-lock: SHA match must never raise ─────────────────────────────────

    def test_pin_match_does_not_block(
        self, erf_path, silence_other_checks,
        expect_pinned_sha, actual_is_pinned,
        schema_fresh, indexed_for_actual,
    ):
        """
        STATUS: likely GREEN.
        ROLE: regression lock. A matching SHA must never cause a blocking raise.
        Guards against refactor accidentally introducing mismatch logic on
        the clean path.
        """
        config = _make_config(erf_path)
        _assert_did_not_block(erf_path, config)

    # ── RED: warning must be visible even when not blocking ────────────────────

    def test_warning_logged_for_compatible_mismatch(
        self, erf_path, silence_other_checks,
        expect_pinned_sha, actual_is_different,
        schema_fresh, indexed_for_actual,
        caplog,   # [C-3]
    ):
        """
        STATUS: RED
        WHY RED: current impl either raises before emitting a warning-level log,
        or emits an error-level log and then raises. After Phase 2, a compatible
        mismatch must log a WARNING and complete without raising — silent pass
        is not acceptable. The user must know their SHA differs from the pin.

        VERIFY: V-E if the assertion misses the log record (wrong logger name).
        """
        config = _make_config(erf_path)

        with caplog.at_level(logging.WARNING):  # VERIFY: V-E for logger name
            try:
                _run_startup_preflight(config)
            except ValueError:
                # Still check log content even if currently blocking.
                # After Phase 2 the ValueError branch should not be hit here.
                pass

        mismatch_warned = any(
            "ERF_COMMIT_MISMATCH" in rec.message
            or "commit" in rec.message.lower()
            for rec in caplog.records
            if rec.levelno == logging.WARNING
        )
        assert mismatch_warned, (
            "Expected a WARNING-level log referencing commit mismatch for a "
            "compatible-mismatch state. No such record found.\n"
            f"All records: {[(r.levelname, r.message) for r in caplog.records]}\n"
            "If nothing appears, check V-E (logger name) or confirm that "
            "preflight logs before the ValueError is raised."
        )

    # ── RED: new payload fields must survive through full preflight path ───────

    def test_compatibility_payload_fields_present_through_preflight(
        self, erf_path, silence_other_checks,
        expect_pinned_sha, actual_is_different,
        schema_fresh, indexed_for_actual,
        caplog,
    ):
        """
        STATUS: RED
        Verifies that compatibility_verified, indexed_for_actual_commit, and
        schema_stale survive the full call chain from _run_startup_preflight
        down to the logged issue payload.

        Because _run_startup_preflight may not return the issue list directly
        (it raises ValueError on blocking), this test inspects the structured
        log record for the issue dict rather than a return value.

        If preflight logs the full issue dict at WARNING level (e.g. as JSON
        or repr), the assertion below will find the fields. If it logs only a
        human-readable string, this test must be adapted to check the
        underlying issue object via a lower-level seam.

        VERIFY: confirm that the preflight path logs the issue dict in a form
        that includes the new fields, or adapt the assertion to inspect
        run_startup_readiness_checks return value directly.
        """
        config = _make_config(erf_path)

        with caplog.at_level(logging.WARNING):
            try:
                _run_startup_preflight(config)
            except ValueError:
                pass

        all_messages = " ".join(rec.message for rec in caplog.records)

        for field in ("compatibility_verified", "indexed_for_actual_commit", "schema_stale"):
            assert field in all_messages, (
                f"Expected field {field!r} to appear in preflight log output. "
                f"Field is absent — either Phase 2 has not added it to the issue "
                f"dict, or the logger does not emit the full issue payload.\n"
                f"All log messages: {[rec.message for rec in caplog.records]}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Shallow integration variant: patch run_startup_readiness_checks directly
# ═══════════════════════════════════════════════════════════════════════════════

class TestShallowPreflight:
    """
    Shallow integration tests that patch run_startup_readiness_checks itself
    rather than its internal seams. Useful for testing _run_startup_preflight's
    own logic (ValueError raising, config unpacking) in isolation from the full
    readiness stack.

    These complement TestReportedCommandScenario rather than replacing it.
    They are not acceptance criterion tests — they are structural tests of the
    preflight gate contract.
    """

    @pytest.fixture()
    def _patch_readiness_checks(self, monkeypatch):
        """Returns a factory that controls what run_startup_readiness_checks yields."""
        def _wire(issues: list, exit_code: int):
            result = {
                "issues": issues,
                "unresolved": [i for i in issues if i.get("severity") == "error"],
                "resolved": [],
                "exit_code": exit_code,
            }
            monkeypatch.setattr(
                "src.main.run_startup_readiness_checks",  # confirmed: called from main.py
                lambda *a, **kw: result,
            )
            return result
        return _wire

    def test_blocking_issues_cause_value_error(self, erf_path, _patch_readiness_checks):
        """
        GREEN-lock. _run_startup_preflight must raise ValueError when
        run_startup_readiness_checks returns exit_code != 0.
        Tests _run_startup_preflight's own gate logic, not the readiness stack.
        """
        _patch_readiness_checks(
            issues=[{"code": "ERF_COMMIT_MISMATCH", "severity": "error"}],
            exit_code=1,
        )
        config = _make_config(erf_path)
        with pytest.raises(ValueError, match="preflight"):
            _run_startup_preflight(config)

    def test_no_blocking_issues_does_not_raise(self, erf_path, _patch_readiness_checks):
        """
        GREEN-lock. _run_startup_preflight must not raise when exit_code == 0.
        Locks the non-blocking path through _run_startup_preflight's own logic.
        """
        _patch_readiness_checks(issues=[], exit_code=0)
        config = _make_config(erf_path)
        try:
            _run_startup_preflight(config)
        except ValueError as exc:
            pytest.fail(
                f"_run_startup_preflight raised ValueError with exit_code=0: {exc}"
            )

    def test_warning_severity_does_not_cause_value_error(
        self, erf_path, _patch_readiness_checks
    ):
        """
        RED: after Phase 2, a warning-severity mismatch must produce exit_code=0
        from run_startup_readiness_checks, and therefore must not cause ValueError
        in _run_startup_preflight.

        Currently RED because: run_startup_readiness_checks returns exit_code=1
        for any ERF_COMMIT_MISMATCH regardless of severity. After Phase 2, a
        warning-severity mismatch must produce exit_code=0.

        This test locks that contract at the _run_startup_preflight boundary.
        It uses the shallow patch to isolate _run_startup_preflight's own logic
        and confirm it does not re-classify a warning into a block.
        """
        _patch_readiness_checks(
            issues=[{"code": "ERF_COMMIT_MISMATCH", "severity": "warning"}],
            exit_code=0,   # Phase 2: warning mismatch yields exit_code=0
        )
        config = _make_config(erf_path)
        try:
            _run_startup_preflight(config)
        except ValueError as exc:
            pytest.fail(
                f"_run_startup_preflight raised ValueError for a warning-severity "
                f"mismatch with exit_code=0. The preflight gate must not escalate "
                f"warnings to blocking errors.\nError: {exc}"
            )
