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

    if spec.fluid is not None:
        fluid = spec.fluid
        # Validate pressure range - EQUIL uses 4800 psia default
        p_min, p_max = fluid.pressure_range
        if p_max < 4800:
            raise ValueError(
                f"Fluid pressure range max ({p_max} psia) must be >= 4800 psia "
                f"(EQUIL datum pressure). Extend pressure_range_psi to at least 4800."
            )

        # Build PVT blocks
        pvt_blocks = build_pvt_blocks(fluid)

        # Validate
        unit_system = "FIELD" if spec.field_units else "METRIC"
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

    return {
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