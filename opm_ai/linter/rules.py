# opm_ai/linter/rules.py
"""
Static rule engine — fast regex/parse checks that run before the LLM.

Each rule is a function:
    rule_fn(deck_text: str) -> list[DeckDiagnostic]

Rules are registered in RULES list at the bottom of this file.
The linter runs all rules in sequence and aggregates results.
"""
import re
from typing import Callable
from .models import DeckDiagnostic, DiagnosticSeverity

RuleFn = Callable[[str], list[DeckDiagnostic]]


# ── helpers ───────────────────────────────────────────────────────────────

def _diag(
    rule_id: str,
    severity: DiagnosticSeverity,
    keyword: str,
    raw_message: str,
    plain_english: str,
    fix_hint: str,
    line: int | None = None,
) -> DeckDiagnostic:
    return DeckDiagnostic(
        severity=severity,
        keyword=keyword,
        line=line,
        raw_message=raw_message,
        plain_english=plain_english,
        fix_hint=fix_hint,
        rule_id=rule_id,
    )


def _find_line(deck_text: str, pattern: re.Pattern) -> int | None:
    """Return 1-based line number of first match, or None."""
    for i, line in enumerate(deck_text.splitlines(), start=1):
        if pattern.search(line):
            return i
    return None


# ── Section rules ───────────────────────────────────────────────────────────

REQUIRED_SECTIONS = ["RUNSPEC", "GRID", "PROPS", "SOLUTION", "SCHEDULE"]


def rule_required_sections(deck_text: str) -> list[DeckDiagnostic]:
    """R001 — All five mandatory sections must be present."""
    findings = []
    for section in REQUIRED_SECTIONS:
        if not re.search(rf"^\s*{section}\b", deck_text, re.MULTILINE):
            findings.append(_diag(
                rule_id="R001",
                severity=DiagnosticSeverity.FATAL,
                keyword=section,
                raw_message=f"Section {section} not found in deck",
                plain_english=f"The {section} section is missing entirely from your deck.",
                fix_hint=f"Add a '{section}' keyword on its own line to start that section.",
            ))
    return findings


def rule_end_keyword(deck_text: str) -> list[DeckDiagnostic]:
    """R002 — SCHEDULE section must end with END keyword."""
    if re.search(r"^\s*SCHEDULE\b", deck_text, re.MULTILINE):
        if not re.search(r"^\s*END\s*$", deck_text, re.MULTILINE):
            return [_diag(
                rule_id="R002",
                severity=DiagnosticSeverity.FATAL,
                keyword="END",
                raw_message="END keyword not found after SCHEDULE",
                plain_english="Your deck has no END keyword. OPM Flow will not know where the simulation stops.",
                fix_hint="Add 'END' on its own line at the very end of the deck.",
            )]
    return []


# ── RUNSPEC rules ───────────────────────────────────────────────────────────

def rule_dimens(deck_text: str) -> list[DeckDiagnostic]:
    """R003 — DIMENS must be declared in RUNSPEC with three positive integers."""
    if not re.search(r"^\s*DIMENS\b", deck_text, re.MULTILINE):
        return [_diag(
            rule_id="R003",
            severity=DiagnosticSeverity.FATAL,
            keyword="DIMENS",
            raw_message="DIMENS keyword missing",
            plain_english="DIMENS is missing. OPM Flow needs to know the grid dimensions (NX NY NZ).",
            fix_hint="Under RUNSPEC add: DIMENS\n  <NX> <NY> <NZ> /",
        )]
    # Check values are three positive integers
    m = re.search(r"^\s*DIMENS\s*\n\s*(\d+)\s+(\d+)\s+(\d+)", deck_text, re.MULTILINE)
    if m:
        nx, ny, nz = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 in (nx, ny, nz):
            return [_diag(
                rule_id="R003",
                severity=DiagnosticSeverity.FATAL,
                keyword="DIMENS",
                raw_message=f"DIMENS has zero dimension: {nx} {ny} {nz}",
                plain_english=f"DIMENS has a zero value ({nx} {ny} {nz}). Grid dimensions must all be positive.",
                fix_hint="Replace the zero value in DIMENS with a positive integer (minimum 1).",
                line=_find_line(deck_text, re.compile(r"^\s*DIMENS\b")),
            )]
    return []


