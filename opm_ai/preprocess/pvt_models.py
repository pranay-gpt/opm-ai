# opm_ai/preprocess/pvt_models.py
"""
Input / output dataclasses for the per-fluid PVT table builders.

These form the public API consumed by test_preprocess.py and the
higher-level pvt_builder.build_pvt_props().
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


# ── Correlation selection ────────────────────────────────────────────────────

class CorrelationMethod(str, Enum):
    """Selectable correlation for each PVT table."""
    # Oil Bo
    STANDING     = "standing"
    VASQUEZ_BEGGS = "vasquez_beggs"
    AL_MARHOUN   = "al_marhoun"
    # Gas Z
    PAPAY        = "papay"
    # Water (only one implemented)
    MEEHAN       = "meehan"


# ── Input dataclasses ────────────────────────────────────────────────────────

@dataclass
class OilFluidInput:
    """Parameters required to build a PVTO table."""
    api_gravity   : float              = 35.0    # °API
    sg_gas        : float              = 0.65    # gas specific gravity (air=1)
    gor_scf_stb   : float              = 500.0   # solution GOR at bubble point SCF/STB
    p_bubble_bar  : float              = 200.0   # bubble-point pressure [bar]
    t_reservoir_c : float              = 80.0    # reservoir temperature [°C]
    p_min_bar     : float              = 20.0    # lowest pressure in table [bar]
    p_max_bar     : float | None       = None    # highest pressure (defaults to 1.3 * p_bubble)
    n_points      : int                = 8       # rows in the PVTO table
    bo_method     : CorrelationMethod  = CorrelationMethod.STANDING


@dataclass
class WaterFluidInput:
    """Parameters required to build a PVTW record."""
    salinity_ppm  : float              = 50_000.0  # NaCl concentration [ppm]
    t_reservoir_c : float              = 80.0      # reservoir temperature [°C]
    p_ref_bar     : float              = 350.0     # reference pressure [bar]


@dataclass
class GasFluidInput:
    """Parameters required to build a PVDG table."""
    gas_gravity   : float              = 0.65    # specific gravity (air=1)
    t_reservoir_c : float              = 80.0    # reservoir temperature [°C]
    p_min_bar     : float              = 20.0    # lowest pressure [bar]
    p_max_bar     : float              = 400.0   # highest pressure [bar]
    n_points      : int                = 8       # rows in the PVDG table
    co2_fraction  : float              = 0.0     # mole fraction CO2 (Wichert-Aziz)
    h2s_fraction  : float              = 0.0     # mole fraction H2S
    z_method      : CorrelationMethod  = CorrelationMethod.PAPAY


# ── Output dataclasses ────────────────────────────────────────────────────────

@dataclass
class PVTPoint:
    """A single pressure-point row in a PVT table."""
    pressure_bar  : float
    fvf           : float   # Rm³/Sm³  (or 1/bar for Cw in PVTW)
    viscosity_cp  : float
    rs_sm3_sm3    : float   = 0.0   # solution GOR (PVTO only)
    z_factor      : float   = 0.0   # Z-factor (PVDG only)


@dataclass
class PVTTableResult:
    """
    Fully rendered PVT table ready for insertion into an OPM .DATA deck.

    Attributes
    ----------
    table_type       : OPM keyword ("PVTO", "PVTW", "PVDG", "PVCDO")
    opm_block        : The complete keyword block as a string (includes keyword + data + /)
    points           : List of PVTPoint rows (empty for single-row records like PVTW)
    correlation_used : Human-readable string naming the correlation(s) applied
    """
    table_type       : str
    opm_block        : str
    points           : List[PVTPoint]  = field(default_factory=list)
    correlation_used : str             = ""
