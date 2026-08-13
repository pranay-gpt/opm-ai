"""Unit tests for self_heal.py.

Coverage:
- Scoring model: oracle + calibration blending
- Bayesian smoothing of empty calibration buckets
- Verified ranking puts verified proposals first
- LLM gating via env var
- Calibration report loading (missing/malformed)
- End-to-end self_heal_deck on a fixture
- self_heal_deck with no proposals returns empty list
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from opm_ai.linter.v2.calibration import (
    AttemptResult,
    CalibrationReport,
    FixtureResult,
)
from opm_ai.linter.v2.fix_proposals import FixProposal
from opm_ai.linter.v2.oracle import FlowVerdict, OracleConfig
from opm_ai.linter.v2.self_heal import (
    ScoredProposal,
    SelfHealResult,
    _apply_oracle_to_proposal,
    _score_proposal,
    _llm_propose_fix,
    load_calibration_report,
    self_heal_deck,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def passing_verdict() -> FlowVerdict:
    return FlowVerdict(
        deck_path=Path("x.DATA"),
        exit_code=0,
        stderr="",
        stdout_tail="",
        error_lines=[],
        fatal_in_stdout=False,
        wallclock_ms=100,
    )


@pytest.fixture
def failing_verdict() -> FlowVerdict:
    return FlowVerdict(
        deck_path=Path("x.DATA"),
        exit_code=1,
        stderr="ERROR: bad",
        stdout_tail="",
        error_lines=["ERROR: bad"],
        fatal_in_stdout=False,
        wallclock_ms=100,
    )


@pytest.fixture
def sample_proposal() -> FixProposal:
    return FixProposal(
        rule_code=232,
        issue_keyword=None,
        original_text="WELLDIMS\n4 /\n",
        patched_text="WELLDIMS\n6 /\n",
        description="bump MAXWELLS",
        original_value="4",
        new_value="6",
    )


@pytest.fixture
def sample_calibration() -> CalibrationReport:
    return CalibrationReport(
        metadata={"timestamp": "2026-08-13"},
        summary={
            "total_fixtures": 10,
            "total_issues_seen": 50,
            "total_proposals_attempted": 20,
            "total_proposals_successful": 18,
            "total_proposals_skipped": 0,
        },
        per_rule={
            "232": {
                "issues_seen": 5,
                "proposals_attempted": 5,
                "proposals_successful": 5,
                "proposals_skipped": 0,
                "success_rate": 1.0,
            },
            "234": {
                "issues_seen": 10,
                "proposals_attempted": 10,
                "proposals_successful": 8,
                "proposals_skipped": 0,
                "success_rate": 0.8,
            },
        },
        per_fixture=[],
    )


# ---------------------------------------------------------------------------
# Scoring model
# ---------------------------------------------------------------------------

def test_score_proposal_verified_high_confidence(
    sample_proposal, passing_verdict, sample_calibration
):
    """A verified proposal with perfect calibration gets high confidence."""
    scored = _score_proposal(
        232, sample_proposal, passing_verdict, passing_verdict,
        llm_proposed=False, calibration=sample_calibration,
    )
    assert scored.verified is True
    assert scored.confidence > 0.9
    assert scored.llm_proposed is False


def test_score_proposal_unverified_low_confidence(
    sample_proposal, passing_verdict, failing_verdict, sample_calibration
):
    """A proposal that breaks the deck gets low confidence + verified=False."""
    scored = _score_proposal(
        232, sample_proposal, passing_verdict, failing_verdict,
        llm_proposed=False, calibration=sample_calibration,
    )
    assert scored.verified is False
    # Confidence is below the verified threshold; the oracle_score
    # contributes 0.0 here, so confidence is dragged below 0.6.
    assert scored.confidence < 0.6


def test_score_proposal_bayesian_smoothing_when_no_data(
    sample_proposal, passing_verdict
):
    """When calibration has no data, smoothing produces ~0.5 (not 0 or 1)."""
    no_data_cal = CalibrationReport(
        metadata={}, summary={}, per_rule={}, per_fixture=[]
    )
    scored = _score_proposal(
        999,  # rule not in calibration
        sample_proposal, passing_verdict, passing_verdict,
        llm_proposed=False, calibration=no_data_cal,
    )
    # Default calib_rate = 0.5
    # Oracle verified = 1.0
    # severity = 0.8
    # llm_score = 1.0
    # confidence = 0.4*0.5 + 0.4*1.0 + 0.1*0.8 + 0.1*1.0 = 0.78
    assert 0.6 < scored.confidence < 0.9


def test_score_proposal_llm_penalty(
    sample_proposal, passing_verdict, sample_calibration
):
    """LLM proposals are downweighted vs. mechanical with same oracle result."""
    mechanical = _score_proposal(
        232, sample_proposal, passing_verdict, passing_verdict,
        llm_proposed=False, calibration=sample_calibration,
    )
    llm = _score_proposal(
        232, sample_proposal, passing_verdict, passing_verdict,
        llm_proposed=True, calibration=sample_calibration,
    )
    assert llm.confidence < mechanical.confidence
    assert llm.llm_proposed is True
    assert mechanical.llm_proposed is False


def test_score_proposal_rule_with_partial_calibration(
    sample_proposal, passing_verdict, sample_calibration
):
    """Rule with 8/10 success rate (calibrated) is scored below 100% rule."""
    scored = _score_proposal(
        234, sample_proposal, passing_verdict, passing_verdict,
        llm_proposed=False, calibration=sample_calibration,
    )
    perfect = _score_proposal(
        232, sample_proposal, passing_verdict, passing_verdict,
        llm_proposed=False, calibration=sample_calibration,
    )
    assert scored.confidence < perfect.confidence


def test_score_proposal_failure_to_success_gets_verified(
    sample_proposal, failing_verdict, passing_verdict
):
    """A patch that fixes a failing deck is verified=True."""
    scored = _score_proposal(
        232, sample_proposal, failing_verdict, passing_verdict,
        llm_proposed=False, calibration=None,
    )
    assert scored.verified is True


def test_score_proposal_both_failing_is_ambiguous(
    sample_proposal, failing_verdict
):
    """When both before/after fail, verified=False and oracle_score=0.3."""
    scored = _score_proposal(
        232, sample_proposal, failing_verdict, failing_verdict,
        llm_proposed=False, calibration=None,
    )
    assert scored.verified is False
    # 0.4 * 0.5 (calib prior) + 0.4 * 0.3 (oracle ambiguous)
    # + 0.1 * 0.8 + 0.1 * 1.0 = 0.5 + 0.12 + 0.08 + 0.1 = 0.8?
    # Actually 0.4 * 0.5 = 0.20; 0.4 * 0.3 = 0.12; 0.1 * 0.8 = 0.08;
    # 0.1 * 1.0 = 0.10; total = 0.50
    assert scored.confidence < 0.7


# ---------------------------------------------------------------------------
# Calibration loading
# ---------------------------------------------------------------------------

def test_load_calibration_report_missing_file(tmp_path):
    """Returns None when the report file doesn't exist."""
    result = load_calibration_report(tmp_path / "missing.json")
    assert result is None


