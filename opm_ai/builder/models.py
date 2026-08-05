"""Pydantic models for the builder module."""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

from opm_ai.preprocess.models import FluidDescriptor


class WellType(str, Enum):
    """Well type enumeration."""
    PROD = "PROD"
    INJ = "INJ"


class ControlMode(str, Enum):
    """Well control mode."""
    RATE = "RATE"
    BHP = "BHP"
    RESV = "RESV"


class InjectFluid(str, Enum):
    """Injection fluid type."""
    WATER = "WATER"
    GAS = "GAS"
    STEAM = "STEAM"


class ReservoirSpec(BaseModel):
    """Reservoir grid and property specification."""

    nx: int = Field(default=10, ge=1, le=1000, description="Number of grid blocks in X")
    ny: int = Field(default=10, ge=1, le=1000, description="Number of grid blocks in Y")
    nz: int = Field(default=3, ge=1, le=100, description="Number of grid blocks in Z")

    # Grid geometry
    dx: float | list[float] = Field(default=1000.0, description="Cell size in X (ft)")
    dy: float | list[float] = Field(default=1000.0, description="Cell size in Y (ft)")
    dz: float | list[float] = Field(default_factory=lambda: [20.0, 30.0, 50.0], description="Cell size in Z (ft) per layer")

    top_depth: float = Field(default=8325.0, description="Top depth of layer 1 (ft)")
    porosity: float = Field(default=0.3, ge=0.01, le=0.5, description="Porosity (fraction)")

    # Initial reservoir pressure at datum depth (psia). The deck's EQUIL
    # block needs this for the initialization step. Default 4800 psia is
    # the SPE1 reference value; users describing deeper or shallower
    # reservoirs routinely override it (see builder.extract).
    initial_pressure: float = Field(
        default=4800.0, ge=14.7, le=20000.0,
        description="Initial reservoir pressure at datum depth (psia)",
    )

    # Permeability (mD)
    permx: float | list[float] = Field(default_factory=lambda: [500.0, 50.0, 200.0])
    permy: float | list[float] = Field(default_factory=lambda: [500.0, 50.0, 200.0])
    permz: float | list[float] = Field(default_factory=lambda: [500.0, 50.0, 200.0])

    @property
    def total_cells(self) -> int:
        return self.nx * self.ny * self.nz


class WellSpec(BaseModel):
    """Well specification."""

    name: str
    well_type: WellType
    i: int = Field(ge=1, description="I index (1-based)")
    j: int = Field(ge=1, description="J index (1-based)")
    k1: int = Field(ge=1, description="Top layer (1-based)")
    k2: int = Field(ge=1, description="Bottom layer (1-based)")
    reference_depth: float = Field(default=8400.0, description="Reference depth for BHP (ft)")
    well_bore_diameter: float = Field(default=0.5, description="Wellbore diameter (ft)")

    # Production well controls
    control_mode: ControlMode = ControlMode.RATE
    target_rate: float = Field(default=500.0, description="Target rate (STB/day for oil, Mscf/day for gas)")
    bhp_limit: float = Field(default=2000.0, description="Bottom hole pressure limit (psia)")

    # Injection well controls
    inject_fluid: InjectFluid = InjectFluid.WATER
    inject_rate: float = Field(default=500.0, description="Injection rate (STB/day water, Mscf/day gas)")
    bhp_max: float = Field(default=6000.0, description="Max BHP for injector (psia)")


class ScenarioType(str, Enum):
    """Predefined scenario types."""
    DEPLETION = "depletion"
    WATERFLOOD_5SPOT = "5spot_waterflood"
    WATERFLOOD_LINE_DRIVE = "line_drive_waterflood"
    WAG = "wag"
    GAS_CAP = "gas_cap"
    CO2_EOR = "co2_eor"
    MULTILAYER = "multilayer"
    BUILDUP = "buildup"


# Alias for backward compatibility with tests
Scenario = ScenarioType


class ScheduleEvent(BaseModel):
    """A single schedule phase: keyword actions applied at the current time,
    then a time advance (calendar DATES or one/more TSTEP steps).

    Consumed by base.j2 (Stage D). Actions are raw deck-text blocks (e.g. a
    full WCONINJE record) rendered verbatim before the time advance, matching
    Eclipse semantics (change controls, then step time). When ``schedule`` is
    empty the deck output is byte-identical to the pre-Stage-D template.
    """

    date: str | None = Field(default=None, description="Calendar date for a DATES advance, e.g. \"1 'JUL' 2015\"")
    tstep_days: float | list[float] | None = Field(
        default=None, description="TSTEP advance: one length or a list of substep lengths (days)"
    )
    actions: list[str] = Field(default_factory=list, description="Raw SCHEDULE keyword blocks applied before the advance")


class ModelSpec(BaseModel):
    """Complete model specification for deck generation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    scenario: ScenarioType = ScenarioType.DEPLETION
    title: str = "OPM-AI Generated Deck"
    reservoir: ReservoirSpec = Field(default_factory=ReservoirSpec)
    wells: list[WellSpec] = Field(default_factory=list)
    start_date: str = "1 'JAN' 2015"
    timesteps: list[float] = Field(default_factory=lambda: [30.0] * 12 + [90.0] * 4)  # Monthly then quarterly
    field_units: bool = Field(default=True, description="Use FIELD units (vs METRIC)")
    fluid: FluidDescriptor | None = None
    schedule: list[ScheduleEvent] = Field(
        default_factory=list,
        description="Optional schedule phases appended after the initial TSTEP block",
    )

    # Initialization overrides (FIELD units; None keeps the SPE1-style defaults).
    # EQUIL items: datum depth/pressure, WOC depth (item 3), GOC depth (item 5).
    equil_datum_depth: float | None = Field(default=None, description="EQUIL datum depth (ft)")
    equil_datum_pressure: float | None = Field(default=None, description="EQUIL pressure at datum (psia)")
    equil_woc_depth: float | None = Field(default=None, description="EQUIL water-oil contact depth (ft)")
    equil_goc_depth: float | None = Field(default=None, description="EQUIL gas-oil contact depth (ft); above/inside the reservoir creates an initial gas cap")

    # PROPS override: replaces the default methane-like PVDG table (rows of
    # "pressure Bg viscosity" in FIELD units). Used by CO2_EOR for a denser,
    # more viscous injection gas while staying in the black-oil subset.
    pvdg_rows: list[str] | None = Field(
        default=None,
        description="Override PVDG table rows, each 'psia rb/Mscf cP' (black-oil PVDG stays, values change)",
    )

    def total_cells(self) -> int:
        return self.reservoir.total_cells