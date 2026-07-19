"""Validator for PVT blocks - checks monotonicity, endpoints, physical bounds.

Called by linter rules (see 02-linter.md section 4) and by build_pvt_blocks
for self-validation.
"""

from __future__ import annotations

from typing import Literal

from opm_ai.preprocess.pvt_builder import PVTBlocks, UnitSystem


def validate_pvt_blocks(
    blocks: PVTBlocks,
    unit_system: UnitSystem,
) -> list[str]:
    """
    Validate PVT blocks for physical consistency and OPM requirements.

    Returns list of error strings (empty = valid).
    Checks per spec Section 5:
    - PVTO: Rs non-decreasing, Bo >= 1.0 (saturated), MUO > 0
    - PVDG: Pressure increasing, BG > 0 decreasing, MUG > 0
    - PVTW: BW > 0, MUW > 0
    - SWOF: Sw strictly increasing, Krw/Kro in [0,1], first Krw==0, last Kro==0
    - SGOF: Sg strictly increasing, Krg/Kro in [0,1]
    - DENSITY: three positive numbers
    """
    errors = []

    # Parse block strings into structured data
    pvto_rows = _parse_pvto(blocks.pvt_oil)
    pvdg_rows = _parse_pvdg(blocks.pvdg)
    pvt_water_rows = _parse_pvtw(blocks.pvt_water)
    rock_rows = _parse_rock(blocks.rock)
    density_vals = _parse_density(blocks.density)
    swof_rows = _parse_swof(blocks.swof)
    sgof_rows = _parse_sgof(blocks.sgof)

    # PVTO validation
    errors.extend(_validate_pvto(pvto_rows))

    # PVDG validation
    errors.extend(_validate_pvdg(pvdg_rows))

    # PVTW validation
    errors.extend(_validate_pvtw(pvt_water_rows))

    # ROCK validation (basic)
    errors.extend(_validate_rock(rock_rows))

    # DENSITY validation
    errors.extend(_validate_density(density_vals))

    # SWOF validation
    errors.extend(_validate_swof(swof_rows))

    # SGOF validation
    errors.extend(_validate_sgof(sgof_rows))

    return errors


def _parse_pvto(block: str) -> list[dict]:
    """Parse PVTO block into list of {RS, P, BO, MUO} dicts."""
    rows = []
    lines = block.strip().split("\n")
    current_rs = None

    for line in lines:
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("PVTO"):
            continue
        if line == "/":
            current_rs = None
            continue

        parts = line.split()
        if len(parts) == 1:
            # RS header line
            current_rs = float(parts[0])
        elif len(parts) == 3 and current_rs is not None:
            # Data row: P BO MUO
            p, bo, muo = map(float, parts)
            rows.append({"RS": current_rs, "P": p, "BO": bo, "MUO": muo})

    return rows


def _parse_pvdg(block: str) -> list[dict]:
    """Parse PVDG block into list of {P, BG, MUG} dicts."""
    rows = []
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("PVDG"):
            continue
        parts = line.split()
        if len(parts) == 3:
            p, bg, mug = map(float, parts)
            rows.append({"P": p, "BG": bg, "MUG": mug})
    return rows


def _parse_pvtw(block: str) -> list[dict]:
    """Parse PVTW block into list of dicts."""
    rows = []
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("PVTW"):
            continue
        parts = line.split()
        if len(parts) >= 5:
            p, bw, cw, muw, visco = map(float, parts[:5])
            rows.append({"P": p, "BW": bw, "CW": cw, "MUW": muw, "VISCO": visco})
    return rows


