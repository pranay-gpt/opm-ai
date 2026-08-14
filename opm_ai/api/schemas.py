"""Pydantic DTOs for FastAPI routes and tool schemas."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Re-export the canonical lint models so the rest of the API can
# import them from opm_ai.api.schemas (the historic surface) without
# the extra dataclass-to-Pydantic hop. The linter owns the truth; the
# API used to keep a parallel Pydantic copy that had to be kept in
# sync and converted into in two routes. With this re-export,
# `LintIssue` and `LintResult` from opm_ai.api.schemas are the SAME
# classes as the ones in opm_ai.linter.models — no conversion, no
# drift.
from opm_ai.linter.models import LintIssue, LintResult  # noqa: E402

# Import explainer types
try:
    from opm_ai.explainer.models import ExplanationLevel
except ImportError:
    # Fallback for when explainer not yet available
    ExplanationLevel = Literal["beginner", "intermediate", "advanced"]

if TYPE_CHECKING:
    # Used only in `from_runner` classmethods (F4.2/F4.7 audit fix).
    # Importing these at runtime would create a circular dependency:
    # api.schemas -> runner.models -> ... -> api.routes -> api.schemas.
    # The forward-reference strings on the from_runner signatures are
    # enough for type checking and runtime, this TYPE_CHECKING block
    # is just for the IDE/pytest typing.
    from opm_ai.runner.models import CrashReport, SimulationResult


class FluidDescriptorRequest(BaseModel):
    """Fluid descriptor for PVT table generation (optional)."""
    model_config = ConfigDict(from_attributes=True)

    api_gravity: float = Field(gt=0, le=80, description="Oil API gravity (0-80)")
    gas_specific_gravity: float = Field(gt=0, le=2.0, description="Gas specific gravity (0-2.0)")
    gor: float = Field(ge=0, description="Gas-oil ratio (scf/stb), >= 0")
    reservoir_temp_f: float | None = Field(default=None, ge=-459.67, description="Reservoir temperature in degF")
    reservoir_temp_c: float | None = Field(default=None, ge=-273.15, description="Reservoir temperature in degC")
    salinity_ppm: float = Field(ge=0, default=0.0, description="Water salinity in ppm")
    pressure_range_psi: list[float] | None = None  # [min, max]
    unit_system: Literal["FIELD", "METRIC"] = "FIELD"
    # Oil PVT correlation family. Defaults to Standing when null.
    # Restricted to the three oil correlations (Standing | VasquezBeggs |
    # AlMarhoun); LET/Corey are excluded because they are relative
    # permeability correlations, not PVT.
    correlation: Literal["Standing", "VasquezBeggs", "AlMarhoun"] | None = Field(
        default=None,
        description="Oil PVT correlation family (Standing | VasquezBeggs | AlMarhoun). Defaults to Standing when null.",
    )

    @field_validator("correlation", mode="before")
    @classmethod
    def _allow_null_correlation(cls, v):
        # Frontend may send empty string or null when user has not picked
        # anything yet; accept both and let None flow through as "Standing".
        if v == "" or v is None:
            return None
        return v

    @model_validator(mode="after")
    def _check_temperatures(self) -> "FluidDescriptorRequest":
        """Validate that not both temperature fields are provided."""
        if self.reservoir_temp_f is not None and self.reservoir_temp_c is not None:
            raise ValueError("Provide only one of reservoir_temp_f or reservoir_temp_c, not both")
        return self


class BuildRequest(BaseModel):
    """Request to build a deck from natural language description."""
    model_config = ConfigDict(from_attributes=True)

    description: str
    output_path: str | None = None
    use_llm: bool = False
    fluid: FluidDescriptorRequest | None = None

    # Optional rock-basics overrides the UI lets the user confirm or
    # adjust before generation. None = use the extracted/defaulted value.
    # See Stage 3.2 in docs/superpowers/specs/2026-08-03-phase-2-design.md.
    porosity: float | None = Field(default=None, ge=0.01, le=0.5, description="Override porosity (fraction)")
    top_depth: float | None = Field(default=None, ge=0, le=30000, description="Override top depth (ft)")
    initial_pressure: float | None = Field(default=None, ge=14.7, le=20000, description="Override initial pressure at datum (psia)")
    dz: list[float] | None = Field(default=None, description="Override layer thickness per layer (ft)")
    permx: list[float] | None = Field(default=None, description="Override X-permeability per layer (mD)")
    permy: list[float] | None = Field(default=None, description="Override Y-permeability per layer (mD)")
    permz: list[float] | None = Field(default=None, description="Override Z-permeability per layer (mD)")


# Provenance tags for the rock-basics fields exposed via BuildResponse.
# Plain string literals - the UI matches on these without needing a
# shared enum import, and they serialise directly to JSON.
PROVENANCE_EXTRACTED = "extracted"
PROVENANCE_DEFAULTED = "defaulted"
PROVENANCE_USER_OVERRIDE = "user_override"
PROVENANCE_REQUIRED_MISSING = "required_missing"

# The set of rock-basics fields surfaced to the UI. Adding a new field
# here requires extending the parser, the merge step in builder.build_deck,
# and the DeckBuilder form - keep this list aligned with all three.
ROCK_BASICS_FIELDS: tuple[str, ...] = (
    "porosity",
    "top_depth",
    "initial_pressure",
    "dz",
    "permx",
    "permy",
    "permz",
)


class BuildResponse(BaseModel):
    """Response from deck build operation."""
    model_config = ConfigDict(from_attributes=True)

    deck: str
    lint: LintResult
    # Provenance per rock-basics field: where did the value come from?
    # Keys: "porosity", "top_depth", "initial_pressure", "dz",
    #       "permx", "permy", "permz". Values: see FieldProvenance.
    provenance: dict[str, str] = Field(default_factory=dict)
    # Final resolved values for the rock-basics fields, so the UI can
    # render the same numbers it just generated without re-parsing the
    # deck text. Lists are serialised as arrays; scalars stay scalars.
    resolved: dict[str, Any] = Field(default_factory=dict)


class LintRequest(BaseModel):
    """Request to lint a deck file."""
    model_config = ConfigDict(from_attributes=True)

    deck_path: str


class RunRequest(BaseModel):
    """Request to run a simulation."""
    model_config = ConfigDict(from_attributes=True)

    deck_path: str
    timeout: int = 120


class JobStatus(BaseModel):
    """Status of an async simulation job."""
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    result: "SimulationResultDTO | None" = None
    error: str | None = None
    kind: str = "real"  # "real" or "imported"


class SimulationResultDTO(BaseModel):
    """DTO for simulation result in job store."""
    model_config = ConfigDict(from_attributes=True)

    success: bool
    output_dir: str
    crash_report: "CrashReportDTO | None" = None
    returncode: int | None = None
    duration_s: float = 0.0
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = []
    summary_files: dict[str, str] = {}
    prt_path: str | None = None

    @classmethod
    def from_runner(cls, result: "SimulationResult") -> "SimulationResultDTO":
        """Convert a runner SimulationResult to its JSON-serializable DTO.

        F4.2 audit fix: collapses the 12-line inline conversion that was
        duplicated in run.py (success and failure branches). All Path
        fields are stringified here because the DTO's job-store contract
        is "serializable", and Path is not JSON-serializable. Returns a
        new DTO; the runner model is untouched so callers can keep using
        it for filesystem ops.
        """
        return cls(
            success=result.success,
            output_dir=str(result.output_dir) if result.output_dir is not None else "",
            crash_report=CrashReportDTO.from_runner(result.crash_report),
            returncode=result.returncode,
            duration_s=result.duration_s,
            stdout=result.stdout,
            stderr=result.stderr,
            warnings=list(result.warnings),
            summary_files={k: str(v) for k, v in result.summary_files.items()},
            prt_path=str(result.prt_path) if result.prt_path else None,
        )


class CrashReportDTO(BaseModel):
    """DTO for crash report in job store."""
    model_config = ConfigDict(from_attributes=True)

    keyword: str | None = None
    line: int | None = None
    message: str

    @classmethod
    def from_runner(cls, report: "CrashReport | None") -> "CrashReportDTO | None":
        """Convert a runner CrashReport to its JSON-serializable DTO.

        F4.7 audit fix: removes the inline field-by-field copy that
        lived in run.py. Returns None when the runner report is None so
        callers can chain without an extra guard.
        """
        if report is None:
            return None
        return cls(
            keyword=report.keyword,
            line=report.line,
            message=report.message,
        )


class KPIsResponse(BaseModel):
    """Response with KPIs and plots."""
    model_config = ConfigDict(from_attributes=True)

    kpis: dict[str, Any]
    plots: dict[str, str]  # plot_name -> Plotly JSON (fig.to_json())
    viewer_available: bool = False  # True if /api/results/{id}/resinsight can launch a GUI


class CsvFrequency(str, Enum):
    """Resampling frequency for CSV export."""
    NATIVE = "native"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CategorizedVectorsResponse(BaseModel):
    """Categorised view of a summary DataFrame."""
    model_config = ConfigDict(from_attributes=True)

    field_rates: list[str] = []
    field_cumulative: list[str] = []
    field_derived: list[str] = []
    well_rates: dict[str, list[str]] = {}
    well_cumulative: dict[str, list[str]] = {}
    well_injection: dict[str, list[str]] = {}
    wells: list[str] = []


class PlotGroupResponse(BaseModel):
    """Response from /plot_group/{group}.

    `figure_json` is `""` when plot generation failed (the route already
    logged the trace; the client renders an empty card).
    """
    model_config = ConfigDict(from_attributes=True)

    group: str
    figure_json: str = ""
    error: str | None = None


class SnapshotsResponse(BaseModel):
    """Response with ResInsight 3D snapshot export results."""
    model_config = ConfigDict(from_attributes=True)

    success: bool
    snapshots: list[str]  # PNG filenames, served at /results/{job_id}/snapshots/{name}
    error: str | None = None
    duration_s: float


class ResinsightLaunchResponse(BaseModel):
    """Response from POST /api/results/{job_id}/resinsight.

    Either a fresh launch (launched=True, pid set) or a no-op because the
    previous launch is still alive (launched=False, pid set, reason set).
    """
    model_config = ConfigDict(from_attributes=True)

    launched: bool
    pid: int | None = None
    reason: str | None = None  # why launched is False; null on a fresh launch
    error: str | None = None  # why the route failed; null on success


class GridTimeStep(BaseModel):
    """One restart report step of a 3D case."""
    model_config = ConfigDict(from_attributes=True)

    index: int
    report: int
    days: float
    date: str  # ISO yyyy-mm-dd, "" when the restart header had no valid date


class GridBBox(BaseModel):
    """Axis-aligned bounds of the drawn cells, in viewer coordinates."""
    model_config = ConfigDict(from_attributes=True)

    min: list[float]  # [x, y, z]
    max: list[float]


class GridInfoResponse(BaseModel):
    """Dimensions, available properties and time steps of a case's grid."""
    model_config = ConfigDict(from_attributes=True)

    nx: int
    ny: int
    nz: int
    active_cells: int
    total_cells: int
    unit_system: str  # METRIC | FIELD | LAB | PVT-M, "" when unknown
    length_unit: str  # m | ft | cm
    origin: list[float]  # subtracted from every exported coordinate
    bbox: GridBBox
    static_properties: list[str]
    dynamic_properties: list[str]
    derived_properties: list[str]  # subset of dynamic_properties we compute
    time_steps: list[GridTimeStep]
    fault_face_count: int
    nnc_count: int
    has_wells: bool


