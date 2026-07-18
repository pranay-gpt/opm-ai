"""Builder module for generating OPM Flow decks from natural language descriptions."""

from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader

from opm_ai.builder.models import ModelSpec, ReservoirSpec, WellSpec, WellType
from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.linter import lint_deck, LintResult


def build_deck(
    description: str,
    output_path: Optional[Path] = None,
) -> tuple[str, LintResult]:
    """
    Build an OPM Flow deck from natural language description.

    Args:
        description: Natural language description of the model.
        output_path: Optional path to write the deck file.

    Returns:
        Tuple of (deck_string, LintResult).
    """
    # Extract parameters from description (offline path)
    spec = extract_parameters_offline(description)

    # Ensure we have at least one well
    if not spec.wells:
        spec.wells = [
            WellSpec(
                name="PROD",
                well_type=WellType.PROD,
                i=spec.reservoir.nx,
                j=spec.reservoir.ny,
                k1=1,
                k2=spec.reservoir.nz,
                reference_depth=spec.reservoir.top_depth + sum(spec.reservoir.dz) / 2,
            )
        ]

    # Render template
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("base.j2")

    deck_string = template.render(
        title=spec.title,
        reservoir=spec.reservoir,
        wells=spec.wells,
        field_units=True,
        start_date=spec.start_date,
        max_connections=spec.reservoir.nz,
    )

    # Write to file if requested
    if output_path:
        output_path.write_text(deck_string)

    # Lint the generated deck
    if output_path:
        lint_result = lint_deck(output_path)
    else:
        # Write to temp file for linting
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".DATA", delete=False) as f:
            f.write(deck_string)
            temp_path = Path(f.name)
        lint_result = lint_deck(temp_path)
        temp_path.unlink()

    return deck_string, lint_result


__all__ = ["build_deck"]