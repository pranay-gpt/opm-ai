"""Data models for the preprocess module.

Defines FluidDescriptor and related types used by correlations, tables, and validators.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


UnitSystem = Literal["FIELD", "METRIC"]
CorrelationName = Literal["Standing", "VasquezBeggs", "AlMarhoun", "Corey", "LET"]


def _require_finite(value: float, name: str) -> None:
    """Reject NaN/Inf on a finite-bounded float field (F2.5 audit fix)."""
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite (got {value!r})")


@dataclass(frozen=True)
class FluidDescriptor:
    """User-facing fluid description (matches Builder's ModelSpec.fluid)."""

    api_gravity: float
    gas_specific_gravity: float
    gor: float
    reservoir_temp_f: float | None = None
    reservoir_temp_c: float | None = None
    salinity_ppm: float = 0.0
    pressure_range_psi: tuple[float, float] | None = None
    unit_system: UnitSystem = "FIELD"
    # Oil PVT correlation family (Standing | VasquezBeggs | AlMarhoun).
    # LET/Corey are excluded - they are relative permeability correlations,
    # not PVT correlations, and surface separately in build_pvt_blocks.
    correlation: CorrelationName = "Standing"

    def __post_init__(self) -> None:
        for name, value in (
            ("api_gravity", self.api_gravity),
            ("gas_specific_gravity", self.gas_specific_gravity),
            ("gor", self.gor),
            ("salinity_ppm", self.salinity_ppm),
        ):
            _require_finite(value, name)
        if self.reservoir_temp_f is not None:
            _require_finite(self.reservoir_temp_f, "reservoir_temp_f")
        if self.reservoir_temp_c is not None:
            _require_finite(self.reservoir_temp_c, "reservoir_temp_c")
        if self.api_gravity <= 0:
            raise ValueError("api_gravity must be > 0")
        if self.gas_specific_gravity <= 0:
            raise ValueError("gas_specific_gravity must be > 0")
        if self.gor < 0:
            raise ValueError("gor must be >= 0")
        if self.reservoir_temp_f is not None and self.reservoir_temp_f < -459.67:
            raise ValueError("reservoir_temp_f must be >= -459.67")
        if self.reservoir_temp_c is not None and self.reservoir_temp_c < -273.15:
            raise ValueError("reservoir_temp_c must be >= -273.15")
        if self.salinity_ppm < 0:
            raise ValueError("salinity_ppm must be >= 0")
        if self.pressure_range_psi is not None:
            pmin, pmax = self.pressure_range_psi
            _require_finite(pmin, "pressure_range_psi[0]")
            _require_finite(pmax, "pressure_range_psi[1]")
            if pmin >= pmax:
                raise ValueError("pressure_range_psi must have p_min < p_max")
        if self.unit_system not in ("FIELD", "METRIC"):
            raise ValueError("unit_system must be 'FIELD' or 'METRIC'")
        if self.correlation not in ("Standing", "VasquezBeggs", "AlMarhoun"):
            raise ValueError(
                "correlation must be one of 'Standing', 'VasquezBeggs', 'AlMarhoun' "
                "(oil PVT correlations only; LET/Corey are relperm)"
            )

    @property
    def temp_f(self) -> float:
        """Return reservoir temperature in degF."""
        if self.reservoir_temp_f is not None:
            return self.reservoir_temp_f
        if self.reservoir_temp_c is not None:
            return self.reservoir_temp_c * 9.0 / 5.0 + 32.0
        # Default based on unit system
        return 200.0 if self.unit_system == "FIELD" else 93.33

    @property
    def pressure_range(self) -> tuple[float, float]:
        """Return pressure range in psia (FIELD) or bar (METRIC)."""
        if self.pressure_range_psi is not None:
            return self.pressure_range_psi
        if self.unit_system == "FIELD":
            return (14.7, 5000.0)
        return (1.01325, 344.74)  # 14.7 psi, 5000 psi in bar

    @property
    def oil_specific_gravity(self) -> float:
        """Oil specific gravity (water = 1.0) from API gravity."""
        return 141.5 / (131.5 + self.api_gravity)


@dataclass(frozen=True)
class PVTBlocks:
    """Rendered PROPS blocks as strings ready for Jinja2 template."""

    pvt_oil: str
    pvdg: str
    pvt_water: str
    rock: str
    density: str
    swof: str
    sgof: str


class AmbiguousCorrelation(Exception):
    """Raised when multiple correlations are equally valid and user must choose."""

    def __init__(self, options: list[CorrelationName]) -> None:
        self.options = options
        super().__init__(f"Ambiguous correlation choice: {options}")