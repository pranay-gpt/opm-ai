"""Test deck parser and linter."""
import time
import pytest
from pathlib import Path
from opm_ai.linter.deck import Deck, TokenType
from opm_ai.linter.linter import lint_deck
from opm_ai.linter.rules.schedule import (
    get_schedule_index,
    _extract_well_names,
    _has_keyword,
    _is_producer,
    _is_injector,
)


def test_parse_spe1_deck(spe1_deck):
    """Parse SPE1 fixture and check structure."""
    deck_path = spe1_deck
    assert deck_path.exists()

    deck = Deck(deck_path)

    # Should have major sections
    assert len(deck.sections) > 0

    # Should have RUNSPEC
    runspec = deck.get_section("RUNSPEC")
    assert runspec is not None

    # Should have GRID
    grid = deck.get_section("GRID")
    assert grid is not None


def test_lint_spe1_deck(spe1_deck):
    """Lint SPE1 fixture.

    SPE1 is a reference deck for keyword completeness. After L002 was
    registered in the rule list (F6.1) and calibrated to accept PVDG as
    a dry-gas alternative to PVTG, SPE1 produces no errors: it has PVTG
    for GAS and DISGAS plus SWOF for OIL.
    """
    deck_path = spe1_deck

    result = lint_deck(deck_path)

    assert result is not None
    assert result.deck_path == str(deck_path)
    # SPE1 declares OIL/GAS/WATER/DISGAS and includes PVTG + SWOF, so
    # the L002 phase-mismatch rule has nothing to complain about.
    assert len(result.errors) == 0


def test_lint_sample_deck(tmp_path):
    """Lint a minimal sample deck."""
    # Phase 3 (linter-redesign): the L2 layer now flags missing
    # WELLDIMS as an ERROR (WELLDIMS is required per the spec). This
    # test exercises the bare-minimum-deck lint path, so we include
    # a valid WELLDIMS record. The L3 layer has always required
    # DIMENS (L015), so that stays.
    deck_content = """
RUNSPEC

DIMENS
  10 10 5 /

WELLDIMS
  5  2  1  9  0  0  0  0  0  0  0  0 /

METRIC

GRID

DX
  500*100 /

DY
  500*100 /

DZ
  500*10 /

TOPS
  500*3000 /

PORO
  500*0.2 /

PERMX
  500*100 /

PROPS

SCHEDULE
"""
    deck_file = tmp_path / "test.DATA"
    deck_file.write_text(deck_content)

    result = lint_deck(deck_file)

    assert result.passed
    assert len(result.errors) == 0


# --- ScheduleIndex (F10.1) -------------------------------------------------

def test_schedule_index_parses_spe1(spe1_deck):
    """ScheduleIndex builds once and exposes the keyword/record view the
    SCHEDULE rules need.

    Note: SPE1's WELSPECS block starts with a column-header comment
    (`-- Item #: ...`). The original regex-based parser stopped at
    that comment and produced an empty body, so the L007/L017/L018
    rules effectively became no-ops on real decks. The structured
    index preserves that quirk to keep the rule semantics intact
    (audit F10.1: "do not change rule semantics"). We assert that
    behaviour here so a future refactor that "fixes" it knows it is
    changing test contract, not just code."""
    deck = Deck(spe1_deck)
    idx = get_schedule_index(deck)
    assert idx is not None
    # The keyword is detected as present, but its body is empty
    # because of the column-comment quirk.
    assert "WELSPECS" in idx.present_keywords
    assert idx.keyword_records.get("WELSPECS") == []
    assert _extract_well_names(idx, "WELSPECS") == []

    # WCONPROD has the same property: header present, body empty.
    assert "WCONPROD" in idx.present_keywords
    assert idx.keyword_records.get("WCONPROD") == []


def test_schedule_index_cached_on_deck(spe1_deck):
    """The index is built once and reused for every rule call, so the
    second call returns the exact same object (the audit's whole point:
    avoid O(N*M) regex rescans)."""
    deck = Deck(spe1_deck)
    first = get_schedule_index(deck)
    second = get_schedule_index(deck)
    assert first is second


