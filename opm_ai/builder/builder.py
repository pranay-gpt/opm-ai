"""Deck builder: natural language -> OPM Flow deck."""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader

from opm_ai.builder.models import ModelSpec, Scenario, ReservoirSpec, WellSpec, WellType
from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.linter import lint_deck, LintResult
from opm_ai.settings import settings


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

    return {
        "title": spec.title,
        "reservoir": reservoir,
        "wells": spec.wells,
        "max_connections": max_connections,
        "start_date": spec.start_date,
        "timesteps": timesteps,
        "timesteps_with_index": timesteps_with_index,
        "field_units": spec.field_units,
    }


def build_deck(
    desc: str,
    output_path: Optional[Path] = None,
    use_llm: bool = False,
) -> tuple[str, LintResult]:
    """
    Build an OPM Flow deck from natural language description.

    Args:
        desc: Natural language description (e.g., "10x10x5 grid, simple depletion, one producer")
        output_path: Optional path to write the deck file
        use_llm: Whether to use LLM for parameter extraction (requires API key)

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