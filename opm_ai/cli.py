"""CLI module for OPM-AI."""

import click
from pathlib import Path

from opm_ai.builder import build_deck
from opm_ai.linter import lint_deck
from opm_ai.runner import run_simulation, SimulationJob


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """OPM-AI: AI layer on top of open source reservoir simulators."""
    pass


@main.command()
@click.argument("deck_path", type=click.Path(exists=True, path_type=Path))
def lint(deck_path: Path) -> None:
    """Lint an OPM Flow deck file."""
    result = lint_deck(deck_path)

    if result.passed:
        click.echo("Passed")
    else:
        click.echo(f"Failed: {len(result.errors)} errors")
        for error in result.errors:
            click.echo(f"  {error}")
    if result.warnings:
        for warning in result.warnings:
            click.echo(f"  Warning: {warning}")


@main.command()
@click.argument("description")
@click.option("-o", "--output", "output_path", type=click.Path(path_type=Path), help="Output deck file path")
def build(description: str, output_path: Path | None) -> None:
    """Build an OPM Flow deck from natural language description."""
    try:
        deck_string, lint_result = build_deck(description, output_path=output_path)

        if lint_result.passed:
            click.echo("Lint passed")
        else:
            click.echo(f"Lint failed: {len(lint_result.errors)} errors")
            for error in lint_result.errors:
                click.echo(f"  {error}")

        if output_path:
            click.echo(f"Deck written to {output_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@main.command()
@click.argument("deck_path", type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), help="Output directory for results")
@click.option("-t", "--timeout", type=int, default=3600, help="Timeout in seconds")
def run(deck_path: Path, output_dir: Path | None, timeout: int) -> None:
    """Run an OPM Flow simulation."""
    if output_dir is None:
        output_dir = deck_path.parent / f"{deck_path.stem}_output"

    job = SimulationJob(
        deck_path=deck_path,
        output_dir=output_dir,
        timeout=timeout,
    )

    click.echo(f"Running simulation: {deck_path}")
    click.echo(f"Output directory: {output_dir}")

    result = run_simulation(job)

    if result.success:
        click.echo("Simulation completed successfully")
        click.echo(f"Output: {result.output_dir}")
    else:
        click.echo("Simulation failed")
        if result.crash_report:
            click.echo(f"Crash report: {result.crash_report}")
        raise click.Abort()


if __name__ == "__main__":
    main()