def test_schedule_index_phase_helpers_preserve_semantics(spe1_deck):
    """_is_producer / _is_injector preserve the original regex behaviour
    on the section text directly: the patterns look for `'NAME'.*?'OIL'`
    or `'NAME'.*?'GAS|WATER'` anywhere in SCHEDULE. This is the same
    behaviour the old code had; the helpers are not responsible for
    scoping to WELSPECS records — the L017/L018 rules do that by
    intersecting with the (now empty for decks with column comments)
    WELSPECS well list."""
    deck = Deck(spe1_deck)
    idx = get_schedule_index(deck)
    assert _has_keyword(idx, "WELSPECS")
    # PROD has OIL in the same WELSPECS record; the regex finds it.
    assert _is_producer(idx, "PROD") is True
    assert _is_injector(idx, "PROD") is False
    # INJ has GAS; the regex finds it.
    assert _is_producer(idx, "INJ") is False
    assert _is_injector(idx, "INJ") is True


def test_schedule_index_handles_simple_block_without_comments(tmp_path):
    """A WELSPECS block with no column comments parses into a record
    list — i.e. the parser is functional, the SPE1 case is just the
    quirk. The linter test deck in test_linter_negative.py is shaped
    this way and exercises the L017/L018 rules end-to-end."""
    deck = (
        "RUNSPEC\nDIMENS\n  10 10 3 /\nGRID\nDX\n  1000*1 /\n"
        "SCHEDULE\nWELSPECS\n  'PROD1' 1 1 1* 'OIL' 1* 1* 'STD' /\n/\n"
        "TSTEP\n  30.0 /\n"
    )
    p = tmp_path / "simple.DATA"
    p.write_text(deck)

    deck_obj = Deck(p)
    idx = get_schedule_index(deck_obj)
    assert idx is not None
    assert _extract_well_names(idx, "WELSPECS") == ["PROD1"]
    assert _is_producer(idx, "PROD1") is True
    assert _is_injector(idx, "PROD1") is False


@pytest.mark.slow
def test_schedule_index_handles_large_synthetic_deck(tmp_path):
    """A deck with thousands of schedule lines must still lint quickly
    because every rule queries the pre-built index rather than
    re-scanning the text. Skip-marked so it does not slow down the
    default unit run; CI on a quiet machine is the right home for it."""
    n_wells = 500
    body = ["WELSPECS", "-- header"]
    for i in range(n_wells):
        body.append(f"  'W{i:04d}' 1 1 1* 'OIL' 1* 1* 'STD' /")
    body.append("/")
    body.append("COMPDAT")
    for i in range(n_wells):
        body.append(f"  'W{i:04d}' 1 1 1 1 1* 1* 0.2 1* 0.0 1* 'Z' /")
    body.append("/")
    body.append("WCONPROD")
    for i in range(n_wells):
        body.append(f"  'W{i:04d}' 'OPEN' 'ORAT' 2000.0 1* 1* 1* 50.0 1* 1* /")
    body.append("/")
    body.append("TSTEP\n  30.0 /")
    schedule = "\n".join(body)

    deck = (
        "RUNSPEC\nDIMENS\n  10 10 3 /\nGRID\nDX\n  1000*1 /\n"
        "SCHEDULE\n" + schedule + "\n"
    )
    p = tmp_path / "big.DATA"
    p.write_text(deck)

    t0 = time.perf_counter()
    result = lint_deck(p)
    elapsed = time.perf_counter() - t0

    # The exact threshold is loose; the goal is regression detection,
    # not a tight SLA. If a refactor accidentally re-introduces a
    # quadratic loop, this test will go from ~1s to many seconds.
    assert elapsed < 10.0, f"lint of 500-well deck took {elapsed:.2f}s"
    assert result is not None


# --- Deck parse memoization (F10.2) ----------------------------------------

def test_lint_deck_caches_deck_parse(tmp_path, monkeypatch):
    """lint_deck must only construct one Deck per (path, mtime). The
    second call hits the cache; the third (after the file is rewritten)
    triggers a fresh parse because mtime changed."""
    import time
    from opm_ai.linter import linter as linter_mod

    deck = (
        "RUNSPEC\nDIMENS\n  10 10 3 /\nGRID\nDX\n  1000*1 /\n"
        "SCHEDULE\nTSTEP\n  30.0 /\n"
    )
    p = tmp_path / "cache_test.DATA"
    p.write_text(deck)

    linter_mod.clear_deck_cache()

    parse_count = {"n": 0}
    original_init = linter_mod.Deck.__init__

    def counting_init(self, path):
        parse_count["n"] += 1
        original_init(self, path)

    monkeypatch.setattr(linter_mod.Deck, "__init__", counting_init)

    # Two lint calls on the same file: only the first parses.
    lint_deck(p)
    lint_deck(p)
    assert parse_count["n"] == 1, (
        f"expected exactly 1 parse for repeated lint, got {parse_count['n']}"
    )

    # Rewriting the file bumps mtime, so the next lint must re-parse.
    # The tmp filesystem on most CI runners has ~50ms mtime
    # resolution, so a brief sleep guarantees the new mtime_ns.
    time.sleep(0.1)
    p.write_text(deck + "TSTEP\n  60.0 /\n")
    lint_deck(p)
    assert parse_count["n"] == 2, (
        f"expected a fresh parse after mtime change, got {parse_count['n']}"
    )


