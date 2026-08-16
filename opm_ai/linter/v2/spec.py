"""Type definitions for the v2 linter's keyword catalogue.

A `KeywordSpec` describes what a keyword looks like in deck text:
which sections it's valid in, how many records it takes, the per-column
schema. The parser uses these specs to dispatch parsing (e.g. "this
keyword takes N records of M items each, so collect M tokens per
record until a terminator").

This module is intentionally *minimal*. We support the 4 SizeKind
values from OPM-flow-editor-support and opm-common's 4 value types
(INT, DOUBLE, STRING, RAW_STRING). UDA (User-Defined Argument) is
recognized but not parsed — it's a stub for now.

Full opm-common integration (3,200+ keywords) is deferred to Phase 2.5.
The minimal catalogue in catalogue/keywords.py covers ~80 keywords
that appear in SPE1/SPE3/SPE5/SPE9 and the v1-known-bad fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SectionName(str, Enum):
    """The 8 deck sections, in fixed order.

    The order matters: the parser enforces that sections appear in
    this sequence. `EDIT` is optional and only allowed between GRID
    and PROPS; `REGIONS` is optional and only between PROPS and
    SOLUTION; `SUMMARY` is optional and only between SOLUTION and
    SCHEDULE.

    `PRELUDE` is a virtual section for keywords that appear before
    any explicit section header (typical in INCLUDEd fragment files).
    The resolver merges PRELUDE keywords into the INCLUDE-statement's
    parent section.
    """

    PRELUDE = "PRELUDE"
    RUNSPEC = "RUNSPEC"
    GRID = "GRID"
    EDIT = "EDIT"
    PROPS = "PROPS"
    REGIONS = "REGIONS"
    SOLUTION = "SOLUTION"
    SUMMARY = "SUMMARY"
    SCHEDULE = "SCHEDULE"


# The 8 real sections in canonical order (PRELUDE is virtual).
ALL_SECTIONS = tuple(s.value for s in SectionName if s != SectionName.PRELUDE)
CANONICAL_SECTIONS = (
    SectionName.RUNSPEC,
    SectionName.GRID,
    SectionName.EDIT,
    SectionName.PROPS,
    SectionName.REGIONS,
    SectionName.SOLUTION,
    SectionName.SUMMARY,
    SectionName.SCHEDULE,
)


class SizeKind(str, Enum):
    """How a keyword's records are structured.

    From OPM-flow-editor-support (analysis.ts) and opm-common:

    - `none`: keyword alone, no records (END)
    - `fixed`: exactly N records of M items each (DIMENS, TABDIMS)
    - `list`: one or more records, each with terminator (WELSPECS,
      COMPDAT). May also be "multi_record" if per-record schemas differ.
    - `array`: N items per record, multiple records terminated by a
      block terminator (PORO, PERMX, DX). Block terminator is a
      standalone `/` line.
    """

    NONE = "none"
    FIXED = "fixed"
    LIST = "list"
    ARRAY = "array"


class ValueType(str, Enum):
    """Per-column value type, from opm-common.

    - `INT`: integer literal
    - `DOUBLE`: floating-point literal
    - `STRING`: single-quoted string
    - `RAW_STRING`: unquoted uppercase identifier (e.g. `'OPEN'` is
      STRING but a bare `OPEN` is RAW_STRING)
    - `UDA`: User-Defined Argument — accepted as-is, not parsed
    """

    INT = "INT"
    DOUBLE = "DOUBLE"
    STRING = "STRING"
    RAW_STRING = "RAW_STRING"
    UDA = "UDA"


@dataclass
class ItemSpec:
    """A single column in a keyword's record schema.

    Attributes:
        name: Column name (for diagnostics). May be None for
            positional-only columns.
        value_type: The expected value type.
        options: For STRING/RAW_STRING, the set of allowed values
            (None means "any string").
        default: The default value if a `*` placeholder is used.
            None means "no default declared".
        min: Inclusive minimum (for numeric types).
        max: Inclusive maximum (for numeric types).
        repeatable: If True, this item may appear 0..N times in a
            record. Use for free-form text like TITLE (`TITLE\nfoo bar baz /`)
            or list-of-names keywords like SUMMARY variables
            (`WBHP\n  'INJ' 'PROD' /`). When True, the L202 rule's
            "too many items" check is skipped for this column.
    """

    name: Optional[str] = None
    value_type: ValueType = ValueType.INT
    options: Optional[list[str]] = None
    default: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    repeatable: bool = False


@dataclass
class KeywordSpec:
    """Specification of a single keyword.

    Attributes:
        name: The keyword's name (uppercase, e.g. "WELSPECS").
        sections: Sections in which this keyword is valid.
        size_kind: How records are structured.
        items: Per-column schema (one entry per column).
        record_count: For `fixed`-kind keywords, the exact number
            of records. For other kinds, ignored.
        requires: Other keywords that must appear before this one
            (whole-deck invariant).
        prohibits: Keywords that must NOT appear if this one does.
        opm_only: True if this keyword only works in OPM Flow.
        opm_unsupported: True if OPM Flow explicitly does not
            support this keyword.
        record_schemas: For multi-record keywords (per OPM-ext's
            `RecordMeta`), per-record item schemas. If set, the
            parser uses the first record's schema for records
            1..N-1 and the last entry's schema for the final
            variadic record.
    """

    name: str
    sections: list[SectionName]
    size_kind: SizeKind
    items: list[ItemSpec] = field(default_factory=list)
    record_count: Optional[int] = None
    requires: list[str] = field(default_factory=list)
    prohibits: list[str] = field(default_factory=list)
    opm_only: bool = False
    opm_unsupported: bool = False
    # If True, this LIST/ARRAY keyword accepts multiple records
    # separated by `/`. Each `/` closes the current record but the
    # keyword stays open until EOF or a different keyword appears.
    # Use for TUNING (2 records of N values each), etc.
    multi_record: bool = False
    record_schemas: Optional[list[list[ItemSpec]]] = None
    # When True, the first column of each record is a free-form
    # identifier (well name, group name, region name, etc.) that
    # typically appears at column 0 of its own line. The parser
    # uses this flag to apply "smart dispatch": unknown column-0
    # words inside this keyword's record stream are treated as
    # record items rather than new keywords. False (the default)
    # disables smart dispatch — INCLUDE, for example, has only a
    # file path in its first column, so the column-0 next-word
    # heuristic would mis-classify adjacent keywords.
    first_column_is_name: bool = False
    # When True, the per-record item count is documented in the
    # OPM Flow Reference Manual (or opm-common's keyword handler
    # source), so a record with too many/few items is an ERROR
    # rather than a WARNING. False (the default) keeps L202 as
    # WARNING because the v2 catalogue's per-record item counts
    # are best-effort and may be incomplete for unusual decks.
    # Promote to True for keywords where the OPM spec is
    # unambiguous (DIMENS, TABDIMS, REGDIMS, EQLDIMS, WELLDIMS,
    # WELSPECS, COMPDAT, WCONPROD, WCONINJE, WCONHIST, etc.).
    precise_items: bool = False

    def is_valid_in(self, section: SectionName) -> bool:
        return section in self.sections

    def item_count(self) -> int:
        """Number of items expected per record (1 for `none`)."""
        if self.size_kind == SizeKind.NONE:
            return 0
        return len(self.items)


# Common group of value types for readability.
INT = ValueType.INT
DOUBLE = ValueType.DOUBLE
STRING = ValueType.STRING
RAW_STRING = ValueType.RAW_STRING
UDA = ValueType.UDA