def rule_nwell(deck_text: str) -> list[DeckDiagnostic]:
    """R004 — WELLDIMS should be declared if WELSPECS is present."""
    has_welspecs  = bool(re.search(r"^\s*WELSPECS\b", deck_text, re.MULTILINE))
    has_welldims  = bool(re.search(r"^\s*WELLDIMS\b", deck_text, re.MULTILINE))
    if has_welspecs and not has_welldims:
        return [_diag(
            rule_id="R004",
            severity=DiagnosticSeverity.WARNING,
            keyword="WELLDIMS",
            raw_message="WELSPECS present but WELLDIMS not declared in RUNSPEC",
            plain_english="You defined wells with WELSPECS but never told OPM how many wells to expect (WELLDIMS).",
            fix_hint="Add WELLDIMS in RUNSPEC: WELLDIMS\n  <max_wells> <max_connections> <max_groups> <max_wells_in_group> /",
        )]
    return []


# ── GRID rules ───────────────────────────────────────────────────────────────

def rule_grid_source(deck_text: str) -> list[DeckDiagnostic]:
    """R005 — GRID section must have either INCLUDE, COORD/ZCORN, or DX/DY/DZ."""
    in_grid = False
    grid_block = []
    for line in deck_text.splitlines():
        if re.match(r"^\s*GRID\b", line):    in_grid = True
        if re.match(r"^\s*PROPS\b", line):   in_grid = False
        if in_grid: grid_block.append(line)

    if not grid_block:
        return []

    block = "\n".join(grid_block)
    has_grid_source = any(re.search(p, block, re.MULTILINE) for p in [
        r"^\s*INCLUDE\b", r"^\s*COORD\b", r"^\s*ZCORN\b",
        r"^\s*DX\b",    r"^\s*DY\b",    r"^\s*DZ\b",
        r"^\s*GDFILE\b",
    ])
    if not has_grid_source:
        return [_diag(
            rule_id="R005",
            severity=DiagnosticSeverity.FATAL,
            keyword="GRID",
            raw_message="No grid geometry source found in GRID section",
            plain_english="The GRID section has no geometry. OPM needs either cell dimensions (DX/DY/DZ) or corner-point data (COORD/ZCORN) or an INCLUDE file.",
            fix_hint="Add DX, DY, DZ arrays or use INCLUDE to pull in a .GRDECL file.",
        )]
    return []


# ── PROPS rules ──────────────────────────────────────────────────────────────

def rule_pvt_tables(deck_text: str) -> list[DeckDiagnostic]:
    """R006 — At least one PVT table must be present (PVTO/PVTW/PVDG/PVTG/PVCDO)."""
    pvt_keywords = ["PVTO", "PVTW", "PVDG", "PVTG", "PVCDO", "PVCO"]
    has_pvt = any(
        re.search(rf"^\s*{kw}\b", deck_text, re.MULTILINE)
        for kw in pvt_keywords
    )
    if not has_pvt:
        return [_diag(
            rule_id="R006",
            severity=DiagnosticSeverity.FATAL,
            keyword="PROPS",
            raw_message="No PVT table keyword found in deck",
            plain_english="No fluid PVT data found. OPM cannot model fluid flow without knowing how oil/gas/water behave at reservoir pressure.",
            fix_hint="Add PVTW (for water), PVDG (dry gas), or PVTO (live oil) tables in the PROPS section.",
        )]
    return []


def rule_saturation_tables(deck_text: str) -> list[DeckDiagnostic]:
    """R007 — At least one saturation table must be present (SWOF/SGOF/SWFN/SGFN/SOF3)."""
    sat_keywords = ["SWOF", "SGOF", "SWFN", "SGFN", "SOF3", "SWOF", "SLGOF"]
    has_sat = any(
        re.search(rf"^\s*{kw}\b", deck_text, re.MULTILINE)
        for kw in sat_keywords
    )
    if not has_sat:
        return [_diag(
            rule_id="R007",
            severity=DiagnosticSeverity.FATAL,
            keyword="PROPS",
            raw_message="No saturation table keyword found in deck",
            plain_english="No relative permeability (saturation) tables found. Without these, OPM cannot compute how much oil, gas, or water flows at a given saturation.",
            fix_hint="Add SWOF (oil-water system) or SGOF (gas-oil system) tables in the PROPS section.",
        )]
    return []


# ── SCHEDULE rules ───────────────────────────────────────────────────────────