class GridRangeResponse(BaseModel):
    """Global value range of one property over all time steps."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    min: float
    max: float
    steps_scanned: int


class WellCompletion(BaseModel):
    """One well connection to a grid cell."""
    model_config = ConfigDict(from_attributes=True)

    i: int
    j: int
    k: int
    cell: int  # active cell index, -1 when the cell is inactive
    center: list[float]  # viewer coordinates
    open: bool


class WellDTO(BaseModel):
    """A well at one restart step, in viewer coordinates."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    type: Literal["producer", "oil_injector", "gas_injector", "water_injector", "unknown"]
    head: list[float]
    i: int
    j: int
    k: int
    trajectory: list[list[float]]  # ordered head -> toe, empty when unavailable
    completions: list[WellCompletion]


class WellsResponse(BaseModel):
    """Wells present at one restart step."""
    model_config = ConfigDict(from_attributes=True)

    step: int
    wells: list[WellDTO]


class ChatMessage(BaseModel):
    """Chat message with optional tool calls."""
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant", "tool", "system"]
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    """Request for chat endpoint."""
    model_config = ConfigDict(from_attributes=True)

    messages: list[ChatMessage]
    session_id: str


# OpenAI-style tool schemas for function calling
BUILD_DECK_TOOL = {
    "type": "function",
    "function": {
        "name": "build_deck",
        "description": "Build an OPM Flow deck from a natural language description (e.g., '10x10x3 grid, one producer, 2 year depletion')",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Natural language description of the reservoir model"},
                "output_path": {"type": "string", "description": "Optional path to write the deck file"},
            },
            "required": ["description"],
            "additionalProperties": False,
        },
    },
}

