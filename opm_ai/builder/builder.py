"""Deck builder: natural language -> OPM Flow deck."""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader

from opm_ai.builder.models import ModelSpec, Scenario, ReservoirSpec, WellSpec, WellType
from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.linter import lint_deck, LintResult
from opm_ai.settings import settings
from opm_ai.preprocess import build_pvt_blocks, validate_pvt_blocks, FluidDescriptor
from opm_ai.preprocess.correlations import standing_rs_bubble
from opm_ai.preprocess.tables import build_pvt_oil_table


def _get_template_env() -> Environment:
    """Get Jinja2 environment with template directory."""
    template_dir = Path(__file__).parent / "templates"
    return Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _compute_template_context(spec: ModelSpec) -> dict:
    """Compute template context from ModelSpec."""
    reservoir = spec.reservoir

    # Determine max connections per well (all layers)
    max_connections = reservoir.nz

    # Get timesteps - default to monthly for 10 years
    timesteps = spec.timesteps if spec.timesteps else [30.0] * 12 + [90.0] * 40

    # Add enumerate for template
    timesteps_with_index = list(enumerate(timesteps))

    # Build PVT blocks if fluid is specified
    pvt_blocks = None
    rsvd_rs = 1.270  # Default SPE1 value
    unit_system = "FIELD"  # Default unit system for the deck

    if spec.fluid is not None:
        fluid = spec.fluid
        unit_system = fluid.unit_system  # Use fluid's unit_system for deck and PVT

        # Validate pressure range - EQUIL uses 4800 psia default
        # fluid.pressure_range returns bar for METRIC, psia for FIELD
        # We need to compare in psia for the EQUIL check
        p_min, p_max = fluid.pressure_range
        if fluid.unit_system == "METRIC":
            p_max_psi = p_max / 0.0689476  # Convert bar to psia
        else:
            p_max_psi = p_max
        if p_max_psi < 4800:
            raise ValueError(
                f"Fluid pressure range max ({p_max_psi:.1f} psia) must be >= 4800 psia "
                f"(EQUIL datum pressure). Extend pressure_range_psi to at least 4800."
            )

        # Build PVT blocks
        pvt_blocks = build_pvt_blocks(fluid)

        # Validate using fluid's unit_system
        validation_errors = validate_pvt_blocks(pvt_blocks, unit_system)
        if validation_errors:
            raise ValueError(f"PVT block validation failed: {validation_errors}")

        # Compute RSVD RS value at initial pressure (4800 psia default EQUIL pressure)
        # Using Standing correlation to get Rs at 4800 psia, then clamp to max Rs in PVTO table
        p_init = 4800.0
        if fluid.pressure_range_psi:
            # Use the max pressure from the fluid descriptor if it's different
            p_init = max(p_init, fluid.pressure_range_psi[1])

        rs_at_pinit, _ = standing_rs_bubble(
            fluid.api_gravity, fluid.gas_specific_gravity, fluid.temp_f, p_init
        )

        # Get max Rs from the PVTO table
        pvt_oil_table = build_pvt_oil_table(
            fluid,
            "Standing",  # Use Standing for consistency with standing_rs_bubble
            {"swc": 0.12, "sorw": 0.20, "krw_max": 0.50, "kro_max": 1.0, "nw": 2.0, "no": 2.0}
        )
        max_table_rs = max(row["RS"] for row in pvt_oil_table) if pvt_oil_table else rs_at_pinit

        # Clamp to max table Rs
        rsvd_rs = min(rs_at_pinit, max_table_rs)

    # Build base context with FIELD unit values (original reservoir spec values)
    context = {
        "title": spec.title,
        "reservoir": reservoir,
        "wells": spec.wells,
        "max_connections": max_connections,
        "start_date": spec.start_date,
        "timesteps": timesteps,
        "timesteps_with_index": timesteps_with_index,
        "field_units": spec.field_units,
        "pvt_blocks": pvt_blocks,
        "rsvd_rs": rsvd_rs,
        "unit_system": unit_system,  # "FIELD" or "METRIC" - used in RUNSPEC
    }

    # Add unit-system-aware values for the template
    if unit_system == "METRIC":
        context.update(_compute_metric_context(reservoir, spec.wells, rsvd_rs))
    else:
        # FIELD unit system - use original reservoir values directly
        context.update(_compute_field_context(reservoir, spec.wells, rsvd_rs))

    return context