def rule_tstep(deck_text: str) -> list[DeckDiagnostic]:
    """R008 — SCHEDULE must contain at least one TSTEP or DATES block."""
    has_schedule = bool(re.search(r"^\s*SCHEDULE\b", deck_text, re.MULTILINE))
    if not has_schedule:
        return []
    has_time = any(
        re.search(rf"^\s*{kw}\b", deck_text, re.MULTILINE)
        for kw in ["TSTEP", "DATES"]
    )
    if not has_time:
        return [_diag(
            rule_id="R008",
            severity=DiagnosticSeverity.FATAL,
            keyword="TSTEP",
            raw_message="No TSTEP or DATES keyword in SCHEDULE",
            plain_english="The SCHEDULE section has no time steps. OPM will not advance time at all — the simulation runs for zero days.",
            fix_hint="Add a TSTEP block, e.g.:\nTSTEP\n  30 30 30 30 /",
        )]
    return []


def rule_compdat_slash(deck_text: str) -> list[DeckDiagnostic]:
    """R009 — Every COMPDAT block must end with a forward-slash terminator."""
    findings = []
    lines = deck_text.splitlines()
    in_compdat = False
    block_start = None

    for i, line in enumerate(lines, start=1):
        if re.match(r"^\s*COMPDAT\b", line):
            in_compdat = True
            block_start = i
            continue
        if in_compdat:
            stripped = line.strip()
            if stripped == "/":
                in_compdat = False
            elif re.match(r"^\s*[A-Z]", line) and stripped not in ("", "--"):
                # New keyword started without slash terminator
                if not stripped.startswith("--"):
                    findings.append(_diag(
                        rule_id="R009",
                        severity=DiagnosticSeverity.FATAL,
                        keyword="COMPDAT",
                        raw_message=f"COMPDAT block starting at line {block_start} missing '/' terminator",
                        plain_english=f"The COMPDAT block at line {block_start} has no '/' at the end. Each data record in COMPDAT must end with '/' and the block must end with a '/' on its own line.",
                        fix_hint="Add '/' at the end of each COMPDAT data line and a standalone '/' to close the block.",
                        line=block_start,
                    ))
                    in_compdat = False
    return findings


def rule_wconprod_mode(deck_text: str) -> list[DeckDiagnostic]:
    """R010 — WCONPROD control mode must be a known value."""
    VALID_MODES = {"ORAT", "WRAT", "GRAT", "LRAT", "RESV", "BHP", "THP", "GRUP"}
    findings = []
    for i, line in enumerate(deck_text.splitlines(), start=1):
        # WCONPROD data lines: 'WELL_NAME  OPEN  MODE  ...'
        m = re.match(r"^\s*'[\w\-]+?'\s+(OPEN|SHUT|STOP|AUTO)\s+(\w+)", line)
        if m:
            mode = m.group(2).upper()
            if mode not in VALID_MODES:
                findings.append(_diag(
                    rule_id="R010",
                    severity=DiagnosticSeverity.ERROR,
                    keyword="WCONPROD",
                    raw_message=f"Unknown WCONPROD control mode '{mode}' at line {i}",
                    plain_english=f"'{mode}' is not a valid production control mode. OPM will reject this well definition.",
                    fix_hint=f"Replace '{mode}' with one of: {', '.join(sorted(VALID_MODES))}.",
                    line=i,
                ))
    return findings


# ── Style rules ────────────────────────────────────────────────────────────────

def rule_no_title(deck_text: str) -> list[DeckDiagnostic]:
    """S001 — TITLE keyword is recommended for traceability."""
    if not re.search(r"^\s*TITLE\b", deck_text, re.MULTILINE):
        return [_diag(
            rule_id="S001",
            severity=DiagnosticSeverity.STYLE,
            keyword="TITLE",
            raw_message="TITLE keyword not present",
            plain_english="No TITLE keyword found. This makes it hard to identify what this simulation represents.",
            fix_hint="Add 'TITLE' at the top of RUNSPEC followed by a descriptive name on the next line.",
        )]
    return []


# ── Rule registry ──────────────────────────────────────────────────────────────

RULES: list[RuleFn] = [
    rule_required_sections,
    rule_end_keyword,
    rule_dimens,
    rule_nwell,
    rule_grid_source,
    rule_pvt_tables,
    rule_saturation_tables,
    rule_tstep,
    rule_compdat_slash,
    rule_wconprod_mode,
    rule_no_title,
]
