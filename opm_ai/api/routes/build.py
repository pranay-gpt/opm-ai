"""Build route: POST /api/build -> builder.build_deck"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from opm_ai.api.paths import validate_output_path
from opm_ai.api.schemas import (
    BuildRequest, BuildResponse, LintResult, FluidDescriptorRequest,
    PROVENANCE_USER_OVERRIDE, ROCK_BASICS_FIELDS,
)
from opm_ai.builder import build_deck, extract_parameters_offline_with_provenance
from opm_ai.preprocess import FluidDescriptor

router = APIRouter()


def _apply_rock_basics_overrides(spec, request, provenance: dict[str, str]) -> None:
    """Apply BuildRequest overrides to spec.reservoir and update provenance.

    A non-None field on the request always wins over the extracted/defaulted
    value, and its provenance tag becomes "user_override". Fields the user
    did not touch keep whatever tag extract_parameters_offline_with_provenance
    set.
    """
    overrides = {
        "porosity": request.porosity,
        "top_depth": request.top_depth,
        "initial_pressure": request.initial_pressure,
        "dz": request.dz,
        "permx": request.permx,
        "permy": request.permy,
        "permz": request.permz,
    }
    for field, value in overrides.items():
        if value is None:
            continue
        setattr(spec.reservoir, field, value)
        provenance[field] = PROVENANCE_USER_OVERRIDE


def _resolved_rock_basics(spec) -> dict:
    """Snapshot the rock-basics fields the UI renders. Lists preserved as lists."""
    out: dict = {}
    for field in ROCK_BASICS_FIELDS:
        v = getattr(spec.reservoir, field)
        if isinstance(v, list):
            out[field] = list(v)
        else:
            out[field] = v
    return out


@router.post("/build", response_model=BuildResponse)
async def build_deck_endpoint(request: BuildRequest) -> BuildResponse:
    """
    Build an OPM Flow deck from natural language description.

    Surfaces provenance (extracted/defaulted/user_override) for the rock-basics
    fields so the UI can confirm defaulted values before the user runs a
    simulation. See Stage 3.2 in docs/superpowers/specs/2026-08-03-phase-2-design.md.
    """
    try:
        # Validate output path if provided
        output_path = None
        if request.output_path:
            output_path = validate_output_path(request.output_path)

        # Convert fluid descriptor if provided
        fluid = None
        if request.fluid is not None:
            fluid = FluidDescriptor(
                api_gravity=request.fluid.api_gravity,
                gas_specific_gravity=request.fluid.gas_specific_gravity,
                gor=request.fluid.gor,
                reservoir_temp_f=request.fluid.reservoir_temp_f,
                reservoir_temp_c=request.fluid.reservoir_temp_c,
                salinity_ppm=request.fluid.salinity_ppm,
                pressure_range_psi=tuple(request.fluid.pressure_range_psi) if request.fluid.pressure_range_psi else None,
                unit_system=request.fluid.unit_system,
                # correlation defaults to Standing when the UI sends null
                # (the dropdown starts unpicked in stored state).
                correlation=request.fluid.correlation or "Standing",
            )

        # Extract with provenance, apply overrides, build. build_deck_from_spec
        # is used (not build_deck) so the provenance reflects the same spec
        # that gets rendered.
        spec, provenance = extract_parameters_offline_with_provenance(request.description)
        _apply_rock_basics_overrides(spec, request, provenance)
        if fluid is not None:
            spec.fluid = fluid

        from opm_ai.builder.builder import build_deck_from_spec
        deck, lint_result = build_deck_from_spec(spec, output_path)

        # lint_result is already the canonical Pydantic LintResult
        # (re-exported from opm_ai.linter.models via api.schemas), so
        # we do not rebuild it from dataclass instances any more.
        return BuildResponse(
            deck=deck,
            lint=lint_result,
            provenance=provenance,
            resolved=_resolved_rock_basics(spec),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build failed: {e}")