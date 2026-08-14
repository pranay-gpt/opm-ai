"""Unit tests for the v2 INCLUDE/IMPORT resolver.

Covers:
- Basic INCLUDE merging
- PATHS-alias substitution
- Cycle detection
- File-not-found errors
- IMPORT (binary file references, not parsed)
- Multi-record INCLUDE
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.linter.v2.parser import parse_file
from opm_ai.linter.v2.paths_aliases import PathsTable
from opm_ai.linter.v2.resolver import Resolver, resolve_deck


FIXTURES_ROOT = Path("opm_ai/linter/v2/fixtures/resolver")


# ---------------------------------------------------------------------------
# PATHS alias substitution
# ---------------------------------------------------------------------------


def test_paths_table_simple_definition():
    """Defining aliases and substituting them works."""
    tbl = PathsTable()
    tbl.define("$DATA", "/some/path")
    assert tbl.substitute("$DATA/file") == "/some/path/file"


def test_paths_table_nested_substitution():
    """$A = $B/x with $B = /y → $A resolves to /y/x."""
    tbl = PathsTable()
    tbl.define("$B", "/y")
    tbl.define("$A", "$B/x")
    assert tbl.substitute("$A") == "/y/x"


def test_paths_table_cycle_protection():
    """Cyclic alias graph: $A = $B, $B = $A → no infinite loop."""
    tbl = PathsTable()
    tbl.define("$A", "$B")
    tbl.define("$B", "$A")
    # Either termination is acceptable; we just don't infinite-loop.
    result = tbl.substitute("$A")
    assert "$A" in result or "$B" in result  # cycle preserved as literal


def test_paths_table_unknown_alias_preserved():
    """Unknown $ALIAS stays literal."""
    tbl = PathsTable()
    assert tbl.substitute("$UNKNOWN/x") == "$UNKNOWN/x"


# ---------------------------------------------------------------------------
# Resolver: basic
# ---------------------------------------------------------------------------


def test_resolver_basic_two_includes(tmp_path):
    """MAIN.DATA includes GRID.INC and PROPS.INC; keywords merge correctly."""
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nINCLUDE 'GRID.INC' /\n\n"
        "PROPS\nINCLUDE 'PROPS.INC' /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    (tmp_path / "GRID.INC").write_text(
        "DX\n  27*100 /\n"
    )
    (tmp_path / "PROPS.INC").write_text(
        "SWOF\n  0.0 0.0 1.0\n  1.0 1.0 0.0 /\n"
    )
    deck = parse_file(main.read_text(), source_file=main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert len(cd.includes) == 2
    # MAIN.DATA's own keywords are merged with included keywords
    # (the resolver mutates the AST to attach included keywords).
    # MAIN had 5 keywords originally (DIMENS, INCLUDE, INCLUDE,
    # WELSPECS, END); after resolution it has 7 (added DX from
    # GRID.INC and SWOF from PROPS.INC).
    assert cd.source_files[main.resolve()].keyword_count() == 7
    # Check merged AST: included keywords (DX, SWOF) are merged in
    grid = deck.section("GRID")
    assert grid is not None
    grid_kw_names = [k.name for k in grid.keywords]
    assert "DX" in grid_kw_names
    assert "INCLUDE" in grid_kw_names
    props = deck.section("PROPS")
    assert props is not None
    props_kw_names = [k.name for k in props.keywords]
    assert "SWOF" in props_kw_names


def test_resolver_includes_merge_into_correct_section():
    """An INCLUDE in PROPS puts the included keywords in PROPS."""
    main = tmp_path = Path("/tmp/__test_resolver_includes")
    main.mkdir(exist_ok=True)
    deck_path = main / "MAIN.DATA"
    deck_path.write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "PROPS\nINCLUDE 'PROPS.INC' /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    (main / "PROPS.INC").write_text(
        "ROCK\n  1.0e-5 0.3 /\n"
    )
    deck = parse_file(deck_path.read_text(), source_file=deck_path)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    props = deck.section("PROPS")
    kw_names = [k.name for k in props.keywords]
    assert "ROCK" in kw_names


# ---------------------------------------------------------------------------
# Resolver: cycles
# ---------------------------------------------------------------------------


def test_resolver_cycle_detected_no_infinite_loop(tmp_path):
    """A↔B cycle produces one error and stops recursion."""
    (tmp_path / "MAIN.DATA").write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nINCLUDE 'A.INC' /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    (tmp_path / "A.INC").write_text(
        "INCLUDE 'B.INC' /\nDX\n  27*100 /\n"
    )
    (tmp_path / "B.INC").write_text(
        "INCLUDE 'A.INC' /\nDY\n  27*100 /\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 1
    assert any("cycle" in e for e in cd.errors)


def test_resolver_self_reference_detected(tmp_path):
    """A file that includes itself is caught."""
    (tmp_path / "MAIN.DATA").write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nINCLUDE 'MAIN.DATA' /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 1
    assert any("cycle" in e for e in cd.errors)


# ---------------------------------------------------------------------------
# Resolver: missing files
# ---------------------------------------------------------------------------


def test_resolver_missing_file_records_error_with_line(tmp_path):
    """An INCLUDE pointing at a non-existent file records an error."""
    (tmp_path / "MAIN.DATA").write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nINCLUDE 'NONEXISTENT.INC' /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 1
    assert any("not found" in e for e in cd.errors)
    # The error message includes the line number
    assert any("MAIN.DATA:5" in e or "MAIN.DATA:6" in e for e in cd.errors)


# ---------------------------------------------------------------------------
# Resolver: PATHS substitution
# ---------------------------------------------------------------------------


def test_resolver_paths_substitution(tmp_path):
    """PATHS-alias substitution resolves correctly through INCLUDE."""
    (tmp_path / "MAIN.DATA").write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n"
        "PATHS\n  $DATA ./data/ /\n  $GRID $DATA/grid/ /\n/\n\n"
        "GRID\nINCLUDE '$GRID/GRID.INC' /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "grid").mkdir()
    (tmp_path / "data" / "grid" / "GRID.INC").write_text(
        "DX\n  27*100 /\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert len(cd.includes) == 1
    inc = cd.includes[0]
    assert inc.actual_file.exists()


def test_resolver_paths_table_populated(tmp_path):
    """PATHS keywords accumulate into a PathsTable (literal, unsubstituted)."""
    (tmp_path / "MAIN.DATA").write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n"
        "PATHS\n  $DATA /data/ /\n  $GRID $DATA/grid/ /\n/\n\n"
        "SCHEDULE\nEND\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert "$DATA" in cd.paths_table.entries
    assert "$GRID" in cd.paths_table.entries
    assert cd.paths_table.entries["$DATA"] == "/data/"
    # The table stores literal values; substitution happens at use-time.
    # $GRID's value references $DATA, which is what substitute() resolves.
    assert cd.paths_table.entries["$GRID"] == "$DATA/grid/"
    # Verify substitution works correctly:
    resolved = cd.paths_table.substitute("$GRID/foo")
    assert "data" in resolved
    assert "grid" in resolved


# ---------------------------------------------------------------------------
# Resolver: IMPORT (binary file references)
# ---------------------------------------------------------------------------


def test_resolver_import_records_path_without_parsing(tmp_path):
    """IMPORT records the file path but does not parse it."""
    (tmp_path / "MAIN.DATA").write_text(
        "GRID\nIMPORT 'GRID.GRDECL' /\n\n"
        "SCHEDULE\nEND\n"
    )
    (tmp_path / "GRID.GRDECL").write_text("BINARY GRID DATA")  # not a deck
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert len(cd.imports) == 1
    assert cd.imports[0].target_file == "GRID.GRDECL"
    assert cd.imports[0].actual_file.exists()


def test_resolver_import_missing_file_records_error(tmp_path):
    """IMPORT pointing at a missing file records an error."""
    (tmp_path / "MAIN.DATA").write_text(
        "GRID\nIMPORT 'NONEXISTENT.GRDECL' /\n\n"
        "SCHEDULE\nEND\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 1
    assert any("not found" in e for e in cd.errors)


# ---------------------------------------------------------------------------
# Resolver: edge cases
# ---------------------------------------------------------------------------


def test_resolver_no_includes_no_errors(tmp_path):
    """A deck without INCLUDE/IMPORT/PATHS still resolves cleanly."""
    (tmp_path / "MAIN.DATA").write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G' 1 1 1.0 'LIQ' /\nEND\n"
    )
    deck = parse_file((tmp_path / "MAIN.DATA").read_text(),
                      source_file=tmp_path / "MAIN.DATA")
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert cd.includes == []
    assert cd.imports == []


def test_resolver_deck_without_source_file_records_error():
    """A deck parsed from in-memory text (no source_file) records an error
    if it tries to resolve INCLUDEs."""
    deck = parse_file(
        "RUNSPEC\nINCLUDE 'whatever' /\nEND\n",
        source_file=None,
    )
    cd = resolve_deck(deck)
    # No source_file → resolver cannot determine INCLUDE base dir
    # but it should not crash. It records an error.
    assert cd.error_count() >= 1
    assert any("no source_file" in e for e in cd.errors)


# ---------------------------------------------------------------------------
# Synthetic fixtures (committed)
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_main():
    return FIXTURES_ROOT / "basic" / "MAIN.DATA"


@pytest.fixture
def cycle_main():
    return FIXTURES_ROOT / "cycle" / "MAIN.DATA"


@pytest.fixture
def missing_main():
    return FIXTURES_ROOT / "missing" / "MAIN.DATA"


@pytest.fixture
def paths_main():
    return FIXTURES_ROOT / "paths" / "MAIN.DATA"


def test_synthetic_basic_fixture(basic_main):
    """The basic synthetic fixture resolves without errors."""
    deck = parse_file(basic_main.read_text(), source_file=basic_main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert len(cd.includes) == 2


def test_synthetic_cycle_fixture(cycle_main):
    """The cycle fixture produces a single cycle error."""
    deck = parse_file(cycle_main.read_text(), source_file=cycle_main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 1
    assert any("cycle" in e for e in cd.errors)


def test_synthetic_missing_fixture(missing_main):
    """The missing fixture records a file-not-found error."""
    deck = parse_file(missing_main.read_text(), source_file=missing_main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 1
    assert any("not found" in e for e in cd.errors)


def test_synthetic_paths_fixture(paths_main):
    """The PATHS fixture resolves $DATA / $GRID aliases."""
    deck = parse_file(paths_main.read_text(), source_file=paths_main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    assert "$DATA" in cd.paths_table.entries
    assert "$GRID" in cd.paths_table.entries
    assert len(cd.includes) == 1


# ---------------------------------------------------------------------------
# Resolver: post-INCLUDE retag (L170 false-positive fix)
# ---------------------------------------------------------------------------


def test_retag_post_include_moves_keywords_to_includes_section(tmp_path):
    """Parent deck has RUNSPEC, then INCLUDE 'SCHED.INC', then
    SCHEDULE-only keywords. The parser tags them to RUNSPEC
    because no section header follows INCLUDE. The resolver's
    `_retag_post_include_keywords` moves them to SCHEDULE.

    Pattern from SPE5CASE1 (44 L170 false-positives before fix).
    """
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "INCLUDE\n  'SCHED.INC' /\n\n"
        "WCONPROD\n  'P1' 'OPEN' 'ORAT' 12000 4* 1000 /\n"
        "END\n"
    )
    (tmp_path / "SCHED.INC").write_text(
        "SCHEDULE\nWELSPECS 'P1' 'G' 1 1 1.0 'OIL' /\n"
    )
    deck = parse_file(main.read_text(), source_file=main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    # WCONPROD should now be in SCHEDULE, not RUNSPEC.
    schedule = deck.section("SCHEDULE")
    sched_names = [k.name for k in schedule.keywords]
    assert "WCONPROD" in sched_names
    runspec = deck.section("RUNSPEC")
    runspec_names = [k.name for k in runspec.keywords]
    assert "WCONPROD" not in runspec_names


def test_retag_does_not_move_preexisting_keywords(tmp_path):
    """Keywords before the INCLUDE stay in their original section."""
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "PROPS\nROCK 1.0e-5 0.3 /\n\n"
        "INCLUDE\n  'SCHED.INC' /\n\n"
        "END\n"
    )
    (tmp_path / "SCHED.INC").write_text("SCHEDULE\n/\n")
    deck = parse_file(main.read_text(), source_file=main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    props = deck.section("PROPS")
    props_names = [k.name for k in props.keywords]
    # DIMENS stays in RUNSPEC, ROCK stays in PROPS.
    assert "ROCK" in props_names
    assert "DIMENS" in [k.name for k in deck.section("RUNSPEC").keywords]


def test_retag_handles_multiple_includes(tmp_path):
    """Two INCLUDEs in RUNSPEC, each followed by post-INCLUDE keywords.
    Each should be retagged to its include's first section.
    """
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "INCLUDE 'SCHED1.INC' /\nWCONPROD 'P1' 'OPEN' 'ORAT' 12000 4* 1000 /\n\n"
        "INCLUDE 'SCHED2.INC' /\nWCONINJE 'I1' 'WAT' 'RATE' 1000 4* /\n\n"
        "END\n"
    )
    (tmp_path / "SCHED1.INC").write_text("SCHEDULE\n/\n")
    (tmp_path / "SCHED2.INC").write_text("SCHEDULE\n/\n")
    deck = parse_file(main.read_text(), source_file=main)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0
    # Both WCONPROD and WCONINJE should now be in SCHEDULE.
    all_kws_by_section: dict[str, list[str]] = {}
    for sec_name, sec in deck.sections.items():
        all_kws_by_section[sec_name.value] = [k.name for k in sec.keywords]
    sched_names = all_kws_by_section.get("SCHEDULE", [])
    assert "WCONPROD" in sched_names
    assert "WCONINJE" in sched_names
    # And not in RUNSPEC anymore.
    assert "WCONPROD" not in all_kws_by_section.get("RUNSPEC", [])
    assert "WCONINJE" not in all_kws_by_section.get("RUNSPEC", [])


def test_retag_does_not_move_into_earlier_section(tmp_path):
    """An INCLUDE that introduces an EARLIER section (shouldn't happen
    in well-formed decks, but) must not move post-INCLUDE keywords
    backwards. Verifies the cur_idx < target_idx guard.
    """
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        "SOLUTION\nPRESSURE 1 100 1 1 1 /\n\n"
        "INCLUDE 'RUN.INC' /\nWCONPROD 'P1' 'OPEN' 'ORAT' 12000 4* 1000 /\n\n"
        "END\n"
    )
    # Include introduces RUNSPEC (earlier than SOLUTION).
    (tmp_path / "RUN.INC").write_text("RUNSPEC\n/\n")
    deck = parse_file(main.read_text(), source_file=main)
    cd = resolve_deck(deck)
    # WCONPROD should stay in SOLUTION because we never demote.
    all_kws_by_section = {
        sec_name.value: [k.name for k in sec.keywords]
        for sec_name, sec in deck.sections.items()
    }
    sched_names = all_kws_by_section.get("SCHEDULE", [])
    sol_names = all_kws_by_section.get("SOLUTION", [])
    assert "WCONPROD" not in sched_names
    # WCONPROD stays in SOLUTION (where the parser put it; we don't
    # move it backwards into the include's earlier section).
    assert "WCONPROD" in sol_names