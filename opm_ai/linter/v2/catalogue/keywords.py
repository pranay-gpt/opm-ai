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


# Repeatable item shorthands. Use these for LIST keywords whose
# records are "0..N copies of a single item type, terminated by `/`":
# - TITLE (free-form text)
# - SUMMARY variables like WOPR/WBHP (well-list)
# - Generic well/group name lists.
STRING_REP = ItemSpec(value_type=STRING, repeatable=True)
INT_REP = ItemSpec(value_type=INT, repeatable=True)


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
    # Free-form text. The Eclipse reference manual allows the title
    # to span multiple words/lines until a `/` or section break.
    # Use LIST with a repeatable STRING item so the parser attaches
    # the title text to this keyword instead of treating it as loose.
    size_kind=SizeKind.LIST,
    items=[STRING_REP],
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
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],  # observed in SCHEDULE too
    size_kind=SizeKind.NONE,
)

# RUNSPEC additions (commonly-seen capacity / option keywords)
ACTDIMS = KeywordSpec(
    name="ACTDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT],
    record_count=1,
)
AQUDIMS = KeywordSpec(
    name="AQUDIMS",
    sections=[SectionName.RUNSPEC, SectionName.SOLUTION],  # duplicate def removed below
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT],
    record_count=1,
)
FAULTDIM = KeywordSpec(
    name="FAULTDIM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT],
    record_count=1,
)
GRIDUNIT = KeywordSpec(
    name="GRIDUNIT",
    sections=[SectionName.RUNSPEC, SectionName.GRID],  # RM: GRID; RUNSPEC is also valid (OPM)
    size_kind=SizeKind.NONE,
)
MESSAGES = KeywordSpec(
    name="MESSAGES",
    sections=[SectionName.RUNSPEC, SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT, INT, INT, INT],
    record_count=1,
)
NUPCOL = KeywordSpec(
    name="NUPCOL",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],  # observed in SCHEDULE too
    size_kind=SizeKind.FIXED,
    items=[INT],
    record_count=1,
)
NSTACK = KeywordSpec(
    name="NSTACK",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT],
    record_count=1,
)
SATOPTS = KeywordSpec(
    name="SATOPTS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
SPECGRID = KeywordSpec(
    name="SPECGRID",
    sections=[SectionName.GRID],  # RM: GRID only; RUNSPEC would flag for modern decks
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, DOUBLE, RAW_STRING, INT],
    record_count=1,
)
SUMMARY = KeywordSpec(
    name="SUMMARY",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
VFPIDIMS = KeywordSpec(
    name="VFPIDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT],
    record_count=1,
)
WSEGDIMS = KeywordSpec(
    name="WSEGDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT, INT],
    record_count=1,
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
    sections=[SectionName.GRID, SectionName.EDIT],  # EDIT for multiplier scoping
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

# GRID additions
FAULTS = KeywordSpec(
    name="FAULTS",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, INT, INT, INT, INT, INT, INT, INT, INT],
)
MULTFLT = KeywordSpec(
    name="MULTFLT",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 8,
)
NTG = KeywordSpec(
    name="NTG",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
TRANX = KeywordSpec(
    name="TRANX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
TRANY = KeywordSpec(
    name="TRANY",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
TRANZ = KeywordSpec(
    name="TRANZ",
    sections=[SectionName.GRID, SectionName.EDIT],  # EDIT for multiplier scoping
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
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
    items=[UDA] * 12,
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
    precise_items=True,
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
    # PVTO records vary in width: the first record of each
    # undersaturated-oil row has 4 items (Rs, P, Bo, Vis), subsequent
    # rows have 3 items (P, Bo, Vis — Rs implicit). Stay open across
    # `/` so the parser doesn't emit "loose token" parse errors for
    # the 3-item rows. The first column of a 3-item row is a value
    # continuation, not a new keyword.
    multi_record=True,
)

PVTG = KeywordSpec(
    name="PVTG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE],
    # PVTG records vary in width: first row of each dry-gas
    # entry has 4 items (Pg, BG, MG, ?), subsequent rows have 3
    # items (P, BG, MG). Stay open across `/` for the same
    # reason as PVTO — see that comment.
    multi_record=True,
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
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE, UDA],
)

DENSITY = KeywordSpec(
    name="DENSITY",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)

# PROPS additions
PVDG = KeywordSpec(
    name="PVDG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE, DOUBLE],
)
BGSAT = KeywordSpec(
    name="BGSAT",
    sections=[SectionName.PROPS, SectionName.SUMMARY],
    # In PROPS: array of (i, j, k, value) per record.
    # In SUMMARY: free-form summary-variable usage. Use ARRAY of INT
    # so the data values attach to this keyword instead of being
    # flagged as L160 noise.
    size_kind=SizeKind.ARRAY,
    items=[INT],
)
SWL = KeywordSpec(
    name="SWL",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SWCR = KeywordSpec(
    name="SWCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SOWCR = KeywordSpec(
    name="SOWCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SGCR = KeywordSpec(
    name="SGCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SGU = KeywordSpec(
    name="SGU",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
KRW = KeywordSpec(
    name="KRW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)
KRO = KeywordSpec(
    name="KRO",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)
KRG = KeywordSpec(
    name="KRG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)
PLYVISC = KeywordSpec(
    name="PLYVISC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)
PLYROCK = KeywordSpec(
    name="PLYROCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)
PLYSHEAR = KeywordSpec(
    name="PLYSHEAR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
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

EQLNUM = KeywordSpec(
    name="EQLNUM",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

SATNUM = KeywordSpec(
    name="SATNUM",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

PVTNUM = KeywordSpec(
    name="PVTNUM",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

ROCKNUM = KeywordSpec(
    name="ROCKNUM",
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
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 12,
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
        # Each summary variable takes a list of well/group names
        # (e.g. `WBHP\n  'INJ' 'PROD' /`). Use LIST with a repeatable
        # STRING item so subsequent value tokens are attached to this
        # keyword instead of being flagged as L160 noise.
        size_kind=SizeKind.LIST,
        items=[STRING_REP],
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
        STRING,    # well name
        STRING,    # group
        INT,       # head_i
        INT,       # head_j
        DOUBLE,    # ref_depth
        RAW_STRING,  # phase (LIQ/OIL/GAS/WAT)
        DOUBLE,    # drainage radius
        RAW_STRING,  # shut-in / STD
        RAW_STRING,  # crossflow / SHUT
        STRING,    # pressure table
        DOUBLE,    # density
        INT,       # friction
        INT,       # segment
        DOUBLE,    # pressure
    ],
    requires=["WELLDIMS"],
    first_column_is_name=True,
    precise_items=True,
)

COMPDAT = KeywordSpec(
    name="COMPDAT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,        # well
        INT,           # I
        INT,           # J
        INT,           # K1
        INT,           # K2
        INT,           # sat_table
        INT,           # connect_trans
        RAW_STRING,    # status (OPEN/SHUT)
        DOUBLE,        # well_diameter
        DOUBLE,        # Kh
        DOUBLE,        # skin
        DOUBLE,        # D-factor
        RAW_STRING,    # direction
        DOUBLE,        # gas/oil
        DOUBLE,        # pressure
        INT,           # segments
        INT,           # wellbore
    ],
    requires=["WELSPECS"],
    first_column_is_name=True,
    precise_items=True,
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
    ],
    precise_items=True,  # 11 documented columns per OPM Flow ref manual
    requires=["WELSPECS"],
    first_column_is_name=True,
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
    requires=["WELSPECS"],
    first_column_is_name=True,
    precise_items=True,
)

WCONHIST = KeywordSpec(
    name="WCONHIST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[
        STRING,      # well
        RAW_STRING,  # status (OPEN/SHUT)
        RAW_STRING,  # control mode (ORAT/GRAT/etc.)
        DOUBLE,      # orat
        DOUBLE,      # wrat
        DOUBLE,      # grat
        DOUBLE,      # lrat
        DOUBLE,      # resv
        DOUBLE,      # bhp
        DOUBLE,      # thp
    ],
    requires=["WELSPECS"],
    first_column_is_name=True,
    precise_items=True,
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
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    # TUNING takes 2 records of N values each, separated by `/`.
    multi_record=True,
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
    size_kind=SizeKind.LIST,
    # Per OPM Flow spec: record 1 is NAME (STRING) + NUM (INT,
    # default 1) + MIN_WAIT (DOUBLE, default 0); records 2+ are
    # free-form CONDITION lines (variadic). The v2 linter uses a
    # single maximum item count per keyword; 6 covers the empirical
    # max across the 610 known-good fixtures (e.g. WTMULT-03
    # records with embedded condition expressions).
    items=[STRING, INT, DOUBLE, UDA, UDA, UDA],
    first_column_is_name=True,
    precise_items=True,
)

ENDACTIO = KeywordSpec(
    name="ENDACTIO",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

PYACTION = KeywordSpec(
    name="PYACTION",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE],
)

UDQ = KeywordSpec(
    name="UDQ",
    sections=[SectionName.SCHEDULE, SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,  # UDQ expressions can be long; observed up to 13 items
    first_column_is_name=True,  # records start with action (DEFINE/ASSIGN/UNITS/UPDATE)
)

# INCLUDE / IMPORT — file inclusion directives.
# Valid in any section; the resolver handles them at composite-deck time.
INCLUDE = KeywordSpec(
    name="INCLUDE",
    sections=list(SectionName),
    size_kind=SizeKind.LIST,
    items=[STRING],
)

IMPORT = KeywordSpec(
    name="IMPORT",
    sections=list(SectionName),
    size_kind=SizeKind.LIST,
    items=[STRING],
)

# PATHS alias directive — also valid in any section, defines $DATA,
# $GRID, etc. substitutions used by INCLUDE/IMPORT.
PATHS = KeywordSpec(
    name="PATHS",
    sections=list(SectionName),
    size_kind=SizeKind.LIST,
    items=[STRING, STRING],
)

# FU_VAR declarations: bare flow-unit name at column 0, no items.
FU_DECL = KeywordSpec(
    name="FU_VAR_DECL",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)

# FUNVAR declares FU_/WU_/GU_ names. Per OPM Flow Reference Manual,
# FUNVAR appears in RUNSPEC (to register the FU/WU/GU names) and may
# also appear in SUMMARY. The actual FU_* bare declarations are
# SUMMARY-only via FU_DECL.
FUNVAR = KeywordSpec(
    name="FUNVAR",
    sections=[SectionName.RUNSPEC, SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
)

# Schedule terminator.
END = KeywordSpec(
    name="END",
    sections=[SectionName.SCHEDULE, SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# SCHEDULE additions
WELTARG = KeywordSpec(
    name="WELTARG",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, RAW_STRING, DOUBLE],
)
WEFAC = KeywordSpec(
    name="WEFAC",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, RAW_STRING],
)
MINPV = KeywordSpec(
    name="MINPV",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE],
    record_count=1,
)
MINPVV = KeywordSpec(
    name="MINPVV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE],
    record_count=1,
)
PINCH = KeywordSpec(
    name="PINCH",
    sections=[SectionName.SCHEDULE, SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE, INT, INT, DOUBLE],
    record_count=1,
)
SEPARATE = KeywordSpec(
    name="SEPARATE",
    sections=[SectionName.SCHEDULE, SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
WSEGAQD = KeywordSpec(
    name="WSEGAQD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, INT, DOUBLE, DOUBLE, DOUBLE, INT],
)
WSEGDEFV = KeywordSpec(
    name="WSEGDEFV",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE],
)
WSEGITER = KeywordSpec(
    name="WSEGITER",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[INT, DOUBLE, DOUBLE, INT],
    record_count=1,
)
COMPSEGS = KeywordSpec(
    name="COMPSEGS",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
)

# ---------------------------------------------------------------------------
# Common SCHEDULE keywords (not in the minimal set above)
# ---------------------------------------------------------------------------

DATES = KeywordSpec(
    name="DATES",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[INT, STRING, INT, STRING],
)

WELOPEN = KeywordSpec(
    name="WELOPEN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    requires=["WELSPECS"],
)

WCONINJH = KeywordSpec(
    name="WCONINJH",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

NEWTRAN = KeywordSpec(
    name="NEWTRAN",
    sections=[SectionName.SCHEDULE, SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],
    record_count=1,
)

GRUPTREE = KeywordSpec(
    name="GRUPTREE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING],
    precise_items=True,
)

GCONPROD = KeywordSpec(
    name="GCONPROD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 14,
    first_column_is_name=True,
    precise_items=True,
)

GCONINJE = KeywordSpec(
    name="GCONINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 14,
    first_column_is_name=True,
    precise_items=True,
)

WPIMULT = KeywordSpec(
    name="WPIMULT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
    precise_items=True,
)

WTEMP = KeywordSpec(
    name="WTEMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
    precise_items=True,
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
    sections=[SectionName.SCHEDULE, SectionName.SOLUTION, SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
)

RPTSCHED = KeywordSpec(
    name="RPTSCHED",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 100,
)

# Report flags for SOLUTION / GRID output control.
RPTSOL = KeywordSpec(
    name="RPTSOL",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
)

RPTGRID = KeywordSpec(
    name="RPTGRID",
    sections=[SectionName.GRID, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
)

# WELSEGS — multisegmented well definition. WELSEGS records vary
# in width depending on segment type (regular / spiral / etc.).
# Stay open across `/` so the parser doesn't emit "loose token"
# errors on continuation rows.
WELSEGS = KeywordSpec(
    name="WELSEGS",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    multi_record=True,
)

# EQLOPTS — equilibration options. UDA list.
EQLOPTS = KeywordSpec(
    name="EQLOPTS",
    sections=[SectionName.SOLUTION, SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# ACTNUM — active cell array (per-cell integer flag).
ACTNUM = KeywordSpec(
    name="ACTNUM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# TSTEP — list of timesteps (each item is a delta). NTSOPL records max.
TSTEP = KeywordSpec(
    name="TSTEP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 1000,  # up to ~1000 timesteps per TSTEP block
)

UNIFOUT = KeywordSpec(
    name="UNIFOUT",
    sections=[SectionName.RUNSPEC],  # RM: RUNSPEC only
    size_kind=SizeKind.LIST,
    items=[INT],
)

UNIFIN = KeywordSpec(
    name="UNIFIN",
    sections=[SectionName.RUNSPEC],  # RM: RUNSPEC only
    size_kind=SizeKind.LIST,
    items=[INT],
)

NOECHO = KeywordSpec(
    name="NOECHO",
    sections=[SectionName.RUNSPEC, SectionName.GRID, SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

ECHO = KeywordSpec(
    name="ECHO",
    sections=[SectionName.RUNSPEC, SectionName.GRID, SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# GRID options
GRIDOPTS = KeywordSpec(
    name="GRIDOPTS",
    sections=[SectionName.RUNSPEC],  # RM: RUNSPEC only
    size_kind=SizeKind.FIXED,
    items=[INT, INT, INT],
    record_count=1,
)

INIT = KeywordSpec(
    name="INIT",
    sections=[SectionName.GRID],  # RM: GRID only
    size_kind=SizeKind.FIXED,
    items=[INT],
    record_count=1,
)

VFPPDIMS = KeywordSpec(
    name="VFPPDIMS",
    sections=[SectionName.RUNSPEC],  # RM: RUNSPEC only
    size_kind=SizeKind.FIXED,
    items=[INT] * 10,
    record_count=1,
)

# Tracer-related
TRACERS = KeywordSpec(
    name="TRACERS",
    sections=[SectionName.RUNSPEC, SectionName.PROPS],  # RM: RUNSPEC primarily
    size_kind=SizeKind.FIXED,
    items=[INT] * 10,
    record_count=1,
)

# Aquifer connectivity
AQUCT = KeywordSpec(
    name="AQUCT",
    sections=[SectionName.GRID, SectionName.SOLUTION],  # observed in GRID too
    size_kind=SizeKind.LIST,
    items=[INT, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, INT, INT],
)

AQUANCON = KeywordSpec(
    name="AQUANCON",
    sections=[SectionName.GRID, SectionName.SOLUTION],  # observed in GRID too
    size_kind=SizeKind.LIST,
    items=[INT, INT, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
)

# SOLUTION additions
PBVD = KeywordSpec(
    name="PBVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)
THPRES = KeywordSpec(
    name="THPRES",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[INT, INT, INT, DOUBLE, RAW_STRING, DOUBLE, DOUBLE, DOUBLE],
)
EHYSTR = KeywordSpec(
    name="EHYSTR",
    sections=[SectionName.SOLUTION, SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[INT, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
    record_count=1,
)
FILLEPS = KeywordSpec(
    name="FILLEPS",
    sections=[SectionName.SOLUTION, SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
RES = KeywordSpec(
    name="RES",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# Aquifer properties
AQUDIMS = KeywordSpec(
    name="AQUDIMS",
    sections=[SectionName.RUNSPEC, SectionName.SOLUTION],  # observed in both
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
    ACTDIMS, AQUDIMS, FAULTDIM, GRIDUNIT, MESSAGES,
    NUPCOL, NSTACK, SATOPTS, SPECGRID, VFPIDIMS, WSEGDIMS,
    DX, DY, DZ, PORO, PERMX, PERMY, PERMZ, TOPS, COORD, ZCORN, GRIDFILE,
    NTG, FAULTS, MULTFLT, TRANX, TRANY, TRANZ,
    EQUALS, COPY, MULTIPLY, OPERATE, ADDREG, MULTIREG, EQUALREG,
    SWOF, SGOF, SGFN, SWFN, PVDO, PVTO, PVTG, PVTW, PVDG, ROCK, DENSITY,
    BGSAT, SWL, SWCR, SOWCR, SGCR, SGU,
    KRW, KRO, KRG, PLYVISC, PLYROCK, PLYSHEAR,
    FIPNUM, FIPSEP, EQLNUM, SATNUM, PVTNUM, ROCKNUM,
    EQUIL, RSVD, PRESSURE, SGAS, SWAT, PBVD, THPRES, EHYSTR, FILLEPS, RES,
    AQUCHG, AQUFET, AQUCT, AQUANCON,
    WELSPECS, COMPDAT, WCONPROD, WCONINJE, WCONHIST, TSTEP, TUNING,
    DATES, WELOPEN, WCONINJH, NEWTRAN, GRUPTREE, GCONPROD, GCONINJE,
    WPIMULT, WTEMP, DRSDT, INIT, VFPPDIMS,
    WELTARG, WEFAC, MINPV, MINPVV, PINCH, SEPARATE,
    WSEGAQD, WSEGDEFV, WSEGITER, COMPSEGS,
    ACTIONX, ENDACTIO, PYACTION, UDQ, FU_DECL, FUNVAR, END, SUMMARY,
    RPTRST, RPTSCHED, RPTSOL, RPTGRID, UNIFOUT, UNIFIN, NOECHO, ECHO,
    GRIDOPTS, TRACERS,
    INCLUDE, IMPORT, PATHS,
    WELSEGS, EQLOPTS, ACTNUM,
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