"""Empirical fix-confidence calibration loop.

For each known_good fixture, run the v2 linter. For each ERROR/WARNING
issue, propose a fix (via `fix_proposals.py`) and apply it. Then run
`flow --enable-dry-run=true` on the original deck and the patched deck.
A proposal is "successful" if the patched deck still passes Flow's
acceptance check (and ideally passes more cleanly than the original).

The calibration report records per-rule success rates. These become
the empirical confidence scores that the agentic self-heal module
uses to weight proposals.

Design
------

- Single-fixture isolation: each (issue, fix) pair is tested
  independently. We do NOT chain multiple proposals per deck.
  Single-fix isolation is what the calibration report needs.

- Cache oracle results: he oracle is the slow step (flow binary
  startup is ~500ms). We cache by (deck_path, deck_text_hash) so
  multiple issue-attempts on the same original deck don't re-run
  flow for the same input.

- Parallelism: the runner supports a `workers` parameter to
  ThreadPoolExecutor over (issue, fix) attempts. The fixture-run
  step is fast (linter is milliseconds), so the bottleneck is the
  oracle invocations.

- Sample size: we pick a random sample of N fixtures to keep the
  loop bounded. The default is 50 fixtures, which gives ~50-100
  issue attempts per rule (depending on per-fixture issue count).
  This is enough for a directional signal, not enough for a hard
  threshold claim.

Output
------

The calibration report is a JSON file with the structure:

    {
      "metadata": {
        "timestamp": "...",
        "sample_size": 50,
        "linter_version": "2.0.0a0",
        "flow_binary": "/usr/bin/flow"
      },
      "summary": {
        "total_issues_seen": 100,
        "total_proposals_attempted": 60,
        "total_proposals_successful": 50,
        "calibration_rate": 0.83
      },
      "per_rule": {
        "232": {
          "issues_seen": 30,
          "proposals_attempted": 25,
          "proposals_successful": 23,
          "success_rate": 0.92
        },
        ...
      },
      "per_fixture": [
        {
          "path": "tests/fixtures/...",
          "issues_seen": 3,
          "attempts": [
            {
              "rule_code": 232,
              "original_value": "4",
              "new_value": "6",
              "oracle_passed_before": true,
              "oracle_passed_after": true,
              "oracle_after_wallclock_ms": 530,
              "successful": true,
              "description": "WELLDIMS line 7: MAXWELLS 4 -> 6"
            },
            ...
          ]
        },
        ...
      ]
    }

The report is the single source of truth for "how often does this
rule's proposal actually fix the issue?" Calibration rates feed
the self-heal agent's confidence scores.
"""

from __future__ import annotations

import hashlib
import json
import random
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .fix_proposals import FixProposal, propose_fix
from .oracle import (
    DEFAULT_TIMEOUT_S,
    FlowVerdict,
    OracleConfig,
    find_flow,
    run_flow,
)
from .parser import parse_file
from .resolver import resolve_deck
from .validator import LintIssue, validate


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AttemptResult:
    """The result of attempting one proposal on one issue.

    Attributes:
        rule_code: The LintIssue code (231, 232, 234, ...).
        original_value: The integer that was replaced.
        new_value: The integer that replaced it.
        oracle_passed_before: Did Flow accept the original deck?
        oracle_passed_after: Did Flow accept the patched deck?
        oracle_after_wallclock_ms: Flow wallclock for the patched deck.
        successful: True iff the proposal made the deck pass Flow (or
            kept it passing). Proposals that succeed are what the
            self-heal module should prefer.
        description: Human-readable summary of the change.
        skipped_reason: If proposal was skipped, why (e.g. "no
            proposal registered", "could not locate source line").
    """

    rule_code: int
    original_value: str
    new_value: str
    oracle_passed_before: bool
    oracle_passed_after: bool
    oracle_after_wallclock_ms: int
    successful: bool
    description: str
    skipped_reason: Optional[str] = None


@dataclass
class FixtureResult:
    """The calibration result for a single fixture.

    Attributes:
        path: The fixture path (relative to repo root).
        issues_seen: Total LintIssues produced by the linter.
        attempts: List of AttemptResult, one per fix attempt.
        oracle_passed_before: Did Flow accept the original deck?
    """

    path: str
    issues_seen: int
    attempts: list[AttemptResult] = field(default_factory=list)
    oracle_passed_before: bool = True