def test_lint_deck_cache_returns_same_instance(tmp_path):
    """The cache must return the *same* Deck object across calls, not
    just an equal one. The ScheduleIndex is memoised on the Deck
    instance, so handing out a fresh parse would silently double the
    index build cost."""
    from opm_ai.linter import linter as linter_mod

    p = tmp_path / "identity.DATA"
    p.write_text("RUNSPEC\nDIMENS\n  10 10 3 /\nGRID\nDX\n  1000*1 /\n")

    linter_mod.clear_deck_cache()
    a = linter_mod._get_deck(p)
    b = linter_mod._get_deck(p)
    assert a is b


# --- Model unification (F4.1) ---------------------------------------------

def test_lint_models_unified_with_api_schemas():
    """`opm_ai.api.schemas.LintIssue` and `LintResult` are the SAME
    classes as the ones in `opm_ai.linter.models`. Two definitions
    would re-introduce the conversion boilerplate the audit F4.1 set
    out to remove, and a divergence would silently re-introduce
    wire-format drift."""
    from opm_ai.api.schemas import LintIssue as ApiLintIssue
    from opm_ai.api.schemas import LintResult as ApiLintResult
    from opm_ai.linter.models import LintIssue as LinterLintIssue
    from opm_ai.linter.models import LintResult as LinterLintResult

    assert ApiLintIssue is LinterLintIssue, (
        "api.schemas.LintIssue must be the same class as "
        "linter.models.LintIssue (F4.1)"
    )
    assert ApiLintResult is LinterLintResult, (
        "api.schemas.LintResult must be the same class as "
        "linter.models.LintResult (F4.1)"
    )


def test_lint_result_errors_and_passed_are_derived():
    """`errors` and `passed` are auto-computed from `issues`, so a
    linter can build a LintResult with just the issues and the
    wire-format fields appear without a separate compute_fields()
    pass. This is the whole point of the Pydantic unification."""
    from opm_ai.linter.models import LintIssue, LintResult

    result = LintResult(
        deck_path="/tmp/x.DATA",
        issues=[
            LintIssue(severity="ERROR", section="SCHEDULE", keyword="WCONPROD",
                      line=10, message="Missing WCONPROD", rule_id="L017"),
            LintIssue(severity="WARNING", section="SCHEDULE", keyword="COMPDAT",
                      line=20, message="Minor issue"),
        ],
    )
    assert result.errors == ["Missing WCONPROD"]
    assert result.passed is False
    # error_issues gives the rich LintIssue list for consumers that
    # need rule_id / line / section.
    assert len(result.error_issues) == 1
    assert result.error_issues[0].rule_id == "L017"

    empty = LintResult(deck_path="/tmp/y.DATA", issues=[])
    assert empty.passed is True
    assert empty.errors == []



# ---------------------------------------------------------------------- #
# Phase 1 — Token classification (FU_*, WU_* user variables)             #
# See docs/personal/LINTER_REDESIGN_PLAN.md.                              #
# ---------------------------------------------------------------------- #

@pytest.mark.unit
@pytest.mark.parametrize("token,expected", [
    # User-defined variables (FU_*, WU_*) — OPM Flow UDQ convention.
    ("FU_WBHP", TokenType.USER_VARIABLE),
    ("FU_PAR14", TokenType.USER_VARIABLE),
    ("FU_NEWVEC", TokenType.USER_VARIABLE),
    ("WU_TEST", TokenType.USER_VARIABLE),
    ("WU_WBHP0", TokenType.USER_VARIABLE),
    # Lowercase input still classified (lex is case-insensitive).
    ("fu_wbhp", TokenType.USER_VARIABLE),
    ("wu_test", TokenType.USER_VARIABLE),
    # Real OPM keywords stay KEYWORD.
    ("WELLDIMS", TokenType.KEYWORD),
    ("WELSPECS", TokenType.KEYWORD),
    ("DIMENS", TokenType.KEYWORD),
    ("TABDIMS", TokenType.KEYWORD),
    ("TITLE", TokenType.KEYWORD),
    # Single letter still KEYWORD (matches regex; OPM doesn't have single-
    # letter keywords in practice but the lexer's job is structural).
    ("A", TokenType.KEYWORD),
    # Numeric / terminator / non-alpha → OTHER.
    ("123", TokenType.OTHER),
    ("+", TokenType.OTHER),
    ("/", TokenType.OTHER),
    ("", TokenType.OTHER),
    # Non-alphabetic first char is OTHER.
    ("1ABC", TokenType.OTHER),
])
def test_classify_token(token, expected):
    """Pure-function classification of deck tokens.

    Critical invariant for Phase 1: FU_/WU_ must be classified as
    USER_VARIABLE so L016 ignores them, but real keywords like WELLDIMS
    stay KEYWORD. Real typos (FU_ lowercase, etc.) still classify
    correctly because the function uppercases defensively.
    """
    assert Deck._classify_token(token) is expected