LINT_DECK_TOOL = {
    "type": "function",
    "function": {
        "name": "lint_deck",
        "description": "Lint an OPM Flow deck file for syntax and best practices",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_path": {"type": "string", "description": "Path to the .DATA deck file"},
            },
            "required": ["deck_path"],
            "additionalProperties": False,
        },
    },
}

RUN_SIMULATION_TOOL = {
    "type": "function",
    "function": {
        "name": "run_simulation",
        "description": "Run an OPM Flow simulation as a background job",
        "parameters": {
            "type": "object",
            "properties": {
                "deck_path": {"type": "string", "description": "Path to the .DATA deck file"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)"},
            },
            "required": ["deck_path"],
            "additionalProperties": False,
        },
    },
}

GET_KPIS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_kpis",
        "description": "Get KPIs and plots for a completed simulation job",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID from run_simulation"},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
}

EXPORT_SNAPSHOTS_TOOL = {
    "type": "function",
    "function": {
        "name": "export_snapshots",
        "description": "Export 3D reservoir view snapshots (PNG images) for a completed simulation using ResInsight",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job ID from run_simulation"},
            },
            "required": ["job_id"],
            "additionalProperties": False,
        },
    },
}

# Explainer tool schemas for chat
EXPLAIN_CONCEPT_TOOL = {
    "type": "function",
    "function": {
        "name": "explain_concept",
        "description": "Explain a reservoir engineering concept at a specified pedagogical level",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic or question to explain (e.g., 'why did watercut spike after 3 years?')"},
                "level": {"type": "string", "enum": ["beginner", "intermediate", "advanced"], "default": "intermediate", "description": "Explanation level"},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
}

GENERATE_QUIZ_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_quiz",
        "description": "Generate a multiple-choice quiz from a scenario description",
        "parameters": {
            "type": "object",
            "properties": {
                "scenario_summary": {"type": "string", "description": "Description of the simulation scenario"},
                "n_questions": {"type": "integer", "default": 3, "minimum": 1, "maximum": 10, "description": "Number of questions"},
            },
            "required": ["scenario_summary"],
            "additionalProperties": False,
        },
    },
}

