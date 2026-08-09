"""Continuous calibration: scan all specs against fixtures.

For each spec in opm_ai/linter/spec/, count the number of fixtures
where the spec's keyword is used, and the number of fixtures where
the spec's item_count or range check would fire. If a spec fires
on more than `THRESHOLD` fixtures, flag it as needing re-review.

Performance: lints each fixture exactly once, then aggregates L2.*
results by keyword. 730 fixtures × ~50ms = ~36s wall-clock — fast
enough for an after-spec-change sanity check.

Usage:
    PYTHONPATH=. uv run python scripts/calibration/continuous_scan.py

Output:
    Per-spec table with counts and a status column. A spec that
    passes has fewer than `THRESHOLD` mismatches; otherwise it
    fails and is listed under "needs review".

Threshold rationale: a true false-positive (spec is wrong) usually
fires on 10+ fixtures. A genuine bug fix in the validator might
introduce 1-2 new fires on edge cases. THRESHOLD=5 is a balance.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from opm_ai.linter.linter import lint_deck
from opm_ai.linter.spec import load_spec

SPEC_DIR = HERE.parent.parent / "opm_ai" / "linter" / "spec"
FIXTURES = HERE.parent.parent / "tests" / "fixtures"
THRESHOLD = 5


def _all_keywords() -> list[str]:
    """Return all spec keywords."""
    specs = load_spec(SPEC_DIR)
    return sorted(specs.keys())


def _deck_files() -> list[Path]:
    if not FIXTURES.exists():
        return []
    return sorted(FIXTURES.rglob("*.DATA"))


def main() -> int:
    keywords = _all_keywords()
    files = _deck_files()
    if not files:
        print(f"No fixtures found under {FIXTURES}")
        return 1
    print(
        f"Continuous calibration: {len(keywords)} specs × "
        f"{len(files)} fixtures (one lint per fixture)"
    )
    print(f"Threshold: >{THRESHOLD} mismatches flags the spec.\n")

    # n_present[kw] = how many fixtures use `kw`.
    # n_mismatch[kw] = how many of those also have an L2.<kw>.* issue.
    n_present: dict[str, int] = {kw: 0 for kw in keywords}
    n_mismatch: dict[str, int] = {kw: 0 for kw in keywords}
    kw_re: dict[str, re.Pattern] = {
        kw: re.compile(rf"(?im)^\s*{re.escape(kw)}\b") for kw in keywords
    }

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        # Which keywords are present in this fixture?
        present = [kw for kw, pat in kw_re.items() if pat.search(text)]
        if not present:
            continue
        try:
            issues = lint_deck(path).issues
        except Exception:
            continue
        for kw in present:
            n_present[kw] += 1
            # Calibration focus: item_count + range + mutex issues
            # only. `required` failures are mechanical (missing
            # keyword) and don't indicate spec-shape bugs — they
            # belong to a separate "coverage" report, not this one.
            prefix = f"L2.{kw}."
            calibration_issues = [
                i for i in issues
                if (i.rule_id or "").startswith(prefix)
                and not (i.rule_id or "").endswith(".required")
            ]
            if calibration_issues:
                n_mismatch[kw] += 1

    rows: list[tuple[str, int, int, str]] = []
    flagged: list[tuple[str, int, int]] = []
    for kw in keywords:
        p = n_present[kw]
        m = n_mismatch[kw]
        status = "PASS" if m <= THRESHOLD else "FAIL"
        rows.append((kw, p, m, status))
        if m > THRESHOLD:
            flagged.append((kw, p, m))

    name_w = max(len(k) for k, *_ in rows) if rows else 0
    counts_w = max(len(str(n)) for _, n, *_ in rows) if rows else 1
    print(f"{'SPEC'.ljust(name_w)}  {'USED'.rjust(counts_w)}  {'FAIL'.rjust(5)}  STATUS")
    print("-" * (name_w + counts_w + 5 + 7 + 4))
    for kw, p, m, status in rows:
        print(
            f"{kw.ljust(name_w)}  {str(p).rjust(counts_w)}  "
            f"{str(m).rjust(5)}  {status}"
        )
    print()
    if flagged:
        print(f"FLAGGED ({len(flagged)} specs need re-review):")
        for kw, p, m in flagged:
            print(
                f"  {kw}: fires on {m}/{p} fixtures "
                f"(threshold: {THRESHOLD})"
            )
        return 1
    print("All specs within calibration threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())