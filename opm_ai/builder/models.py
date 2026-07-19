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

    def total_cells(self) -> int:
        return self.reservoir.total_cells