"""Minimal hand-curated keyword catalogue for the v2 linter.

This catalogue covers ~80 keywords that appear in SPE1, SPE3, SPE5,
SPE9, and the v1-known-bad fixtures. It is intentionally minimal:
full opm-common integration (3,200+ keywords) is deferred to Phase 2.5.

For each keyword we record:
  - size_kind (none / fixed / list / array)
  - the sections it's valid in
  - per-column item schema (for `fixed` and `list`)
  - record_count (for `fixed`)

Naming conventions:
  - All keyword names are uppercase, exact match.
  - Section transitions follow the OPM spec: 8 sections in fixed order
    (RUNSPEC → GRID → [EDIT] → PROPS → [REGIONS] → SOLUTION →
    [SUMMARY] → SCHEDULE).
  - `array`-kind keywords are terminated by a standalone `/` line,
    which the parser handles separately from record terminators.
"""

from __future__ import annotations

from ..spec import (
    DOUBLE,
    INT,
    RAW_STRING,
    STRING,
    UDA,
    ItemSpec,
    KeywordSpec,
    SectionName,
    SizeKind,
)


# ---------------------------------------------------------------------------
# RUNSPEC
# ---------------------------------------------------------------------------

DIMENS = KeywordSpec(
    name="DIMENS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],  # NX NY NZ
    record_count=1,
)

TABDIMS = KeywordSpec(
    name="TABDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT, INT, INT, INT, INT],
    record_count=1,
)

WELLDIMS = KeywordSpec(
    name="WELLDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT, INT, INT],
    record_count=1,
)

EQLDIMS = KeywordSpec(
    name="EQLDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT],
    record_count=1,
)

REGDIMS = KeywordSpec(
    name="REGDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT, INT, INT, INT, INT],
    record_count=1,
)

# Phases: zero-item keywords.
PHASE_KEYWORDS = ["OIL", "GAS", "WATER", "DISGAS", "VAPOIL", "LIQUID"]
PHASES = {
    name: KeywordSpec(
        name=name,
        sections=[SectionName.RUNSPEC],
        size_kind=SizeKind.NONE,
    )
    for name in PHASE_KEYWORDS
}

TITLE = KeywordSpec(
    name="TITLE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[STRING],
)

START = KeywordSpec(
    name="START",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],
    record_count=1,
)

