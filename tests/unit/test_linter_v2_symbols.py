"""Unit tests for the v2 symbol table.

Tests cover:
- SymbolTable dataclass construction
- WELSPECS extraction (well name, group, head, depth)
- GRUPTREE extraction (parent/child relationships)
- FIPNUM/EQLNUM/SATNUM/PVTNUM region collection
- SUMMARY variable classification (field/well/group/region)
- FUNVAR FU/WU/GU/CU kind detection
- UDQ DEFINE registration as rudq
- Cross-references built correctly across INCLUDEs
"""

from __future__ import annotations

from pathlib import Path

from opm_ai.linter.v2.parser import parse_file
from opm_ai.linter.v2.resolver import resolve_deck
from opm_ai.linter.v2.symbols import (
    FluidTableInfo,
    FuVarInfo,
    GroupInfo,
    RegionInfo,
    SummaryVarInfo,
    SymbolTable,
    WellInfo,
    build_symbol_table,
)


def test_symbol_table_empty_default():
    """SymbolTable() with no args has empty maps."""
    st = SymbolTable()
    assert st.wells == {}
    assert st.groups == {}
    assert st.regions == set()
    assert st.fluid_tables == []
    assert st.summary_vars == []
    assert st.fu_vars == {}
    assert st.well_count() == 0
    assert st.group_count() == 0
    assert st.fluid_table_count() == 0


def test_symbol_table_wellspecs_extracts_well():
    """WELSPECS records populate the wells map."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "WELSPECS 'W2' 'G2' 2 2 2.0 'WAT' /\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert "W1" in st.wells
    assert "W2" in st.wells
    w1 = st.wells["W1"]
    assert isinstance(w1, WellInfo)
    assert w1.name == "W1"
    assert w1.group == "G1"
    assert w1.head_i == 1
    assert w1.head_j == 1
    assert w1.ref_depth == 1.0


def test_symbol_table_wellspecs_default_ref_depth():
    """WELSPECS with 1* for ref_depth uses 0.0 (not crash)."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1* 'OIL' /\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert "W1" in st.wells
    assert st.wells["W1"].ref_depth == 0.0


def test_symbol_table_wellspecs_dedup_first_wins():
    """If WELSPECS repeats a well name, first definition wins."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "WELSPECS 'W1' 'G2' 2 2 2.0 'WAT' /\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert st.well_count() == 1
    assert st.wells["W1"].group == "G1"


def test_symbol_table_wellspecs_implicitly_declares_group():
    """WELSPECS referencing a group declares that group in the symbol table."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert "G1" in st.groups