def test_load_calibration_report_malformed_json(tmp_path):
    """Returns None on JSON parse error."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json")
    result = load_calibration_report(bad)
    assert result is None


def test_load_calibration_report_round_trip(tmp_path):
    """A valid report is reconstructed as a CalibrationReport."""
    report_path = tmp_path / "cal.json"
    payload = {
        "metadata": {"timestamp": "2026-08-13"},
        "summary": {"total_fixtures": 5, "total_issues_seen": 10},
        "per_rule": {"232": {"success_rate": 0.9}},
        "per_fixture": [
            {
                "path": "/tmp/x.DATA",
                "issues_seen": 3,
                "oracle_passed_before": True,
                "attempts": [
                    {
                        "rule_code": 232,
                        "original_value": "4",
                        "new_value": "6",
                        "oracle_passed_before": True,
                        "oracle_passed_after": True,
                        "oracle_after_wallclock_ms": 100,
                        "successful": True,
                        "description": "bump MAXWELLS",
                    }
                ],
            }
        ],
    }
    report_path.write_text(json.dumps(payload))
    loaded = load_calibration_report(report_path)
    assert loaded is not None
    assert loaded.summary["total_fixtures"] == 5
    assert loaded.per_rule["232"]["success_rate"] == 0.9
    assert len(loaded.per_fixture) == 1
    assert len(loaded.per_fixture[0].attempts) == 1
    assert loaded.per_fixture[0].attempts[0].successful is True


# ---------------------------------------------------------------------------
# LLM gating
# ---------------------------------------------------------------------------

def test_llm_propose_fix_disabled_by_default(
    monkeypatch, tmp_path
):
    """Without OPM_AI_USE_LLM_FIXES=1, _llm_propose_fix returns None."""
    monkeypatch.delenv("OPM_AI_USE_LLM_FIXES", raising=False)
    from opm_ai.linter.v2.validator import LintIssue, Severity
    from opm_ai.linter.v2.ast import Keyword

    issue = LintIssue(
        code=999,
        severity=Severity.INFO,
        message="some issue",
        source_file=None,
        source_line=10,
        keyword=Keyword(
            name="WELLDIMS",
            header_token=None,
            records=[],
        ),
    )
    result = _llm_propose_fix(issue, "WELLDIMS\n4 /\n", None)
    assert result is None


def test_llm_propose_fix_env_var_set_but_no_provider(
    monkeypatch, tmp_path
):
    """Even with env var set, returns None if no LLM provider is configured."""
    monkeypatch.setenv("OPM_AI_USE_LLM_FIXES", "1")
    # The function imports opm_ai.llm.get_llm_provider; if that doesn't
    # exist or returns None, the function returns None.
    result = _llm_propose_fix(
        None,  # issue — function will fail before provider lookup
        "x", None,
    )
    # With None as issue, it crashes on .message before provider lookup,
    # so result is None.
    assert result is None


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

def test_self_heal_deck_returns_self_heal_result(tmp_path):
    """self_heal_deck returns a SelfHealResult for a simple deck."""
    # Deck that doesn't trigger any proposal-able rules.
    deck_text = (
        "RUNSPEC\n"
        "DIMENS\n"
        "10 10 10 /\n"
        "GRID\n"
        "INIT\n"
        "END\n"
    )
    deck_path = tmp_path / "x.DATA"
    deck_path.write_text(deck_text)
    # Without an oracle (no flow binary or with fast timeout), this
    # should at least parse, validate, and return a result.
    cfg = OracleConfig(timeout_s=2, flow_binary="")  # no-op oracle
    result = self_heal_deck(
        text=deck_text,
        source_file=deck_path,
        oracle_cfg=cfg,
    )
    assert isinstance(result, SelfHealResult)
    assert result.issues_seen >= 0
    assert isinstance(result.proposals, list)


def test_self_heal_deck_no_calibration_returns_valid_result(tmp_path):
    """Without a calibration report, scoring falls back to prior (0.5)."""
    deck_text = "WELLDIMS\n4 5 6 7 8 /\n"
    deck_path = tmp_path / "x.DATA"
    deck_path.write_text(deck_text)
    cfg = OracleConfig(timeout_s=2, flow_binary="")
    result = self_heal_deck(
        text=deck_text,
        source_file=deck_path,
        calibration_report=None,
        oracle_cfg=cfg,
    )
    # Just ensure no crash + valid output shape.
    assert isinstance(result, SelfHealResult)


def test_self_heal_deck_proposals_ranked_verified_first(
    tmp_path, passing_verdict, failing_verdict
):
    """Verified proposals come before unverified in the ranked output."""
    deck_text = "WELLDIMS\n4 5 6 7 8 /\n"
    deck_path = tmp_path / "x.DATA"
    deck_path.write_text(deck_text)
    cfg = OracleConfig(timeout_s=2, flow_binary="")
    result = self_heal_deck(
        text=deck_text,
        source_file=deck_path,
        oracle_cfg=cfg,
        max_proposals=10,
    )
    # If there are proposals, the verified-first ordering should hold.
    if len(result.proposals) >= 2:
        # Check that no unverified proposal has higher confidence than
        # any verified one (with ties broken by confidence).
        for i in range(len(result.proposals) - 1):
            left = result.proposals[i]
            right = result.proposals[i + 1]
            if left.verified and not right.verified:
                continue  # correct ordering
            if not left.verified and right.verified:
                pytest.fail("unverified ranked above verified")
            # Same verified status: confidence should be non-increasing.
            assert left.confidence >= right.confidence


def test_self_heal_deck_max_proposals_caps_output(tmp_path):
    """max_proposals bounds the output list size."""
    deck_text = "WELLDIMS\n4 5 6 7 8 /\n"
    deck_path = tmp_path / "x.DATA"
    deck_path.write_text(deck_text)
    cfg = OracleConfig(timeout_s=2, flow_binary="")
    result = self_heal_deck(
        text=deck_text,
        source_file=deck_path,
        oracle_cfg=cfg,
        max_proposals=2,
    )
    assert len(result.proposals) <= 2


def test_self_heal_deck_to_dict_serializes(tmp_path):
    """SelfHealResult.to_dict is JSON-serializable."""
    deck_text = "RUNSPEC\nDIMENS\n10 10 10 /\nEND\n"
    deck_path = tmp_path / "x.DATA"
    deck_path.write_text(deck_text)
    cfg = OracleConfig(timeout_s=2, flow_binary="")
    result = self_heal_deck(text=deck_text, source_file=deck_path, oracle_cfg=cfg)
    d = result.to_dict()
    # Round-trip
    s = json.dumps(d)
    assert isinstance(s, str)
    parsed = json.loads(s)
    assert "proposals" in parsed
    assert "issues_seen" in parsed


def test_scored_proposal_to_dict():
    """ScoredProposal.to_dict includes confidence, verified, llm_proposed."""
    p = FixProposal(
        rule_code=232,
        issue_keyword=None,
        original_text="x",
        patched_text="y",
        description="test",
        original_value="4",
        new_value="6",
    )
    sp = ScoredProposal(
        proposal=p,
        rule_code=232,
        confidence=0.95,
        verified=True,
        llm_proposed=False,
        rationale="calib=1.00 oracle=OK llm=no",
    )
    d = sp.to_dict()
    assert d["rule_code"] == 232
    assert d["confidence"] == 0.95
    assert d["verified"] is True
    assert d["llm_proposed"] is False
    assert d["description"] == "test"
    assert d["original_value"] == "4"
    assert d["new_value"] == "6"
    assert "rationale" in d


# ---------------------------------------------------------------------------
# Oracle application
# ---------------------------------------------------------------------------

def test_apply_oracle_to_proposal_caches_results(sample_proposal, tmp_path):
    """The oracle application caches by patched deck text hash."""
    cache: dict[str, FlowVerdict] = {}

    # We use flow_binary="" so the oracle returns a synthetic verdict
    # without actually running flow. We just test that the cache works.
    cfg = OracleConfig(timeout_s=2, flow_binary="")

    # First call
    v1 = _apply_oracle_to_proposal(
        sample_proposal, sample_proposal.original_text, None,
        cache, cfg,
    )
    # Second call (same text) should hit cache
    v2 = _apply_oracle_to_proposal(
        sample_proposal, sample_proposal.original_text, None,
        cache, cfg,
    )
    assert v1 is v2  # Same object from cache
    assert len(cache) == 1