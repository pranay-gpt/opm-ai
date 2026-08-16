"""Unit tests for the v2 oracle (opm_ai.linter.v2.oracle).

These tests verify the FlowVerdict classification logic. They do NOT
require `flow` to be installed — the synthetic FlowVerdict objects
exercise the same code paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.linter.v2.oracle import (
    FlowVerdict,
    OracleConfig,
    categorize_failure,
    find_flow,
    run_flow,
)


# ---------------------------------------------------------------------------
# Tests that don't require `flow`
# ---------------------------------------------------------------------------


def _verdict(
    exit_code: int = 0,
    stderr: str = "",
    stdout_tail: str = "",
    error_lines: list[str] | None = None,
    fatal_in_stdout: bool = False,
    timeout: bool = False,
    wallclock_ms: int = 100,
) -> FlowVerdict:
    return FlowVerdict(
        deck_path=Path("/tmp/CASE.DATA"),
        exit_code=exit_code,
        stderr=stderr,
        stdout_tail=stdout_tail,
        error_lines=error_lines or [],
        fatal_in_stdout=fatal_in_stdout,
        wallclock_ms=wallclock_ms,
        timeout=timeout,
    )


def test_known_good_verdict():
    v = _verdict()
    assert v.passed
    assert not v.failure_reason


def test_known_bad_exit_code():
    v = _verdict(exit_code=1)
    assert not v.passed
    assert "flow exit 1" in v.failure_reason


def test_known_bad_stderr_error():
    v = _verdict(
        exit_code=0,
        stderr="ERROR: keyword CECON not supported",
        error_lines=["ERROR: keyword CECON not supported"],
    )
    assert not v.passed
    assert "error line" in v.failure_reason


def test_known_bad_timeout():
    v = _verdict(exit_code=-1, timeout=True, wallclock_ms=30000)
    assert not v.passed
    assert "timeout" in v.failure_reason
    assert v.timeout


def test_known_bad_fatal_in_stdout():
    v = _verdict(
        exit_code=0,
        stdout_tail="Failed to create valid EclipseState object.",
        fatal_in_stdout=True,
    )
    assert not v.passed
    assert "fatal error in stdout" in v.failure_reason


def test_warning_lines_in_stderr_do_not_cause_failure():
    v = _verdict(
        exit_code=0,
        stderr="Warning: deprecated keyword",
        error_lines=[],
    )
    assert v.passed
    assert "Warning" not in v.failure_reason


def test_categorize_failure():
    assert categorize_failure(_verdict(exit_code=1)) == "flow-exit"
    assert (
        categorize_failure(_verdict(error_lines=["ERROR"])) == "flow-stderr-error"
    )
    assert (
        categorize_failure(_verdict(fatal_in_stdout=True)) == "flow-stdout-fatal"
    )
    assert categorize_failure(_verdict(timeout=True)) == "flow-timeout"
    assert categorize_failure(_verdict(exit_code=-2)) == "oracle-error"


# ---------------------------------------------------------------------------
# Tests that require `flow` (skipped if not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(find_flow() is None, reason="flow binary not installed")
def test_run_flow_spe1(tmp_path):
    """A simple SPE1 fixture must pass Flow dry-run."""
    config = OracleConfig(timeout_s=60, output_dir=tmp_path / "out")
    fixture = Path("tests/fixtures/spe1/SPE1CASE1.DATA").resolve()
    if not fixture.exists():
        pytest.skip(f"fixture not present: {fixture}")
    verdict = run_flow(fixture, config)
    assert verdict.passed, (
        f"SPE1CASE1 should pass Flow dry-run: {verdict.failure_reason}\n"
        f"STDERR tail: {verdict.stderr[-500:]}"
    )


@pytest.mark.skipif(find_flow() is None, reason="flow binary not installed")
def test_run_flow_spe1_import(tmp_path):
    """The v1-known-bad INCLUDE-based fixture must pass Flow dry-run
    when run from the right cwd. This is the v2 regression test target."""
    config = OracleConfig(
        timeout_s=60,
        output_dir=tmp_path / "out",
        cwd=Path("tests/fixtures"),
    )
    fixture = Path(
        "tests/fixtures/spe1/SPE1CASE1_IMPORT.DATA"
    ).resolve()
    if not fixture.exists():
        pytest.skip(f"fixture not present: {fixture}")
    verdict = run_flow(fixture, config)
    assert verdict.passed, (
        f"SPE1CASE1_IMPORT should pass Flow: {verdict.failure_reason}\n"
        f"STDERR tail: {verdict.stderr[-500:]}"
    )
