"""Build route: POST /api/build -> builder.build_deck"""

from fastapi import APIRouter, HTTPException
from pathlib import Path

from opm_ai.api.schemas import BuildRequest, BuildResponse, LintResult, LintIssue, FluidDescriptorRequest
from opm_ai.builder import build_deck
from opm_ai.preprocess import FluidDescriptor

router = APIRouter()


@router.post("/build", response_model=BuildResponse)
async def build_deck_endpoint(request: BuildRequest) -> BuildResponse:
    """
    Build an OPM Flow deck from natural language description.

    Delegates to opm_ai.builder.builder.build_deck.
    """
    try:
        output_path = Path(request.output_path) if request.output_path else None

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
            )

        deck, lint_result = build_deck(request.description, output_path, request.use_llm, fluid)

        return BuildResponse(
            deck=deck,
            lint=LintResult(
                deck_path=lint_result.deck_path,
                issues=[
                    LintIssue(
                        severity=issue.severity,
                        section=issue.section,
                        keyword=issue.keyword,
                        line=issue.line,
                        message=issue.message,
                        rule_id=issue.rule_id,
                    )
                    for issue in lint_result.issues
                ],
                lint_summary=lint_result.lint_summary,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))