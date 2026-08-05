"""Tests for L016: unknown_keyword rule."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from opm_ai.linter import lint_deck
from opm_ai.linter.rules.keywords import _get_catalogue, rule_L016_unknown_keyword

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _write_deck(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "TESTCASE.DATA"
    path.write_text(body)
    return path


def _l016_issues(deck_path: Path) -> list:
    result = lint_deck(deck_path)
    return [i for i in result.issues if i.rule_id == "L016"]


@pytest.mark.unit
def test_catalogue_loads_with_reasonable_size():
    """Smoke: the catalogue must load and have at least 1000 entries."""
    cat = _get_catalogue()
    assert len(cat) >= 1000


@pytest.mark.unit
def test_spe1_has_no_l016_issues():
    """SPE1 should be fully covered by the catalogue."""
    if not (FIXTURES / "spe1" / "SPE1CASE1.DATA").exists():
        pytest.skip("SPE1 fixture not present")
    issues = _l016_issues(FIXTURES / "spe1" / "SPE1CASE1.DATA")
    assert issues == [], (
        f"SPE1 produced L016 false positives: "
        f"{[(i.section, i.keyword, i.message) for i in issues]}"
    )


@pytest.mark.unit
def test_unknown_keyword_emits_warning_with_suggestion(tmp_path):
    """A typo'd keyword produces a WARNING with a 'did you mean' suggestion."""
    deck = _write_deck(tmp_path, """\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /

GRID
DX
  300*100.0 /
DY
  300*100.0 /
DZ
  300*20.0 /
PORO
  300*0.2 /
PERMX
  300*100.0 /

PROPS
SWOF
  0 0 1 0
  1 0 0 0 /

SOLUTION
PRESSURE
  300*4800 /
SWAT
  300*0.2 /
EQUIL
  8400 4800 8450 0 8300 0 1 0 1* /

SUMMARY
FOPR /

SCHEDULE
-- WELSPEC missing trailing S
WELSPEC
  'W1' 1 1 1* 'OIL' 1* 1* 'STD' /
COMPDAT
  'W1' 1 1 1 1 1* 1* 0.2 1* 0.0 1* 'Z' /
WCONPROD
  'W1' 'OPEN' 'ORAT' 2000.0 1* 1* 1* 50.0 1* 1* /
TSTEP
  30.0 /
END
""")
    issues = _l016_issues(deck)
    welspec_issues = [i for i in issues if i.keyword == "WELSPEC"]
    assert len(welspec_issues) == 1, (
        f"expected 1 L016 issue for WELSPEC, got {len(welspec_issues)}: "
        f"{[(i.section, i.message) for i in issues]}"
    )
    issue = welspec_issues[0]
    assert issue.severity == "WARNING"
    assert "WELSPECS" in issue.message, (
        f"suggestion missing: {issue.message!r}"
    )
    assert "did you mean" in issue.message


@pytest.mark.unit
def test_unknown_keyword_no_close_match(tmp_path):
    """A garbage token with no close match produces a warning without suggestion."""
    deck = _write_deck(tmp_path, """\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /

GRID
DX
  300*100.0 /
DY
  300*100.0 /
DZ
  300*20.0 /
PORO
  300*0.2 /
PERMX
  300*100.0 /

PROPS
SWOF
  0 0 1 0
  1 0 0 0 /

SOLUTION
PRESSURE
  300*4800 /
SWAT
  300*0.2 /
EQUIL
  8400 4800 8450 0 8300 1* /

SUMMARY
FOPR /

SCHEDULE
XYZABC
  'W1' 1 1 1* 'OIL' 1* 1* 'STD' /
COMPDAT
  'W1' 1 1 1 1 1* 1* 0.2 1* 0.0 1* 'Z' /
WCONPROD
  'W1' 'OPEN' 'ORAT' 2000.0 1* 1* 1* 50.0 1* 1* /
TSTEP
  30.0 /
END
""")
    issues = _l016_issues(deck)
    assert len(issues) >= 1, "expected at least one L016 issue for XYZABC"
    garbage = [i for i in issues if i.keyword == "XYZABC"]
    assert len(garbage) == 1
    assert "did you mean" not in garbage[0].message


