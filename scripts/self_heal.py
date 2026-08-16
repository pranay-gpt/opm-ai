#!/usr/bin/env python3
"""Run self-heal on a single .DATA deck and print ranked proposals.

Phase 6 user-facing CLI. Reads a deck, lints it, proposes fixes,
verifies via Flow, ranks by confidence, prints the result.

Usage:
    python scripts/self_heal.py path/to/deck.DATA
    python scripts/self_heal.py path/to/deck.DATA --calibration-report path/to/cal.json
    python scripts/self_heal.py path/to/deck.DATA --use-llm
    python scripts/self_heal.py path/to/deck.DATA --json

Output:
    Human-readable by default. --json prints the full SelfHealResult
    dict for programmatic consumption.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from opm_ai.linter.v2.self_heal import (
    load_calibration_report,
    self_heal_deck,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run agentic self-heal on an OPM Flow .DATA deck."
    )
    parser.add_argument("deck", type=Path, help="Path to the .DATA deck")
    parser.add_argument(
        "--calibration-report",
        type=Path,
        default=REPO_ROOT / "opm_ai/linter/v2/calibration_report.json",
        help="Path to calibration_report.json (for confidence weighting)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Ask LLM to propose fixes for issues without mechanical proposals "
             "(gated by OPM_AI_USE_LLM_FIXES=1 env var)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Per-Flow-invocation timeout (default: 60s)",
    )
    parser.add_argument(
        "--max-proposals",
        type=int,
        default=20,
        help="Max proposals to show (default: 20)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    args = parser.parse_args()

    if not args.deck.exists():
        print(f"ERROR: deck not found: {args.deck}", file=sys.stderr)
        return 2

    text = args.deck.read_text(errors="replace")
    calibration = load_calibration_report(args.calibration_report)

    result = self_heal_deck(
        text=text,
        source_file=args.deck,
        calibration_report=calibration,
        use_llm=args.use_llm,
        max_proposals=args.max_proposals,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        # Human-readable output
        print(f"\n=== Self-heal: {args.deck} ===\n")
        print(f"Issues seen:           {result.issues_seen}")
        print(f"Oracle before:         {'PASS' if result.oracle_passed_before else 'FAIL'}")
        print(f"Oracle after (best):   {'PASS' if result.oracle_passed_after_best else 'FAIL'}")
        print(f"\nProposals ({len(result.proposals)}):\n")
        for i, sp in enumerate(result.proposals, 1):
            tag = "✓" if sp.verified else "✗"
            llm = " (LLM)" if sp.llm_proposed else ""
            print(
                f"  {i:2d}. [{tag}] L{sp.rule_code}  "
                f"conf={sp.confidence:.2f}{llm}"
            )
            print(f"      {sp.proposal.description}")
            print(f"      rationale: {sp.rationale}")
        print()

    # Exit code: 0 if deck was already passing or we have a verified fix.
    if result.oracle_passed_before or any(sp.verified for sp in result.proposals):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())