@pytest.mark.unit
def test_user_variable_prefixes_are_narrow():
    """Guard against pre-emptive prefix expansion.

    The user-variable prefix list must stay narrow: only prefixes
    actually observed in fixtures belong here. Pre-emptive expansion
    (TU_*, GI_*, WI_*, GU_*, AU_*) is exactly the brute-force pattern
    the LinkedIn critique named. If you find yourself wanting to add
    one, add a fixture demonstrating the need first.
    """
    from opm_ai.linter.deck import _USER_VARIABLE_PREFIXES
    assert _USER_VARIABLE_PREFIXES == ("FU_", "WU_"), (
        f"Unexpected prefixes: {_USER_VARIABLE_PREFIXES}. "
        "Phase 1 forbids pre-emptive expansion; add only when a "
        "real fixture demonstrates the need."
    )


@pytest.mark.unit
def test_fu_variable_not_flagged(tmp_path):
    """FU_*/WU_* tokens in any section never produce L016 issues.

    This is the headline Phase 1 fix. A deck containing FU_NEWVEC
    anywhere must lint clean of L016 issues for those tokens. We use
    a minimal but valid RUNSPEC/SUMMARY/SCHEDULE skeleton so the
    other rules' required-keyword fires don't drown out the test.
    """
    from opm_ai.linter.linter import lint_deck
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\
RUNSPEC
DIMENS
  10 10 3 /
TITLE
  FU_TEST_VAR /
FUNVAR
  FU_NEWVEC /
WELLDIMS
  1 1 1 1 /
SUMMARY
FU_NEWVEC
WU_USER_THING
ALL
/
""")
    issues = lint_deck(deck).issues
    l016 = [i for i in issues if i.rule_id == "L016"]
    fu_wu = [
        i for i in l016
        if i.keyword and i.keyword.startswith(("FU_", "WU_"))
    ]
    assert fu_wu == [], (
        f"FU_/WU_ tokens were flagged by L016: "
        f"{[(i.section, i.keyword, i.line) for i in fu_wu]}"
    )


@pytest.mark.unit
def test_typo_still_flagged(tmp_path):
    """WELSPECS typo WELSECS still produces L016 WARNING.

    Regression guard: Phase 1 must not widen acceptance. Real typos
    still produce a 'did you mean X?' suggestion.
    """
    from opm_ai.linter.linter import lint_deck
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("RUNSPEC\nWELSECS\n/\n")
    issues = lint_deck(deck).issues
    l016 = [i for i in issues if i.rule_id == "L016"]
    assert len(l016) >= 1
    assert l016[0].severity == "WARNING"
    assert "WELSPECS" in l016[0].message, (
        f"L016 message should suggest WELSPECS, got: {l016[0].message!r}"
    )


@pytest.mark.unit
def test_fu_variable_not_flagged_for_missing_terminator(tmp_path):
    """FU_* lines don't need a terminating '/' (Phase 1 fallout fix).

    L001 (terminator detection) used to flag FU_TEST_VAR\n as
    'missing terminating /' because it looks like a keyword. Phase 1
    classifies FU_* as USER_VARIABLE so L001 treats it as not-a-keyword.
    """
    from opm_ai.linter.linter import lint_deck
    deck = tmp_path / "TESTCASE.DATA"
    deck.write_text("""\
RUNSPEC
DIMENS
  10 10 3 /
TITLE
  test /
FU_FREE_LINE_NO_SLASH
WELLDIMS
  1 1 1 1 /
""")
    issues = lint_deck(deck).issues
    # No L001 issue should be for FU_FREE_LINE_NO_SLASH.
    bad = [
        i for i in issues
        if i.rule_id == "L001"
        and i.keyword == "FU_FREE_LINE_NO_SLASH"
    ]
    assert bad == [], (
        f"FU_ token falsely flagged as missing terminator: {bad}"
    )
