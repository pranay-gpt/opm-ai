"""GRID section lint rules - L003, L004, L011."""

import re
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


def _has_keyword(section_text: str, keyword: str) -> bool:
    """Check if keyword exists in section."""
    pattern = rf"(?im)^\s*{re.escape(keyword)}\b"
    return bool(re.search(pattern, section_text))


def _get_keyword_values(section_text: str, keyword: str) -> list[str]:
    """Extract all values for a keyword (handles multipliers like 500*100)."""
    values = []
    # Use \Z (end of string) instead of $ (end of line in MULTILINE mode)
    pattern = rf"(?is)^\s*{re.escape(keyword)}\b\s*(.*?)(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|\Z)"
    match = re.search(pattern, section_text, re.MULTILINE | re.DOTALL)
    if match:
        content = match.group(1)
        tokens = content.split()
        for token in tokens:
            if token == "/":
                continue
            # Handle multiplier syntax: 500*100
            if "*" in token:
                parts = token.split("*")
                if len(parts) == 2:
                    try:
                        count = int(parts[0])
                        value = parts[1]
                        values.extend([value] * count)
                        continue
                    except ValueError:
                        pass
            values.append(token)
    return values


def _get_dims_product(deck: Deck) -> Optional[int]:
    """Get DIMENS nx*ny*nz product from RUNSPEC."""
    runspec = deck.get_section("RUNSPEC")
    if not runspec:
        return None

    values = _get_keyword_values(runspec, "DIMENS")
    if len(values) >= 3:
        try:
            nx, ny, nz = int(values[0]), int(values[1]), int(values[2])
            return nx * ny * nz
        except ValueError:
            pass
    return None


def rule_L003_dimens_grid_match(deck: Deck) -> list[LintIssue]:
    """L003: DIMENS product != count of DX/DY/DZ values (ERROR)."""
    issues = []

    runspec = deck.get_section("RUNSPEC")
    grid = deck.get_section("GRID")

    if not runspec or not grid:
        return issues

    expected_cells = _get_dims_product(deck)
    if expected_cells is None:
        return issues

    for keyword in ["DX", "DY", "DZ"]:
        values = _get_keyword_values(grid, keyword)
        if values and len(values) != expected_cells:
            grid_lines = deck.get_section_lines("GRID")
            line_num = grid_lines[0] if grid_lines else None
            issues.append(LintIssue(
                severity="ERROR",
                section="GRID",
                keyword=keyword,
                line=line_num,
                message=f"DIMENS product ({expected_cells}) does not match {keyword} value count ({len(values)})",
                rule_id="L003"
            ))

    return issues


def rule_L003b_missing_grid_keywords(deck: Deck) -> list[LintIssue]:
    """L003b: Required GRID keywords missing (ERROR).

    Required: DX, DY, DZ, TOPS, PORO, PERMX

    Skipped when the GRID section contains INCLUDE (keywords may live in the
    included file, which the v1 linter does not resolve) or corner-point
    geometry (COORD/ZCORN replace DX/DY/DZ/TOPS).
    """
    issues = []

    grid = deck.get_section("GRID")
    if not grid:
        return issues

    # IMPORT loads binary grid data (EGRID) - same unresolvable-in-v1 class
    if _has_keyword(grid, "INCLUDE") or _has_keyword(grid, "IMPORT"):
        return issues
    if _has_keyword(grid, "COORD") or _has_keyword(grid, "ZCORN"):
        return issues
    # Radial geometry replaces DX/DY/PERMX with INRAD/DRV/DTHETAV/PERMR/PERMTHT
    runspec = deck.get_section("RUNSPEC") or ""
    if _has_keyword(runspec, "RADIAL") or _has_keyword(grid, "COORDSYS") or _has_keyword(grid, "INRAD"):
        return issues

    required_keywords = ["DX", "DY", "DZ", "TOPS", "PORO", "PERMX"]
    for keyword in required_keywords:
        if not _has_keyword(grid, keyword):
            grid_lines = deck.get_section_lines("GRID")
            line_num = grid_lines[0] if grid_lines else None
            issues.append(LintIssue(
                severity="ERROR",
                section="GRID",
                keyword=keyword,
                line=line_num,
                message=f"Required GRID keyword '{keyword}' is missing",
                rule_id="L003b"
            ))

    return issues


def rule_L004_negative_permeability(deck: Deck) -> list[LintIssue]:
    """L004: Negative PERMX/PERMY/PERMZ (ERROR)."""
    issues = []

    grid = deck.get_section("GRID")
    if not grid:
        return issues

    for keyword in ["PERMX", "PERMY", "PERMZ"]:
        values = _get_keyword_values(grid, keyword)
        for i, val in enumerate(values):
            try:
                if float(val) < 0:
                    grid_lines = deck.get_section_lines("GRID")
                    line_num = grid_lines[0] if grid_lines else None
                    issues.append(LintIssue(
                        severity="ERROR",
                        section="GRID",
                        keyword=keyword,
                        line=line_num,
                        message=f"Negative permeability {keyword}={val} at index {i}",
                        rule_id="L004"
                    ))
            except ValueError:
                pass

    return issues


def rule_L011_porosity_range(deck: Deck) -> list[LintIssue]:
    """L011: PORO values outside (0, 1] (WARNING)."""
    issues = []

    grid = deck.get_section("GRID")
    if not grid:
        return issues

    values = _get_keyword_values(grid, "PORO")
    for i, val in enumerate(values):
        try:
            poro = float(val)
            if not (0 < poro <= 1):
                grid_lines = deck.get_section_lines("GRID")
                line_num = grid_lines[0] if grid_lines else None
                issues.append(LintIssue(
                    severity="WARNING",
                    section="GRID",
                    keyword="PORO",
                    line=line_num,
                    message=f"Porosity {poro} at index {i} outside physical range (0, 1]",
                    rule_id="L011"
                ))
        except ValueError:
            pass

    return issues