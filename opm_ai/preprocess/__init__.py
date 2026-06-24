"""Pre-processing layer: PVT correlations, input models, and table builders."""

# ── Low-level correlations (kept for direct import by tests) ──────────────────
from .pvt_correlations import (
    visc_water_kestin,
    bw_meehan,
    cw_osif,
    bo_standing,
    bo_vasquez_beggs,
    visc_dead_oil_beggs_robinson,
    visc_saturated_oil_beggs_robinson,
    z_factor_papay,
    bg_rm3_sm3,
    visc_gas_lee_gonzalez,
)

# ── Input / output models ─────────────────────────────────────────────────────
from .pvt_models import (
    CorrelationMethod,
    OilFluidInput,
    WaterFluidInput,
    GasFluidInput,
    PVTPoint,
    PVTTableResult,
)

# ── Per-fluid table builders (public API) ─────────────────────────────────────
from .pvt_tables import (
    build_pvto,
    build_pvtw,
    build_pvdg,
)

# ── Higher-level builder used by opm_ai.builder ───────────────────────────────
from .pvt_builder import build_pvt_props

__all__ = [
    # correlations
    "visc_water_kestin", "bw_meehan", "cw_osif",
    "bo_standing", "bo_vasquez_beggs",
    "visc_dead_oil_beggs_robinson", "visc_saturated_oil_beggs_robinson",
    "z_factor_papay", "bg_rm3_sm3", "visc_gas_lee_gonzalez",
    # models
    "CorrelationMethod",
    "OilFluidInput", "WaterFluidInput", "GasFluidInput",
    "PVTPoint", "PVTTableResult",
    # builders
    "build_pvto", "build_pvtw", "build_pvdg",
    "build_pvt_props",
]
