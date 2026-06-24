# opm_ai/builder/models.py
"""
Dataclasses for the Description-to-Deck builder.

ReservoirDescription holds all parameters needed to render a valid OPM deck.
PVT fields (water_fvf, water_visc, etc.) are populated automatically by
build_pvt_props() in opm_ai.preprocess.pvt_builder when the builder runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class FluidSystem(str, Enum):
    OIL_WATER = "oil_water"
    BLACK_OIL  = "black_oil"
    GAS_WATER  = "gas_water"
    DRY_GAS    = "dry_gas"


class GridType(str, Enum):
    CARTESIAN = "cartesian"
    CPGRID    = "cpgrid"


@dataclass
class WellSpec:
    name        : str   = "PROD1"
    type        : str   = "PRODUCER"   # PRODUCER | INJECTOR
    i           : int   = 5
    j           : int   = 5
    k1          : int   = 1
    k2          : int   = 3
    group       : str   = "FIELD"
    control     : str   = "BHP"
    rate        : float = 0.0
    bhp_limit   : float = 100.0
    inj_fluid   : str   = "WATER"
    inj_rate    : float = 0.0
    inj_bhp_max : float = 400.0


@dataclass
class ReservoirDescription:
    # ---- Metadata ----------------------------------------------------------
    title           : str         = "opm-ai Generated Reservoir"
    grid_type       : GridType    = GridType.CARTESIAN

    # ---- Grid --------------------------------------------------------------
    nx              : int         = 10
    ny              : int         = 10
    nz              : int         = 3
    dx              : float       = 100.0   # m
    dy              : float       = 100.0   # m
    dz              : float       = 10.0    # m
    depth_top       : float       = 2000.0  # m TVD

    # ---- Rock --------------------------------------------------------------
    porosity        : float       = 0.20
    permeability    : float       = 100.0   # mD
    perm_v_h_ratio  : float       = 0.10

    # ---- Fluid system & reservoir conditions --------------------------------
    fluid_system    : FluidSystem = FluidSystem.OIL_WATER
    p_init          : float       = 350.0   # bar
    t_res           : float       = 80.0    # °C   (NEW: reservoir temperature)
    swi             : float       = 0.20
    api             : float       = 35.0    # oil API gravity
    sg_gas          : float       = 0.65    # gas specific gravity
    salinity_ppm    : float       = 50_000.0

    # ---- Simulation schedule -----------------------------------------------
    sim_years       : float       = 5.0
    report_freq     : str         = "monthly"

    # ---- Wells -------------------------------------------------------------
    wells           : List[WellSpec] = field(default_factory=list)

    # ---- PVT props (computed by build_pvt_props, not set by user) ----------
    # Water
    water_fvf       : float       = 1.0
    water_comp      : float       = 4.0e-5
    water_visc      : float       = 0.5
    # Oil (dead or saturated)
    oil_fvf         : float       = 1.2
    oil_visc        : float       = 2.0
    # Gas
    gas_fvf         : float       = 0.005
    gas_visc        : float       = 0.020
    # Surface densities (kg/m3, METRIC)
    rho_oil         : float       = 820.0
    rho_water       : float       = 1025.0
    rho_gas         : float       = 1.0
    # Full tables for PVTO and PVDG (populated for black_oil, gas_water)
    pvto_rows       : list        = field(default_factory=list)
    pvdg_rows       : list        = field(default_factory=list)


@dataclass
class BuildResult:
    description  : ReservoirDescription
    deck_text    : str
    lint_passed  : bool
    lint_summary : str
    warnings     : List[str] = field(default_factory=list)