def _compute_field_context(reservoir, wells, rsvd_rs) -> dict:
    """
    Compute FIELD unit system values for template.

    Reservoir spec values are stored in FIELD units, so pass through directly.
    Returns flat variables that the template can use directly.
    """
    # FIELD EQUIL defaults from base.j2: 8400 4800 8450 0 8300 0 1 0 0
    # EQUIL format: datum_depth pressure_datum WOC GOC OWC ...
    equil_datum_depth = 8400.0
    equil_pressure_datum = 4800.0
    equil_woc = 8450.0      # Water-oil contact depth
    equil_goc = 0.0         # Gas-oil contact depth (0 = not set)
    equil_owc_depth = 8300.0  # Reference depth for oil-water contact pressure

    # FIELD RSVD defaults: 8300 and 8450 depths
    rsvd_depth1 = 8300.0
    rsvd_depth2 = 8450.0

    # Handle dz list
    if isinstance(reservoir.dz, list):
        dz_list = reservoir.dz
    else:
        dz_list = [reservoir.dz] * reservoir.nz

    return {
        # Reservoir geometry
        "dx": reservoir.dx,
        "dy": reservoir.dy,
        "dz": reservoir.dz if not isinstance(reservoir.dz, list) else reservoir.dz[0],
        "dz_list": dz_list,
        "top_depth": reservoir.top_depth,
        # EQUIL parameters
        "equil_datum_depth": equil_datum_depth,
        "equil_pressure_datum": equil_pressure_datum,
        "equil_woc": equil_woc,
        "equil_goc": equil_goc,
        "equil_owc_depth": equil_owc_depth,
        # RSVD parameters
        "rsvd_depth1": rsvd_depth1,
        "rsvd_depth2": rsvd_depth2,
        "rsvd_rs": rsvd_rs,
        # Wells with FIELD values
        "wells": wells,
    }


