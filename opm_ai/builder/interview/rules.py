"""Interview validation rules: semantic sanity checks the interview owns.

The linter owns deck structure (L-rules); the interview owns spec-level
semantics. Blocks stop finish(); warnings advance with a banner.
"""

from dataclasses import dataclass
from typing import Any

from opm_ai.builder.models import ModelSpec, ScenarioType, WellType


@dataclass(frozen=True)
class Finding:
    """One validation finding: id, severity, message, offending question id."""

    id: str
    severity: str  # "block" | "warn"
    message: str
    question_id: str | None = None


def _dz_list(spec: ModelSpec) -> list[float]:
    return spec.reservoir.dz if isinstance(spec.reservoir.dz, list) \
        else [spec.reservoir.dz] * spec.reservoir.nz


def validate(spec: ModelSpec, answers: dict[str, Any] | None = None) -> list[Finding]:
    """Run the semantic checks. Never raises; returns findings."""
    findings: list[Finding] = []
    r = spec.reservoir

    # -- structural blocks --------------------------------------------------
    for idx, well in enumerate(spec.wells):
        if well.k1 > well.k2:
            findings.append(Finding(
                "R06a", "block",
                f"Well {well.name}: top completion layer k1={well.k1} is below "
                f"bottom layer k2={well.k2}.",
                question_id=f"wells[{idx}].k1",
            ))
        if well.k2 > r.nz:
            findings.append(Finding(
                "R06", "block",
                f"Well {well.name}: bottom completion layer k2={well.k2} is "
                f"deeper than the reservoir has layers (nz={r.nz}).",
                question_id=f"wells[{idx}].k2",
            ))
        if well.i > r.nx or well.j > r.ny:
            findings.append(Finding(
                "R07", "block",
                f"Well {well.name}: location (i={well.i}, j={well.j}) is outside "
                f"the grid (nx={r.nx}, ny={r.ny}).",
                question_id=f"wells[{idx}].i",
            ))
        if well.well_type == WellType.PROD and well.target_rate <= 0:
            findings.append(Finding(
                "R12", "block",
                f"Well {well.name}: producer target rate must be positive.",
                question_id=f"wells[{idx}].target_rate",
            ))
        if well.well_type == WellType.INJ and well.inject_rate <= 0:
            findings.append(Finding(
                "R12", "block",
                f"Well {well.name}: injector rate must be positive.",
                question_id=f"wells[{idx}].inject_rate",
            ))

    # Well-index collision: two wells at the same (i, j) share a connection
    # factor; the deck is wrong rather than crashed.
    seen: dict[tuple[int, int], str] = {}
    for well in spec.wells:
        key = (well.i, well.j)
        if key in seen:
            findings.append(Finding(
                "R06b", "block",
                f"Wells {seen[key]} and {well.name} occupy the same grid block "
                f"(i={well.i}, j={well.j}).",
                question_id=None,
            ))
        else:
            seen[key] = well.name

    # -- array-length blocks -------------------------------------------------
    if isinstance(r.dz, list) and len(r.dz) != r.nz:
        findings.append(Finding(
            "R08", "block",
            f"Layer thickness count ({len(r.dz)}) does not match the layer "
            f"count (nz={r.nz}).",
            question_id="grid.dz",
        ))
    for axis in ("permx", "permy", "permz"):
        v = getattr(r, axis)
        if isinstance(v, list) and len(v) != r.nz:
            findings.append(Finding(
                "R08", "block",
                f"{axis.upper()} count ({len(v)}) does not match the layer "
                f"count (nz={r.nz}).",
                question_id=f"rock.{axis}",
            ))

    # -- scenario consistency -------------------------------------------------
    if spec.scenario in (ScenarioType.WATERFLOOD_5SPOT, ScenarioType.WATERFLOOD_LINE_DRIVE):
        if not any(w.well_type == WellType.INJ for w in spec.wells):
            # Name a well-type question, not intent.scenario: the scenario
            # is already answered and the interview never re-asks it, so
            # pointing there told the user to fix something they can no
            # longer change. Flipping one well to INJ is the actual fix.
            first_well = "wells[0].type" if spec.wells else "intent.scenario"
            findings.append(Finding(
                "R09", "block",
                f"Scenario {spec.scenario.value} is a waterflood but no well is "
                f"an injector. Set a well to INJ, or pick a different scenario.",
                question_id=first_well,
            ))
    if spec.scenario == ScenarioType.GAS_CAP and spec.equil_goc_depth is None:
        findings.append(Finding(
            "R04", "block",
            "Gas cap scenario needs a gas-oil contact depth (where the cap "
            "base sits).",
            question_id="equil.goc_depth",
        ))

    # -- equil sanity ----------------------------------------------------------
    dz_list = _dz_list(spec)
    datum = spec.equil_datum_depth if spec.equil_datum_depth is not None \
        else r.top_depth + 50.0
    span_top = r.top_depth
    span_bottom = r.top_depth + sum(dz_list)
    if not (span_top <= datum <= span_bottom):
        findings.append(Finding(
            "R02", "block",
            f"Pressure datum depth ({datum:.0f} ft) lies outside the grid span "
            f"({span_top:.0f} to {span_bottom:.0f} ft).",
            question_id="equil.datum_depth",
        ))
    if spec.equil_woc_depth is not None and \
            not (span_top <= spec.equil_woc_depth <= span_bottom):
        findings.append(Finding(
            "R03", "warn",
            f"Water-oil contact depth ({spec.equil_woc_depth:.0f} ft) lies "
            f"outside the grid span.",
            question_id="equil.woc_depth",
        ))

    # -- well controls ----------------------------------------------------------
    for idx, well in enumerate(spec.wells):
        if well.well_type == WellType.INJ and well.bhp_max < r.initial_pressure:
            findings.append(Finding(
                "R05", "warn",
                f"Well {well.name}: max injection BHP ({well.bhp_max:.0f} psia) "
                f"is below the initial reservoir pressure ({r.initial_pressure:.0f} "
                f"psia) - the injector will not inject.",
                question_id=f"wells[{idx}].bhp_max",
            ))

    # -- fluid pressure range ------------------------------------------------------
    if spec.fluid is not None:
        p_min, p_max = spec.fluid.pressure_range
        p_max_psia = p_max if spec.fluid.unit_system == "FIELD" \
            else p_max / 0.0689476
        needed = max(4800.0, r.initial_pressure)
        if p_max_psia < needed:
            findings.append(Finding(
                "R13", "block",
                f"Fluid PVT table pressure range tops out at {p_max_psia:.0f} "
                f"psia but the initialization needs {needed:.0f} psia. Extend "
                f"the pressure range.",
                question_id="fluid.pressure_range_psi",
            ))

    # -- CO2 honesty --------------------------------------------------------------
    if spec.scenario == ScenarioType.CO2_EOR:
        findings.append(Finding(
            "R15", "warn",
            "CO2 EOR scenario simulates a dense viscous gas via the PVDG "
            "table override, not a compositional CO2 model.",
            question_id="intent.scenario",
        ))

    return findings