TOOLS = [
    BUILD_DECK_TOOL,
    LINT_DECK_TOOL,
    RUN_SIMULATION_TOOL,
    GET_KPIS_TOOL,
    EXPORT_SNAPSHOTS_TOOL,
    EXPLAIN_CONCEPT_TOOL,
    GENERATE_QUIZ_TOOL,
]


# Explainer request/response schemas
class ExplainRequest(BaseModel):
    """Request for explanation generation."""
    model_config = ConfigDict(from_attributes=True)

    topic: str | None = None
    kpis: dict[str, Any] | None = None
    level: ExplanationLevel = "intermediate"
    context: dict | None = None


class ExplainResponse(BaseModel):
    """Response from explanation generation."""
    model_config = ConfigDict(from_attributes=True)

    topic: str
    level: ExplanationLevel
    text: str
    citations: list[dict[str, str]]
    follow_up_questions: list[str]


class QuizRequest(BaseModel):
    """Request for quiz generation."""
    model_config = ConfigDict(from_attributes=True)

    scenario_summary: str
    level: ExplanationLevel = "intermediate"
    n_questions: int = Field(default=3, ge=1, le=10)
    topic_focus: list[str] | None = None


class QuizResponse(BaseModel):
    """Response from quiz generation."""
    model_config = ConfigDict(from_attributes=True)

    scenario_summary: str
    questions: list[dict[str, Any]]


class LearningReportRequest(BaseModel):
    """Request for learning report generation."""
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    conversation_history: list[dict[str, Any]]
    kpis_history: list[dict] | None = None


class LearningReportResponse(BaseModel):
    """Response from learning report generation."""
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    topics_covered: list[str]
    explanations_generated: int
    questions_asked: int
    quiz_scores: dict[str, float] | None
    key_concepts: list[str]
    citations_used: list[dict[str, str]]
    markdown: str


class UploadResponse(BaseModel):
    """Response from /api/upload_deck.

    The frontend fills the deck path input with ``deck_path`` so
    the existing /api/run flow consumes it unchanged. ``include_dir``
    is set only when the upload included any include/ files - the
    frontend uses it to render a "Uploaded to" hint so the user can
    find the files again if the run fails. ``byte_count`` is the
    sum of the deck + include/ bytes written, useful for the
    progress UI.
    """
    deck_path: str
    include_dir: str | None = None
    byte_count: int


class ImportedResultResponse(BaseModel):
    """Response from POST /api/imported-results."""
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    files_received: list[str]
    warnings: list[str]