def _compute_metric_context(reservoir, wells, rsvd_rs) -> dict:
    """
    Compute METRIC unit system converted values for template.

    Reservoir spec values are stored in FIELD units (ft, psia, mD, scf/stb).
    When unit_system=METRIC, convert to:
    - Depths/lengths: ft -> m (factor 0.3048)
    - Pressures: psia -> bar (factor 0.0689476)
    - Rs: scf/stb -> sm3/sm3 (factor 0.17811)

    Returns flat variables that the template can use directly.
    """
    FT_TO_M = 0.3048
    PSIA_TO_BAR = 0.0689476
    SCF_STB_TO_SM3_SM3 = 0.17811

    # Convert reservoir geometry
    dx = reservoir.dx * FT_TO_M
    dy = reservoir.dy * FT_TO_M
    if isinstance(reservoir.dz, list):
        dz = [d * FT_TO_M for d in reservoir.dz]
        dz_list = dz
    else:
        dz = reservoir.dz * FT_TO_M
        dz_list = [dz] * reservoir.nz

    top_depth = reservoir.top_depth * FT_TO_M

    # Convert EQUIL datum depth and pressures
    # Default EQUIL in base.j2: 8400 4800 8450 0 8300 0 1 0 0
    # Format: datum_depth pressure_datum WOC GOC OWC
    equil_datum_depth = 8400.0 * FT_TO_M
    equil_pressure_datum = 4800.0 * PSIA_TO_BAR
    equil_woc = 8450.0 * FT_TO_M      # Water-oil contact depth
    equil_goc = 0.0                   # Gas-oil contact depth (0 = not set)
    equil_owc_depth = 8300.0 * FT_TO_M  # Reference depth for oil-water contact pressure

    # Convert RSVD depths and Rs
    # Default RSVD in base.j2: 8300 and 8450 depths
    rsvd_depth1 = 8300.0 * FT_TO_M
    rsvd_depth2 = 8450.0 * FT_TO_M
    rsvd_rs_metric = rsvd_rs * SCF_STB_TO_SM3_SM3

    # Convert well reference depths
    wells_metric = []
    for well in wells:
        well_metric = {
            "name": well.name,
            "well_type": well.well_type,
            "i": well.i,
            "j": well.j,
            "k1": well.k1,
            "k2": well.k2,
            "reference_depth": well.reference_depth * FT_TO_M,
            "well_bore_diameter": well.well_bore_diameter * FT_TO_M,
            "control_mode": well.control_mode,
            "target_rate": well.target_rate,
            "bhp_limit": well.bhp_limit * PSIA_TO_BAR,
            "inject_fluid": well.inject_fluid,
            "inject_rate": well.inject_rate,
            "bhp_max": well.bhp_max * PSIA_TO_BAR,
        }
        wells_metric.append(well_metric)

    return {
        # Reservoir geometry (flat for template)
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "dz_list": dz_list,
        "top_depth": top_depth,
        # EQUIL parameters
        "equil_datum_depth": equil_datum_depth,
        "equil_pressure_datum": equil_pressure_datum,
        "equil_woc": equil_woc,
        "equil_goc": equil_goc,
        "equil_owc_depth": equil_owc_depth,
        # RSVD parameters
        "rsvd_depth1": rsvd_depth1,
        "rsvd_depth2": rsvd_depth2,
        "rsvd_rs": rsvd_rs_metric,
        # Wells with metric values
        "wells": wells_metric,
        # Conversion constants (for reference in template if needed)
        "FT_TO_M": FT_TO_M,
        "PSIA_TO_BAR": PSIA_TO_BAR,
        "SCF_STB_TO_SM3_SM3": SCF_STB_TO_SM3_SM3,
    }


def build_deck(
    desc: str,
    output_path: Optional[Path] = None,
    use_llm: bool = False,
    fluid: Optional[FluidDescriptor] = None,
) -> tuple[str, LintResult]:
    """
    Build an OPM Flow deck from natural language description.

    Args:
        desc: Natural language description (e.g., "10x10x5 grid, simple depletion, one producer")
        output_path: Optional path to write the deck file
        use_llm: Whether to use LLM for parameter extraction (requires API key)
        fluid: Optional FluidDescriptor for fluid-specific PVT tables

    Returns:
        Tuple of (deck_string, lint_result)

    Raises:
        ValueError: If deck generation or linting fails
    """
    # Extract parameters (offline by default, LLM path optional)
    if use_llm and settings.active_llm_client != "offline":
        # TODO: Add LLM extraction path (Phase 2)
        spec = extract_parameters_offline(desc)
    else:
        spec = extract_parameters_offline(desc)

    # Attach fluid if provided
    if fluid is not None:
        spec.fluid = fluid

    # Get template context
    context = _compute_template_context(spec)

    # Render deck
    env = _get_template_env()
    template = env.get_template("base.j2")
    deck_string = template.render(**context)

    # Lint the generated deck
    if output_path:
        output_path.write_text(deck_string)

    # Create temporary file for linting if no output path
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_string)
        temp_path = Path(f.name)

    try:
        lint_result = lint_deck(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return deck_string, lint_result


def build_deck_from_spec(
    spec: ModelSpec,
    output_path: Optional[Path] = None,
) -> tuple[str, LintResult]:
    """
    Build an OPM Flow deck from a ModelSpec directly.

    Args:
        spec: ModelSpec object with full specification
        output_path: Optional path to write the deck file

    Returns:
        Tuple of (deck_string, lint_result)
    """
    context = _compute_template_context(spec)

    env = _get_template_env()
    template = env.get_template("base.j2")
    deck_string = template.render(**context)

    if output_path:
        output_path.write_text(deck_string)

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_string)
        temp_path = Path(f.name)

    try:
        lint_result = lint_deck(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    return deck_string, lint_result