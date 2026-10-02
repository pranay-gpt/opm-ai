"""Question catalog for the reservoir-context interview.

Data, not code: a static ordered list of Question entries covering the
ModelSpec sections. Each question is skippable; skipped answers record the
declared default. Questions are reachable only when their applies_when
predicate holds against the spec built so far, which is the whole
"never asks a nonsense question" guarantee.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from opm_ai.builder.models import ModelSpec, ScenarioType


@dataclass(frozen=True)
class Question:
    """One interview question.

    id: stable dot-path, e.g. "grid.dz", "wells[0].target_rate".
    section: one of intent|grid|rock|fluid|equil|wells|schedule.
    kind: number|csv_number|text|select|bool - matches the UI input types.
    default: the value recorded when the user skips (value or callable).
    apply: writes the answered value onto the spec.
    applies_when: predicate over the spec; false = question not asked.
    blocking: True = finish() refuses while unanswered (a skipped answer
        still records the default, so blocking only stops a bare finish).
    """

    id: str
    section: str
    prompt: str
    kind: str
    apply: Callable[[ModelSpec, Any], None]
    default: Any = None
    units: str | None = None
    options: list[str] | None = None
    applies_when: Callable[[ModelSpec], bool] = lambda spec: True
    blocking: bool = False


def _set_reservoir(field_name: str) -> Callable[[ModelSpec, Any], None]:
    def apply(spec: ModelSpec, value: Any) -> None:
        setattr(spec.reservoir, field_name, value)
    return apply


def _set_top(field_name: str) -> Callable[[ModelSpec, Any], None]:
    def apply(spec: ModelSpec, value: Any) -> None:
        setattr(spec, field_name, value)
    return apply


def _set_well(idx: int, field_name: str) -> Callable[[ModelSpec, Any], None]:
    def apply(spec: ModelSpec, value: Any) -> None:
        if idx < len(spec.wells):
            setattr(spec.wells[idx], field_name, value)
    return apply


def _has_well(idx: int) -> Callable[[ModelSpec], bool]:
    return lambda spec: idx < len(spec.wells)


def _wants_fluid(spec: ModelSpec) -> bool:
    # Fluid questions appear when a fluid was extracted/uploaded or the
    # scenario needs one (gas cap, CO2, WAG).
    return spec.fluid is not None or spec.scenario in (
        ScenarioType.GAS_CAP, ScenarioType.CO2_EOR, ScenarioType.WAG,
    )


def _is_gas_cap(spec: ModelSpec) -> bool:
    return spec.scenario == ScenarioType.GAS_CAP


# Ordering: intent first (scenario drives later defaults), then grid, rock,
# fluid, equil, wells, schedule.
CATALOG: list[Question] = [
    # -- S0 intent ----------------------------------------------------------
    Question(
        id="intent.scenario", section="intent",
        prompt="What are we modelling? Pick the scenario.",
        kind="select",
        options=[s.value for s in ScenarioType],
        apply=lambda spec, v: setattr(spec, "scenario", ScenarioType(v)),
        default=lambda spec: spec.scenario.value,
        blocking=True,
    ),
    Question(
        id="intent.title", section="intent",
        prompt="Project or model name (goes in the deck TITLE).",
        kind="text",
        apply=lambda spec, v: setattr(spec, "title", str(v).replace("/", "")),
        default=lambda spec: spec.title,
    ),
    Question(
        id="intent.start_date", section="intent",
        prompt="Simulation start date, e.g. 1 'JAN' 2015.",
        kind="text",
        apply=lambda spec, v: setattr(spec, "start_date", str(v)),
        default=lambda spec: spec.start_date,
    ),

    # -- S1 grid ------------------------------------------------------------
    Question(
        id="grid.nx", section="grid",
        prompt="How many grid blocks in X?",
        kind="number",
        apply=_set_reservoir("nx"),
        default=lambda spec: spec.reservoir.nx,
        units="blocks",
        blocking=True,
    ),
    Question(
        id="grid.ny", section="grid",
        prompt="How many grid blocks in Y?",
        kind="number",
        apply=_set_reservoir("ny"),
        default=lambda spec: spec.reservoir.ny,
        units="blocks",
        blocking=True,
    ),
    Question(
        id="grid.nz", section="grid",
        prompt="How many layers (grid blocks in Z)?",
        kind="number",
        apply=_set_reservoir("nz"),
        default=lambda spec: spec.reservoir.nz,
        units="layers",
        blocking=True,
    ),
    Question(
        id="grid.dx", section="grid",
        prompt="Cell size in X (uniform).",
        kind="number",
        apply=_set_reservoir("dx"),
        default=lambda spec: spec.reservoir.dx if not isinstance(spec.reservoir.dx, list) else spec.reservoir.dx[0],
        units="ft",
        blocking=True,
    ),
    Question(
        id="grid.dy", section="grid",
        prompt="Cell size in Y (uniform).",
        kind="number",
        apply=_set_reservoir("dy"),
        default=lambda spec: spec.reservoir.dy if not isinstance(spec.reservoir.dy, list) else spec.reservoir.dy[0],
        units="ft",
        blocking=True,
    ),
    Question(
        id="grid.dz", section="grid",
        prompt="Layer thicknesses, one value per layer (comma-separated).",
        kind="csv_number",
        apply=_set_reservoir("dz"),
        default=lambda spec: list(spec.reservoir.dz) if isinstance(spec.reservoir.dz, list) else [spec.reservoir.dz],
        units="ft",
        blocking=True,
    ),
    Question(
        id="grid.top_depth", section="grid",
        prompt="Depth to the top of the reservoir?",
        kind="number",
        apply=_set_reservoir("top_depth"),
        default=lambda spec: spec.reservoir.top_depth,
        units="ft",
        blocking=True,
    ),

    # -- S2 rock ------------------------------------------------------------
    Question(
        id="rock.porosity", section="rock",
        prompt="Average porosity?",
        kind="number",
        apply=_set_reservoir("porosity"),
        default=lambda spec: spec.reservoir.porosity,
        units="fraction (0.01-0.5)",
        blocking=True,
    ),
    Question(
        id="rock.permx", section="rock",
        prompt="Horizontal permeability KX, one value per layer (comma-separated).",
        kind="csv_number",
        apply=_set_reservoir("permx"),
        default=lambda spec: list(spec.reservoir.permx) if isinstance(spec.reservoir.permx, list) else [spec.reservoir.permx],
        units="mD",
        blocking=True,
    ),
    Question(
        id="rock.permy", section="rock",
        prompt="Horizontal permeability KY, one value per layer (comma-separated).",
        kind="csv_number",
        apply=_set_reservoir("permy"),
        default=lambda spec: list(spec.reservoir.permy) if isinstance(spec.reservoir.permy, list) else [spec.reservoir.permy],
        units="mD",
    ),
    Question(
        id="rock.permz", section="rock",
        prompt="Vertical permeability KZ, one value per layer (comma-separated).",
        kind="csv_number",
        apply=_set_reservoir("permz"),
        default=lambda spec: list(spec.reservoir.permz) if isinstance(spec.reservoir.permz, list) else [spec.reservoir.permz],
        units="mD",
    ),

    # -- S3 fluid (conditional) ----------------------------------------------
    Question(
        id="fluid.use_custom", section="fluid",
        prompt="Do you have fluid PVT data, or use the built-in SPE1-like defaults?",
        kind="select",
        options=["defaults", "describe fluid"],
        applies_when=_wants_fluid,
        apply=lambda spec, v: None,  # answered "defaults" keeps spec.fluid as-is
        default=lambda spec: "defaults" if spec.fluid is None else "describe fluid",
    ),
    Question(
        id="fluid.api_gravity", section="fluid",
        prompt="Oil API gravity?",
        kind="number",
        applies_when=_wants_fluid,
        apply=lambda spec, v: None,  # placeholder; wired to fluid in engine
        default=lambda spec: 35.0,
        units="deg API",
    ),
    Question(
        id="fluid.gor", section="fluid",
        prompt="Solution GOR?",
        kind="number",
        applies_when=_wants_fluid,
        apply=lambda spec, v: None,
        default=lambda spec: 768.0,
        units="scf/STB",
    ),
    Question(
        id="fluid.reservoir_temp_f", section="fluid",
        prompt="Reservoir temperature?",
        kind="number",
        applies_when=_wants_fluid,
        apply=lambda spec, v: None,
        default=lambda spec: 200.0,
        units="degF",
    ),
    Question(
        id="fluid.salinity_ppm", section="fluid",
        prompt="Water salinity?",
        kind="number",
        applies_when=_wants_fluid,
        apply=lambda spec, v: None,
        default=lambda spec: 0.0,
        units="ppm",
    ),
    Question(
        id="fluid.correlation", section="fluid",
        prompt="Which PVT correlation for the oil?",
        kind="select",
        options=["Standing", "VasquezBeggs", "AlMarhoun"],
        applies_when=_wants_fluid,
        apply=lambda spec, v: None,
        default=lambda spec: "Standing",
    ),

    # -- S4 equil ------------------------------------------------------------
    Question(
        id="equil.datum_depth", section="equil",
        prompt="Depth of the pressure datum? (Leave the default to place it one layer below the top.)",
        kind="number",
        applies_when=lambda spec: spec.equil_datum_depth is not None,
        apply=lambda spec, v: setattr(spec, "equil_datum_depth", v),
        default=lambda spec: spec.equil_datum_depth,
        units="ft",
    ),
    Question(
        id="equil.datum_pressure", section="equil",
        prompt="Initial reservoir pressure at the datum?",
        kind="number",
        apply=_set_reservoir("initial_pressure"),
        default=lambda spec: spec.reservoir.initial_pressure,
        units="psia",
        blocking=True,
    ),
    Question(
        id="equil.woc_depth", section="equil",
        prompt="Depth of the water-oil contact? (Blank = none.)",
        kind="number",
        apply=lambda spec, v: setattr(spec, "equil_woc_depth", v),
        default=lambda spec: None,
        units="ft",
    ),
    Question(
        id="equil.goc_depth", section="equil",
        prompt="Depth of the gas-oil contact (gas cap base)?",
        kind="number",
        applies_when=_is_gas_cap,
        apply=lambda spec, v: setattr(spec, "equil_goc_depth", v),
        default=lambda spec: spec.equil_goc_depth,
        units="ft",
        blocking=True,
    ),

    # -- S6 schedule ----------------------------------------------------------
    Question(
        id="schedule.horizon_years", section="schedule",
        prompt="How long should the simulation run?",
        kind="number",
        apply=lambda spec, v: setattr(
            spec, "timesteps",
            [30.0] * min(int(round(float(v) * 12)), 1200)
            if float(v) > 0 else [30.0] * 12,
        ),
        default=lambda spec: sum(
            spec.timesteps if isinstance(spec.timesteps, list) else [30.0]
        ) / 365.0,
        units="years",
        blocking=True,
    ),
]


def dynamic_questions(spec: ModelSpec) -> list[Question]:
    """Per-well questions, generated from the wells the extraction produced.

    Returned as editable cards: each well contributes its own questions
    (name/type/location/completion/controls), rendered as one card per well
    in the UI rather than ten separate pages.
    """
    questions: list[Question] = []
    for idx, well in enumerate(spec.wells):
        questions.append(Question(
            id=f"wells[{idx}].i", section="wells",
            prompt=f"Well {well.name}: I index (1-based, column)?",
            kind="number",
            apply=_set_well(idx, "i"),
            default=lambda spec, idx=idx, well=well: well.i,
            units="1..nx",
            blocking=True,
        ))
        questions.append(Question(
            id=f"wells[{idx}].j", section="wells",
            prompt=f"Well {well.name}: J index (1-based, row)?",
            kind="number",
            apply=_set_well(idx, "j"),
            default=lambda spec, idx=idx, well=well: well.j,
            units="1..ny",
            blocking=True,
        ))
        questions.append(Question(
            id=f"wells[{idx}].k1", section="wells",
            prompt=f"Well {well.name}: top completion layer?",
            kind="number",
            apply=_set_well(idx, "k1"),
            default=lambda spec, idx=idx, well=well: well.k1,
            units="1..nz",
            blocking=True,
        ))
        questions.append(Question(
            id=f"wells[{idx}].k2", section="wells",
            prompt=f"Well {well.name}: bottom completion layer?",
            kind="number",
            apply=_set_well(idx, "k2"),
            default=lambda spec, idx=idx, well=well: well.k2,
            units="1..nz",
            blocking=True,
        ))
        if well.well_type.value == "PROD":
            questions.append(Question(
                id=f"wells[{idx}].target_rate", section="wells",
                prompt=f"Well {well.name}: target oil rate?",
                kind="number",
                apply=_set_well(idx, "target_rate"),
                default=lambda spec, idx=idx, well=well: well.target_rate,
                units="STB/day",
                blocking=True,
            ))
            questions.append(Question(
                id=f"wells[{idx}].bhp_limit", section="wells",
                prompt=f"Well {well.name}: minimum bottom-hole pressure (BHP limit)?",
                kind="number",
                apply=_set_well(idx, "bhp_limit"),
                default=lambda spec, idx=idx, well=well: well.bhp_limit,
                units="psia",
            ))
        else:
            questions.append(Question(
                id=f"wells[{idx}].inject_fluid", section="wells",
                prompt=f"Well {well.name}: injected fluid?",
                kind="select",
                options=["WATER", "GAS", "STEAM"],
                apply=_set_well(idx, "inject_fluid"),
                default=lambda spec, idx=idx, well=well: well.inject_fluid.value,
                blocking=True,
            ))
            questions.append(Question(
                id=f"wells[{idx}].inject_rate", section="wells",
                prompt=f"Well {well.name}: injection rate?",
                kind="number",
                apply=_set_well(idx, "inject_rate"),
                default=lambda spec, idx=idx, well=well: well.inject_rate,
                units="STB/day (water) or Mscf/day (gas)",
                blocking=True,
            ))
            questions.append(Question(
                id=f"wells[{idx}].bhp_max", section="wells",
                prompt=f"Well {well.name}: maximum injection BHP?",
                kind="number",
                apply=_set_well(idx, "bhp_max"),
                default=lambda spec, idx=idx, well=well: well.bhp_max,
                units="psia",
            ))
    return questions