def _parse_rock(block: str) -> list[dict]:
    """Parse ROCK block."""
    rows = []
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("ROCK"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            p, cr = map(float, parts[:2])
            rows.append({"P": p, "CR": cr})
    return rows


def _parse_density(block: str) -> dict[str, float]:
    """Parse DENSITY block."""
    vals = {}
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("DENSITY"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            vals["OIL"] = float(parts[0])
            vals["WATER"] = float(parts[1])
            vals["GAS"] = float(parts[2])
    return vals


def _parse_swof(block: str) -> list[dict]:
    """Parse SWOF block into list of {SW, KRW, KRO, PCOW} dicts."""
    rows = []
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("SWOF"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            sw, krw, kro, pcow = map(float, parts[:4])
            rows.append({"SW": sw, "KRW": krw, "KRO": kro, "PCOW": pcow})
    return rows


def _parse_sgof(block: str) -> list[dict]:
    """Parse SGOF block into list of {SG, KRG, KRO, PCOG} dicts."""
    rows = []
    for line in block.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("/") or line.startswith("SGOF"):
            continue
        parts = line.split()
        if len(parts) >= 4:
            sg, krg, kro, pcog = map(float, parts[:4])
            rows.append({"SG": sg, "KRG": krg, "KRO": kro, "PCOG": pcog})
    return rows


def _validate_pvto(rows: list[dict]) -> list[str]:
    """Validate PVTO table."""
    errors = []
    if not rows:
        errors.append("PVTO: no data rows found")
        return errors

    # Check Rs non-decreasing
    prev_rs = -1.0
    for i, row in enumerate(rows):
        rs = row["RS"]
        if rs < prev_rs - 1e-6:
            errors.append(f"PVTO row {i}: Rs decreases ({prev_rs:.4f} -> {rs:.4f})")
        prev_rs = rs

    # Check Bo >= 1.0 for saturated rows (where P <= Pb, approximated by Rs < max Rs)
    max_rs = max(r["RS"] for r in rows)
    for i, row in enumerate(rows):
        if row["RS"] < max_rs - 1e-6:  # saturated region
            if row["BO"] < 1.0 - 1e-6:
                errors.append(f"PVTO row {i}: Bo < 1.0 in saturated region ({row['BO']:.6f})")

    # Check MUO > 0
    for i, row in enumerate(rows):
        if row["MUO"] <= 0:
            errors.append(f"PVTO row {i}: MUO <= 0 ({row['MUO']:.6f})")

    return errors


def _validate_pvdg(rows: list[dict]) -> list[str]:
    """Validate PVDG table."""
    errors = []
    if not rows:
        errors.append("PVDG: no data rows found")
        return errors

    prev_p = -1.0
    prev_bg = float("inf")
    for i, row in enumerate(rows):
        p = row["P"]
        bg = row["BG"]
        mug = row["MUG"]

        if p <= prev_p + 1e-6:
            errors.append(f"PVDG row {i}: pressure not strictly increasing ({prev_p:.4f} -> {p:.4f})")
        if bg <= 0:
            errors.append(f"PVDG row {i}: BG <= 0 ({bg:.6f})")
        if bg > prev_bg + 1e-6:
            errors.append(f"PVDG row {i}: BG not decreasing ({prev_bg:.6f} -> {bg:.6f})")
        if mug <= 0:
            errors.append(f"PVDG row {i}: MUG <= 0 ({mug:.6f})")

        prev_p = p
        prev_bg = bg

    return errors


def _validate_pvtw(rows: list[dict]) -> list[str]:
    """Validate PVTW table."""
    errors = []
    if not rows:
        errors.append("PVTW: no data rows found")
        return errors

    for i, row in enumerate(rows):
        if row["BW"] <= 0:
            errors.append(f"PVTW row {i}: BW <= 0 ({row['BW']:.6f})")
        if row["MUW"] <= 0:
            errors.append(f"PVTW row {i}: MUW <= 0 ({row['MUW']:.6f})")

    return errors


def _validate_rock(rows: list[dict]) -> list[str]:
    """Validate ROCK table."""
    errors = []
    if not rows:
        errors.append("ROCK: no data rows found")
        return errors

    for i, row in enumerate(rows):
        if row["CR"] < 0:
            errors.append(f"ROCK row {i}: CR < 0 ({row['CR']:.6e})")

    return errors


def _validate_density(vals: dict[str, float]) -> list[str]:
    """Validate DENSITY block."""
    errors = []
    required = ["OIL", "WATER", "GAS"]
    for key in required:
        if key not in vals:
            errors.append(f"DENSITY: missing {key}")
        elif vals[key] <= 0:
            errors.append(f"DENSITY: {key} <= 0 ({vals[key]:.6f})")
    return errors


def _validate_swof(rows: list[dict]) -> list[str]:
    """Validate SWOF table."""
    errors = []
    if not rows:
        errors.append("SWOF: no data rows found")
        return errors

    prev_sw = -1.0
    for i, row in enumerate(rows):
        sw = row["SW"]
        krw = row["KRW"]
        kro = row["KRO"]

        if sw <= prev_sw + 1e-6:
            errors.append(f"SWOF row {i}: Sw not strictly increasing ({prev_sw:.4f} -> {sw:.4f})")
        if not (0.0 <= krw <= 1.0 + 1e-6):
            errors.append(f"SWOF row {i}: KRW out of [0,1] ({krw:.6f})")
        if not (0.0 <= kro <= 1.0 + 1e-6):
            errors.append(f"SWOF row {i}: KRO out of [0,1] ({kro:.6f})")

        prev_sw = sw

    # Check endpoints
    if rows:
        if abs(rows[0]["KRW"]) > 1e-6:
            errors.append(f"SWOF first row: KRW should be 0 at Swc ({rows[0]['KRW']:.6f})")
        if abs(rows[-1]["KRO"]) > 1e-6:
            errors.append(f"SWOF last row: KRO should be 0 at Sw=1 ({rows[-1]['KRO']:.6f})")

    return errors


def _validate_sgof(rows: list[dict]) -> list[str]:
    """Validate SGOF table."""
    errors = []
    if not rows:
        errors.append("SGOF: no data rows found")
        return errors

    prev_sg = -1.0
    for i, row in enumerate(rows):
        sg = row["SG"]
        krg = row["KRG"]
        kro = row["KRO"]

        if sg <= prev_sg + 1e-6:
            errors.append(f"SGOF row {i}: Sg not strictly increasing ({prev_sg:.4f} -> {sg:.4f})")
        if not (0.0 <= krg <= 1.0 + 1e-6):
            errors.append(f"SGOF row {i}: KRG out of [0,1] ({krg:.6f})")
        if not (0.0 <= kro <= 1.0 + 1e-6):
            errors.append(f"SGOF row {i}: KRO out of [0,1] ({kro:.6f})")

        prev_sg = sg

    # Check first row: Sg=0, KRG=0, KRO=kro_max
    if rows:
        if abs(rows[0]["SG"]) > 1e-6:
            errors.append(f"SGOF first row: SG should be 0 ({rows[0]['SG']:.6f})")
        if abs(rows[0]["KRG"]) > 1e-6:
            errors.append(f"SGOF first row: KRG should be 0 at Sg=0 ({rows[0]['KRG']:.6f})")

    return errors