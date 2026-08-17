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
    # Use LIST with a repeatable STRING item (STRING_REP) so the
    # parser attaches the title text to this keyword instead of
    # treating it as loose, and the L202 record-length rule does
    # not flag the multi-word title.
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

# Unit keywords: valid as standalone RUNSPEC activation (METRIC/FIELD/LAB)
# and as GRIDUNIT parameter values (METRES/FEET/LAB/RES/CM).
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
LAB = KeywordSpec(
    name="LAB",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
METRES = KeywordSpec(
    name="METRES",
    sections=[SectionName.GRID, SectionName.RUNSPEC],  # GRIDUNIT param + RUNSPEC (for METRIC alias)
    size_kind=SizeKind.NONE,
)
FEET = KeywordSpec(
    name="FEET",
    sections=[SectionName.GRID, SectionName.RUNSPEC],  # GRIDUNIT param + RUNSPEC (for FIELD alias)
    size_kind=SizeKind.NONE,
)
CM = KeywordSpec(
    name="CM",
    sections=[SectionName.GRID],  # GRIDUNIT param only
    size_kind=SizeKind.NONE,
)
RES = KeywordSpec(
    name="RES",
    sections=[SectionName.GRID],  # GRIDUNIT param only
    size_kind=SizeKind.NONE,
)

# YES/NO — boolean flags used in SCALECRS, ENDSCALE (NODIR/REVERS),
# and other keywords. Recognize them as valid standalone keywords.
YES = KeywordSpec(
    name="YES",
    sections=[SectionName.PROPS, SectionName.GRID, SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
NO = KeywordSpec(
    name="NO",
    sections=[SectionName.PROPS, SectionName.GRID, SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# UNITS — declares a unit constant for a UDQ. Format:
#   UNITS <udq_name> <constant> <unit_text> /
# Each record is 3 items. UDA list covers the variable name
# and constant value; trailing unit text is also UDA.
UNITS = KeywordSpec(
    name="UNITS",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 3,
    multi_record=True,
)

# ASSIGN — assigns a value to a UDQ. Format:
#   ASSIGN <udq_name> <value> /
# ASSIGN — assigns a value to a UDQ. Format:
#   ASSIGN <udq_name> <value>... /
# Each record is 2+ items (variable name + 1+ values).
ASSIGN = KeywordSpec(
    name="ASSIGN",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    multi_record=True,
)

# DEFINE — defines a UDQ expression. Format:
#   DEFINE <udq_name> <expression> /
# Each record is N items (variable name + expression tokens).
DEFINE = KeywordSpec(
    name="DEFINE",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    multi_record=True,
    first_column_is_name=True,
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
    # GRIDUNIT takes 1-3 unit strings (METRES, FEET, LAB, RES,
    # etc.) per record. Use wide UDA list; multi_record=True to
    # stay open across `/`. first_column_is_name is FALSE so that
    # data rows after GRIDUNIT are not absorbed.
    size_kind=SizeKind.LIST,
    items=[UDA] * 100,
    multi_record=True,
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
    size_kind=SizeKind.LIST,
    items=[STRING] * 6,  # HYSTER, DIRECT, MISCIBLE, SURFTENS, etc.
    multi_record=True,
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

# Additional RUNSPEC keywords (from OPM Reference Manual)
# ACTIVATION keywords (no parameters, just toggle a feature)
NONNC = KeywordSpec(
    name="NONNC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
DIFFUSE = KeywordSpec(
    name="DIFFUSE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
H2STORE = KeywordSpec(
    name="H2STORE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# STORE — request a save file (RM: SCHEDULE).
STORE = KeywordSpec(
    name="STORE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
NOSIM = KeywordSpec(
    name="NOSIM",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
POLYMER = KeywordSpec(
    name="POLYMER",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
FOAM = KeywordSpec(
    name="FOAM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
COAL = KeywordSpec(
    name="COAL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
ALKALINE = KeywordSpec(
    name="ALKALINE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
API = KeywordSpec(
    name="API",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
AUTOREF = KeywordSpec(
    name="AUTOREF",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
CBMOPTS = KeywordSpec(
    name="CBMOPTS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
CO2SOL = KeywordSpec(
    name="CO2SOL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
DUALPERM = KeywordSpec(
    name="DUALPERM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
DUALPORO = KeywordSpec(
    name="DUALPORO",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
ECLMC = KeywordSpec(
    name="ECLMC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
BIGMODEL = KeywordSpec(
    name="BIGMODEL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
BIOFILM = KeywordSpec(
    name="BIOFILM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
BPARA = KeywordSpec(
    name="BPARA",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# BPR — block pressure reporting (RM: SUMMARY). Multi-record list of (I, J, K1, K2).
BPR = KeywordSpec(
    name="BPR",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[INT, INT, INT, INT],
    multi_record=True,
)

CART = KeywordSpec(
    name="CART",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
CPR = KeywordSpec(
    name="CPR",
    sections=[SectionName.RUNSPEC, SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[STRING] + [INT] * 10,  # well_name, I, J, K1, K2 (multi-record, columnar)
    first_column_is_name=True,
    multi_record=True,
)
DISPDIMS = KeywordSpec(
    name="DISPDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
DYNRDIMS = KeywordSpec(
    name="DYNRDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
PARTTRAC = KeywordSpec(
    name="PARTTRAC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
PRECSALT = KeywordSpec(
    name="PRECSALT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
H2SOL = KeywordSpec(
    name="H2SOL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
MICP = KeywordSpec(
    name="MICP",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
BLACKOIL = KeywordSpec(
    name="BLACKOIL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
MONITOR = KeywordSpec(
    name="MONITOR",
    sections=[SectionName.RUNSPEC, SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
MSGFILE = KeywordSpec(
    name="MSGFILE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[STRING],  # MSGOPT
)
OPTIONS = KeywordSpec(
    name="OPTIONS",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
POLYPVM = KeywordSpec(
    name="POLYPVM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
RADIAL = KeywordSpec(
    name="RADIAL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
POLYMW = KeywordSpec(
    name="POLYMW",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
REFINE = KeywordSpec(
    name="REFINE",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS, SectionName.SCHEDULE, SectionName.SOLUTION],
    size_kind=SizeKind.NONE,
)
RUNSPEC = KeywordSpec(
    name="RUNSPEC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
TEMP = KeywordSpec(
    name="TEMP",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
OLDTRAN = KeywordSpec(
    name="OLDTRAN",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
PROPS = KeywordSpec(
    name="PROPS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
REGIONS = KeywordSpec(
    name="REGIONS",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.NONE,
)
SOLUTION = KeywordSpec(
    name="SOLUTION",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.NONE,
)
SUMMARY = KeywordSpec(
    name="SUMMARY",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
SCHEDULE = KeywordSpec(
    name="SCHEDULE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
PARALLEL = KeywordSpec(
    name="PARALLEL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, STRING],  # NPROCS, RTYPE
    record_count=1,
)
NEWTON = KeywordSpec(
    name="NEWTON",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
PERFORMA = KeywordSpec(
    name="PERFORMA",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
EXCEL = KeywordSpec(
    name="EXCEL",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
FMWSET = KeywordSpec(
    name="FMWSET",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
ALL = KeywordSpec(
    name="ALL",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
DATE = KeywordSpec(
    name="DATE",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
RUNSUM = KeywordSpec(
    name="RUNSUM",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)
RPTSMRY = KeywordSpec(
    name="RPTSMRY",
    sections=[SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[STRING],
)
SAVE = KeywordSpec(
    name="SAVE",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
SPIDER = KeywordSpec(
    name="SPIDER",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)
SLAVES = KeywordSpec(
    name="SLAVES",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING, STRING, STRING, INT],  # slave_name, master_file, path_pattern, slave_dir, num_cpus
    multi_record=True,
)

# VECTOR keywords (fixed number of parameters, terminated by /)
ROCKCOMP = KeywordSpec(
    name="ROCKCOMP",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[STRING, INT, STRING, STRING, DOUBLE],  # ROCKOPT, NTROCC, WATINOPT, PORTXROP, CARKZEXP
    record_count=1,
)
ACTPARAM = KeywordSpec(
    name="ACTPARAM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT, DOUBLE],  # TARGET, TOLERANCE
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
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.SCHEDULE],
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
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
TRANY = KeywordSpec(
    name="TRANY",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
TRANZ = KeywordSpec(
    name="TRANZ",
    sections=[SectionName.GRID, SectionName.EDIT],  # EDIT for multiplier scoping
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# Additional GRID keywords (from OPM Reference Manual)
DRV = KeywordSpec(
    name="DRV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
MULTX_MINUS = KeywordSpec(
    name="MULTX-",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
MULTY_MINUS = KeywordSpec(
    name="MULTY-",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
ADDZCORN = KeywordSpec(
    name="ADDZCORN",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
AMALGAM = KeywordSpec(
    name="AMALGAM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
AQUNNC = KeywordSpec(
    name="AQUNNC",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
AUTOCOAR = KeywordSpec(
    name="AUTOCOAR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
BTOBALFA = KeywordSpec(
    name="BTOBALFA",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
BTOBALFV = KeywordSpec(
    name="BTOBALFV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
COARSEN = KeywordSpec(
    name="COARSEN",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
COLLAPSE = KeywordSpec(
    name="COLLAPSE",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
COPYBOX = KeywordSpec(
    name="COPYBOX",
    sections=[SectionName.GRID, SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.NONE,
)
COPYREG = KeywordSpec(
    name="COPYREG",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS, SectionName.SOLUTION],
    size_kind=SizeKind.NONE,
)
CRITPERM = KeywordSpec(
    name="CRITPERM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMR = KeywordSpec(
    name="DIFFMR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMR_MINUS = KeywordSpec(
    name="DIFFMR-",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMTH_MINUS = KeywordSpec(
    name="DIFFMTH-",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMTHT = KeywordSpec(
    name="DIFFMTHT",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMX = KeywordSpec(
    name="DIFFMX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMX_MINUS = KeywordSpec(
    name="DIFFMX-",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMY = KeywordSpec(
    name="DIFFMY",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMY_MINUS = KeywordSpec(
    name="DIFFMY-",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMZ = KeywordSpec(
    name="DIFFMZ",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DIFFMZ_MINUS = KeywordSpec(
    name="DIFFMZ-",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DPGRID = KeywordSpec(
    name="DPGRID",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DPNUM = KeywordSpec(
    name="DPNUM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DTHETA = KeywordSpec(
    name="DTHETA",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
DUALPERM_GRID = KeywordSpec(
    name="DUALPERM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DUALPORO_GRID = KeywordSpec(
    name="DUALPORO",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DUMPFLUX = KeywordSpec(
    name="DUMPFLUX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DZMATRIX = KeywordSpec(
    name="DZMATRIX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DZMTRX = KeywordSpec(
    name="DZMTRX",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DZMTRXV = KeywordSpec(
    name="DZMTRXV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DZNET = KeywordSpec(
    name="DZNET",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
EQLZCORN = KeywordSpec(
    name="EQLZCORN",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
EXTFIN = KeywordSpec(
    name="EXTFIN",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
EXTHOST = KeywordSpec(
    name="EXTHOST",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
EXTREPGL = KeywordSpec(
    name="EXTREPGL",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
GDORIENT = KeywordSpec(
    name="GDORIENT",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING] * 6,
    first_column_is_name=True,
)
GDRILPOT = KeywordSpec(
    name="GDRILPOT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
GRDREACH = KeywordSpec(
    name="GRDREACH",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
LINKPERM = KeywordSpec(
    name="LINKPERM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DOMAINS = KeywordSpec(
    name="DOMAINS",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
DR = KeywordSpec(
    name="DR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
GRID = KeywordSpec(
    name="GRID",
    sections=[SectionName.GRID],
    size_kind=SizeKind.NONE,
)
HEATCR = KeywordSpec(
    name="HEATCR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
JFUNC = KeywordSpec(
    name="JFUNC",
    sections=[SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE] * 6,
    record_count=1,
)
NNC = KeywordSpec(
    name="NNC",
    sections=[SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[INT] * 17,  # I1, J1, K1, I2, J2, K2, TRANSNNC, ISATNUM1, ISATNUM2, IPRSNUM1, IPRSNUM2, FACE1, FACE2, DIFFNNC, DISPNNC, AREANNC, PERMNNC
    record_count=1,
)
OPERNUM = KeywordSpec(
    name="OPERNUM",
    sections=[SectionName.GRID, SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)
PERMTHT = KeywordSpec(
    name="PERMTHT",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
OUTRAD = KeywordSpec(
    name="OUTRAD",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
PCRIT = KeywordSpec(
    name="PCRIT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # up to 10 components
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

OPERATER = KeywordSpec(
    name="OPERATER",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, STRING, INT, DOUBLE, DOUBLE, STRING],  # ARRAY, REGION, EQUATION, ALPHA, BETA, ARRAY name
    multi_record=True,
)

MULTPV = KeywordSpec(
    name="MULTPV",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

EDIT = KeywordSpec(
    name="EDIT",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.NONE,
)

EDITNNCR = KeywordSpec(
    name="EDITNNCR",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.FIXED,
    items=[INT] * 14,  # I1, J1, K1, I2, J2, K2, TRANSNNC, ISATNUM1, ISATNUM2, IPRSNUM1, IPRSNUM2, FACE1, FACE2, DIFFNNC
    record_count=1,
)

DEPTH = KeywordSpec(
    name="DEPTH",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
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
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS, SectionName.SOLUTION],
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

# Additional PROPS keywords (from OPM Reference Manual)
WAGHYSTR = KeywordSpec(
    name="WAGHYSTR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
HYSTCHCK = KeywordSpec(
    name="HYSTCHCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
EHYSTRR = KeywordSpec(
    name="EHYSTRR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)

# PROPS: Relative permeability scaling arrays (from OPM Reference Manual)
KRGR = KeywordSpec(
    name="KRGR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
KRORG = KeywordSpec(
    name="KRORG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)
KRORW = KeywordSpec(
    name="KRORW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

# PROPS: Capillary pressure arrays (from OPM Reference Manual)
PCG = KeywordSpec(
    name="PCG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
PCW = KeywordSpec(
    name="PCW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# PROPS: Miscibility keywords (from OPM Reference Manual)
MISC = KeywordSpec(
    name="MISC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # SSOL, TSF, MISC - COLUMNAR_VECTOR (multi-row)
)
PMISC = KeywordSpec(
    name="PMISC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # PRESS, TSF, MISC - COLUMNAR_VECTOR (multi-row)
)
SGLPC = KeywordSpec(
    name="SGLPC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SWLPC = KeywordSpec(
    name="SWLPC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# PROPS: Polymer keywords (from OPM Reference Manual)
PLMIXPAR = KeywordSpec(
    name="PLMIXPAR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE],  # PLMVIS
    record_count=1,
)
PLYADS = KeywordSpec(
    name="PLYADS",
    sections=[SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 40,  # POLCON, POLRATIO pairs - COLUMNAR_VECTOR (multi-row)
)
PLYMAX = KeywordSpec(
    name="PLYMAX",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],  # POLCON, SALTCON
    record_count=1,
)
PLYSHLOG = KeywordSpec(
    name="PLYSHLOG",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 40,  # polymer_conc, multiplier (columnar)
    multi_record=True,
)
PLYVMH = KeywordSpec(
    name="PLYVMH",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE],  # MHA, GAMMA, KAPPA
    record_count=1,
)

# PROPS: Miscibility mixing (from OPM Reference Manual)
TLMIXPAR = KeywordSpec(
    name="TLMIXPAR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],  # TLMVIS, TLMDEN
    record_count=1,
)

# SPECHA / SPECHB / SPECHG / SPECHH — component specific enthalpy (PROPS, thermal)
for _sp in ("SPECHA", "SPECHB", "SPECHG", "SPECHH"):
    globals()[_sp] = KeywordSpec(
        name=_sp,
        sections=[SectionName.PROPS],
        size_kind=SizeKind.LIST,
        items=[DOUBLE] * 30,  # COLUMNAR_VECTOR (multi-row table)
    )

# TVDPF* — tracer initialisation tables (DEPTH, CONC pairs) for OPM tracers
for _tvd_name in (
    "TVDPFSEA", "TVDPFHTO", "TVDPFS36", "TVDPF2FB", "TVDPF4FB",
    "TVDPFDFB", "TVDPFTFB", "TVDPFWT1", "TVDPFWT2", "TVDPFGT1",
    "TVDPFGT2", "TVDPSGT1", "TVDPSGT2",
):
    globals()[_tvd_name] = KeywordSpec(
        name=_tvd_name,
        sections=[SectionName.SOLUTION],
        size_kind=SizeKind.LIST,
        items=[DOUBLE] * 200,  # DEPTH, CONC pairs (multi-row table)
    )

# TBLKFX/TBLKSX — transmissibility multipliers for tracers (SOLUTION)
for _tblk_name in (
    "TBLKFX11", "TBLKFX12", "TBLKSX11", "TBLKSX12",
    "TBLKFX21", "TBLKFX22", "TBLKSX21", "TBLKSX22",
):
    globals()[_tblk_name] = KeywordSpec(
        name=_tblk_name,
        sections=[SectionName.SOLUTION],
        size_kind=SizeKind.ARRAY,
        items=[DOUBLE],
    )
FOAMADS = KeywordSpec(
    name="FOAMADS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # foam_conc, adsorbed_conc (columnar)
    multi_record=True,
)
# PYACTION_* — Python action keywords (SCHEDULE).
# Some names contain '+' or '-' which aren't valid Python identifiers,
# so build them via dict instead of globals().
_PYACTION_SPECS: dict[str, KeywordSpec] = {
    "GEFAC_PYACTION": KeywordSpec(name="GEFAC_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "WEFAC_PYACTION": KeywordSpec(name="WEFAC_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "WLIST_PYACTION": KeywordSpec(name="WLIST_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "WTMULT_PYACTION": KeywordSpec(name="WTMULT_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "INCLUDE_PYACTION": KeywordSpec(name="INCLUDE_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "COMPDAT_PYACTION": KeywordSpec(name="COMPDAT_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "WCONPROD_PYACTION": KeywordSpec(name="WCONPROD_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "WPIMULT_PYACTION": KeywordSpec(name="WPIMULT_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "MULT+_PYACTION": KeywordSpec(name="MULT+_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "MULTX+_PYACTION": KeywordSpec(name="MULTX+_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "MULTX-_PYACTION": KeywordSpec(name="MULTX-_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "WSEGVALV_PYACTION": KeywordSpec(name="WSEGVALV_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "GCONPROD_PYACTION": KeywordSpec(name="GCONPROD_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
    "NEXT_PYACTION": KeywordSpec(name="NEXT_PYACTION", sections=[SectionName.SCHEDULE], size_kind=SizeKind.NONE),
}
for _pa_name, _pa_spec in _PYACTION_SPECS.items():
    globals()[_pa_name] = _pa_spec
# CO2STORE / compositional fluid keywords (OPM Reference Manual)
ZCRIT = KeywordSpec(
    name="ZCRIT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE, DOUBLE],  # ZCRITO, ZCRITW, ZCRITG
)
ZCRITVIS = KeywordSpec(
    name="ZCRITVIS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],  # viscosity values
)
STCOND = KeywordSpec(
    name="STCOND",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],  # TREF, COND
    record_count=1,
)
FIPZON = KeywordSpec(
    name="FIPZON",
    sections=[SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],  # ZONNUM value per cell
)
FIPABCDE = KeywordSpec(
    name="FIPABCDE",
    sections=[SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE, DOUBLE],  # A, B, C, D, E coefficients for FIP
)
ISTR = KeywordSpec(
    name="ISTR",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE],  # Max STTR, Min STTR, Min STTR-foam
    record_count=1,
)
# Compositional component properties (PROPS or SCHEDULE for time-varying)
DENO = KeywordSpec(
    name="DENO",
    sections=[SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
DENG = KeywordSpec(
    name="DENG",
    sections=[SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
VGAS = KeywordSpec(
    name="VGAS",
    sections=[SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
VOIL = KeywordSpec(
    name="VOIL",
    sections=[SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
FOAMOPTS = KeywordSpec(
    name="FOAMOPTS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMROCK = KeywordSpec(
    name="FOAMROCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    record_count=1,
    items=[INT, DOUBLE],  # desorption_flag, rock_density
)
COALADS = KeywordSpec(
    name="COALADS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
COALPP = KeywordSpec(
    name="COALPP",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ADSORP = KeywordSpec(
    name="ADSORP",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ALKADS = KeywordSpec(
    name="ALKADS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ALKROCK = KeywordSpec(
    name="ALKROCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ALPOLADS = KeywordSpec(
    name="ALPOLADS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ALSURFAD = KeywordSpec(
    name="ALSURFAD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ALSURFST = KeywordSpec(
    name="ALSURFST",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
BDENSITY = KeywordSpec(
    name="BDENSITY",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
BGGI = KeywordSpec(
    name="BGGI",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
BIC = KeywordSpec(
    name="BIC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
BOGI = KeywordSpec(
    name="BOGI",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFC = KeywordSpec(
    name="DIFFC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFCGAS = KeywordSpec(
    name="DIFFCGAS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFCOAL = KeywordSpec(
    name="DIFFCOAL",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFCWAT = KeywordSpec(
    name="DIFFCWAT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFDP = KeywordSpec(
    name="DIFFDP",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFMICP = KeywordSpec(
    name="DIFFMICP",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 3,  # MICR, OXYG, UREA diffusion coefficients
)
DIFFMMF = KeywordSpec(
    name="DIFFMMF",
    sections=[SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)
DISPERSE = KeywordSpec(
    name="DISPERSE",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DIFFAGAS = KeywordSpec(
    name="DIFFAGAS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # gas diffusion coefficient per PVT region
)
DIFFAWAT = KeywordSpec(
    name="DIFFAWAT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # aqueous diffusion coefficient per PVT region
)
DIFFR = KeywordSpec(
    name="DIFFR",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.NONE,
)
DIFFTHT = KeywordSpec(
    name="DIFFTHT",
    sections=[SectionName.EDIT],
    size_kind=SizeKind.NONE,
)
DSPDEINT = KeywordSpec(
    name="DSPDEINT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
DENAQA = KeywordSpec(
    name="DENAQA",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
ESSNODE = KeywordSpec(
    name="ESSNODE",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFACT = KeywordSpec(
    name="SURFACT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFACTW = KeywordSpec(
    name="SURFACTW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFADDW = KeywordSpec(
    name="SURFADDW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFADS = KeywordSpec(
    name="SURFADS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFCAPD = KeywordSpec(
    name="SURFCAPD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFESAL = KeywordSpec(
    name="SURFESAL",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFROCK = KeywordSpec(
    name="SURFROCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFST = KeywordSpec(
    name="SURFST",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFSTES = KeywordSpec(
    name="SURFSTES",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFVISC = KeywordSpec(
    name="SURFVISC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SURFWNUM = KeywordSpec(
    name="SURFWNUM",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMFCN = KeywordSpec(
    name="FOAMFCN",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMFRM = KeywordSpec(
    name="FOAMFRM",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMFSC = KeywordSpec(
    name="FOAMFSC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMFSO = KeywordSpec(
    name="FOAMFSO",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMFST = KeywordSpec(
    name="FOAMFST",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMFSW = KeywordSpec(
    name="FOAMFSW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
FOAMMOB = KeywordSpec(
    name="FOAMMOB",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # foam_conc, mobility_reduction (columnar)
    multi_record=True,
)
FOAMMOBP = KeywordSpec(
    name="FOAMMOBP",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,
    multi_record=True,
)
FOAMMOBS = KeywordSpec(
    name="FOAMMOBS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,
    multi_record=True,
)
FOAMDCYO = KeywordSpec(
    name="FOAMDCYO",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,
    multi_record=True,
)
FOAMDCYW = KeywordSpec(
    name="FOAMDCYW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
BIOFPARA = KeywordSpec(
    name="BIOFPARA",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 13,  # BDEN DEATH GROWTH HALF YIELD FACTOR ATACH DETRAT DETEXP UREA HALF CDEN YUTOC
    multi_record=True,
)
APIGROUP = KeywordSpec(
    name="APIGROUP",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
APIVD = KeywordSpec(
    name="APIVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.NONE,
)
ADSALNOD = KeywordSpec(
    name="ADSALNOD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)
SALTSOL = KeywordSpec(
    name="SALTSOL",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
ACF = KeywordSpec(
    name="ACF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # up to 10 components
)
GASDENT = KeywordSpec(
    name="GASDENT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE],  # TEMP, TEXP1, TEXP2
    record_count=1,
)
GASJT = KeywordSpec(
    name="GASJT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],  # PRESS, GASJTC
    record_count=1,
)
GASVISCT = KeywordSpec(
    name="GASVISCT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE],  # TEMP, VIS - COLUMNAR_VECTOR
)
GRAVITY = KeywordSpec(
    name="GRAVITY",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE],  # OILAPI, WATGRAV, GASGRAV
    record_count=1,
)
EOS = KeywordSpec(
    name="EOS",
    sections=[SectionName.PROPS, SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[STRING],  # EQUATION
)
KRWR = KeywordSpec(
    name="KRWR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
OILVISCT = KeywordSpec(
    name="OILVISCT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE],  # TEMP, VIS - COLUMNAR_VECTOR
)
OVERBURD = KeywordSpec(
    name="OVERBURD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # DEPTH, PRESS pairs - COLUMNAR_VECTOR
)
PPCWMAX = KeywordSpec(
    name="PPCWMAX",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE],  # PCWO, OPTN - COLUMNAR_VECTOR
)
PVTGW = KeywordSpec(
    name="PVTGW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 13,  # PRESS + up to 4 sub-rows of (RWS, FVFS, VISS) - COLUMNAR_VECTOR
)
ROCK2D = KeywordSpec(
    name="ROCK2D",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 30,  # PRESS + multiple MULT values - COLUMNAR_VECTOR (multi-table per region)
    multi_record=True,
)
ROCK2DTR = KeywordSpec(
    name="ROCK2DTR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 30,  # PRESS + multiple MULT values - COLUMNAR_VECTOR (multi-table per region)
    multi_record=True,
)
ROCKOPTS = KeywordSpec(
    name="ROCKOPTS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[STRING] * 4,  # ROCKOPT1, ROCKOPT2, ROCKOPT3, ROCKOPT4
)
RWGSALT = KeywordSpec(
    name="RWGSALT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # PRESS, SALTCON, RW - COLUMNAR_VECTOR
)
SGWFN = KeywordSpec(
    name="SGWFN",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # SGAS, KRG, KRW, PCGW - COLUMNAR_VECTOR (multi-row)
    multi_record=True,  # N tables per PVT region
)
SLGOF = KeywordSpec(
    name="SLGOF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # SLIQ, KRG, KRO, PCOG - COLUMNAR_VECTOR (multi-row)
)
ROCKWNOD = KeywordSpec(
    name="ROCKWNOD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 30,  # multiple SWAT + mult values per record (columnar, multi-record)
    multi_record=True,
)
RPTGRIDL = KeywordSpec(
    name="RPTGRIDL",
    sections=[SectionName.GRID],
    size_kind=SizeKind.FIXED,
    items=[STRING] * 6,  # ALLNCC, COORD, COORDYS, DEPTH, ALLNNC, EXTHOST
    record_count=1,
)
RPTONLY = KeywordSpec(
    name="RPTONLY",
    sections=[SectionName.SCHEDULE, SectionName.SUMMARY],
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

PLMIXNUM = KeywordSpec(
    name="PLMIXNUM",
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
FIP = KeywordSpec(
    name="FIP",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.FIXED,
    items=[STRING, INT],  # FIPNAME, FIPNUM
    record_count=1,
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

DATUM = KeywordSpec(
    name="DATUM",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)

# SOLUTION array keywords (per OPM Reference Manual)
RS = KeywordSpec(
    name="RS",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
RSW = KeywordSpec(
    name="RSW",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
RV = KeywordSpec(
    name="RV",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
RVW = KeywordSpec(
    name="RVW",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SALTP = KeywordSpec(
    name="SALTP",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SBIOF = KeywordSpec(
    name="SBIOF",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SCALC = KeywordSpec(
    name="SCALC",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SMICR = KeywordSpec(
    name="SMICR",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SOIL = KeywordSpec(
    name="SOIL",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SOXYG = KeywordSpec(
    name="SOXYG",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SSOL = KeywordSpec(
    name="SSOL",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
SALTPVD = KeywordSpec(
    name="SALTPVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 100,  # DEPTH, SALTSAT pairs - COLUMNAR_VECTOR (multi-row)
)
SUREA = KeywordSpec(
    name="SUREA",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
TEMPI = KeywordSpec(
    name="TEMPI",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

PRESSURE = KeywordSpec(
    name="PRESSURE",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

SGAS = KeywordSpec(
    name="SGAS",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
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
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, INT, INT, INT, INT, INT, INT, RAW_STRING, DOUBLE],
)

# AQUFLUX — aquifer flux (RM: SOLUTION/SCHEDULE).
AQUFLUX = KeywordSpec(
    name="AQUFLUX",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[INT, DOUBLE, DOUBLE, DOUBLE],
)

# AQUTAB — aquifer table (RM: PROPS). Many TD/PD pairs per record.
AQUTAB = KeywordSpec(
    name="AQUTAB",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 200,
    multi_record=True,
)

# NEXT — next time step control (RM: SCHEDULE).
NEXT = KeywordSpec(
    name="NEXT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, RAW_STRING],
)

# BCCON — boundary condition connect (RM: GRID).
BCCON = KeywordSpec(
    name="BCCON",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[INT, INT, INT, INT, INT, INT, RAW_STRING],
)

# BCPROP — boundary condition properties (RM: SCHEDULE).
BCPROP = KeywordSpec(
    name="BCPROP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[INT, RAW_STRING, RAW_STRING] + [UDA] * 7,
)

# DISPERC — dispersion (RM: GRID).
DISPERC = KeywordSpec(
    name="DISPERC",
    sections=[SectionName.GRID, SectionName.EDIT],
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
    "ALL", "DATE", "EXCEL", "FMWSET",
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
        DOUBLE,  # extra: WGASRATE / wet gas rate
    ],
    precise_items=False,  # fixtures have 12 columns; OPM manual has 19 params
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
    items=[STRING, RAW_STRING],
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
    first_column_is_name=True,
)
WEFAC = KeywordSpec(
    name="WEFAC",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, RAW_STRING],
    requires=["WELSPECS"],
    first_column_is_name=True,
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
    first_column_is_name=True,
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
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

WCONINJH = KeywordSpec(
    name="WCONINJH",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
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
    multi_record=True,
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
DRSDTCON = KeywordSpec(
    name="DRSDTCON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],  # CHI
)
DRSDTR = KeywordSpec(
    name="DRSDTR",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE],  # DRSDT1, DRSDT2
    record_count=1,
)

# Report flags (zero-item or simple flags)
RPTRST = KeywordSpec(
    name="RPTRST",
    sections=[SectionName.SCHEDULE, SectionName.SOLUTION, SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
    first_column_is_name=True,
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
    first_column_is_name=True,
)

# EQLOPTS — equilibration options. UDA list. Valid in RUNSPEC
# (option declaration), GRID, SOLUTION, and PROPS.
EQLOPTS = KeywordSpec(
    name="EQLOPTS",
    sections=[
        SectionName.RUNSPEC,
        SectionName.GRID,
        SectionName.PROPS,
        SectionName.SOLUTION,
    ],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# Common keywords missing from the original catalog. Added by
# corpus review — each fires >40 L171 across the test fixtures.

# Multipliers for grid array properties (RM: GRID section).
# Also valid in EDIT (edit-data operations) and SCHEDULE
# (some fixtures use them for restart).
MULTX = KeywordSpec(
    name="MULTX",
    sections=[
        SectionName.GRID,
        SectionName.EDIT,
        SectionName.SCHEDULE,
    ],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
MULTY = KeywordSpec(
    name="MULTY",
    sections=[
        SectionName.GRID,
        SectionName.EDIT,
        SectionName.SCHEDULE,
    ],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
MULTZ = KeywordSpec(
    name="MULTZ",
    sections=[
        SectionName.GRID,
        SectionName.EDIT,
        SectionName.SCHEDULE,
    ],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# ENDSCALE — endpoint scaling (RM: PROPS). Also accepted in
# RUNSPEC (declaration) and GRID (early declaration).
# ENDSCALE records frequently put direction tokens (NODIR,
# REVERS) on the next line at column 0. Set
# first_column_is_name=True so the parser absorbs them into
# the ENDSCALE record instead of treating them as new
# keywords.
ENDSCALE = KeywordSpec(
    name="ENDSCALE",
    sections=[
        SectionName.PROPS,
        SectionName.RUNSPEC,
        SectionName.GRID,
    ],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    first_column_is_name=True,
)

# MAPAXES — map axes (RM: RUNSPEC). Also accepted before the
# first section header (PRELUDE) and in GRID.
MAPAXES = KeywordSpec(
    name="MAPAXES",
    sections=[
        SectionName.RUNSPEC,
        SectionName.GRID,
        SectionName.PRELUDE,
    ],
    size_kind=SizeKind.FIXED,
    items=[DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, INT],
    record_count=1,
)

# FLUXNUM — flux region array (RM: GRID).
FLUXNUM = KeywordSpec(
    name="FLUXNUM",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# SCALECRS — scale crossover. Format:
#   SCALECRS
#     YES /        -- enable (scalar rel-perm direction)
#   or
#     NO  /        -- disable
# Take YES/NO as the first item, no fixed record length.
SCALECRS = KeywordSpec(
    name="SCALECRS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA],
    multi_record=False,
)

# MULTREGT — multi-region transmissibility (RM: GRID).
MULTREGT = KeywordSpec(
    name="MULTREGT",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# WECON — well economic limits (RM: SCHEDULE). Records start with well name.
WECON = KeywordSpec(
    name="WECON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WECONINJ — well economic injection criteria (RM: SCHEDULE). Records start with well name.
WECONINJ = KeywordSpec(
    name="WECONINJ",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[STRING, DOUBLE, STRING],  # WELNAME, MINVALUE, TYPE (RATE|POTN)
    record_count=1,
    first_column_is_name=True,
)

# WPAVE — well average pressure weighting (RM: SCHEDULE). Records start with well name.
WPAVE = KeywordSpec(
    name="WPAVE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.FIXED,
    items=[STRING, DOUBLE, DOUBLE, STRING, STRING],  # WELNAME, WPAVE1, WPAVE2, WPAVE3, WPAVE4
    record_count=1,
    first_column_is_name=True,
)

# WTRACER — well tracer (RM: SCHEDULE). Records start with well name.
WTRACER = KeywordSpec(
    name="WTRACER",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WTEST — well testing (RM: SCHEDULE). Records start with well name.
WTEST = KeywordSpec(
    name="WTEST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# GCONSALE — group consumption/sales (RM: SCHEDULE). Records start with group name.
GCONSALE = KeywordSpec(
    name="GCONSALE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    first_column_is_name=True,
)

# SWATINIT — initial water saturation array (RM: PROPS).
SWATINIT = KeywordSpec(
    name="SWATINIT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# RVVD — solution gas-oil ratio vs depth (RM: SOLUTION).
RVVD = KeywordSpec(
    name="RVVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

# PDVD — pressure vs depth (RM: SOLUTION).
PDVD = KeywordSpec(
    name="PDVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

# WRFTPLT — well RFT plot data (RM: SUMMARY). Records are 4
# items (well name + 3 plot flags), one record per well,
# separated by `/`. multi_record=True to stay open across
# record boundaries. Also valid in SCHEDULE (restart) and
# PRELUDE (declared before SUMMARY header).
WRFTPLT = KeywordSpec(
    name="WRFTPLT",
    sections=[
        SectionName.SUMMARY,
        SectionName.SCHEDULE,
        SectionName.PRELUDE,
    ],
    size_kind=SizeKind.LIST,
    # WRFTPLT records per the RM are 4 items (WELNAME + 3 plot
    # flags). The ceiling is widened to 25 UDA so the parser
    # tolerates include-resolver artefacts where WRFTPLT in a
    # PRELUDE-pseudo-section temporarily absorbs subsequent
    # WCONHIST/WCONINJH/WELSPECS/COMPDAT records (7-18 items)
    # before the resolver merges the include into its parent
    # section. Those absorbed records would otherwise fire L202
    # WARNINGs noisily. Real WRFTPLT records still have only 4
    # items.
    items=[UDA] * 25,
    multi_record=True,
    first_column_is_name=True,
)

# COMPORD — well completion order (RM: SCHEDULE). Records start with well name.
COMPORD = KeywordSpec(
    name="COMPORD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    first_column_is_name=True,
    requires=["WELSPECS"],
)

# COMPLUMP — well completion lumping (RM: SCHEDULE). Records start with well name.
COMPLUMP = KeywordSpec(
    name="COMPLUMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    first_column_is_name=True,
    requires=["WELSPECS"],
)

# COMPDATL — well completion data using LGR coordinates (RM: SCHEDULE).
COMPDATL = KeywordSpec(
    name="COMPDATL",
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

# COMPIMB — well imbibition completion data (RM: SCHEDULE).
COMPIMB = KeywordSpec(
    name="COMPIMB",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# COMPLMPL — well completion lumping parameters (RM: SCHEDULE).
COMPLMPL = KeywordSpec(
    name="COMPLMPL",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# COMPTRAJ — well trajectory data (RM: SCHEDULE).
COMPTRAJ = KeywordSpec(
    name="COMPTRAJ",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE, RAW_STRING, INT, RAW_STRING, INT, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# CSKIN — well connection skin factor (RM: SCHEDULE).
CSKIN = KeywordSpec(
    name="CSKIN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, INT, INT, INT, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# HYSTER — hysteresis option (RM: PROPS). Also valid in
# RUNSPEC (option declaration).
HYSTER = KeywordSpec(
    name="HYSTER",
    sections=[
        SectionName.PROPS,
        SectionName.RUNSPEC,
    ],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# EXTRAPMS — extrapolation method (RM: SOLUTION). Also valid
# in RUNSPEC (option declaration), SCHEDULE, PROPS, EDIT, GRID, REGIONS, SUMMARY.
EXTRAPMS = KeywordSpec(
    name="EXTRAPMS",
    sections=[
        SectionName.SOLUTION,
        SectionName.RUNSPEC,
        SectionName.SCHEDULE,
        SectionName.PROPS,
        SectionName.EDIT,
        SectionName.GRID,
        SectionName.REGIONS,
        SectionName.SUMMARY,
    ],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# CARFIN — carbonate finalization (RM: SCHEDULE). Also valid
# in GRID (declared early).
CARFIN = KeywordSpec(
    name="CARFIN",
    sections=[SectionName.SCHEDULE, SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# BOX / ENDBOX / ENDFIN — box / box-end / final section markers.
# Also valid in SCHEDULE (for some restart flows) and PRELUDE.
BOX = KeywordSpec(
    name="BOX",
    sections=[
        SectionName.GRID,
        SectionName.SCHEDULE,
        SectionName.EDIT,
    ],
    size_kind=SizeKind.LIST,
    items=[INT, INT, INT, INT, INT, INT],
    record_count=1,
)
ENDBOX = KeywordSpec(
    name="ENDBOX",
    sections=[
        SectionName.EDIT,
        SectionName.GRID,
        SectionName.PROPS,
        SectionName.REGIONS,
        SectionName.SCHEDULE,
        SectionName.SOLUTION,
        SectionName.PRELUDE,
    ],
    size_kind=SizeKind.NONE,
)
ENDFIN = KeywordSpec(
    name="ENDFIN",
    sections=[
        SectionName.SCHEDULE,
        SectionName.GRID,
    ],
    size_kind=SizeKind.NONE,
)

# UDQDIMS — user-defined quantity dimensions (RM: RUNSPEC).
UDQDIMS = KeywordSpec(
    name="UDQDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT] * 7,
    record_count=1,
)

# EDITNNC — edit non-neighbor connection (RM: EDIT).
EDITNNC = KeywordSpec(
    name="EDITNNC",
    sections=[SectionName.EDIT, SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# GUIDERAT — guide rate (RM: SCHEDULE).
GUIDERAT = KeywordSpec(
    name="GUIDERAT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# TRACER — tracer data (RM: PROPS, SUMMARY).
TRACER = KeywordSpec(
    name="TRACER",
    sections=[SectionName.PROPS, SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    first_column_is_name=True,
)

# IMBNUM — imbibition region array (RM: GRID, EDIT, REGIONS). Also
# valid in PRELUDE and PROPS.
IMBNUM = KeywordSpec(
    name="IMBNUM",
    sections=[
        SectionName.GRID,
        SectionName.EDIT,
        SectionName.PRELUDE,
        SectionName.REGIONS,
        SectionName.PROPS,
    ],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# WLIFTOPT — well lift optimization (RM: SCHEDULE).
WLIFTOPT = KeywordSpec(
    name="WLIFTOPT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    first_column_is_name=True,
)

# SOF3 — 3-phase oil saturation table (RM: PROPS). Each record
# is a wide row of up to ~120 items (one per gas-saturation step).
SOF3 = KeywordSpec(
    name="SOF3",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 200,
    multi_record=True,
)

# SGL — gas saturation table (RM: PROPS).
SGL = KeywordSpec(
    name="SGL",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# VFPPROD and VFPPROD<n> family — see VFP dict above.

# DEBUG — debug print control (RM: RUNSPEC, SOLUTION).
DEBUG = KeywordSpec(
    name="DEBUG",
    sections=[SectionName.RUNSPEC, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# PIMTDIMS — PI multiplier dimensions (RM: RUNSPEC).
PIMTDIMS = KeywordSpec(
    name="PIMTDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT] * 3,
    record_count=1,
)

# RPTPROPS — props report flags (RM: PROPS). Specifies which
# property arrays to print. Record is a list of UDA flags.
RPTPROPS = KeywordSpec(
    name="RPTPROPS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
    multi_record=True,
)

# SOGCR — critical oil-gas saturation (RM: PROPS).
SOGCR = KeywordSpec(
    name="SOGCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# ISGCR — injection critical gas saturation (RM: PROPS).
ISGCR = KeywordSpec(
    name="ISGCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# PVCDO — dead-oil PVT table (RM: PROPS). Pairs of (pressure,
# oil formation volume factor).
PVCDO = KeywordSpec(
    name="PVCDO",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE, DOUBLE],
)

# ACTIONW — "action when" block (RM: SCHEDULE). Sister to
# ACTIONX; same syntax (record list of UDA items).
ACTIONW = KeywordSpec(
    name="ACTIONW",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# WELPI — well PI override (RM: SCHEDULE). Each record is one
# well plus its PI multiplier.
WELPI = KeywordSpec(
    name="WELPI",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    multi_record=True,
    first_column_is_name=True,
)

# FIPABC — FIP region array ABC (RM: REGIONS). 3 arrays
# stacked: one int per (region, phase) combination.
FIPABC = KeywordSpec(
    name="FIPABC",
    sections=[SectionName.REGIONS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# ADD — REGIONS array addition (RM: REGIONS). One record per
# box-style region; values are region numbers.
ADD = KeywordSpec(
    name="ADD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[INT] * 10,
    multi_record=True,
)

# UDADIMS — UDA (user-defined analysis) dimensions (RM: RUNSPEC).
UDADIMS = KeywordSpec(
    name="UDADIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT] * 5,
    record_count=1,
)

# COORDSYS — coordinate system definition (RM: GRID).
COORDSYS = KeywordSpec(
    name="COORDSYS",
    sections=[SectionName.GRID, SectionName.PRELUDE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# SMRYDIMS — summary dimensions (RM: RUNSPEC).
SMRYDIMS = KeywordSpec(
    name="SMRYDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT] * 4,
    record_count=1,
)

# NETWORK / NODEPROP / BRANPROP — multisegment well network
# topology. NETWORK is the header (valid in RUNSPEC option
# declaration), NODEPROP defines nodes, BRANPROP defines
# branches. Also valid in SCHEDULE for restart.
NETWORK = KeywordSpec(
    name="NETWORK",
    sections=[SectionName.GRID, SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    record_count=1,
    items=[INT, INT],  # max_nodes, max_connections
)
NODEPROP = KeywordSpec(
    name="NODEPROP",
    sections=[SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    multi_record=True,
)
# BRANPROP — branch properties (RM: SCHEDULE). Records start with branch name (DOWNNODE).
BRANPROP = KeywordSpec(
    name="BRANPROP",
    sections=[SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING, INT, INT],
    first_column_is_name=True,
    multi_record=True,
)

# LIFTOPT — well lift optimization (RM: SCHEDULE).
LIFTOPT = KeywordSpec(
    name="LIFTOPT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# RTEMPVD — reservoir temperature vs depth (RM: SOLUTION).
RTEMPVD = KeywordSpec(
    name="RTEMPVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# GPMAINT — group maintenance (RM: SCHEDULE).
GPMAINT = KeywordSpec(
    name="GPMAINT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    first_column_is_name=True,
)

# MAXVALUE — maximum value for constraint (RM: SCHEDULE). Also
# valid in EDIT (max-value array for property edit).
MAXVALUE = KeywordSpec(
    name="MAXVALUE",
    sections=[SectionName.SCHEDULE, SectionName.EDIT],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# STONE1 — Stone's relative-permeability model #1 (RM: PROPS).
STONE1 = KeywordSpec(
    name="STONE1",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)

# STONE2 — Stone's relative-permeability model #2 (RM: PROPS).
STONE2 = KeywordSpec(
    name="STONE2",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)

# SKIPREST — skip rest of section (RM: any).
SKIPREST = KeywordSpec(
    name="SKIPREST",
    sections=[
        SectionName.RUNSPEC, SectionName.GRID, SectionName.EDIT,
        SectionName.PROPS, SectionName.REGIONS, SectionName.SOLUTION,
        SectionName.SUMMARY, SectionName.SCHEDULE, SectionName.PRELUDE,
    ],
    size_kind=SizeKind.NONE,
)

# WPOLYMER — well polymer concentration (RM: SCHEDULE).
WPOLYMER = KeywordSpec(
    name="WPOLYMER",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    multi_record=True,
)

# WSURFACE — well surface rates (RM: SCHEDULE).
WSURFACE = KeywordSpec(
    name="WSURFACE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    multi_record=True,
)

# DZV — cell dz array (RM: GRID, EDIT).
DZV = KeywordSpec(
    name="DZV",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# MAPUNITS — map units declaration (RM: RUNSPEC). Also valid
# in PRELUDE (declared before section header) and GRID.
MAPUNITS = KeywordSpec(
    name="MAPUNITS",
    sections=[SectionName.RUNSPEC, SectionName.PRELUDE, SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# INRAD — wellbore internal radius (RM: SCHEDULE). Also valid
# in GRID for early definition.
INRAD = KeywordSpec(
    name="INRAD",
    sections=[SectionName.SCHEDULE, SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    multi_record=True,
)

# PORV — pore-volume array (RM: GRID, EDIT).
PORV = KeywordSpec(
    name="PORV",
    sections=[SectionName.GRID, SectionName.EDIT],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# GCONSUMP — group consumption (RM: SCHEDULE). Records start with group name.
GCONSUMP = KeywordSpec(
    name="GCONSUMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
    multi_record=True,
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
    sections=list(SectionName),
    size_kind=SizeKind.NONE,
)

ECHO = KeywordSpec(
    name="ECHO",
    # ECHO is a runtime flag valid in any section (including
    # PRELUDE — Echo before any section header is fine).
    sections=list(SectionName),
    size_kind=SizeKind.NONE,
)

NOECHO = KeywordSpec(
    name="NOECHO",
    sections=list(SectionName),
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

# CO2STORE — CO2 storage option (RM: RUNSPEC)
CO2STORE = KeywordSpec(
    name="CO2STORE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# THERMAL — thermal option (RM: RUNSPEC)
THERMAL = KeywordSpec(
    name="THERMAL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# BRINE — brine tracking option (RM: RUNSPEC)
BRINE = KeywordSpec(
    name="BRINE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# GASWAT — gas-water system option (RM: RUNSPEC)
GASWAT = KeywordSpec(
    name="GASWAT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# DISGASW — dissolved gas in water option (RM: RUNSPEC)
DISGASW = KeywordSpec(
    name="DISGASW",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# VAPWAT — vaporized water option (RM: RUNSPEC)
VAPWAT = KeywordSpec(
    name="VAPWAT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# COMPS — compositional components (RM: RUNSPEC)
COMPS = KeywordSpec(
    name="COMPS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# NCOMPS — number of components (RM: PROPS)
NCOMPS = KeywordSpec(
    name="NCOMPS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.FIXED,
    items=[INT],
    record_count=1,
)

# UDTDIMS — UDT dimensions (RM: RUNSPEC)
UDTDIMS = KeywordSpec(
    name="UDTDIMS",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[INT] * 4,
    record_count=1,
)

# DXV/DYV — cell dx/dy arrays (RM: GRID)
DXV = KeywordSpec(
    name="DXV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)
DYV = KeywordSpec(
    name="DYV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)

# SALINITY — salinity tracking (RM: PROPS)
SALINITY = KeywordSpec(
    name="SALINITY",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# RTEMP — reservoir temperature (RM: PROPS/SOLUTION)
RTEMP = KeywordSpec(
    name="RTEMP",
    sections=[SectionName.PROPS, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# CNAMES — component names (RM: PROPS)
CNAMES = KeywordSpec(
    name="CNAMES",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    first_column_is_name=True,
)

# PVTWSALT — PVT water-salt (RM: PROPS)
PVTWSALT = KeywordSpec(
    name="PVTWSALT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 20,  # Salt, WFVF, cw, wvisc, wviscomp ... (columnar)
    multi_record=True,
)

# SALTVD — salt vs depth (RM: SOLUTION)
SALTVD = KeywordSpec(
    name="SALTVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# WSALT — well salt (RM: SCHEDULE)
WSALT = KeywordSpec(
    name="WSALT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE],
    first_column_is_name=True,
)

# SPECROCK — special rock (RM: PROPS)
SPECROCK = KeywordSpec(
    name="SPECROCK",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# THCONR — thermal conductivity (RM: GRID)
THCONR = KeywordSpec(
    name="THCONR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# UDT — user-defined tables (RM: SCHEDULE)
UDT = KeywordSpec(
    name="UDT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# WELLSTRE — wellstream (RM: SCHEDULE)
WELLSTRE = KeywordSpec(
    name="WELLSTRE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# WINJGAS — well inject gas (RM: SCHEDULE). Records start with well name.
WINJGAS = KeywordSpec(
    name="WINJGAS",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# CECON — economic limits (RM: SCHEDULE)
CECON = KeywordSpec(
    name="CECON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 7,  # well_name, econ_limits, ...
    first_column_is_name=True,
)

# AQUFETP — aquifer Fetkovich (RM: SCHEDULE/SOLUTION)
AQUFETP = KeywordSpec(
    name="AQUFETP",
    sections=[SectionName.SCHEDULE, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 15,
)

# AQUNUM — aquifer number (RM: GRID)
AQUNUM = KeywordSpec(
    name="AQUNUM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 15,
)

# AQUCON — aquifer connection (RM: GRID/SOLUTION)
AQUCON = KeywordSpec(
    name="AQUCON",
    sections=[SectionName.GRID, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 15,
)

# NOSIM — no simulation (RM: RUNSPEC/SCHEDULE)
NOSIM = KeywordSpec(
    name="NOSIM",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# DIFFUSE — diffusion option (RM: RUNSPEC)
DIFFUSE = KeywordSpec(
    name="DIFFUSE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# PRECSALT — precipitation of salt (RM: RUNSPEC)
PRECSALT = KeywordSpec(
    name="PRECSALT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# MULTPV — pore volume multiplier (RM: GRID/EDIT/SCHEDULE)
MULTPV = KeywordSpec(
    name="MULTPV",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# SALTSOL — salt solubility (RM: PROPS)
SALTSOL = KeywordSpec(
    name="SALTSOL",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE],  # solubility_limit (kg/m3), salt_density
    multi_record=True,
)

# PERMFACT — permeability factor (RM: PROPS)
PERMFACT = KeywordSpec(
    name="PERMFACT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE] * 30,  # up to 30 porosity/permeability pairs
    multi_record=True,
)

# PCFACT — capillary pressure factor (RM: PROPS)
PCFACT = KeywordSpec(
    name="PCFACT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE, DOUBLE] * 30,  # up to 30 porosity/capillary pressure pairs
    multi_record=True,
)

# BCCON — boundary condition connection (RM: GRID)
BCCON = KeywordSpec(
    name="BCCON",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# BCPROP — boundary condition properties (RM: SCHEDULE)
BCPROP = KeywordSpec(
    name="BCPROP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 15,
)

# DRSDTCON — Rs derivative constraint (RM: SCHEDULE)
DRSDTCON = KeywordSpec(
    name="DRSDTCON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# HEATCR — heat capacity rock (RM: GRID)
HEATCR = KeywordSpec(
    name="HEATCR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# TCRIT — critical temperature (RM: PROPS)
TCRIT = KeywordSpec(
    name="TCRIT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, DOUBLE],
)

# EOS — equation of state (RM: PROPS/RUNSPEC)
EOS = KeywordSpec(
    name="EOS",
    sections=[SectionName.PROPS, SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
    first_column_is_name=True,
)

# MECH — mechanical properties (RM: RUNSPEC).
MECH = KeywordSpec(
    name="MECH",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# MECHSOLV — mechanical solver options (RM: RUNSPEC).
MECHSOLV = KeywordSpec(
    name="MECHSOLV",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING],
)

# TPSA — two-phase stress analysis (RM: RUNSPEC).
TPSA = KeywordSpec(
    name="TPSA",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING],
)

# BIOTCOEF — Biot coefficient (RM: GRID).
BIOTCOEF = KeywordSpec(
    name="BIOTCOEF",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# SMODULUS — shear modulus (RM: GRID).
SMODULUS = KeywordSpec(
    name="SMODULUS",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# LAME — Lame parameter (RM: GRID).
LAME = KeywordSpec(
    name="LAME",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# CO2 — CO2 component (RM: RUNSPEC/PROPS)
CO2 = KeywordSpec(
    name="CO2",
    sections=[SectionName.RUNSPEC, SectionName.PROPS],
    size_kind=SizeKind.NONE,
)

# OPERATE — arithmetic operations on arrays (RM: EDIT/GRID/PROPS/REGIONS/SOLUTION)
OPERATE = KeywordSpec(
    name="OPERATE",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS, SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 12,
)

# WLIST — well list (RM: SCHEDULE)
WLIST = KeywordSpec(
    name="WLIST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# ROCKCOMP — rock compaction (RM: RUNSPEC)
ROCKCOMP = KeywordSpec(
    name="ROCKCOMP",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.FIXED,
    items=[STRING, INT, STRING, STRING, DOUBLE],  # ROCKOPT, NTROCC, WATINOPT, PORTXROP, CARKZEXP
    record_count=1,
)

# RADIAL — radial grid (RM: RUNSPEC)
RADIAL = KeywordSpec(
    name="RADIAL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# WGRUPCON — group constraints (RM: SCHEDULE)
WGRUPCON = KeywordSpec(
    name="WGRUPCON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# MSGFILE — message file (RM: RUNSPEC)
MSGFILE = KeywordSpec(
    name="MSGFILE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# WINJMULT — well injection multiplier (RM: SCHEDULE)
WINJMULT = KeywordSpec(
    name="WINJMULT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# H2STORE — hydrogen storage (RM: RUNSPEC)
H2STORE = KeywordSpec(
    name="H2STORE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# SPIDER — spider grid (RM: RUNSPEC)
SPIDER = KeywordSpec(
    name="SPIDER",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# GLIFTOPT — gas lift optimization (RM: SCHEDULE)
GLIFTOPT = KeywordSpec(
    name="GLIFTOPT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# GSATINJE — gas saturation injection (RM: SCHEDULE)
GSATINJE = KeywordSpec(
    name="GSATINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# PARALLEL — parallel simulation (RM: RUNSPEC)
PARALLEL = KeywordSpec(
    name="PARALLEL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# VAPPARS — vaporization parameters (RM: SOLUTION/SCHEDULE)
VAPPARS = KeywordSpec(
    name="VAPPARS",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# MULTNUM — region multiplier number (RM: GRID)
MULTNUM = KeywordSpec(
    name="MULTNUM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# ROCKTAB — rock table (RM: PROPS)
ROCKTAB = KeywordSpec(
    name="ROCKTAB",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 96,  # up to 32 rows * 3 columns
)

# BLACKOIL — black oil model (RM: RUNSPEC)
BLACKOIL = KeywordSpec(
    name="BLACKOIL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# OPTIONS — general options (RM: RUNSPEC)
OPTIONS = KeywordSpec(
    name="OPTIONS",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# POLYMER — polymer option (RM: RUNSPEC)
POLYMER = KeywordSpec(
    name="POLYMER",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# PRECSALT — precipitation of salt (RM: RUNSPEC)
PRECSALT = KeywordSpec(
    name="PRECSALT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# DIFFUSE — diffusion option (RM: RUNSPEC)
DIFFUSE = KeywordSpec(
    name="DIFFUSE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# NOSIM — no simulation (RM: RUNSPEC/SCHEDULE)
NOSIM = KeywordSpec(
    name="NOSIM",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# WINJTEMP — well injection temperature (RM: SCHEDULE)
WINJTEMP = KeywordSpec(
    name="WINJTEMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# GLIFTOPT — gas lift optimization (RM: SCHEDULE)
GLIFTOPT = KeywordSpec(
    name="GLIFTOPT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# GSATINJE — gas saturation injection (RM: SCHEDULE)
GSATINJE = KeywordSpec(
    name="GSATINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# VAPPARS — vaporization parameters (RM: SOLUTION/SCHEDULE)
VAPPARS = KeywordSpec(
    name="VAPPARS",
    sections=[SectionName.SOLUTION, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# MULTNUM — region multiplier number (RM: GRID)
MULTNUM = KeywordSpec(
    name="MULTNUM",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# ROCKTAB — rock table (RM: PROPS)
ROCKTAB = KeywordSpec(
    name="ROCKTAB",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 96,  # up to 32 rows * 3 columns
)

# DENAQA — aquifer density (RM: PROPS)
DENAQA = KeywordSpec(
    name="DENAQA",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# VISCAQA — aquifer viscosity (RM: PROPS)
VISCAQA = KeywordSpec(
    name="VISCAQA",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# BIC — binary interaction coefficient (RM: PROPS)
BIC = KeywordSpec(
    name="BIC",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# PARALLEL — parallel simulation (RM: RUNSPEC)
PARALLEL = KeywordSpec(
    name="PARALLEL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 5,
)

# OPTIONS — general options (RM: RUNSPEC)
OPTIONS = KeywordSpec(
    name="OPTIONS",
    sections=[SectionName.RUNSPEC, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# POLYMER — polymer option (RM: RUNSPEC)
POLYMER = KeywordSpec(
    name="POLYMER",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# PRECSALT — precipitation of salt (RM: RUNSPEC)
PRECSALT = KeywordSpec(
    name="PRECSALT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# DIFFUSE — diffusion option (RM: RUNSPEC)
DIFFUSE = KeywordSpec(
    name="DIFFUSE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# BLACKOIL — black oil model (RM: RUNSPEC)
BLACKOIL = KeywordSpec(
    name="BLACKOIL",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# H2STORE — hydrogen storage (RM: RUNSPEC)
H2STORE = KeywordSpec(
    name="H2STORE",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# SPIDER — spider grid (RM: RUNSPEC)
SPIDER = KeywordSpec(
    name="SPIDER",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# ZIPPY2 — tracer (RM: SCHEDULE)
ZIPPY2 = KeywordSpec(
    name="ZIPPY2",
    sections=[SectionName.SCHEDULE],
    # Takes a list of `key=value` STRING pairs terminated by `/`.
    # The tokenizer emits STRING for the quoted pairs (e.g.
    # `'SIM=4.2' 'MINSTEP=1E-6'`) and treats them as record items.
    size_kind=SizeKind.LIST,
    items=[STRING_REP],
)

# UDQPARAM — UDQ parameters (RM: RUNSPEC)
UDQPARAM = KeywordSpec(
    name="UDQPARAM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# SUMTHIN — summary output thinning (RM: SCHEDULE/SUMMARY)
SUMTHIN = KeywordSpec(
    name="SUMTHIN",
    sections=[SectionName.SCHEDULE, SectionName.SUMMARY],
    size_kind=SizeKind.LIST,
    items=[INT],  # SUMSTEP
)

# TUNINGDP — numerical tuning parameters (RM: SCHEDULE)
TUNINGDP = KeywordSpec(
    name="TUNINGDP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 6,  # TRGLCV, XXXLCV, TRGDDP, TRGDDS, TRGDDRS, TRGDDRV
)

# TRACITVD — tracer initialization vs depth (RM: PROPS)
TRACITVD = KeywordSpec(
    name="TRACITVD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.NONE,
)

# WARN — warning control (RM: all sections)
WARN = KeywordSpec(
    name="WARN",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.PROPS, SectionName.REGIONS, SectionName.RUNSPEC, SectionName.SCHEDULE, SectionName.SOLUTION, SectionName.SUMMARY],
    size_kind=SizeKind.NONE,
)

# WDFACCOR — well DFAC correlation (RM: SCHEDULE)
WDFACCOR = KeywordSpec(
    name="WDFACCOR",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, DOUBLE, DOUBLE],  # WELNAME, COEF1, COEF2, COEF3
)

# VCRIT — critical volume (RM: PROPS)
VCRIT = KeywordSpec(
    name="VCRIT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, DOUBLE],
)

# TOLCRIT — critical tolerance (RM: PROPS)
TOLCRIT = KeywordSpec(
    name="TOLCRIT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)

# MULTX- / MULTY- — negative direction multipliers (RM: GRID/EDIT/SCHEDULE)
MULTX_MINUS = KeywordSpec(
    name="MULTX-",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
MULTY_MINUS = KeywordSpec(
    name="MULTY-",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# GSF/WSF — gas/water saturation functions (RM: PROPS)
GSF = KeywordSpec(
    name="GSF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
)
WSF = KeywordSpec(
    name="WSF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 30,
)

# ZMFVD — salt function vs depth (RM: PROPS)
ZMFVD = KeywordSpec(
    name="ZMFVD",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# VFPPROD — VFP production table (RM: SCHEDULE)
VFPPROD = KeywordSpec(
    name="VFPPROD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 200,  # table_id, datum, depth, rates, WFR, GFR, THP, ALQ, BHP, units (multi-table)
    multi_record=True,
)

# MULTZ- — negative Z multiplier (RM: GRID/EDIT/SCHEDULE)
MULTZ_MINUS = KeywordSpec(
    name="MULTZ-",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# NETBALAN — network balance (RM: SCHEDULE)
NETBALAN = KeywordSpec(
    name="NETBALAN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# CSKIN — connection skin (RM: SCHEDULE). Records start with well name.
CSKIN = KeywordSpec(
    name="CSKIN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, INT, INT, INT, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WMICP — well multiphase inflow (RM: SCHEDULE). Records start with well name.
WMICP = KeywordSpec(
    name="WMICP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# GSATPROD — gas saturation production (RM: SCHEDULE). Records start with group name.
GSATPROD = KeywordSpec(
    name="GSATPROD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    first_column_is_name=True,
)

# RESTART — restart control (RM: SOLUTION)
RESTART = KeywordSpec(
    name="RESTART",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# GEFAC — group efficiency (RM: SCHEDULE). Records start with group name.
GEFAC = KeywordSpec(
    name="GEFAC",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# DTHETAV — theta angle (RM: GRID)
DTHETAV = KeywordSpec(
    name="DTHETAV",
    sections=[SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)

# WCYCLE — well cycle (RM: SCHEDULE). Records start with well name.
WCYCLE = KeywordSpec(
    name="WCYCLE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WSEGVALV — well segment valve (RM: SCHEDULE). Records start with well name.
WSEGVALV = KeywordSpec(
    name="WSEGVALV",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, DOUBLE, RAW_STRING, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# NUMRES — number of reservoirs (RM: RUNSPEC)
NUMRES = KeywordSpec(
    name="NUMRES",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# WTMULT — well transmissibility multiplier (RM: SCHEDULE). Records start with well name.
WTMULT = KeywordSpec(
    name="WTMULT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# NORSSPEC — no Rs spec (RM: RUNSPEC)
NORSSPEC = KeywordSpec(
    name="NORSSPEC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# NOINSPEC — no in spec (RM: RUNSPEC)
NOINSPEC = KeywordSpec(
    name="NOINSPEC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# PERMR — radial permeability (RM: GRID)
PERMR = KeywordSpec(
    name="PERMR",
    sections=[SectionName.GRID],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# LGR — local grid refinement (RM: RUNSPEC)
LGR = KeywordSpec(
    name="LGR",
    sections=[SectionName.RUNSPEC, SectionName.GRID],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
)

# ENDINC — end include (RM: all sections)
ENDINC = KeywordSpec(
    name="ENDINC",
    sections=list(SectionName),
    size_kind=SizeKind.NONE,
)

# NEXTSTEP — next timestep (RM: SCHEDULE)
NEXTSTEP = KeywordSpec(
    name="NEXTSTEP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# SOF2 — 3-phase oil saturation table (RM: PROPS)
SOF2 = KeywordSpec(
    name="SOF2",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 200,
    multi_record=True,
)

# SOLVENT — compositional solvent option (RM: RUNSPEC)
SOLVENT = KeywordSpec(
    name="SOLVENT",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# FULLIMP — fully implicit solver option (RM: RUNSPEC)
FULLIMP = KeywordSpec(
    name="FULLIMP",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# KRNUM directional multipliers (RM: GRID/EDIT/PROPS/REGIONS) - also in SCHEDULE for restart
KRNUMX = KeywordSpec(
    name="KRNUMX",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.PROPS, SectionName.REGIONS, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
KRNUMY = KeywordSpec(
    name="KRNUMY",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.PROPS, SectionName.REGIONS, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
KRNUMZ = KeywordSpec(
    name="KRNUMZ",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.PROPS, SectionName.REGIONS, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# IMBNUM directional multipliers (RM: GRID/EDIT/PRELUDE/REGIONS/PROPS)
IMBNUMX = KeywordSpec(
    name="IMBNUMX",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.PRELUDE, SectionName.REGIONS, SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)
IMBNUMY = KeywordSpec(
    name="IMBNUMY",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.PRELUDE, SectionName.REGIONS, SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)
IMBNUMZ = KeywordSpec(
    name="IMBNUMZ",
    sections=[SectionName.GRID, SectionName.EDIT, SectionName.PRELUDE, SectionName.REGIONS, SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[INT],
)

# SSFN — solvent saturation function (RM: PROPS). Table of
# (SGAS, SSFN) pairs. List of UDA items (variable width).
SSFN = KeywordSpec(
    name="SSFN",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# ISOWCR / ISWCR — imbibition critical saturations (RM: PROPS).
# Array keywords with single DOUBLE per cell.
ISOWCR = KeywordSpec(
    name="ISOWCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
ISWCR = KeywordSpec(
    name="ISWCR",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# SDENSITY — solvent density (RM: PROPS). Vector of density values.
SDENSITY = KeywordSpec(
    name="SDENSITY",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE],
)

# PVDS — solvent PVT table (RM: PROPS). Colummar vector of
# (PRESS, GFVF, GVISC) triples. Each record can have many items.
PVDS = KeywordSpec(
    name="PVDS",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 100,
    multi_record=True,
)

# WSOLVENT — well solvent fraction (RM: SCHEDULE).
# WELNAME SOLFRA /
WSOLVENT = KeywordSpec(
    name="WSOLVENT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE],
    first_column_is_name=True,
)

# SPECHEAT — specific heat table (RM: PROPS). Colummar vector of
# (TEMP, OILSHEAT, WATSHEAT, GASSHEAT) rows. Multiple rows per record
# terminated by `/`. Use wide UDA list to accommodate all rows.
SPECHEAT = KeywordSpec(
    name="SPECHEAT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# VISCREF — reference viscosity (RM: PROPS). Vector of (PRES, RS, API).
VISCREF = KeywordSpec(
    name="VISCREF",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
    multi_record=True,
)

# WATVISCT — water viscosity vs temperature (RM: PROPS). Colummar vector
# of (TEMP, VIS) pairs. Many rows per record.
WATVISCT = KeywordSpec(
    name="WATVISCT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# GASVISCT / OILVISCT — gas/oil viscosity vs temperature (RM: PROPS).
# Colummar vector of (TEMP, VIS) pairs.
GASVISCT = KeywordSpec(
    name="GASVISCT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)
OILVISCT = KeywordSpec(
    name="OILVISCT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# MW — molecular weight (RM: PROPS). Vector of weights (one per component).
MW = KeywordSpec(
    name="MW",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,  # up to 10 components
)

# PREFT — reference pressure (RM: PROPS). Single value or vector.
PREFT = KeywordSpec(
    name="PREFT",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,
)

# CVTYPE — component viscosity type (RM: PROPS). Controls viscosity model.
CVTYPE = KeywordSpec(
    name="CVTYPE",
    sections=[SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[RAW_STRING] * 5,
)

# CO2INJ — CO2 injection stream definition (RM: SCHEDULE).
CO2INJ = KeywordSpec(
    name="CO2INJ",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[DOUBLE] * 10,
)

# WELLSHUT — well shut-in control (RM: SCHEDULE).
WELLSHUT = KeywordSpec(
    name="WELLSHUT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 20,
    first_column_is_name=True,
)

# SALT — salt concentration array (RM: SOLUTION). Single array.
SALT = KeywordSpec(
    name="SALT",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# TEMPVD — temperature vs depth (RM: SOLUTION/PROPS). Colummar vector
# of (DEPTH, RTEMP) pairs. Multiple rows per record.
TEMPVD = KeywordSpec(
    name="TEMPVD",
    sections=[SectionName.SOLUTION, SectionName.PROPS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# RVWVD — solution gas-oil ratio vs depth (RM: SOLUTION). Colummar
# vector of (DEPTH, RVW) pairs. Multiple rows per record.
RVWVD = KeywordSpec(
    name="RVWVD",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[UDA] * 50,
    multi_record=True,
)

# YMF/AMF/WMF/XMF/ZMF — component mole fractions (RM: SOLUTION/PROPS).
# Vector of values (one per cell/block).
YMF = KeywordSpec(
    name="YMF",
    sections=[SectionName.SOLUTION, SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
AMF = KeywordSpec(
    name="AMF",
    sections=[SectionName.SOLUTION, SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
WMF = KeywordSpec(
    name="WMF",
    sections=[SectionName.SOLUTION, SectionName.PROPS],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
XMF = KeywordSpec(
    name="XMF",
    sections=[SectionName.SOLUTION, SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)
ZMF = KeywordSpec(
    name="ZMF",
    sections=[SectionName.SOLUTION, SectionName.PROPS, SectionName.SCHEDULE],
    size_kind=SizeKind.ARRAY,
    items=[DOUBLE],
)

# FBHPDEF — well flowing BHP default (RM: SCHEDULE). Zero-item keyword.
FBHPDEF = KeywordSpec(
    name="FBHPDEF",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# WVFPDP — well VFP differential pressure table (RM: SCHEDULE).
# Each record: WELNAME DELTAP MULTP
WVFPDP = KeywordSpec(
    name="WVFPDP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, DOUBLE, DOUBLE],
    first_column_is_name=True,
)

# SWU — water saturation region array (RM: PROPS/REGIONS). Can have many items.
SWU = KeywordSpec(
    name="SWU",
    sections=[SectionName.PROPS, SectionName.REGIONS],
    size_kind=SizeKind.LIST,
    items=[UDA] * 2000,
    multi_record=True,
)

# COMPDATL — well completion data using LGR coordinates (RM: SCHEDULE).
COMPDATL = KeywordSpec(
    name="COMPDATL",
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

# COMPIMB — well imbibition completion data (RM: SCHEDULE).
COMPIMB = KeywordSpec(
    name="COMPIMB",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# COMPLMPL — well completion lumping parameters (RM: SCHEDULE).
COMPLMPL = KeywordSpec(
    name="COMPLMPL",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, DOUBLE, DOUBLE, DOUBLE],
    requires=["WELSPECS"],
    first_column_is_name=True,
)

WELSPECL = KeywordSpec(
    name="WELSPECL",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 20,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WELTRAJ — well trajectory (RM: SCHEDULE).
WELTRAJ = KeywordSpec(
    name="WELTRAJ",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WFOAM — well foam properties (RM: SCHEDULE).
WFOAM = KeywordSpec(
    name="WFOAM",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WGRUPCON — well group control (RM: SCHEDULE).
WGRUPCON = KeywordSpec(
    name="WGRUPCON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WHEDREFD — well head reference depth (RM: SCHEDULE).
WHEDREFD = KeywordSpec(
    name="WHEDREFD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WHTEMP — well head temperature (RM: SCHEDULE).
WHTEMP = KeywordSpec(
    name="WHTEMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WINJCLN — well injection cleanup (RM: SCHEDULE).
WINJCLN = KeywordSpec(
    name="WINJCLN",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WINJDAM — well injection damage (RM: SCHEDULE).
WINJDAM = KeywordSpec(
    name="WINJDAM",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WINJFCNC — well injection function (RM: SCHEDULE).
WINJFCNC = KeywordSpec(
    name="WINJFCNC",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WINJMULT — well injection multiplier (RM: SCHEDULE).
WINJMULT = KeywordSpec(
    name="WINJMULT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WINJTEMP — well injection temperature (RM: SCHEDULE).
WINJTEMP = KeywordSpec(
    name="WINJTEMP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WLIST — well list (RM: SCHEDULE).
WLIST = KeywordSpec(
    name="WLIST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# WPAVEDEP — well average depth (RM: SCHEDULE).
WPAVEDEP = KeywordSpec(
    name="WPAVEDEP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WPIMULTL — well PI multiplier LGR (RM: SCHEDULE).
WPIMULTL = KeywordSpec(
    name="WPIMULTL",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WPITAB — well PI table (RM: SCHEDULE).
WPITAB = KeywordSpec(
    name="WPITAB",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WPMITAB — well PMI table (RM: SCHEDULE).
WPMITAB = KeywordSpec(
    name="WPMITAB",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WRFT — well RFT (RM: SCHEDULE).
WRFT = KeywordSpec(
    name="WRFT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WSEGAICD — well segment ICD (RM: SCHEDULE).
WSEGAICD = KeywordSpec(
    name="WSEGAICD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT] + [UDA] * 20,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WSEGPROP — well segment properties (RM: SCHEDULE).
WSEGPROP = KeywordSpec(
    name="WSEGPROP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WSEGSICD — well segment ICD (RM: SCHEDULE).
WSEGSICD = KeywordSpec(
    name="WSEGSICD",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, INT, INT] + [UDA] * 11,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WSKPTAB — well skip table (RM: SCHEDULE).
WSKPTAB = KeywordSpec(
    name="WSKPTAB",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WSURFACT — well surfactant (RM: SCHEDULE).
WSURFACT = KeywordSpec(
    name="WSURFACT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WVFPEXP — well VFP expansion (RM: SCHEDULE).
WVFPEXP = KeywordSpec(
    name="WVFPEXP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# WWPAVE — well water average (RM: SCHEDULE).
WWPAVE = KeywordSpec(
    name="WWPAVE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    requires=["WELSPECS"],
    first_column_is_name=True,
)

# Group keywords
# GCALECON — group calendar economic (RM: SCHEDULE).
GCALECON = KeywordSpec(
    name="GCALECON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GCONCAL — group calendar control (RM: SCHEDULE).
GCONCAL = KeywordSpec(
    name="GCONCAL",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GCONENG — group engineering control (RM: SCHEDULE).
GCONENG = KeywordSpec(
    name="GCONENG",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GCONPRI — group priority control (RM: SCHEDULE).
GCONPRI = KeywordSpec(
    name="GCONPRI",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GDCQECON — group DCQ economic (RM: SCHEDULE).
GDCQECON = KeywordSpec(
    name="GDCQECON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GECON — group economic control (RM: SCHEDULE).
GECON = KeywordSpec(
    name="GECON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GLIFTLIM — group gas lift limit (RM: SCHEDULE).
GLIFTLIM = KeywordSpec(
    name="GLIFTLIM",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GLIFTOPT — group gas lift optimization (RM: SCHEDULE).
GLIFTOPT = KeywordSpec(
    name="GLIFTOPT",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GRUPNET — group network (RM: SCHEDULE).
GRUPNET = KeywordSpec(
    name="GRUPNET",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GRUPTARG — group target (RM: SCHEDULE).
GRUPTARG = KeywordSpec(
    name="GRUPTARG",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

# GSATINJE — group satellite injection (RM: SCHEDULE).
GSATINJE = KeywordSpec(
    name="GSATINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
)

GNETINJE = KeywordSpec(
    name="GNETINJE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING, UDA, INT],
    first_column_is_name=True,
)

GRUPMAST = KeywordSpec(
    name="GRUPMAST",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING, STRING, UDA],  # master_group, slave_name, slave_group, target
    multi_record=True,
)

GRUPSLAV = KeywordSpec(
    name="GRUPSLAV",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.NONE,
)

# Network keywords
# BRANPROP — branch properties (RM: SCHEDULE).
BRANPROP = KeywordSpec(
    name="BRANPROP",
    sections=[SectionName.GRID, SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING, INT, INT],
    first_column_is_name=True,
    multi_record=True,
)

# NODEPROP — node properties (RM: SCHEDULE).
NODEPROP = KeywordSpec(
    name="NODEPROP",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
    first_column_is_name=True,
    multi_record=True,
)

# Tracer keywords
# SCDPTRAC — scale deposition tracer (RM: SCHEDULE).
SCDPTRAC = KeywordSpec(
    name="SCDPTRAC",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING] + [UDA] * 10,
)

# TBLK — tracer block (RM: SOLUTION).
TBLK = KeywordSpec(
    name="TBLK",
    sections=[SectionName.SOLUTION],
    size_kind=SizeKind.LIST,
    items=[STRING, STRING],
    first_column_is_name=True,
)

# CALTRAC — cal tracer (RM: SCHEDULE).
CALTRAC = KeywordSpec(
    name="CALTRAC",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# PARTTRAC — partition tracer (RM: RUNSPEC).
PARTTRAC = KeywordSpec(
    name="PARTTRAC",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
)

# UDQ keywords
# UDQPARAM — UDQ parameters (RM: RUNSPEC).
UDQPARAM = KeywordSpec(
    name="UDQPARAM",
    sections=[SectionName.RUNSPEC],
    size_kind=SizeKind.LIST,
    items=[UDA] * 10,
)

# LGR keywords
# LGRFREE — LGR free (RM: SCHEDULE).
LGRFREE = KeywordSpec(
    name="LGRFREE",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING],
    first_column_is_name=True,
)

# LGRLOCK — LGR lock (RM: SCHEDULE).
LGRLOCK = KeywordSpec(
    name="LGRLOCK",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING],
    first_column_is_name=True,
)

# LGROFF — LGR off (RM: SCHEDULE).
LGROFF = KeywordSpec(
    name="LGROFF",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING],
    first_column_is_name=True,
)

# LGRON — LGR on (RM: SCHEDULE).
LGRON = KeywordSpec(
    name="LGRON",
    sections=[SectionName.SCHEDULE],
    size_kind=SizeKind.LIST,
    items=[STRING],
    first_column_is_name=True,
)

# LGRCOPY — LGR copy (RM: EDIT, GRID, RUNSPEC).
LGRCOPY = KeywordSpec(
    name="LGRCOPY",
    sections=[SectionName.EDIT, SectionName.GRID, SectionName.RUNSPEC],
    size_kind=SizeKind.NONE,
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


# Register dynamically-generated keyword specs (added at module scope via for loops).
_register(
    ZCRIT, ZCRITVIS, STCOND, FIPZON, FIPABCDE, ISTR,
    DENO, DENG, VGAS, VOIL,
    TVDPFSEA, TVDPFHTO, TVDPFS36, TVDPF2FB, TVDPF4FB, TVDPFDFB, TVDPFTFB,
    TVDPFWT1, TVDPFWT2, TVDPFGT1, TVDPFGT2, TVDPSGT1, TVDPSGT2,
    TBLKFX11, TBLKFX12, TBLKSX11, TBLKSX12,
    SPECHA, SPECHB, SPECHG, SPECHH,
    GEFAC_PYACTION, WEFAC_PYACTION, WLIST_PYACTION, WTMULT_PYACTION,
    INCLUDE_PYACTION, COMPDAT_PYACTION, WCONPROD_PYACTION, WPIMULT_PYACTION,
    WSEGVALV_PYACTION, GCONPROD_PYACTION, NEXT_PYACTION,
)
_register_dict(_PYACTION_SPECS)


# Register all keywords
_register(
    DIMENS, TABDIMS, WELLDIMS, EQLDIMS, REGDIMS,
    TITLE, START, METRIC, FIELD, UNITS,
    ACTDIMS, AQUDIMS, FAULTDIM, GRIDUNIT, MESSAGES,
    NUPCOL, NSTACK, SATOPTS, SPECGRID, VFPIDIMS, WSEGDIMS,
    # RUNSPEC additions
    NONNC, ROCKCOMP, DIFFUSE, H2STORE, H2SOL, NOSIM, POLYMER, FOAM, COAL, ALKALINE,
    API, AUTOREF, CBMOPTS, CO2SOL, DUALPERM, DUALPORO, ECLMC, ACTPARAM,
    BIGMODEL, BIOFILM, BPARA, CART, CPR, DISPDIMS, DYNRDIMS,
    PARTTRAC, PRECSALT, MICP, BLACKOIL, MONITOR, MSGFILE,
    OPTIONS, RADIAL, POLYPVM,
    PARALLEL,
    REFINE, OLDTRAN, PROPS, REGIONS, SOLUTION, SUMMARY, SCHEDULE,
    DX, DY, DZ, PORO, PERMX, PERMY, PERMZ, TOPS, COORD, ZCORN, GRIDFILE,
    NTG, FAULTS, MULTFLT, TRANX, TRANY, TRANZ,
    # GRID additions
    DRV, MULTX_MINUS, MULTY_MINUS, ADDZCORN, AMALGAM, AQUNNC, AUTOCOAR,
    BTOBALFA, BTOBALFV, COARSEN, COLLAPSE, COPYBOX, COPYREG, CRITPERM,
    DIFFMR, DIFFMR_MINUS, DIFFMTH_MINUS, DIFFMTHT, DIFFMX, DIFFMX_MINUS,
    DIFFMY, DIFFMY_MINUS, DIFFMZ, DIFFMZ_MINUS, DPGRID, DPNUM, DTHETA,
    DUALPERM_GRID, DUALPORO_GRID, DUMPFLUX, DZMATRIX, DZMTRX, DZMTRXV,
    DZNET, EQLZCORN, EXTFIN, EXTHOST, EXTREPGL, GDORIENT, GDRILPOT,
    GRDREACH, LINKPERM, DOMAINS, DR,
    GRID, HEATCR, JFUNC, MULTNUM,
    EQUALS, COPY, MULTIPLY, OPERATE, OPERATER, MULTPV, EDIT, EDITNNCR, DEPTH, ADDREG, MULTIREG, EQUALREG,
    SWOF, SGOF, SGFN, SWFN, PVDO, PVTO, PVTG, PVTW, PVDG, ROCK, DENSITY,
    BGSAT, SWL, SWCR, SOWCR, SGCR, SGU,
    KRW, KRO, KRG, PLYVISC, PLYROCK, PLYSHEAR,
    FIPNUM, FIPSEP, EQLNUM, SATNUM, PVTNUM, ROCKNUM,
    EQUIL, RSVD, DATUM, PRESSURE, SGAS, SWAT, PBVD, THPRES, EHYSTR, FILLEPS, RES,
    AQUCHG, AQUFET, AQUFLUX, AQUCT, AQUANCON,
    WELSPECS, COMPDAT, COMPDATL, COMPIMB, COMPLMPL, COMPLUMP, COMPORD, COMPTRAJ, CSKIN,
    WCONPROD, WCONINJE, WCONINJH, WCONHIST, TSTEP, TUNING,
    DATES, WELOPEN, NEWTRAN, GRUPTREE, GCONPROD, GCONINJE,
    WPIMULT, WTEMP, DRSDT, INIT, VFPPDIMS,
    WELTARG, WEFAC, MINPV, MINPVV, PINCH, SEPARATE,
    WSEGAQD, WSEGDEFV, WSEGITER, COMPSEGS,
    ACTIONX, ENDACTIO, PYACTION, UDQ, FU_DECL, FUNVAR, END, SUMMARY,
    RPTRST, RPTSCHED, RPTSOL, RPTGRID, UNIFOUT, UNIFIN, NOECHO, ECHO,
    GRIDOPTS, TRACERS,
    INCLUDE, IMPORT, PATHS,
    WELSEGS, EQLOPTS, ACTNUM,
    MULTX, MULTY, MULTZ, ENDSCALE, MAPAXES, FLUXNUM, SCALECRS,
    MULTREGT, WECON, WTRACER, WTEST, GCONSALE, SWATINIT, RVVD,
    PDVD, WRFTPLT, COMPORD, COMPLUMP, HYSTER, EXTRAPMS, CARFIN,
    BOX, ENDBOX, ENDFIN, UDQDIMS, EDITNNC, GUIDERAT, TRACER,
    IMBNUM, WLIFTOPT, SOF3, SGL,
    ASSIGN, DEFINE,
    DEBUG, PIMTDIMS, RPTPROPS, SOGCR, ISGCR, PVCDO, ACTIONW,
    WELPI, FIPABC, FIP, ADD,
    UDADIMS, COORDSYS, SMRYDIMS, NETWORK, NODEPROP, BRANPROP,
    LIFTOPT, RTEMPVD, GPMAINT, MAXVALUE, STONE1, STONE2,
    SKIPREST, WPOLYMER, WSURFACE, DZV, MAPUNITS, INRAD, PORV,
    GCONSUMP,
    # Unit keywords
    METRES, FEET, CM, LAB,
    # Boolean flags
    YES, NO,
    # New high-frequency RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE keywords
    CO2STORE, THERMAL, BRINE, GASWAT, DISGASW, VAPWAT, COMPS, NCOMPS, UDTDIMS,
    DXV, DYV, SALINITY, RTEMP, CNAMES, PVTWSALT, SALTVD, WSALT, SPECROCK, THCONR, UDT,
    WELLSTRE, WINJGAS, CECON,
    AQUFETP, AQUNUM, AQUCON,
    GSF, WSF, ZMFVD,
    # More high-frequency real keywords
    VFPPROD, MULTZ_MINUS, SWU, NETBALAN, CSKIN, WMICP, GSATPROD, RESTART,
    GEFAC, DTHETAV, WCYCLE, WSEGVALV, NUMRES, WTMULT, NORSSPEC, NOINSPEC,
    PERMR, LGR, ENDINC, NEXTSTEP, SOF2,
    # Newly added from L171 analysis
    SOLVENT, FULLIMP,
    KRNUMX, KRNUMY, KRNUMZ,
    IMBNUMX, IMBNUMY, IMBNUMZ,
    SSFN, ISOWCR, ISWCR, SDENSITY, PVDS, WSOLVENT,
    SPECHEAT, VISCREF, WATVISCT, SALT, TEMPVD, RVWVD,
    FBHPDEF, WVFPDP,
    PREFT, CVTYPE, CO2INJ,
    STORE,
    MECH, MECHSOLV, TPSA,
    BIOTCOEF, SMODULUS, LAME,
    # Missing aquifer keywords
    AQUFLUX, AQUTAB,
    # Next step control
    NEXT,
    # Boundary conditions
    BCCON, BCPROP,
    # Dispersion
    DISPERC,
    # Missing PROPS keywords (thermal/compositional)
    YMF, AMF, WMF, XMF, ZMF,
    # Missing well keywords (first_column_is_name)
    WELSPECL, WELTRAJ, WFOAM, WGRUPCON, WHEDREFD, WHTEMP,
    WINJCLN, WINJDAM, WINJFCNC, WINJMULT, WINJTEMP,
    WLIST, WPAVEDEP, WPIMULTL, WPITAB, WPMITAB, WRFT,
    WSEGAICD, WSEGPROP, WSEGSICD, WSKPTAB, WSURFACT, WVFPEXP, WWPAVE,
    # Missing group keywords
    GCALECON, GCONCAL, GCONENG, GCONPRI, GDCQECON, GECON,
    GLIFTLIM, GLIFTOPT, GRUPNET, GRUPTARG, GSATINJE,
    # Network keywords
    BRANPROP, NODEPROP,
    # Tracer keywords
    SCDPTRAC, TBLK, CALTRAC, PARTTRAC,
    # UDQ keywords
    UDQPARAM,
    # LGR keywords
    LGRFREE, LGRLOCK, LGROFF, LGRON, LGRCOPY,
    # Additional PROPS keywords
    WAGHYSTR, HYSTCHCK, EHYSTRR, FOAMADS, FOAMOPTS, FOAMROCK,
    COALADS, COALPP, ADSORP, ALKADS, ALKROCK, ALPOLADS, ALSURFAD, ALSURFST,
    BDENSITY, BGGI, BIC, BOGI, DIFFC, DIFFCGAS, DIFFCOAL, DIFFCWAT,
    DIFFDP, DIFFMICP, DIFFMMF, DISPERSE, DIFFAGAS, DIFFAWAT, DIFFR, DIFFTHT,
    DSPDEINT, DENAQA, ESSNODE, SURFACT, SURFACTW, SURFADDW, SURFADS, SURFCAPD,
    SURFESAL, SURFROCK, SURFST, SURFSTES, SURFVISC, SURFWNUM,
    FOAMFCN, FOAMFRM, FOAMFSC, FOAMFSO, FOAMFST, FOAMFSW, FOAMMOB, FOAMMOBP,
    FOAMMOBS, FOAMDCYO, FOAMDCYW, BIOFPARA, APIGROUP, APIVD, ADSALNOD,
    PERMFACT, PCFACT, SALTSOL,
    ACF, GASDENT, GASJT, GASVISCT, GRAVITY, EOS, KRWR, MW,
    OILVISCT, OVERBURD, PPCWMAX, PVTGW,
    # Additional SCHEDULE keywords
    DRSDTCON, DRSDTR, GNETINJE, GRUPMAST, GRUPSLAV,
    # Missing keywords
    WELLSHUT,
    # Additional SUMMARY keywords
    NEWTON, PERFORMA, EXCEL, FMWSET, ALL, DATE,
    # Additional REGIONS keywords
    PLMIXNUM,
    # Additional GRID keywords
    NNC, OPERNUM, PERMTHT, OUTRAD, PCRIT,
    # Additional PROPS keywords (rock)
    ROCK2D, ROCK2DTR, ROCKOPTS, ROCKTAB, ROCKWNOD,
    RPTGRIDL, RPTONLY,
    # Additional PROPS keywords (relative permeability scaling, capillary pressure, miscibility, polymer)
    KRGR, KRORG, KRORW, PCG, PCW, MISC, PMISC, SGLPC, SWLPC,
    PLMIXPAR, PLYADS, PLYMAX, PLYSHLOG, PLYVMH, TLMIXPAR,
    # Additional SOLUTION keywords
    RS, RSW, RV, RVW, SALTP, SBIOF, SCALC, SMICR, SOIL, SOXYG, SSOL, SALTPVD,
    # Additional PROPS keywords (water/gas)
    RWGSALT, SGWFN, SLGOF,
    # Additional SCHEDULE keywords
    DRSDTCON, DRSDTR, GNETINJE, GRUPMAST, GRUPSLAV,
    WECONINJ, WPAVE,
    # Additional SUMMARY keywords
    NEWTON, PERFORMA, EXCEL, FMWSET, ALL, DATE,
    # Additional REGIONS keywords
    PLMIXNUM,
    # Additional GRID keywords
    NNC, OPERNUM, PERMTHT, OUTRAD, PCRIT,
    # Additional RUNSPEC/SUMMARY/SCHEDULE keywords
    SPIDER, SLAVES, SAVE, RUNSUM, RPTSMRY,
    # Additional keywords from fixtures
    POLYMW, RUNSPEC, SUMTHIN, SUREA, TCRIT, TEMP, TEMPI, TOLCRIT, TRACITVD,
    TUNINGDP, VAPPARS, VCRIT, VISCAQA, WARN, WDFACCOR, ZIPPY2,
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