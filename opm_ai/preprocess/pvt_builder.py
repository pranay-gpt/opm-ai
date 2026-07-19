"""PVT builder module: data classes and main entry point for PVT block generation.

Defines the main build_pvt_blocks entry point. Also provides the AI correlation
advisor and validator. Data classes are in models.py to avoid circular imports.
"""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np

from opm_ai.preprocess.correlations import (
    standing_rs_bubble,
    standing_bo,
    vasquez_beggs_bo,
    almarhoun_bo,
    beggs_robinson_muo_dead,
    beggs_robinson_muo_live,
    gas_z_papay,
    gas_bg,
    lee_gonzalez_mug,
    mccain_bw,
    mccain_muw,
    corey_swof,
    corey_sgof,
    let_swof,
    let_sgof,
)
from opm_ai.preprocess.models import (
    FluidDescriptor,
    PVTBlocks,
    UnitSystem,
    CorrelationName,
    AmbiguousCorrelation,
)
from opm_ai.preprocess.tables import (
    build_pvt_oil_table,
    build_pvdg_table,
    build_pvt_water_table,
    build_rock_table,
    build_density_table,
    build_swof_table,
    build_sgof_table,
    render_pvto,
    render_pvdg,
    render_pvtw,
    render_rock,
    render_density,
    render_swof,
    render_sgof,
)
from opm_ai.preprocess.validate import validate_pvt_blocks as _validate_pvt_blocks


def _select_oil_correlation(
    fluid: FluidDescriptor,
    correlations: dict[str, CorrelationName] | None,
    region: str | None,
) -> tuple[CorrelationName, str]:
    """Select oil PVT correlation, using advisor if not specified."""
    if correlations and "pvt_oil" in correlations:
        return correlations["pvt_oil"], "user specified"

    corr, explanation = recommend_correlation(fluid, region)
    return corr, explanation


def _select_relperm_correlation(
    correlations: dict[str, CorrelationName] | None,
) -> tuple[CorrelationName, str]:
    """Select relative permeability correlation."""
    if correlations and "relperm_water_oil" in correlations:
        return correlations["relperm_water_oil"], "user specified"
    if correlations and "relperm_gas_oil" in correlations:
        return correlations["relperm_gas_oil"], "user specified"
    return "Corey", "default Corey"


def build_pvt_blocks(
    fluid: FluidDescriptor,
    correlations: dict[str, CorrelationName] | None = None,
    relperm_endpoints: dict[str, float] | None = None,
    region: str | None = None,
) -> PVTBlocks:
    """
    Main entry point. Selects correlations (or uses AI advisor if correlations=None),
    computes tables, returns rendered PROPS blocks.

    correlations keys: "pvt_oil" (Standing|VasquezBeggs|AlMarhoun),
                       "relperm_water_oil" (Corey|LET),
                       "relperm_gas_oil" (Corey|LET)
    relperm_endpoints: Swc, Sorw, Sorg, Krw@Sorw, Kro@Swc, Krg@Sorg, ...
    """
    # Select correlations
    oil_corr, oil_explanation = _select_oil_correlation(fluid, correlations, region)
    relperm_corr, relperm_explanation = _select_relperm_correlation(correlations)

    # Default relperm endpoints
    default_endpoints = {
        "swc": 0.12,
        "sorw": 0.20,
        "sorg": 0.05,
        "krw_max": 0.50,
        "kro_max": 1.0,
        "krg_max": 1.0,
        "nw": 2.0,
        "no": 2.0,
        "ng": 2.0,
        "nog": 2.0,
        "l_w": 2.0,
        "e_w": 1.0,
        "t_w": 2.0,
        "l_o": 2.0,
        "e_o": 1.0,
        "t_o": 2.0,
        "l_g": 2.0,
        "e_g": 1.0,
        "t_g": 2.0,
    }
    if relperm_endpoints:
        default_endpoints.update(relperm_endpoints)

    # Build tables
    pvt_oil_table = build_pvt_oil_table(fluid, oil_corr, default_endpoints)
    pvdg_table = build_pvdg_table(fluid)
    pvt_water_table = build_pvt_water_table(fluid)
    rock_table = build_rock_table(fluid)
    density_table = build_density_table(fluid)
    swof_table = build_swof_table(fluid, default_endpoints, relperm_corr)
    sgof_table = build_sgof_table(fluid, default_endpoints, relperm_corr)

    # Render blocks
    return PVTBlocks(
        pvt_oil=render_pvto(pvt_oil_table, fluid),
        pvdg=render_pvdg(pvdg_table, fluid),
        pvt_water=render_pvtw(pvt_water_table, fluid),
        rock=render_rock(rock_table, fluid),
        density=render_density(density_table, fluid),
        swof=render_swof(swof_table, fluid),
        sgof=render_sgof(sgof_table, fluid),
    )


def recommend_correlation(
    fluid: FluidDescriptor, region: str | None = None
) -> tuple[CorrelationName, str]:
    """
    AI advisor (optional, offline-degradable).
    Returns (chosen_correlation, explanation_string).
    If LLM unavailable or offline, returns deterministic fallback
    with explanation containing "offline fallback".
    Never raises.
    """
    # Try to import LLM client
    try:
        from opm_ai.llm import LLMClient
        client = LLMClient()
        if client.available:
            prompt = (
                f"Given fluid: API={fluid.api_gravity}, gas_grav={fluid.gas_specific_gravity}, "
                f"GOR={fluid.gor}, temp_f={fluid.temp_f}, salinity={fluid.salinity_ppm}, "
                f"pressure_range={fluid.pressure_range}, unit_system={fluid.unit_system}. "
                f"Region: {region or 'unspecified'}. "
                f"Recommend PVT correlation (Standing, VasquezBeggs, AlMarhoun) and explain in 2 sentences."
            )
            try:
                response = client.complete(prompt)
                # Parse response for correlation name
                response_lower = response.lower()
                if "almarhoun" in response_lower or "al-marhoun" in response_lower:
                    return "AlMarhoun", f"AI advisor: {response}"
                if "vasquez" in response_lower:
                    return "VasquezBeggs", f"AI advisor: {response}"
                return "Standing", f"AI advisor: {response}"
            except Exception:
                # Fall through to fallback
                pass
    except Exception:
        # Import failed or client unavailable - use fallback
        pass

    # Deterministic fallback
    api = fluid.api_gravity
    gas_grav = fluid.gas_specific_gravity
    region_lower = (region or "").lower()

    if region_lower in ("middle_east", "carbonate"):
        return "AlMarhoun", "offline fallback: middle east carbonate -> AlMarhoun"
    if api > 30 and gas_grav < 0.8:
        return "Standing", "offline fallback: api>30 and gas_grav<0.8 -> Standing"
    if api <= 30:
        return "VasquezBeggs", "offline fallback: api<=30 -> VasquezBeggs"
    return "Standing", "offline fallback: default -> Standing"


# Re-export validator with correct signature
def validate_pvt_blocks(blocks: PVTBlocks, unit_system: UnitSystem) -> list[str]:
    """Validate PVT blocks for monotonicity, endpoints, and physical bounds."""
    return _validate_pvt_blocks(blocks, unit_system)