def test_symbol_table_gruptree_relationships():
    """GRUPTREE records build parent/child relationships."""
    text = (
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "SCHEDULE\n"
        "WELSPECS 'W1' 'PROD' 1 1 1.0 'OIL' /\n"
        "GRUPTREE 'FIELD' 'PROD' 'INJE' /\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert "FIELD" in st.groups
    assert "PROD" in st.groups
    assert "INJE" in st.groups
    assert st.groups["FIELD"].children == ["PROD", "INJE"]
    assert st.groups["PROD"].parent == "FIELD"
    assert st.groups["INJE"].parent == "FIELD"


def test_symbol_table_fipnum_regions():
    """FIPNUM records populate the regions set."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "GRID\nFIPNUM\n 0 0 1 1\n 2 2 0 0 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert st.regions == {0, 1, 2}


def test_symbol_table_eqlnum_regions():
    """EQLNUM records also populate the regions set."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "GRID\nEQLNUM\n 0 0 1 1 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert st.regions == {0, 1}


def test_symbol_table_satnum_regions():
    """SATNUM records also populate the regions set."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "GRID\nSATNUM\n 1 1 1 1 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert st.regions == {1}


def test_symbol_table_swof_table_recorded():
    """SWOF records are recorded as fluid tables."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "PROPS\nSWOF\n 0 0 1 1 /\n 0 1 1 0 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert st.fluid_table_count("SWOF") == 2
    assert all(isinstance(t, FluidTableInfo) for t in st.fluid_tables)


def test_symbol_table_rock_table_recorded():
    """ROCK keyword records a single FluidTableInfo."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "PROPS\nROCK\n 1.0e-5 14.7 /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert st.fluid_table_count("ROCK") == 1


def test_symbol_table_summary_field_var():
    """SUMMARY 'FOPR' is recognized as a field variable."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "SUMMARY\nFOPR\n/\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert len(st.summary_vars) == 1
    sv = st.summary_vars[0]
    assert sv.name == "FOPR"
    assert sv.var_type == "field"


def test_symbol_table_summary_well_var():
    """SUMMARY 'WOPR:W1' is recognized as a well variable."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "SUMMARY\nWOPR:W1\n/\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    sv = st.summary_vars[0]
    assert sv.name == "WOPR:W1"
    assert sv.var_type == "well"
    assert sv.target == "W1"


def test_symbol_table_summary_group_var():
    """SUMMARY 'GOPR:G1' is recognized as a group variable."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "SUMMARY\nGOPR:G1\n/\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    sv = st.summary_vars[0]
    assert sv.var_type == "group"
    assert sv.target == "G1"


def test_symbol_table_fuvar_detected():
    """FUNVAR records populate the fu_vars map."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "SUMMARY\nFUNVAR\nFU_OIL_RATE WU_OIL_RATE GU_OIL_RATE /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert "FU_OIL_RATE" in st.fu_vars
    assert "WU_OIL_RATE" in st.fu_vars
    assert "GU_OIL_RATE" in st.fu_vars
    assert st.fu_vars["FU_OIL_RATE"].kind == "fu"
    assert st.fu_vars["WU_OIL_RATE"].kind == "wu"
    assert st.fu_vars["GU_OIL_RATE"].kind == "gu"


def test_symbol_table_udq_define_as_rudq():
    """UDQ DEFINE registers the UDQ name as rudq in fu_vars."""
    text = (
        "RUNSPEC\nDIMENS 2 2 2 /\n\n"
        "SCHEDULE\nUDQ\n DEFINE 'WU_TEST' WOPR 'W1' - WOPR 'W2' /\n\n"
        "END\n"
    )
    deck = parse_file(text)
    st = build_symbol_table(deck)
    assert "WU_TEST" in st.fu_vars
    assert st.fu_vars["WU_TEST"].kind == "rudq"


def test_symbol_table_includes_resolved(tmp_path):
    """Symbol table extracts wells from INCLUDE'd files."""
    main = tmp_path / "MAIN.DATA"
    main.write_text(
        "RUNSPEC\nDIMENS 3 3 3 /\n\n"
        "SCHEDULE\nWELSPECS 'W1' 'G1' 1 1 1.0 'OIL' /\n"
        "INCLUDE 'GRID.INC' /\n"
        "END\n"
    )
    (tmp_path / "GRID.INC").write_text(
        "GRID\nDX\n 27*100 /\n\n"
        "SCHEDULE\nWELSPECS 'W2' 'G2' 2 2 2.0 'WAT' /\n"
    )
    deck = parse_file(main.read_text(), source_file=main)
    cd = resolve_deck(deck)
    st = build_symbol_table(deck)
    # Both wells should be in the symbol table after resolution
    assert "W1" in st.wells
    assert "W2" in st.wells
    assert st.wells["W2"].group == "G2"


def test_symbol_table_dataclass_types():
    """WellInfo, GroupInfo, etc. are exported dataclasses."""
    from opm_ai.linter.v2.symbols import (
        FluidTableInfo,
        FuVarInfo,
        GroupInfo,
        RegionInfo,
        SummaryVarInfo,
        WellInfo,
    )
    assert WellInfo.__dataclass_fields__  # type: ignore
    assert GroupInfo.__dataclass_fields__  # type: ignore
    assert RegionInfo.__dataclass_fields__  # type: ignore
    assert FluidTableInfo.__dataclass_fields__  # type: ignore
    assert SummaryVarInfo.__dataclass_fields__  # type: ignore
    assert FuVarInfo.__dataclass_fields__  # type: ignore