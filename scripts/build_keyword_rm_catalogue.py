"""Build opm_ai/linter/keywords_rm.json from the Eclipse Reference Manual HTML.

Walks tests/eclipse/ecl_rm/*.html and extracts per-keyword authoritative data:
- Section placement from the flagtable (ECLIPSE 100 column).
- Parameter item count from <ol><li> entries (used for `first_record_arg_count`).
- Per-parameter {name, brief} extracted from each <li> in the first <ol>.
- Free-text description from the first <p> after the flagtable.
- Title from <h1 class="keyword">.

The output is the AUTHORITATIVE schema. It is merged with the observational
fixture catalogue (keywords.json) to give the linter:
- Empirical acceptance (what Flow 2026.04 actually accepts in 730 fixtures).
- Authoritative schema (what the manual says the keyword means and where it
  lives).

Usage:
    python scripts/build_keyword_rm_catalogue.py
    python scripts/build_keyword_rm_catalogue.py --dry-run   # walk + count, no write

Source: Eclipse Reference Manual HTML at tests/eclipse/ecl_rm/ (2,174 files,
MIT-compatible CC-BY-4.0 per Eclipse documentation licence).

Honest limitation: the manual documents Schlumberger ECLIPSE 100/300; OPM
Flow 2026.04 implements a subset. The merged catalogue uses the manual for
schema (parameters, sections) and the fixtures for acceptance evidence.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Standard ECLIPSE sections in the order they appear in every flagtable.
# Hard-coded so the parser does not depend on the table's internal ordering.
SECTIONS = ("RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
            "SOLUTION", "SUMMARY", "SCHEDULE")

# Flagtable: a <table class="flagtable"> containing 2 header rows + 8 body rows.
# Each body row has 2 cells: [x-marker, section-name]. The x-marker for
# ECLIPSE 100 is literal "x" in column 0.
_FLAGTABLE_RE = re.compile(
    r'<table[^>]*class="flagtable"[^>]*>(.*?)</table>',
    re.DOTALL | re.IGNORECASE,
)
_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# <h1 class="keyword">KEYWORD</h1> at the top of each file.
_KEYWORD_H1_RE = re.compile(
    r'<h1[^>]*class="keyword"[^>]*>(.*?)</h1>',
    re.DOTALL | re.IGNORECASE,
)

# <ol>...</ol> containing parameter item descriptions.
_OL_RE = re.compile(r"<ol[^>]*>(.*?)</ol>", re.DOTALL | re.IGNORECASE)
_LI_RE = re.compile(r"<li[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
# First nested BLOCK element within a <li> — the parameter name ends here.
# Anchors (<a>), inline tags (<span>, <samp>, <strong>) are not block-level.
_NESTED_BLOCK_RE = re.compile(
    r"<(p|table|div|ul|ol|pre)\b",
    re.IGNORECASE,
)
# First <p>...</p> child — used as the parameter's brief description.
_FIRST_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
# Briefs are capped to keep the JSON file under ~2 MB.
_BRIEF_MAX = 140


def _strip(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    cleaned = _TAG_RE.sub(" ", html)
    cleaned = cleaned.replace("&nbsp;", " ")
    cleaned = cleaned.replace("&amp;", "&")
    cleaned = cleaned.replace("&lt;", "<")
    cleaned = cleaned.replace("&gt;", ">")
    cleaned = cleaned.replace("&quot;", '"')
    return _WS_RE.sub(" ", cleaned).strip()


def _parse_flagtable(html: str) -> list[str]:
    """Return the list of section names where ECLIPSE 100 supports this keyword.

    Returns an empty list if no flagtable is present (this is the case for
    section-header pages like RUNSPEC.html and GRID.html).
    """
    m = _FLAGTABLE_RE.search(html)
    if not m:
        return []
    rows = _ROW_RE.findall(m.group(1))
    sections: list[str] = []
    for row in rows[2:]:  # skip the two simulator-header rows
        cells = _CELL_RE.findall(row)
        if len(cells) < 2:
            continue
        x_marker = _strip(cells[0]).lower()
        section = _strip(cells[1]).upper()
        if x_marker == "x" and section in SECTIONS:
            sections.append(section)
    return sections


def _parse_keyword_name(html: str, filename: str) -> str:
    """Extract the canonical keyword name from the <h1 class='keyword'>."""
    m = _KEYWORD_H1_RE.search(html)
    if m:
        return _strip(m.group(1)).upper()
    # Fallback: filename without .html
    return filename.upper().removesuffix(".HTML")


def _parse_parameter_count(html: str) -> int:
    """Count <li> items in the first <ol> block.

    The ERM uses <ol> for parameter items; other <li> uses are rare in
    the manual's HTML. Returns 0 if no <ol> is present.
    """
    return len(_parse_parameters(html))


def _parse_parameters(html: str) -> list[dict]:
    """Extract {name, brief} per <li> in the first <ol> block.

    For each <li>:
    - name: text content before the first nested block element
      (<p>, <table>, <div>, <ul>, <ol>, <pre>); HTML tags stripped,
      whitespace collapsed. Empty names are skipped.
    - brief: text of the first <p> child, stripped and truncated to
      140 chars. Empty string if no first <p>.

    Returns an empty list if no <ol> is present.
    """
    m = _OL_RE.search(html)
    if not m:
        return []
    out: list[dict] = []
    for li_html in _LI_RE.findall(m.group(1)):
        bm = _NESTED_BLOCK_RE.search(li_html)
        name_html = li_html[: bm.start()] if bm else li_html
        name = _strip(name_html)
        if not name:
            continue
        pm = _FIRST_P_RE.search(li_html)
        brief = _strip(pm.group(1))[:_BRIEF_MAX] if pm else ""
        out.append({"name": name, "brief": brief})
    return out


def _parse_first_paragraph(html: str) -> str:
    """Pull the first <p>...</p> after the flagtable as a short description."""
    # Find the flagtable's end; search for <p> after that.
    m = _FLAGTABLE_RE.search(html)
    start = m.end() if m else 0
    p = re.search(r"<p[^>]*>(.*?)</p>", html[start:], re.DOTALL | re.IGNORECASE)
    if not p:
        return ""
    text = _strip(p.group(1))
    return text[:400]  # truncate for catalogue readability


def parse_keyword_html(path: Path) -> dict | None:
    """Parse one ERM HTML file into a keyword record, or None to skip.

    Skip rules:
    - Filename ends with `_Examples.html` (sub-page, not a keyword).
    - Filename ends with `_NOTES.html` (sub-page of a topical page).
    - Filename starts with a lowercase letter (topical index pages: a, b, c, d).
    - Keyword name from <h1> contains spaces or non-keyword characters
      (topical pages like "GRID NINE-POINT SCHEME").
    - Keyword name has trailing dash or underscore (sub-page references).
    - File has no flagtable (section header pages or topical pages).
    """
    name = path.name
    if name.endswith("_Examples.html") or name.endswith("_NOTES.html"):
        return None
    if not name.endswith(".html"):
        return None
    # Section-header pages (RUNSPEC.html, GRID.html, etc.) have no flagtable
    # and have <h1 class="keyword"> with the section name as a heading. We
    # still want them indexed as section pages, but their data is empty.
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    sections = _parse_flagtable(html)
    keyword_name = _parse_keyword_name(html, path.stem)
    parameters = _parse_parameters(html)

    # Sanity checks on the parsed name.
    if not keyword_name:
        return None
    if " " in keyword_name:
        return None
    if not keyword_name.replace("_", "").isalnum():
        return None
    if keyword_name.endswith(("-", "_")):
        return None
    # Alphabetic topical index pages: lowercase .html files with single-
    # letter names (a.html → "A", etc.) are index pages, not keywords.
    if len(keyword_name) == 1 and path.name == path.name.lower():
        return None

    record = {
        "name": keyword_name,
        "source_file": path.name,
        "sections_authoritative": sections,
        "section_count_authoritative": len(sections),
        "parameter_count_authoritative": len(parameters),
        "parameters": parameters,
        "parameter_names": [p["name"] for p in parameters],
        "description": _parse_first_paragraph(html),
    }
    return record


def walk_ecl_rm(root: Path) -> dict[str, dict]:
    """Walk `root` and parse every keyword HTML file. Skip _Examples.html."""
    out: dict[str, dict] = {}
    for path in sorted(root.glob("*.html")):
        record = parse_keyword_html(path)
        if record is None:
            continue
        # Only keep keyword-named records (uppercase starts, no underscore_Examples).
        if record["name"] and not record["name"].endswith("_EXAMPLES"):
            out[record["name"]] = record
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--erm-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "eclipse" / "ecl_rm",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "opm_ai" / "linter" / "keywords_rm.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="walk + count, write to stdout, do not write the JSON file",
    )
    args = parser.parse_args()

    if not args.erm_dir.is_dir():
        print(f"ERM dir missing: {args.erm_dir}", file=sys.stderr)
        return 1

    keywords = walk_ecl_rm(args.erm_dir)
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.erm_dir),
        "keyword_count": len(keywords),
        "keywords": keywords,
    }

    if args.dry_run:
        json.dump(
            {"keyword_count": summary["keyword_count"]},
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.output}: {summary['keyword_count']} keywords")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())