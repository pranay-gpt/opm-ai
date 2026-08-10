"""Build the v2 fixture MANIFEST.yaml.

Walks tests/fixtures/, runs `flow --enable-dry-run=true` on every deck,
classifies each into one of 8 categories, and writes a YAML manifest
that the v2 linter and the integration test both consume.

The manifest is the single source of truth for "which decks must lint
clean" and "which decks are expected to fail Flow."

Output: opm_ai/linter/v2/fixtures/MANIFEST.yaml
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import yaml

from .classify import Classification, classify_deck
from .oracle import (
    FlowVerdict,
    OracleConfig,
    categorize_failure,
    find_flow,
    run_flow,
)

DEFAULT_FIXTURES_ROOT = Path("tests/fixtures")
DEFAULT_MANIFEST = Path("opm_ai/linter/v2/fixtures/MANIFEST.yaml")
DEFAULT_TIMEOUT_S = 30
DEFAULT_WORKERS = 4


def _find_decks(root: Path) -> list[Path]:
    """Find all .DATA files under root, recursively."""
    return sorted(root.rglob("*.DATA"))


def _verdict_to_dict(verdict: FlowVerdict) -> dict:
    """Convert a FlowVerdict to a JSON-serializable dict."""
    return {
        "exit_code": verdict.exit_code,
        "error_count": len(verdict.error_lines),
        "fatal_in_stdout": verdict.fatal_in_stdout,
        "timeout": verdict.timeout,
        "wallclock_ms": verdict.wallclock_ms,
        "first_error": verdict.error_lines[0] if verdict.error_lines else None,
        "failure_reason": verdict.failure_reason,
        "failure_category": (
            categorize_failure(verdict) if not verdict.passed else None
        ),
        "stdout_tail": verdict.stdout_tail,
    }


def _classify_to_dict(cls: Classification) -> dict:
    """Convert a Classification to a JSON-serializable dict."""
    return {
        "primary": cls.primary,
        "secondary": cls.secondary,
        "signals": cls.signals,
    }


def _classify_workers(
    decks: list[Path],
    config: OracleConfig,
    workers: int,
) -> dict[Path, tuple[Classification, FlowVerdict]]:
    """Classify and run Flow on every deck in parallel.

    Returns dict mapping path -> (Classification, FlowVerdict).
    """
    results: dict[Path, tuple[Classification, FlowVerdict]] = {}

    # We can't pickle lambdas easily; use a top-level function
    def task(deck: Path) -> tuple[Path, Classification, FlowVerdict]:
        cls = classify_deck(deck)
        try:
            verdict = run_flow(deck, config)
        except Exception as e:
            verdict = FlowVerdict(
                deck_path=deck,
                exit_code=-2,
                stderr=str(e),
                stdout_tail="",
                error_lines=[str(e)],
                fatal_in_stdout=False,
                wallclock_ms=0,
                timeout=False,
            )
        return deck, cls, verdict

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(task, d): d for d in decks}
        for fut in as_completed(futures):
            try:
                deck, cls, verdict = fut.result()
                results[deck] = (cls, verdict)
            except Exception as e:
                deck = futures[fut]
                results[deck] = (
                    Classification(primary="unknown", secondary=[], signals={}),
                    FlowVerdict(
                        deck_path=deck,
                        exit_code=-2,
                        stderr=str(e),
                        stdout_tail="",
                        error_lines=[str(e)],
                        fatal_in_stdout=False,
                        wallclock_ms=0,
                        timeout=False,
                    ),
                )
    return results


def build_manifest(
    fixtures_root: Path = DEFAULT_FIXTURES_ROOT,
    output: Path = DEFAULT_MANIFEST,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    workers: int = DEFAULT_WORKERS,
    flow_binary: str = "flow",
) -> dict:
    """Build the v2 fixture manifest.

    Args:
        fixtures_root: Directory to scan for .DATA files.
        output: Where to write MANIFEST.yaml.
        timeout_s: Per-deck Flow timeout.
        workers: Number of parallel workers.
        flow_binary: Path to flow binary.

    Returns:
        The manifest dict (also written to output).
    """
    if find_flow() is None:
        print(
            "WARNING: flow binary not on PATH; all verdicts will be "
            "oracle-error",
            file=sys.stderr,
        )

    t0 = time.monotonic()
    decks = _find_decks(fixtures_root)
    print(f"Found {len(decks)} decks under {fixtures_root}", file=sys.stderr)

    config = OracleConfig(flow_binary=flow_binary, timeout_s=timeout_s)
    results = _classify_workers(decks, config, workers)
    t1 = time.monotonic()
    print(
        f"Classified and ran Flow on {len(results)} decks in {t1 - t0:.1f}s",
        file=sys.stderr,
    )

    # Build manifest entries
    known_good: list[str] = []
    known_bad: list[str] = []
    entries: list[dict] = []

    for deck, (cls, verdict) in sorted(results.items()):
        rel = deck.relative_to(fixtures_root).as_posix()
        if verdict.passed:
            known_good.append(rel)
        else:
            known_bad.append(rel)
        entries.append(
            {
                "path": rel,
                "classification": _classify_to_dict(cls),
                "verdict": _verdict_to_dict(verdict),
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "flow_binary": flow_binary,
        "fixtures_root": str(fixtures_root),
        "summary": {
            "total": len(entries),
            "known_good": len(known_good),
            "known_bad": len(known_bad),
            "by_primary": {
                cat: sum(
                    1
                    for e in entries
                    if e["classification"]["primary"] == cat
                )
                for cat in (
                    "minimal",
                    "spe",
                    "include",
                    "edit",
                    "udq",
                    "repeat",
                    "region",
                    "action",
                )
            },
            "by_any_tag": {
                cat: sum(
                    1
                    for e in entries
                    if cat
                    in (
                        [e["classification"]["primary"]]
                        + e["classification"]["secondary"]
                    )
                )
                for cat in (
                    "minimal",
                    "spe",
                    "include",
                    "edit",
                    "udq",
                    "repeat",
                    "region",
                    "action",
                )
            },
        },
        "known_good": known_good,
        "known_bad": known_bad,
        "entries": entries,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False, default_flow_style=False)
    print(
        f"Wrote {output} "
        f"({manifest['summary']['known_good']} good, "
        f"{manifest['summary']['known_bad']} bad, "
        f"by_any_tag: {manifest['summary']['by_any_tag']})",
        file=sys.stderr,
    )

    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the v2 fixture MANIFEST.yaml"
    )
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=DEFAULT_FIXTURES_ROOT,
        help="Directory to scan for .DATA files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Output MANIFEST.yaml path",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help="Per-deck Flow timeout in seconds",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Number of parallel Flow workers",
    )
    parser.add_argument(
        "--flow",
        default="flow",
        help="Path to flow binary",
    )
    args = parser.parse_args(argv)

    build_manifest(
        fixtures_root=args.fixtures_root,
        output=args.output,
        timeout_s=args.timeout,
        workers=args.workers,
        flow_binary=args.flow,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
