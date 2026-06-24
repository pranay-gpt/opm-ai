# opm_ai/builder/models.py
"""Data contracts for the Description-to-Deck Builder."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FluidSystem(str, Enum):
    OIL_WATER      = "oil_water"       # WATER + OIL phases
    GAS_WATER      = "gas_water"       # GAS + WATER phases
    BLACK_OIL      = "black_oil"       # OIL + GAS + WATER (full black-oil)
    DRY_GAS        = "dry_gas"         # GAS only


class GridType(str, Enum):
    CARTESIAN      = "cartesian"       # simple DX/DY/DZ box grid
    RADIAL         = "radial"          # cylindrical (r-theta-z) — future


@dataclass
class WellSpec:
    """Minimal description of one well."""
    name        : str
    type        : str           # "PRODUCER" | "INJECTOR"
    i           : int           # I grid index (1-based)
    j           : int           # J grid index (1-based)
    k1          : int = 1       # top perforation layer
    k2          : int = 1       # bottom perforation layer
    group       : str = "FIELD"
    # Production control
    control     : str = "BHP"   # ORAT | GRAT | WRAT | BHP
    rate        : float = 0.0   # surface rate (Sm3/day or Mscf/day)
    bhp_limit   : float = 100.0 # bar
    # Injection control (injectors only)
    inj_fluid   : str = "WATER" # WATER | GAS
    inj_rate    : float = 0.0
    inj_bhp_max : float = 400.0


@dataclass
class ReservoirDescription:
    """
    Everything the builder needs to generate a valid OPM deck.
    All fields have sensible defaults so partial descriptions work.
    """
    # ─ Identity ───────────────────────────────────────────────────────
    title       : str  = "opm-ai Generated Reservoir"

    # ─ Grid ───────────────────────────────────────────────────────────
    grid_type   : GridType   = GridType.CARTESIAN
    nx          : int        = 10
    ny          : int        = 10
    nz          : int        = 3
    dx          : float      = 100.0    # metres
    dy          : float      = 100.0
    dz          : float      = 10.0
    depth_top   : float      = 2000.0   # metres (TVD to top of reservoir)

    # ─ Rock ───────────────────────────────────────────────────────────
    porosity    : float      = 0.20
    permeability: float      = 100.0    # mD
    perm_v_h_ratio: float    = 0.1      # Kv/Kh

    # ─ Fluid system ──────────────────────────────────────────────────
    fluid_system: FluidSystem = FluidSystem.OIL_WATER
    # Pressure / initial conditions
    p_init      : float      = 350.0    # bar
    swi         : float      = 0.20     # initial water saturation
    # PVT (water) — used in all fluid systems
    water_fvf   : float      = 1.0      # Bw (Rm3/Sm3)
    water_comp  : float      = 4.0e-5   # 1/bar
    water_visc  : float      = 0.5      # cP
    # PVT (oil) — for OIL_WATER and BLACK_OIL
    oil_fvf     : float      = 1.2      # Bo (Rm3/Sm3)
    oil_visc    : float      = 2.0      # cP
    # PVT (gas) — for BLACK_OIL and GAS_WATER
    gas_fvf     : float      = 0.004    # Bg (Rm3/Sm3)
    gas_visc    : float      = 0.02     # cP

    # ─ Schedule ────────────────────────────────────────────────────────
    sim_years   : float      = 5.0
    report_freq : str        = "monthly" # "monthly" | "quarterly" | "yearly"
    wells       : list[WellSpec] = field(default_factory=list)


@dataclass
class BuildResult:
    """Output from the builder."""
    description : ReservoirDescription
    deck_text   : str
    lint_passed : bool
    lint_summary: str
    warnings    : list[str] = field(default_factory=list)