@pytest.mark.unit
def test_unknown_keyword_does_not_block_lint(tmp_path):
    """Even with a typo, the lint still passes (WARNING severity)."""
    deck = _write_deck(tmp_path, """\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /
WELSPECS
  'W1' 1 1 1* 'OIL' 1* 1* 'STD' /
COMPDAT
  'W1' 1 1 1 1 1* 1* 0.2 1* 0.0 1* 'Z' /
WCONPROD
  'W1' 'OPEN' 'ORAT' 2000.0 1* 1* 1* 50.0 1* 1* /
TSTEP
  30.0 /
END
""")
    result = lint_deck(deck)
    # Errors only from L001 (WELSPECS missing terminator when not on a line by itself).
    # The L016 rule must not contribute to errors.
    # `.errors` is the wire-format list of error messages; the rich
    # issue list (with .rule_id) lives on `.error_issues` after the
    # dataclass-to-Pydantic unification in F4.1.
    l016_errors = [i for i in result.error_issues if i.rule_id == "L016"]
    assert l016_errors == [], (
        f"L016 should never emit ERROR severity: {l016_errors}"
    )


@pytest.mark.unit
def test_unknown_keyword_quoted_string_not_flagged(tmp_path):
    """A quoted string on a keyword line is not itself a keyword."""
    deck = _write_deck(tmp_path, """\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /
WELSPECS
  'W1' 1 1 1* 'OIL' 1* 1* 'STD' /
COMPDAT
  'W1' 1 1 1 1 1* 1* 0.2 1* 0.0 1* 'Z' /
WCONPROD
  'W1' 'OPEN' 'ORAT' 2000.0 1* 1* 1* 50.0 1* 1* /
TSTEP
  30.0 /
END
""")
    issues = _l016_issues(deck)
    # 'OIL' is a keyword but it's in the catalogue; quoted strings themselves
    # (e.g. 'OIL' with quotes) are not flagged because the regex excludes
    # tokens starting with a quote.
    quoted_issues = [i for i in issues if i.keyword and "'" in i.keyword]
    assert quoted_issues == [], (
        f"quoted strings should not be flagged: {quoted_issues}"
    )


@pytest.mark.unit
def test_unknown_keyword_lowercase_normalised(tmp_path):
    """Lowercase keyword forms (legal in Eclipse) are matched against the catalogue.

    The keyword extraction is case-insensitive (the regex uses re.IGNORECASE),
    and the catalogue has all keys uppercased, so a lowercase keyword like
    'wellspecs' should not be flagged.
    """
    deck = _write_deck(tmp_path, """\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /
WELSPECS
  'W1' 1 1 1* 'OIL' 1* 1* 'STD' /
COMPDAT
  'W1' 1 1 1 1 1* 1* 0.2 1* 0.0 1* 'Z' /
WCONPROD
  'W1' 'OPEN' 'ORAT' 2000.0 1* 1* 1* 50.0 1* 1* /
TSTEP
  30.0 /
END
""")
    issues = _l016_issues(deck)
    # No L016 issues on known keywords (lowercase or uppercase).
    real_keyword_issues = [
        i for i in issues
        if i.keyword and i.keyword.upper() in
        {"WELSPECS", "COMPDAT", "WCONPROD", "TSTEP", "DIMENS", "TITLE", "RUNSPEC"}
    ]
    assert real_keyword_issues == [], (
        f"known keywords should not be flagged: "
        f"{[(i.keyword, i.message) for i in real_keyword_issues]}"
    )


@pytest.mark.unit
def test_unknown_keyword_section_header_not_flagged(tmp_path):
    """Section headers (RUNSPEC, GRID, ...) are sections, not unknown keywords."""
    deck = _write_deck(tmp_path, """\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /

GRID
DX
  300*100.0 /
END
""")
    issues = _l016_issues(deck)
    section_issues = [
        i for i in issues
        if i.keyword and i.keyword.upper() in
        {"RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS", "SOLUTION", "SUMMARY", "SCHEDULE", "ENDFIN"}
    ]
    assert section_issues == [], (
        f"section headers should not be flagged: {section_issues}"
    )


@pytest.mark.slow
@pytest.mark.unit
def test_unknown_keyword_calibration_set():
    """Zero L016 issues across all 722 fixture decks.

    This is the 'by construction' guarantee: the catalogue is built from the
    fixture tree, so the rule should fire zero times on the same set. If it
    fires, the catalogue is stale or the rule's tokenisation disagrees with
    the generator's.
    """
    if not FIXTURES.exists():
        pytest.skip("fixtures dir not present")
    # The slow tag gates this off the fast feedback loop. It still runs the
    # first time it's hit within the session.
    data_files = sorted(FIXTURES.rglob("*.DATA"))
    hits = []
    for path in data_files:
        try:
            result = lint_deck(path)
        except Exception as exc:
            # Skip files that the parser can't read (malformed, weird encoding).
            continue
        for issue in result.issues:
            if issue.rule_id == "L016":
                hits.append((path, issue))
    assert hits == [], (
        f"L016 fired {len(hits)} times on the calibration set. "
        f"First 5: {[(p.name, i.section, i.keyword, i.message) for p, i in hits[:5]]}"
    )