@dataclass
class CalibrationReport:
    """The full calibration report.

    Attributes:
        metadata: When/how the run was made.
        summary: Aggregate counts.
        per_rule: Maps rule code (str) to {issues_seen, ...}.
        per_fixture: List of FixtureResult.
    """

    metadata: dict
    summary: dict
    per_rule: dict
    per_fixture: list[FixtureResult]

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata,
            "summary": self.summary,
            "per_rule": self.per_rule,
            "per_fixture": [asdict(fr) for fr in self.per_fixture],
        }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _hash_deck(text: str) -> str:
    """SHA256 of deck text for cache keys."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _write_deck_to_tempfile(text: str, prefix: str = "cal_") -> Path:
    """Write `text` to a temp file with .DATA suffix, return the path.

    The temp file is created in the default temp dir and is *not*
    auto-cleaned; the caller is responsible for cleanup. (We use a
    persistent temp dir per calibration run so Flow can find the
    file with a relative path. The orchestrator cleans up after
    the run.)
    """
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".DATA", prefix=prefix, delete=False
    )
    f.write(text)
    f.close()
    return Path(f.name)


def _oracle_passed_cached(
    text: str,
    cache: dict[str, FlowVerdict],
    cache_dir: Path,
    oracle_cfg: OracleConfig,
    fixture_dir: Optional[Path] = None,
    leaked_files: Optional[list[Path]] = None,
) -> FlowVerdict:
    """Run the oracle on `text`, caching by content hash.

    Writes `text` to a stable temp file under `cache_dir/` (so the
    file path is deterministic per hash) and runs the oracle on
    that path. The temp file MUST be in the same directory as the
    original fixture so that INCLUDE directives (which are relative
    paths) resolve correctly. If `fixture_dir` is provided, the
    cached file is placed there; otherwise `cache_dir` is used.

    Any file created (in the fixture dir) is appended to
    `leaked_files` so the caller can clean up at exit.
    """
    key = _hash_deck(text)
    if key in cache:
        return cache[key]
    target_dir = fixture_dir if fixture_dir is not None else cache_dir
    deck_path = target_dir / f"{key}.DATA"
    if not deck_path.exists():
        deck_path.write_text(text)
        if leaked_files is not None:
            leaked_files.append(deck_path)
    # Set cwd to the fixture directory so relative INCLUDE paths work.
    cfg = OracleConfig(
        flow_binary=oracle_cfg.flow_binary,
        timeout_s=oracle_cfg.timeout_s,
        output_dir=oracle_cfg.output_dir,
        cwd=target_dir,
        dry_run_flag=oracle_cfg.dry_run_flag,
    )
    verdict = run_flow(deck_path, cfg)
    cache[key] = verdict
    return verdict


def _attempt_proposal(
    issue: LintIssue,
    proposal: FixProposal,
    original_text: str,
    before_verdict: FlowVerdict,
    cache: dict[str, FlowVerdict],
    cache_dir: Path,
    oracle_cfg: OracleConfig,
    fixture_dir: Path,
    leaked_files: list[Path],
) -> AttemptResult:
    """Apply a proposal and measure the patched deck's oracle verdict.

    Args:
        issue: The LintIssue that triggered the proposal.
        proposal: The FixProposal to apply.
        original_text: The original deck text (for context).
        before_verdict: Pre-computed Flow verdict on the original.
        cache: Cache keyed by deck text hash.
        cache_dir: Temp dir for deck files.
        oracle_cfg: OracleConfig.
        fixture_dir: Original fixture's directory (for INCLUDE resolution).
        leaked_files: Shared list of temp files to clean up at exit.

    Returns:
        AttemptResult with the proposal's success flag.
    """
    after_verdict = _oracle_passed_cached(
        proposal.patched_text, cache, cache_dir, oracle_cfg,
        fixture_dir, leaked_files,
    )
    # A successful proposal is one that:
    #   1. Maintains Flow acceptance (if the original passed) OR
    #   2. Achieves Flow acceptance (if the original failed).
    # In Phase 6 we focus on (1) since the corpus is known_good.
    successful = before_verdict.passed or after_verdict.passed in (
        True,
    )
    # More precisely: if the deck passed before, it must pass after.
    # If the deck failed before, the proposal might (or might not)
    # fix it — we count both directions but only flag (1) as
    # unambiguously successful.
    if before_verdict.passed:
        successful = after_verdict.passed
    else:
        # If the deck was already failing, the proposal's value is
        # uncertain. We don't count it as successful unless the
        # patched deck passes.
        successful = after_verdict.passed and not before_verdict.passed

    return AttemptResult(
        rule_code=issue.code,
        original_value=proposal.original_value,
        new_value=proposal.new_value,
        oracle_passed_before=before_verdict.passed,
        oracle_passed_after=after_verdict.passed,
        oracle_after_wallclock_ms=after_verdict.wallclock_ms,
        successful=successful,
        description=proposal.description,
    )


def _no_proposal_attempt(
    issue: LintIssue,
    reason: str,
    before_verdict: FlowVerdict,
) -> AttemptResult:
    """Record a skipped attempt (no proposal function or no fix)."""
    return AttemptResult(
        rule_code=issue.code,
        original_value="",
        new_value="",
        oracle_passed_before=before_verdict.passed,
        oracle_passed_after=before_verdict.passed,
        oracle_after_wallclock_ms=0,
        successful=False,
        description=f"no proposal for {issue.code}: {reason}",
        skipped_reason=reason,
    )


def calibrate_fixture(
    fixture_path: Path,
    cache: dict[str, FlowVerdict],
    cache_dir: Path,
    oracle_cfg: OracleConfig,
    leaked_files: list[Path],
) -> FixtureResult:
    """Calibrate a single fixture.

    Runs the v2 linter, attempts proposals for each issue, runs
    the oracle before and after, returns the FixtureResult.

    Args:
        fixture_path: Absolute path to the .DATA file.
        cache: Cache keyed by deck text hash.
        cache_dir: Temp dir for deck files.
        oracle_cfg: OracleConfig.
        leaked_files: Shared list of temp files to clean up at exit.

    Returns:
        FixtureResult with all attempts.
    """
    text = fixture_path.read_text(errors="replace")
    fixture_dir = fixture_path.parent
    before_verdict = _oracle_passed_cached(
        text, cache, cache_dir, oracle_cfg, fixture_dir, leaked_files
    )

    # Parse + lint
    try:
        deck = parse_file(text, source_file=fixture_path)
        resolve_deck(deck)
        result = validate(deck)
    except Exception as e:
        # If the linter crashes, record a fixture with no attempts.
        return FixtureResult(
            path=str(fixture_path),
            issues_seen=0,
            oracle_passed_before=before_verdict.passed,
            attempts=[
                AttemptResult(
                    rule_code=0,
                    original_value="",
                    new_value="",
                    oracle_passed_before=before_verdict.passed,
                    oracle_passed_after=before_verdict.passed,
                    oracle_after_wallclock_ms=0,
                    successful=False,
                    description=f"linter crashed: {type(e).__name__}: {e}",
                    skipped_reason="linter_crash",
                )
            ],
        )

    attempts: list[AttemptResult] = []
    for issue in result.issues:
        # We attempt proposals for ALL severities, not just WARNING/ERROR.
        # The proposal's success is independent of severity — what
        # matters is whether applying the fix makes the deck pass Flow.
        # The severity is a UI hint, not a calibration input.
        proposal = propose_fix(issue, text)
        if proposal is None:
            attempts.append(
                _no_proposal_attempt(issue, "no_proposal", before_verdict)
            )
            continue
        attempt = _attempt_proposal(
            issue, proposal, text, before_verdict, cache, cache_dir,
            oracle_cfg, fixture_dir, leaked_files,
        )
        attempts.append(attempt)

    return FixtureResult(
        path=str(fixture_path),
        issues_seen=len(result.issues),
        attempts=attempts,
        oracle_passed_before=before_verdict.passed,
    )


def calibrate(
    manifest_path: Path,
    output_path: Path,
    sample_size: int = 50,
    seed: int = 42,
    workers: int = 2,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    bias_paths: Optional[list[str]] = None,
) -> CalibrationReport:
    """Run calibration on a sample of known_good fixtures.

    Args:
        manifest_path: Path to MANIFEST.yaml.
        output_path: Path to write calibration_report.json.
        sample_size: Number of fixtures to sample.
        seed: Random seed for reproducible sampling.
        workers: Parallelism for calibration.
        timeout_s: Per-Flow-invocation timeout.
        bias_paths: Optional list of substring substrings; if any
            fixture's path contains any of these substrings, it is
            always included in the sample. Default is
            ['wtmult', 'actionx', 'gconinje', 'wconinje'] to
            ensure coverage of L231/L232/L234 ISSUES.

    Returns:
        CalibrationReport. Also written to output_path.
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    known_good = manifest["known_good"]
    fixtures_root = Path(manifest["fixtures_root"]).resolve()

    # Bias fixtures likely to trigger the rules we have proposals for.
    # Without this, the random sample rarely hits wtmult (which is the
    # only known_good fixture producing L234 INFO).
    if bias_paths is None:
        bias_paths = ["wtmult", "actionx", "gconinje", "wconinje"]
    biased = []
    seen = set()
    for rel in known_good:
        if any(b in rel.lower() for b in bias_paths):
            biased.append(rel)
            seen.add(rel)
    rest = [r for r in known_good if r not in seen]

    # Sample: take all biased + random sample of the rest
    rng = random.Random(seed)
    sample_size_remaining = max(0, sample_size - len(biased))
    sample_rest = rng.sample(rest, min(sample_size_remaining, len(rest)))
    sample = biased + sample_rest
    fixture_paths = [fixtures_root / rel for rel in sample]

    # Cache + temp dir for deck files
    cache: dict[str, FlowVerdict] = {}
    cache_dir = Path(tempfile.mkdtemp(prefix="calibration_"))
    oracle_cfg = OracleConfig(timeout_s=timeout_s)

    # Track temp files we create in fixture dirs so we can clean them up.
    leaked_files: list[Path] = []

    # Cleanup at exit
    import atexit
    def _cleanup():
        for f in leaked_files:
            try:
                f.unlink()
            except OSError:
                pass
    atexit.register(_cleanup)

    # Calibration loop
    fixture_results: list[FixtureResult] = []
    if workers <= 1:
        for fp in fixture_paths:
            fr = calibrate_fixture(fp, cache, cache_dir, oracle_cfg, leaked_files)
            fixture_results.append(fr)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    calibrate_fixture, fp, cache, cache_dir, oracle_cfg,
                    leaked_files,
                ): fp
                for fp in fixture_paths
            }
            for fut in as_completed(futures):
                try:
                    fr = fut.result()
                except Exception as e:
                    fp = futures[fut]
                    fr = FixtureResult(
                        path=str(fp),
                        issues_seen=0,
                        attempts=[
                            AttemptResult(
                                rule_code=0,
                                original_value="",
                                new_value="",
                                oracle_passed_before=False,
                                oracle_passed_after=False,
                                oracle_after_wallclock_ms=0,
                                successful=False,
                                description=f"calibration crashed: {type(e).__name__}: {e}",
                                skipped_reason="calibration_crash",
                            )
                        ],
                    )
                fixture_results.append(fr)

    # Aggregate
    per_rule: dict[str, dict] = {}
    for fr in fixture_results:
        for att in fr.attempts:
            if att.rule_code == 0:
                continue  # crashes
            key = str(att.rule_code)
            entry = per_rule.setdefault(
                key,
                {
                    "issues_seen": 0,
                    "proposals_attempted": 0,
                    "proposals_successful": 0,
                    "proposals_skipped": 0,
                    "success_rate": 0.0,
                },
            )
            entry["issues_seen"] += 1
            if att.skipped_reason:
                entry["proposals_skipped"] += 1
            else:
                entry["proposals_attempted"] += 1
                if att.successful:
                    entry["proposals_successful"] += 1

    for key, entry in per_rule.items():
        if entry["proposals_attempted"] > 0:
            entry["success_rate"] = round(
                entry["proposals_successful"] / entry["proposals_attempted"], 3
            )

    summary = {
        "total_fixtures": len(fixture_results),
        "total_issues_seen": sum(fr.issues_seen for fr in fixture_results),
        "total_proposals_attempted": sum(
            e["proposals_attempted"] for e in per_rule.values()
        ),
        "total_proposals_successful": sum(
            e["proposals_successful"] for e in per_rule.values()
        ),
        "total_proposals_skipped": sum(
            e["proposals_skipped"] for e in per_rule.values()
        ),
    }
    total_attempted = summary["total_proposals_attempted"]
    if total_attempted > 0:
        summary["calibration_rate"] = round(
            summary["total_proposals_successful"] / total_attempted, 3
        )
    else:
        summary["calibration_rate"] = 0.0

    report = CalibrationReport(
        metadata={
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "sample_size": sample_size,
            "actual_fixtures": len(fixture_results),
            "seed": seed,
            "workers": workers,
            "timeout_s": timeout_s,
            "linter_version": "2.0.0a0",
            "flow_binary": find_flow() or "not found",
        },
        summary=summary,
        per_rule=per_rule,
        per_fixture=fixture_results,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)

    return report


__all__ = [
    "AttemptResult",
    "CalibrationReport",
    "FixtureResult",
    "calibrate",
    "calibrate_fixture",
]
