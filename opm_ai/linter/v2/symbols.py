"""Symbol table for the v2 linter.

Builds a structured representation of the deck's named entities —
wells, groups, regions, fluid tables, summary variables, function
variables (FU_*) — by walking the parsed CompositeDeck. The symbol
table is the input to cross-reference validation (L220) and
dimension-consistency validation (L230).

The parsing is "best-effort" — keys not present are silently absent
from the table. The validator reports cross-reference issues only
when a *referenced* symbol is missing; missing definitions alone
don't trigger errors unless a `requires` rule fires.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ast import Deck, Keyword, Record, Section
from .spec import SectionName
from .tokens import Token


@dataclass
class WellInfo:
    """A well, as declared by WELSPECS.

    Attributes:
        name: Well name (string, without quotes).
        group: Group name (string, without quotes).
        head_i: I index of the well head cell.
        head_j: J index of the well head cell.
        ref_depth: Reference depth for the well (typically BHP datum).
        source_file: File where WELSPECS for this well appears.
        source_line: Line of the WELSPECS record.
        defined_by: The Keyword node that defined this well (used for
            source attribution).
    """

    name: str
    group: str
    head_i: int
    head_j: int
    ref_depth: float
    source_file: Optional[Path]
    source_line: int
    defined_by: Optional[object] = None  # Keyword; typed as object to avoid circular


@dataclass
class GroupInfo:
    """A group, as declared by GRUPTREE or referenced by WELSPECS.

    Attributes:
        name: Group name.
        parent: Parent group (None for top-level groups).
        children: Names of child groups.
        source_file: File where the group first appears.
        source_line: Line number.
    """

    name: str
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)
    source_file: Optional[Path] = None
    source_line: int = 0


@dataclass
class RegionInfo:
    """A region, as declared by FIPNUM or EQLNUM.

    Attributes:
        region_num: The numeric region ID.
        count: How many cells have this region number.
        source_file: File where the region appears.
        source_line: Line number.
    """

    region_num: int
    count: int = 0
    source_file: Optional[Path] = None
    source_line: int = 0


@dataclass
class FluidTableInfo:
    """A fluid property table, declared by SWOF/SGOF/SOF2/PVDO/PVTO/etc.

    Attributes:
        table_type: One of 'SWOF', 'SGOF', 'SGFN', 'SWFN', 'SGFN',
            'SOF2', 'SOF3', 'PVDO', 'PVTO', 'PVTG', 'PVTW', 'ROCK',
            'DENSITY', etc.
        region: SATNUM / PVTNUM / EQLNUM region number, if specified
            (some decks put a single table outside the region loop).
        source_file: File where the table appears.
        source_line: Line number.
    """

    table_type: str
    region: Optional[int] = None
    source_file: Optional[Path] = None
    source_line: int = 0


@dataclass
class SummaryVarInfo:
    """A summary variable, declared by SUMMARY.

    Attributes:
        name: Variable name (e.g. 'FOPR', 'WOPR', 'WOPR:W1').
        var_type: 'field', 'well', 'group', 'region', 'connection',
            'fu'.
        target: Well/group name for well/group variables (None for
            field/fu).
        source_file: File where SUMMARY appears.
        source_line: Line number.
    """

    name: str
    var_type: str = "field"
    target: Optional[str] = None
    source_file: Optional[Path] = None
    source_line: int = 0


@dataclass
class FuVarInfo:
    """A function variable, declared by FUNVAR / PYACTION / UDQ DEFINE.

    Attributes:
        name: Variable name (e.g. 'FU_OIL_RATE', 'WUX').
        kind: One of 'fu', 'wu', 'gu', 'cu', 'au', 'rudq'.
        source_file: File where the FU_VAR was declared.
        source_line: Line number.
    """

    name: str
    kind: str = "fu"
    source_file: Optional[Path] = None
    source_line: int = 0


# Tables that participate in the SATNUM dimension loop.
_SAT_TABLES = frozenset({"SWOF", "SGOF", "SLGOF", "SGFN", "SWFN", "SOF2", "SOF3", "SNFN"})
# Tables that participate in the PVTNUM dimension loop.
_PVT_TABLES = frozenset({"PVDO", "PVTO", "PVTG", "PVTW", "PVDG"})


def build_symbol_table(deck: Deck) -> "SymbolTable":
    """Walk the deck and build a SymbolTable from all known entities."""
    st = SymbolTable()

    # Pass 1: declare wells, groups, regions, tables, summary vars, FU vars
    for section in deck.sections.values():
        for kw in section.keywords:
            if kw.spec is None:
                continue
            sym = _extract_symbol(kw)
            if sym is not None:
                sym(st)
        # The SUMMARY section is a section marker, not a keyword, so
        # we extract summary vars from every keyword in the SUMMARY
        # section regardless of whether SUMMARY itself appears as a kw.
        if section.name == SectionName.SUMMARY:
            _harvest_summary_section(section, st)

    # Pass 2: cross-references (use the just-built tables)
    # (reserved for future expansion; currently the table is fully
    # built in pass 1.)

    return st


@dataclass
class SymbolTable:
    """The composite deck's symbol table.

    Attributes:
        wells: Map of well name → WellInfo.
        groups: Map of group name → GroupInfo.
        regions: Set of region numbers seen (FIPNUM/EQLNUM/SATNUM/PVTNUM).
        fluid_tables: List of FluidTableInfo (in order).
        summary_vars: List of SummaryVarInfo (in order).
        fu_vars: Map of FU/WU/GU/etc. name → FuVarInfo.
    """

    wells: dict[str, WellInfo] = field(default_factory=dict)
    groups: dict[str, GroupInfo] = field(default_factory=dict)
    regions: set[int] = field(default_factory=set)
    fluid_tables: list[FluidTableInfo] = field(default_factory=list)
    summary_vars: list[SummaryVarInfo] = field(default_factory=list)
    fu_vars: dict[str, FuVarInfo] = field(default_factory=dict)

    def well_count(self) -> int:
        return len(self.wells)

    def group_count(self) -> int:
        return len(self.groups)

    def fluid_table_count(self, table_type: str | None = None) -> int:
        if table_type is None:
            return len(self.fluid_tables)
        return sum(1 for t in self.fluid_tables if t.table_type == table_type)


def _extract_symbol(kw: Keyword):
    """Return a function that adds this keyword's symbols to a table.

    Returns None for keywords that don't contribute to the symbol
    table (most of them).
    """
    name = kw.name
    if name == "WELSPECS":
        return _extract_wellspecs(kw)
    if name == "GRUPTREE":
        return _extract_gruptree(kw)
    if name in {"FIPNUM", "EQLNUM", "SATNUM", "PVTNUM", "ROCKNUM"}:
        return _extract_regions(kw, name)
    if name in _SAT_TABLES or name in _PVT_TABLES:
        return _extract_fluid_table(kw, name)
    if name in {"ROCK", "DENSITY"}:
        return _extract_simple_table(kw, name)
    if name == "SUMMARY":
        return _extract_summary(kw)
    if name in {"FUNVAR", "FUNFLT"}:
        return _extract_fuvar(kw)
    if name == "UDQ" and kw.records:
        return _extract_udq(kw)
    return None


def _token_to_str(tok: Token) -> str:
    """Convert a token to its string content (strip quotes for STRING)."""
    return tok.text


def _tokens_to_ints(items: list[Token]) -> list[int]:
    """Convert a list of tokens to ints, skipping non-numeric."""
    out: list[int] = []
    for t in items:
        try:
            out.append(int(t.text))
        except (ValueError, TypeError):
            continue
    return out


def _extract_wellspecs(kw: Keyword):
    """Build an add-wells-to-table function from WELSPECS records."""
    if not kw.records:
        return None
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None
    line = kw.header_token.line

    def add(st: SymbolTable) -> None:
        for rec in kw.records:
            if len(rec.items) < 6:
                continue
            name = _token_to_str(rec.items[0])
            group = _token_to_str(rec.items[1])
            try:
                head_i = int(rec.items[2].text)
                head_j = int(rec.items[3].text)
                ref_depth_tok = rec.items[4]
                # DEFAULT_N_STAR / REPEAT_N_VALUE → use 0 as default
                if ref_depth_tok.kind.name in ("DEFAULT_N_STAR", "REPEAT_N_VALUE"):
                    ref_depth = float(ref_depth_tok.text) if ref_depth_tok.text else 0.0
                else:
                    ref_depth = float(ref_depth_tok.text)
            except (ValueError, IndexError):
                continue
            if name in st.wells:
                continue  # first WELSPECS wins
            st.wells[name] = WellInfo(
                name=name,
                group=group,
                head_i=head_i,
                head_j=head_j,
                ref_depth=ref_depth,
                source_file=src,
                source_line=rec.line,
                defined_by=kw,
            )
            # Also add the group (WELSPECS implicitly declares it)
            if group and group not in st.groups:
                st.groups[group] = GroupInfo(
                    name=group,
                    source_file=src,
                    source_line=rec.line,
                )
            elif group:
                # Update children if this is a nested WELSPECS
                pass

    return add


def _extract_gruptree(kw: Keyword):
    """Build an add-groups-to-table function from GRUPTREE records.

    GRUPTREE syntax:  'PARENT' 'CHILD1'  'CHILD2'  'CHILD3'  ...  /
    The first token is the parent group; subsequent tokens are children.
    """
    if not kw.records:
        return None
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None
    line = kw.header_token.line

    def add(st: SymbolTable) -> None:
        for rec in kw.records:
            if len(rec.items) < 2:
                continue
            parent = _token_to_str(rec.items[0])
            if parent not in st.groups:
                st.groups[parent] = GroupInfo(
                    name=parent,
                    source_file=src,
                    source_line=rec.line,
                )
            parent_info = st.groups[parent]
            for child_tok in rec.items[1:]:
                child = _token_to_str(child_tok)
                if child not in st.groups:
                    st.groups[child] = GroupInfo(
                        name=child,
                        parent=parent,
                        source_file=src,
                        source_line=rec.line,
                    )
                else:
                    existing = st.groups[child]
                    if existing.parent is None and parent:
                        existing.parent = parent
                if child not in parent_info.children:
                    parent_info.children.append(child)

    return add


def _extract_regions(kw: Keyword, kind: str):
    """Build an add-regions-to-table function from FIPNUM/EQLNUM/etc."""
    if not kw.records:
        return None
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None
    line = kw.header_token.line

    def add(st: SymbolTable) -> None:
        # FIPNUM can be either list-kind (one record per cell) or array-kind.
        # For dimension tracking we just collect the unique region numbers.
        regions_seen: set[int] = set()
        for rec in kw.records:
            ints = _tokens_to_ints(rec.items)
            for n in ints:
                if n not in st.regions:
                    regions_seen.add(n)
        st.regions.update(regions_seen)

    return add


def _extract_fluid_table(kw: Keyword, table_type: str):
    """Build an add-fluid-table function for SWOF/SGOF/PVDO/etc."""
    if not kw.records:
        return None
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None
    line = kw.header_token.line

    def add(st: SymbolTable) -> None:
        # SATNUM/PVTNUM-prefixed tables: each record's first value is the
        # region number. Some decks put all regions in one record.
        for rec in kw.records:
            region = None
            if rec.items:
                try:
                    region = int(rec.items[0].text)
                except ValueError:
                    region = None
            st.fluid_tables.append(
                FluidTableInfo(
                    table_type=table_type,
                    region=region,
                    source_file=src,
                    source_line=rec.line,
                )
            )

    return add


def _extract_simple_table(kw: Keyword, table_type: str):
    """Build an add-table function for ROCK/DENSITY (one per deck)."""
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None

    def add(st: SymbolTable) -> None:
        st.fluid_tables.append(
            FluidTableInfo(
                table_type=table_type,
                region=None,
                source_file=src,
                source_line=kw.header_token.line,
            )
        )

    return add


def _harvest_summary_section(section, st: SymbolTable) -> None:
    """Extract SUMMARY variables from every keyword in the SUMMARY section.

    In Eclipse, SUMMARY is a section marker; the actual variables are
    individual keywords (FOPR, WOPR, GOPR, ROPR, COPR, FU_*, etc.) that
    appear in the section.

    Variable names can also include a `:target` suffix (e.g. WOPR:W1)
    to indicate a per-well or per-group query. The tokenizer treats
    these as a single UNKNOWN token, so we special-case them here.
    """
    for kw in section.keywords:
        if not kw.name or kw.name in ("SUMMARY", "END"):
            continue
        name = kw.name
        target = None
        # If the keyword name contains `:` (WOPR:W1, GOPR:G1, ROPR:R1),
        # split into base + target.
        if ":" in name:
            base, tgt = name.split(":", 1)
            target = tgt
            base = base.upper()
            var_type = {
                "W": "well", "G": "group", "R": "region",
                "C": "connection", "F": "field",
            }.get(base[0] if base else "F", "field")
            # The keyword spec field is None for these synthesized names.
            st.summary_vars.append(
                SummaryVarInfo(
                    name=name,
                    var_type=var_type,
                    target=target,
                    source_file=Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None,
                    source_line=kw.header_token.line,
                )
            )
            continue
        var_type = "field"
        if any(name.startswith(p) for p in ("FU_", "WU_", "GU_", "CU_", "AU_")):
            var_type = "fu"
        elif len(name) >= 4 and name[0] in ("F", "W", "G", "R", "C"):
            var_type = {
                "F": "field", "W": "well", "G": "group",
                "R": "region", "C": "connection",
            }[name[0]]
        st.summary_vars.append(
            SummaryVarInfo(
                name=name,
                var_type=var_type,
                target=target,
                source_file=Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None,
                source_line=kw.header_token.line,
            )
        )


def _extract_summary(kw: Keyword):
    """Build an add-summary-vars function from SUMMARY.

    In Eclipse, SUMMARY is a section marker. The actual variables are
    individual keywords (FOPR, WOPR, GOPR, ROPR, COPR, FU_*, etc.) that
    appear in the SUMMARY section. So we extract summary vars from
    *all* keywords in the SUMMARY section, not from SUMMARY records.

    We get the section by looking at where this kw lives; if the caller
    passes the section, we use it directly.
    """
    section = kw.section  # set by the parser
    if section is None:
        return None

    def add(st: SymbolTable) -> None:
        for skw in section.keywords:
            if skw.name == "SUMMARY" or not skw.name:
                continue
            name = skw.name
            # Classify the variable type by prefix.
            var_type = "field"
            target: Optional[str] = None
            # FU_/WU_/GU_/CU_/AU_ -> fu
            if any(name.startswith(p) for p in ("FU_", "WU_", "GU_", "CU_", "AU_")):
                var_type = "fu"
            elif ":" in name:
                # Not normally seen — keywords don't have colons.
                base, tgt = name.split(":", 1)
                var_type = {
                    "W": "well", "G": "group", "R": "region",
                    "C": "connection", "F": "field",
                }.get(base[0] if base else "", "field")
                target = tgt
            else:
                # Classify by 4th character: Fxxx / Wxxx / Gxxx / Rxxx / Cxxx.
                if len(name) >= 4 and name[0] in ("F", "W", "G", "R", "C"):
                    var_type = {
                        "F": "field", "W": "well", "G": "group",
                        "R": "region", "C": "connection",
                    }[name[0]]
            st.summary_vars.append(
                SummaryVarInfo(
                    name=name,
                    var_type=var_type,
                    target=target,
                    source_file=Path(skw.header_token.source_file).resolve() if skw.header_token.source_file else None,
                    source_line=skw.header_token.line,
                )
            )

    return add


def _extract_fuvar(kw: Keyword):
    """Build an add-FU-vars function from FUNVAR."""
    if not kw.records:
        return None
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None

    def add(st: SymbolTable) -> None:
        for rec in kw.records:
            for tok in rec.items:
                name = _token_to_str(tok)
                if name in st.fu_vars:
                    continue
                kind = "fu"
                if name.startswith("WU"):
                    kind = "wu"
                elif name.startswith("GU"):
                    kind = "gu"
                elif name.startswith("CU"):
                    kind = "cu"
                st.fu_vars[name] = FuVarInfo(
                    name=name,
                    kind=kind,
                    source_file=src,
                    source_line=rec.line,
                )

    return add


def _extract_udq(kw: Keyword):
    """Build an add-UDQ-definitions function.

    UDQ syntax (item[1] is the action: DEFINE/ASSIGN/UNITS/UPDATE;
    item[2] is the UDQ name; items[3..] are expressions).
    """
    if not kw.records:
        return None
    src = Path(kw.header_token.source_file).resolve() if kw.header_token.source_file else None

    def add(st: SymbolTable) -> None:
        for rec in kw.records:
            if len(rec.items) < 3:
                continue
            action = _token_to_str(rec.items[0]).upper()
            name = _token_to_str(rec.items[1])
            if action not in ("DEFINE", "ASSIGN", "UNITS", "UPDATE"):
                continue
            if name in st.fu_vars:
                continue
            st.fu_vars[name] = FuVarInfo(
                name=name,
                kind="rudq",
                source_file=src,
                source_line=rec.line,
            )

    return add