METRIC = KeywordSpec(
    name="METRIC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

FIELD = KeywordSpec(
    name="FIELD",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

UNITS = KeywordSpec(
    name="UNITS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# ---------------------------------------------------------------------------
# GRID
# ---------------------------------------------------------------------------

DX = KeywordSpec(
    name="DX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

DY = KeywordSpec(
    name="DY",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

DZ = KeywordSpec(
    name="DZ",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

PORO = KeywordSpec(
    name="PORO",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

PERMX = KeywordSpec(
    name="PERMX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

PERMY = KeywordSpec(
    name="PERMY",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

PERMZ = KeywordSpec(
    name="PERMZ",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

TOPS = KeywordSpec(
    name="TOPS",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

COORD = KeywordSpec(
    name="COORD",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

ZCORN = KeywordSpec(
    name="ZCORN",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

GRIDFILE = KeywordSpec(
    name="GRIDFILE",
    sections=[SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[INT, STRING],
    record_count=1,
)

# ---------------------------------------------------------------------------
# EDIT (operands)
# ---------------------------------------------------------------------------

EQUALS = KeywordSpec(
    name="EQUALS",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING] + [UDA] * 9,
)

COPY = KeywordSpec(
    name="COPY",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING, RAW_STRING, INT, INT, INT, INT, INT, INT],
)

MULTIPLY = KeywordSpec(
    name="MULTIPLY",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING, INT, INT, INT, INT, INT, INT, DOUBLE],
)

OPERATE = KeywordSpec(
    name="OPERATE",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

ADDREG = KeywordSpec(
    name="ADDREG",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

MULTIREG = KeywordSpec(
    name="MULTIREG",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

EQUALREG = KeywordSpec(
    name="EQUALREG",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# ---------------------------------------------------------------------------
# PROPS
# ---------------------------------------------------------------------------

SWOF = KeywordSpec(
    name="SWOF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE],  # SW, KRW, KROW
)

SGOF = KeywordSpec(
    name="SGOF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE],
)

SGFN = KeywordSpec(
    name="SGFN",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

SWFN = KeywordSpec(
    name="SWFN",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

PVDO = KeywordSpec(
    name="PVDO",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE],  # PO, BO, MO
)

PVTO = KeywordSpec(
    name="PVTO",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)

PVTG = KeywordSpec(
    name="PVTG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)

PVTW = KeywordSpec(
    name="PVTW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)

ROCK = KeywordSpec(
    name="ROCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],
    record_count=1,
)

DENSITY = KeywordSpec(
    name="DENSITY",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE],
    record_count=1,
)

# ---------------------------------------------------------------------------
# REGIONS
# ---------------------------------------------------------------------------

FIPNUM = KeywordSpec(
    name="FIPNUM",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

FIPSEP = KeywordSpec(
    name="FIPSEP",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.LIST,
    items=[INT],
)

# ---------------------------------------------------------------------------
# SOLUTION
# ---------------------------------------------------------------------------

EQUIL = KeywordSpec(
    name="EQUIL",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE] * 10,
    record_count=1,
)

RSVD = KeywordSpec(
    name="RSVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

PRESSURE = KeywordSpec(
    name="PRESSURE",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

SGAS = KeywordSpec(
    name="SGAS",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

SWAT = KeywordSpec(
    name="SWAT",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

AQUCHG = KeywordSpec(
    name="AQUCHG",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 8,
)

AQUFET = KeywordSpec(
    name="AQUFET",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------

# FOPR / WOPR / etc. are zero-item keywords (just the name).
SUMMARY_KEYWORDS = [
    "FOPR", "FOPT", "FOIR", "FOIT",
    "FGPR", "FGPT", "FGIR", "FGIT",
    "FWPR", "FWPT", "FWIR", "FWIT",
    "WOPR", "WOPT", "WOIR", "WOIT", "WOGR",
    "WGPR", "WGPT", "WGIR", "WGIT",
    "WWPR", "WWPT", "WWIR", "WWIT",
    "WBHP", "WTHP",
    "FOPRH", "FOPRH",
]
SUMMARY_VARS = {
    name: KeywordSpec(
        name=name,
        sections=[SectionName.SUMMARY],
        size_kind=SizeKind.NONE,
    )
    for name in SUMMARY_KEYWORDS
}

# ---------------------------------------------------------------------------
# SCHEDULE
# ---------------------------------------------------------------------------

WELSPECS = KeywordSpec(
    name="WELSPECS",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,  # well name
        STRING,  # group
        INT,     # head_i
        INT,     # head_j
        DOUBLE,  # ref_depth
        RAW_STRING,  # phase (LIQ/OIL/GAS/WAT)
    ],
)

COMPDAT = KeywordSpec(
    name="COMPDAT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,  # well
        INT,     # I
        INT,     # J
        INT,     # K1
        INT,     # K2
        INT,     # sat_table
        INT,     # connect_trans
        RAW_STRING,  # status (OPEN/SHUT)
        DOUBLE,  # well_diameter
        DOUBLE,  # Kh
        DOUBLE,  # skin
        RAW_STRING,  # direction
    ],
)

WCONPROD = KeywordSpec(
    name="WCONPROD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,  # well
        RAW_STRING,  # status
        RAW_STRING,  # control (ORAT/GRAT/WRAT/etc.)
        DOUBLE,  # target
        DOUBLE,  # lower limit (or *)
        DOUBLE,  # upper limit (or *)
        DOUBLE,  # liquid target (or *)
        DOUBLE,  # rate phase (or *)
        DOUBLE,  # BHP limit
        DOUBLE,  # THP limit
        DOUBLE,  # VFP table
        DOUBLE,  # alq
        DOUBLE,  # history
    ],
)

WCONINJE = KeywordSpec(
    name="WCONINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,
        RAW_STRING,  # type (WATER/GAS/OIL)
        RAW_STRING,  # status
        RAW_STRING,  # control
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
    ],
)

WCONHIST = KeywordSpec(
    name="WCONHIST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,
        RAW_STRING,
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
        DOUBLE,
    ],
)

TSTEP = KeywordSpec(
    name="TSTEP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)

TUNING = KeywordSpec(
    name="TUNING",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[UDA] * 10,
    record_count=1,
)

VFP = {
    f"VFPPROD{n}": KeywordSpec(
        name=f"VFPPROD{n}",
        sections=[SectionName.SCHEDULE],
        size_kind=SizeKind.ARRAY,
        items=[DOUBLE] * 10,
    )
    for n in range(11)
}

ACTIONX = KeywordSpec(
    name="ACTIONX",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[STRING, DOUBLE],
    record_count=1,
)

ENDACTIO = KeywordSpec(
    name="ENDACTIO",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

PYACTION = KeywordSpec(
    name="PYACTION",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[STRING, DOUBLE],
    record_count=1,
)

UDQ = KeywordSpec(
    name="UDQ",
    sections=[SectionName.SCHEDULE, SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# FU_VAR and similar (used in SUMMARY and UDQ context).
FU_DECL = KeywordSpec(
    name="FU_VAR_DECL",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)

# Schedule terminator.
END = KeywordSpec(
    name="END",
    sections=[SectionName.SCHEDULE, SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# ---------------------------------------------------------------------------
# Common SCHEDULE keywords (not in the minimal set above)
# ---------------------------------------------------------------------------

DATES = KeywordSpec(
    name="DATES",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],
    record_count=1,
)

WELOPEN = KeywordSpec(
    name="WELOPEN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

WCONINJH = KeywordSpec(
    name="WCONINJH",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

NEWTRAN = KeywordSpec(
    name="NEWTRAN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],
    record_count=1,
)

GRUPTREE = KeywordSpec(
    name="GRUPTREE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING],
)

GCONPROD = KeywordSpec(
    name="GCONPROD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
)

GCONINJE = KeywordSpec(
    name="GCONINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
)

WPIMULT = KeywordSpec(
    name="WPIMULT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE],
)

WTEMP = KeywordSpec(
    name="WTEMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE],
)

DRSDT = KeywordSpec(
    name="DRSDT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],
    record_count=1,
)

# Report flags (zero-item or simple flags)
RPTRST = KeywordSpec(
    name="RPTRST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING],
)

RPTSCHED = KeywordSpec(
    name="RPTSCHED",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING],
)

UNIFOUT = KeywordSpec(
    name="UNIFOUT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[INT],
)

UNIFIN = KeywordSpec(
    name="UNIFIN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[INT],
)

NOECHO = KeywordSpec(
    name="NOECHO",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

ECHO = KeywordSpec(
    name="ECHO",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# GRID options
GRIDOPTS = KeywordSpec(
    name="GRIDOPTS",
    sections=[SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],
    record_count=1,
)

INIT = KeywordSpec(
    name="INIT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[INT],
    record_count=1,
)

VFPPDIMS = KeywordSpec(
    name="VFPPDIMS",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[INT] * 10,
    record_count=1,
)

# Tracer-related
TRACERS = KeywordSpec(
    name="TRACERS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[INT] * 10,
    record_count=1,
)

# Aquifer connectivity
AQUCT = KeywordSpec(
    name="AQUCT",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE, INT],
    record_count=1,
)

AQUANCON = KeywordSpec(
    name="AQUANCON",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[INT, INT, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)

# Aquifer properties
AQUDIMS = KeywordSpec(
    name="AQUDIMS",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.FIXED,
    items=[INT] * 5,
    record_count=1,
)

# ---------------------------------------------------------------------------
# Master index
# ---------------------------------------------------------------------------

KEYWORD_INDEX: dict[str, KeywordSpec] = {}


def _register(*specs: KeywordSpec) -> None:
    for spec in specs:
        KEYWORD_INDEX[spec.name] = spec


def _register_dict(d: dict[str, KeywordSpec]) -> None:
    for name, spec in d.items():
        KEYWORD_INDEX[name] = spec


# Register all keywords
_register(
    DIMENS, TABDIMS, WELLDIMS, EQLDIMS, REGDIMS,
    TITLE, START, METRIC, FIELD, UNITS,
    DX, DY, DZ, PORO, PERMX, PERMY, PERMZ, TOPS, COORD, ZCORN, GRIDFILE,
    EQUALS, COPY, MULTIPLY, OPERATE, ADDREG, MULTIREG, EQUALREG,
    SWOF, SGOF, SGFN, SWFN, PVDO, PVTO, PVTG, PVTW, ROCK, DENSITY,
    FIPNUM, FIPSEP,
    EQUIL, RSVD, PRESSURE, SGAS, SWAT, AQUCHG, AQUFET, AQUCT, AQUANCON, AQUDIMS,
    WELSPECS, COMPDAT, WCONPROD, WCONINJE, WCONHIST, TSTEP, TUNING,
    DATES, WELOPEN, WCONINJH, NEWTRAN, GRUPTREE, GCONPROD, GCONINJE,
    WPIMULT, WTEMP, DRSDT, INIT, VFPPDIMS,
    ACTIONX, ENDACTIO, PYACTION, UDQ, FU_DECL, END,
    RPTRST, RPTSCHED, UNIFOUT, UNIFIN, NOECHO, ECHO, GRIDOPTS, TRACERS,
)
_register_dict(PHASES)
_register_dict(SUMMARY_VARS)
_register_dict(VFP)


def get_keyword(name: str) -> KeywordSpec | None:
    """Look up a keyword by name (case-sensitive)."""
    return KEYWORD_INDEX.get(name.upper())


def known_keywords() -> list[str]:
    """Return all known keyword names, sorted alphabetically."""
    return sorted(KEYWORD_INDEX.keys())