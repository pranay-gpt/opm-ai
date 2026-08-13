#!/usr/bin/env python3
"""Run the v2 linter fix-confidence calibration loop.

Phase 6 deliverable. Samples known_good fixtures from the manifest,
runs the linter, applies proposed fixes, measures Flow acceptance on
the patched decks, and writes a calibration report (per-rule success
rates) to JSON.

Usage:
    python scripts/run_calibration.py
    python scripts/run_calibration.py --sample-size 100 --workers 4
    python scripts/run_calibration.py --output path/to/report.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script from the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from opm_ai.linter.v2.calibration import calibrate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the v2 linter fix-confidence calibration loop."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "opm_ai/linter/v2/fixtures/MANIFEST.yaml",
        help="Path to MANIFEST.yaml",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "opm_ai/linter/v2/calibration_report.json",
        help="Path to write calibration_report.json",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=50,
        help="Number of fixtures to sample (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Parallel workers for calibration (default: 2)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-Flow-invocation timeout in seconds (default: 30)",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"ERROR: manifest not found at {args.manifest}", file=sys.stderr)
        print("Run scripts/build_manifest.py first.", file=sys.stderr)
        return 2

    print(
        f"Calibrating with {args.sample_size} fixtures, "
        f"{args.workers} workers, {args.timeout}s timeout..."
    )
    report = calibrate(
        manifest_path=args.manifest,
        output_path=args.output,
        sample_size=args.sample_size,
        seed=args.seed,
        workers=args.workers,
        timeout_s=args.timeout,
    )

    # Print summary
    summary = report.summary
    print("\nCalibration summary:")
    print(f"  Fixtures calibrated: {summary['total_fixtures']}")
    print(f"  Issues seen:         {summary['total_issues_seen']}")
    print(f"  Proposals attempted: {summary['total_proposals_attempted']}")
    print(f"  Proposals successful: {summary['total_proposals_successful']}")
    print(f"  Proposals skipped:    {summary['total_proposals_skipped']}")
    print(f"  Calibration rate:    {summary['calibration_rate']:.1%}")

    print("\nPer-rule success rates:")
    for code, entry in sorted(report.per_rule.items()):
        print(
            f"  L{code}: {entry['proposals_successful']}/"
            f"{entry['proposals_attempted']} "
            f"({entry['success_rate']:.1%}) "
            f"[{entry['proposals_skipped']} skipped, "
            f"{entry['issues_seen']} issues seen]"
        )

    print(f"\nReport written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
