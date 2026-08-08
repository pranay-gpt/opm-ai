"""Build opm_ai/linter/keywords.json from the fixture decks.

Walks a tree of .DATA files, parses each via opm_ai.linter.deck.Deck, and
emits a JSON catalogue of every keyword observed, with per-section counts.

Usage:
    python scripts/build_keyword_catalogue.py
    python scripts/build_keyword_catalogue.py --fixtures-dir custom/path --output out.json
    python scripts/build_keyword_catalogue.py --dry-run   # walk + count, no write

The catalogue is committed to the repo so the linter doesn't need to rescan
on every install. Re-run this script when fixtures are added or removed.

Note: this script intentionally uses opm_ai.linter.deck.Deck rather than a
fresh regex. A naive ^([A-Z][A-Z0-9_]{1,7})$ scanner over-attributes
keywords to the previous section because banner headers like
'GRID    ================================' are not handled; Deck does
handle that correctly (word-boundary, case-insensitive, comment-stripping).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# Make opm_ai importable when the script is run directly from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from opm_ai.linter.deck import Deck, TokenType  # noqa: E402


# Same regex the linter uses for per-line keyword detection (rules/general.py:98).
# First char must be a letter; matches the ECLIPSE token subset the linter accepts.
_KEYWORD_LINE_RE = re.compile(
    r"^([A-Z][A-Z0-9_]*)\s*(?:--.*)?$",
    re.IGNORECASE,
)

# Tokens that look like keywords but aren't.
# Section headers are filtered out because the linter's Deck class treats them as
# boundaries, not payloads. END and ENDFIN are flag-only keywords.
_SKIP_TOKENS = frozenset(
    {"RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS", "SOLUTION", "SUMMARY",
     "SCHEDULE", "ENDFIN", "END"}
)


def _iter_keyword_lines(section_text: str) -> Iterable[tuple[str, int]]:
    """Yield (uppercased_keyword, line_index_in_section) for keyword lines.

    Skips blank lines, comments, and lines that are not a single keyword.
    Does NOT skip section headers - the caller is responsible for filtering.

    Phase 1 (linter-redesign): user-defined UDQ variables (FU_*, WU_*)
    are skipped here so they never enter the catalogue. They are valid
    by definition and recognised at lex time by `Deck._classify_token`;
    the catalogue should only contain real OPM Flow keywords.
    """
    for i, line in enumerate(section_text.split("\n"), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        match = _KEYWORD_LINE_RE.match(stripped)
        if not match:
            continue
        token = match.group(1).upper()
        if token in _SKIP_TOKENS:
            continue
        # Phase 1: filter user variables so catalogue size is bounded by
        # real keywords, not by user-variable vocabulary.
        if Deck._classify_token(token) is TokenType.USER_VARIABLE:
            continue
        yield token, i


def _rec_token_count(line: str) -> int:
    """Count tokens on the first record after the keyword, before '/'.

    Returns 0 if the line has no '/' (flag keyword) or consists only of the
    keyword. Strips trailing inline comments first.
    """
    no_comment = line.split("--", 1)[0].strip()
    # Cut at the terminator.
    if "/" in no_comment:
        no_comment = no_comment.split("/", 1)[0]
    parts = no_comment.split()
    # First token is the keyword itself; the rest are arguments.
    return max(0, len(parts) - 1)


def _first_record_tokens(keyword_line: str, all_lines: list[str], line_idx: int) -> tuple[int, str]:
    """Return (token_count, joined_record_string) for the first record of a keyword.

    `line_idx` is the 1-indexed line in `all_lines` where the keyword appears.
    Returns (0, keyword_line) if the keyword has no data (flag keyword).

    The walk mirrors the L001 rule's logic:
      - Stop at the first line containing '/'.
      - Stop at the next keyword line (a new keyword starts a new record;
        the previous keyword's record is implicitly terminated).
      - Skip blank lines and comments.
    """
    pieces = [keyword_line.rstrip()]
    # Walk forward starting AFTER the keyword line itself.
    for j in range(line_idx, len(all_lines)):
        line = all_lines[j]
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        # Is this a new keyword line? If so, the keyword's record ends here
        # (implicitly terminated by the next keyword).
        if _KEYWORD_LINE_RE.match(stripped):
            break
        pieces.append(line.rstrip())
        # Cut at the terminator on this line.
        no_comment = line.split("--", 1)[0]
        if "/" in no_comment:
            break

    joined = "\n".join(pieces)
    joined_no_comment = joined.split("--", 1)[0]
    if "/" in joined_no_comment:
        joined_no_comment = joined_no_comment.split("/", 1)[0]
    parts = joined_no_comment.split()
    token_count = max(0, len(parts) - 1)
    return token_count, joined.strip()


def _walk_deck(deck: Deck) -> dict[str, dict]:
    """Return per-keyword observation dict for a single Deck.

    Returns a dict keyed by uppercase keyword. Each entry accumulates
    sections_observed (dict of section -> distinct-deck count), record_count,
    and arg_shape samples.
    """
    per_keyword: dict[str, dict] = {}

    for section_name in deck.sections:
        section_text = deck.get_section(section_name)
        if not section_text:
            continue

        for token, line_idx in _iter_keyword_lines(section_text):
            entry = per_keyword.setdefault(
                token,
                {
                    "sections_observed": defaultdict(int),
                    "record_count": 0,
                    "first_token_counts": [],
                    "first_record_example": None,
                },
            )
            entry["sections_observed"][section_name] += 1
            entry["record_count"] += 1

            # Record the first record's arg shape (idempotent: only the first
            # occurrence we see per deck becomes the example).
            if entry["first_record_example"] is None:
                lines = section_text.split("\n")
                if line_idx - 1 < len(lines):
                    entry["first_record_example"] = lines[line_idx - 1].strip()
                    entry["first_token_counts"].append(
                        _rec_token_count(entry["first_record_example"])
                    )

    return per_keyword


def _decks_for_section(deck: Deck, section: str) -> list[str]:
    """Yield keyword-line tokens from a single section, uppercased."""
    text = deck.get_section(section)
    if not text:
        return []
    return [tok for tok, _ in _iter_keyword_lines(text)]


def build_catalog(fixtures_dir: Path) -> dict:
    """Walk fixtures_dir and return the catalogue dict (not yet JSON-serialised)."""
    # Two parallel accumulators:
    #   per_deck[i][keyword] = set of sections the keyword appeared in for deck i
    #   per_keyword[token] = accumulator dict (record_count, sections_observed
    #       as distinct-deck counts, arg_shape samples)
    per_deck_keyword_sections: list[dict[str, set]] = []
    per_keyword: dict[str, dict] = {}

    data_files = sorted(fixtures_dir.rglob("*.DATA"))
    deck_count = 0

    for path in data_files:
        try:
            deck = Deck(path)
        except Exception:
            # Skip unreadable / malformed files; the catalogue is best-effort.
            continue

        deck_count += 1
        deck_record: dict[str, set] = defaultdict(set)

        for section_name in deck.sections:
            section_text = deck.get_section(section_name)
            if not section_text:
                continue

            for token, line_idx in _iter_keyword_lines(section_text):
                deck_record[token].add(section_name)

                entry = per_keyword.setdefault(
                    token,
                    {
                        "sections_observed": defaultdict(int),
                        "record_count": 0,
                        "first_token_counts": [],
                        "first_record_example": None,
                    },
                )
                entry["sections_observed"][section_name] += 1
                entry["record_count"] += 1

                if entry["first_record_example"] is None:
                    lines = section_text.split("\n")
                    if line_idx - 1 < len(lines):
                        example = lines[line_idx - 1].strip()
                        entry["first_record_example"] = example[:200]
                        entry["first_token_counts"].append(
                            _rec_token_count(example)
                        )

        per_deck_keyword_sections.append(deck_record)

    # Convert per-deck sets into per-keyword "distinct decks" counts.
    # The per_keyword dict above already aggregates record_count across decks.
    # We need to also count distinct decks per keyword (per (keyword, section)).
    keyword_sections_distinct: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    keyword_deck_count: dict[str, int] = defaultdict(int)
    for deck_record in per_deck_keyword_sections:
        for token, sections in deck_record.items():
            keyword_deck_count[token] += 1
            for section in sections:
                keyword_sections_distinct[token][section] += 1

    # Build the final per-keyword payload.
    keywords_payload: dict[str, dict] = {}
    for token, entry in per_keyword.items():
        sections_observed = dict(entry["sections_observed"])
        # Override with distinct-deck counts (the spec asks for distinct decks
        # per section, not record occurrences).
        sections_observed = dict(keyword_sections_distinct.get(token, {}))
        token_counts = entry["first_token_counts"]
        arg_shape = {
            "min_tokens": min(token_counts) if token_counts else 0,
            "max_tokens": max(token_counts) if token_counts else 0,
            "example": entry["first_record_example"] or "",
        }
        keywords_payload[token] = {
            "sections_observed": sections_observed,
            "section_count": len(sections_observed),
            "deck_count": keyword_deck_count[token],
            "record_count": entry["record_count"],
            "first_token_count": (
                max(set(token_counts), key=token_counts.count)
                if token_counts
                else 0
            ),
            "arg_shape": arg_shape,
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(fixtures_dir),
        "deck_count": deck_count,
        "keyword_count": len(keywords_payload),
        "keywords": dict(
            sorted(keywords_payload.items(), key=lambda kv: (-kv[1]["deck_count"], kv[0]))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build opm_ai/linter/keywords.json from fixtures."
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=_REPO_ROOT / "tests" / "fixtures",
        help="Root directory to scan for .DATA files (default: tests/fixtures).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "opm_ai" / "linter" / "keywords.json",
        help="Output JSON path (default: opm_ai/linter/keywords.json).",
    )
    parser.add_argument(
        "--min-section-count",
        type=int,
        default=1,
        help="Skip keywords observed in fewer than N distinct decks (default: 1).",
    )
    parser.add_argument(
        "--include",
        type=str,
        default="*.DATA",
        help="Glob pattern for fixture files (default: *.DATA).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Per-deck progress on stderr.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk and count, write nothing.",
    )
    args = parser.parse_args()

    fixtures_dir: Path = args.fixtures_dir
    output: Path = args.output

    if not fixtures_dir.exists():
        print(f"error: fixtures directory not found: {fixtures_dir}", file=sys.stderr)
        return 2

    print(f"scanning {fixtures_dir} for {args.include}...", file=sys.stderr)

    # The default glob is *.DATA which rglob already does; only re-glob if the
    # user provided a custom --include that isn't the default.
    if args.include == "*.DATA":
        data_files = sorted(fixtures_dir.rglob("*.DATA"))
    else:
        data_files = sorted(fixtures_dir.rglob(args.include))

    print(f"found {len(data_files)} candidate files", file=sys.stderr)

    # Build by walking the directory directly (build_catalog uses rglob *.DATA
    # internally too; for --include we'll re-walk with the right pattern).
    per_deck_keyword_sections: list[dict[str, set]] = []
    per_keyword: dict[str, dict] = {}

    deck_count = 0
    for path in data_files:
        if args.verbose:
            print(f"  {path}", file=sys.stderr)
        try:
            deck = Deck(path)
        except Exception as exc:
            print(f"  skip {path}: {exc}", file=sys.stderr)
            continue

        deck_count += 1
        deck_record: dict[str, set] = defaultdict(set)

        for section_name in deck.sections:
            section_text = deck.get_section(section_name)
            if not section_text:
                continue

            section_lines = section_text.split("\n")
            for token, line_idx in _iter_keyword_lines(section_text):
                deck_record[token].add(section_name)

                entry = per_keyword.setdefault(
                    token,
                    {
                        "sections_observed": defaultdict(int),
                        "record_count": 0,
                        "first_token_counts": [],
                        "first_record_example": None,
                    },
                )
                entry["sections_observed"][section_name] += 1
                entry["record_count"] += 1

                if entry["first_record_example"] is None:
                    if line_idx - 1 < len(section_lines):
                        keyword_line = section_lines[line_idx - 1]
                        token_count, joined = _first_record_tokens(
                            keyword_line, section_lines, line_idx
                        )
                        entry["first_record_example"] = joined[:200]
                        entry["first_token_counts"].append(token_count)

        per_deck_keyword_sections.append(deck_record)

    keyword_sections_distinct: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    keyword_deck_count: dict[str, int] = defaultdict(int)
    for deck_record in per_deck_keyword_sections:
        for token, sections in deck_record.items():
            keyword_deck_count[token] += 1
            for section in sections:
                keyword_sections_distinct[token][section] += 1

    keywords_payload: dict[str, dict] = {}
    for token, entry in per_keyword.items():
        if keyword_deck_count[token] < args.min_section_count:
            continue
        sections_observed = dict(keyword_sections_distinct.get(token, {}))
        token_counts = entry["first_token_counts"]
        arg_shape = {
            "min_tokens": min(token_counts) if token_counts else 0,
            "max_tokens": max(token_counts) if token_counts else 0,
            "example": entry["first_record_example"] or "",
        }
        keywords_payload[token] = {
            "sections_observed": sections_observed,
            "section_count": len(sections_observed),
            "deck_count": keyword_deck_count[token],
            "record_count": entry["record_count"],
            "first_token_count": (
                max(set(token_counts), key=token_counts.count)
                if token_counts
                else 0
            ),
            "arg_shape": arg_shape,
        }

    catalog = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(fixtures_dir),
        "deck_count": deck_count,
        "keyword_count": len(keywords_payload),
        "keywords": dict(
            sorted(keywords_payload.items(), key=lambda kv: (-kv[1]["deck_count"], kv[0]))
        ),
    }

    print(
        f"deck_count={deck_count} keyword_count={len(keywords_payload)}",
        file=sys.stderr,
    )

    if args.dry_run:
        # Print a tiny summary to stdout for the staleness test.
        print(
            json.dumps(
                {
                    "deck_count": deck_count,
                    "keyword_count": len(keywords_payload),
                    "generated_at": catalog["generated_at"],
                }
            )
        )
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2, sort_keys=False))
    print(f"wrote {output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
