# opm_ai/preprocess/models.py
"""Data contracts for the PVT Pre-Processing Pipeline."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CorrelationMethod(str, Enum):
    STANDING      = "standing"        # Standing (1947) — Gulf of Mexico oils
    VASQUEZ_BEGGS = "vasquez_beggs"   # Vasquez & Beggs (1980) — general
    AL_MARHOUN    = "al_marhoun"      # Al-Marhoun (1988) — Middle East oils
    LEE_KESLER    = "lee_kesler"      # Lee & Kesler (1975) — gas Z-factor


@dataclass
class OilFluidInput:
    """
    Minimum fluid description needed to generate PVT tables for oil.

    All pressures in bar, temperatures in °C, rates in field units.
    """
    # ─ Fluid identity
    api_gravity     : float          # °API  (e.g. 35.0)
    gas_gravity     : float = 0.65   # specific gravity of dissolved gas (air=1)
    gor_scf_stb     : float = 500.0  # Solution GOR at bubble point (scf/STB)

    # ─ Reservoir conditions
    t_reservoir_c   : float = 80.0   # °C
    p_bubble_bar    : float = 200.0  # bubble point pressure (bar)
    p_max_bar       : float = 400.0  # max pressure for table
    p_min_bar       : float = 10.0   # min pressure for table
    n_points        : int   = 10     # number of pressure steps

    # ─ Correlation choice
    bo_method       : CorrelationMethod = CorrelationMethod.STANDING
    visc_method     : CorrelationMethod = CorrelationMethod.VASQUEZ_BEGGS


@dataclass
class WaterFluidInput:
    """Input for PVTW (water PVT)."""
    salinity_ppm    : float = 50_000.0   # mg/L NaCl
    t_reservoir_c   : float = 80.0
    p_ref_bar       : float = 350.0


@dataclass
class GasFluidInput:
    """Input for PVDG (dry gas PVT)."""
    gas_gravity     : float = 0.65   # specific gravity (air = 1.0)
    t_reservoir_c   : float = 80.0
    p_max_bar       : float = 400.0
    p_min_bar       : float = 10.0
    n_points        : int   = 10
    co2_fraction    : float = 0.0    # mole fraction CO2
    h2s_fraction    : float = 0.0    # mole fraction H2S
    n2_fraction     : float = 0.0    # mole fraction N2


@dataclass
class PVTPoint:
    """A single row in a PVT table."""
    pressure_bar    : float
    fvf             : float   # formation volume factor
    viscosity_cp    : float
    rs_scf_stb      : Optional[float] = None   # solution GOR (oil tables)


@dataclass
class PVTTableResult:
    """Full PVT result — table data + rendered OPM PROPS block."""
    table_type      : str              # "PVTO" | "PVTW" | "PVDG" | "PVCDO"
    points          : list[PVTPoint]
    opm_block       : str              # ready to paste into PROPS section
    correlation_used: str
    warnings        : list[str] = field(default_factory=list)
