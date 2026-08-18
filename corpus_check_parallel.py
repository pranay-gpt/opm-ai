#!/usr/bin/env python3
"""Parallel corpus check for OPM AI linter v2.

Uses ProcessPoolExecutor to lint fixtures in parallel.
Runs on (cpu_count - 1) workers.
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple


# ---- Worker function (must be at module level for pickling) ----
def _lint_one(fixture_path: str) -> tuple[str, int, int, int, int, int, int]:
    """Lint a single fixture. Returns (path, total, l171, l160, l202, l170, l221)."""
    # Import inside worker so each process loads its own catalogue
    from opm_ai.linter import lint_deck_v2

    try:
        result = lint_deck_v2(Path(fixture_path))
        issues = result.issues
        total = len(issues)
        l171 = sum(1 for i in issues if i.code == 171)
        l160 = sum(1 for i in issues if i.code == 160)
        l202 = sum(1 for i in issues if i.code == 202)
        l170 = sum(1 for i in issues if i.code == 170)
        l221 = sum(1 for i in issues if i.code == 221)
        return (fixture_path, total, l171, l160, l202, l170, l221)
    except Exception as e:
        return (fixture_path, -1, 0, 0, 0, 0, 0)


class Stats(NamedTuple):
    fixtures: int = 0
    clean: int = 0
    total: int = 0
    l171: int = 0
    l160: int = 0
    l202: int = 0
    l170: int = 0
    l221: int = 0


def main() -> int:
    # Determine fixtures to process
    fixtures_dir = Path("tests/fixtures")
    all_fixtures = sorted(fixtures_dir.rglob("*.DATA"))

    # Test mode: only first 3 fixtures if TEST env var set
    if os.getenv("TEST") == "1":
        fixtures = all_fixtures[:3]
        print(f"TEST MODE: processing {len(fixtures)} fixtures")
    else:
        fixtures = all_fixtures
        print(f"Processing {len(fixtures)} fixtures")

    # Worker count: cpu_count - 1 (minimum 1)
    max_workers = max(1, os.cpu_count() - 1)
    print(f"Using {max_workers} workers (of {os.cpu_count()} CPUs)")

    stats = Stats()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        future_to_path = {
            executor.submit(_lint_one, str(f)): f for f in fixtures
        }

        # Collect results as they complete
        for future in as_completed(future_to_path):
            path, total, l171, l160, l202, l170, l221 = future.result()

            if total == -1:
                print(f"  ERROR: {path}")
                continue

            stats = Stats(
                fixtures=stats.fixtures + 1,
                clean=stats.clean + (1 if total == 0 else 0),
                total=stats.total + total,
                l171=stats.l171 + l171,
                l160=stats.l160 + l160,
                l202=stats.l202 + l202,
                l170=stats.l170 + l170,
                l221=stats.l221 + l221,
            )

            # Progress indicator
            if stats.fixtures % 50 == 0 or stats.fixtures == len(fixtures):
                print(f"  [{stats.fixtures}/{len(fixtures)}] clean={stats.clean} total={stats.total} L171={stats.l171} L160={stats.l160} L202={stats.l202} L170={stats.l170} L221={stats.l221}")

    # Final summary
    print()
    print("=" * 50)
    print(f"Total fixtures: {stats.fixtures}")
    print(f"Clean fixtures: {stats.clean}")
    print(f"Total issues: {stats.total}")
    print(f"L171 (unknown keyword): {stats.l171}")
    print(f"L160 (loose token): {stats.l160}")
    print(f"L202 (record length): {stats.l202}")
    print(f"L170 (wrong section): {stats.l170}")
    print(f"L221 (crossref warning): {stats.l221}")

    return 0


if __name__ == "__main__":
    sys.exit(main())