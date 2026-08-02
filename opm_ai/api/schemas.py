"""Pydantic DTOs for FastAPI routes and tool schemas."""

from pathlib import Path
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Import explainer types
try:
    from opm_ai.explainer.models import ExplanationLevel
except ImportError:
    # Fallback for when explainer not yet available
    ExplanationLevel = Literal["beginner", "intermediate", "advanced"]


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


class BuildResponse(BaseModel):
    """Response from deck build operation."""
    model_config = ConfigDict(from_attributes=True)

    deck: str
    lint: "LintResult"


class LintRequest(BaseModel):
    """Request to lint a deck file."""
    model_config = ConfigDict(from_attributes=True)

    deck_path: str


class LintIssue(BaseModel):
    """Single lint issue."""
    model_config = ConfigDict(from_attributes=True)

    severity: Literal["ERROR", "WARNING", "INFO"]
    section: str | None = None
    keyword: str | None = None
    line: int | None = None
    message: str
    rule_id: str | None = None


class LintResult(BaseModel):
    """Result of linting a deck."""
    model_config = ConfigDict(from_attributes=True)

    deck_path: str
    issues: list[LintIssue] = Field(default_factory=list)
    lint_summary: str | None = None
    errors: list[str] = Field(default_factory=list)
    passed: bool = True

    @property
    def error_issues(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warning_issues(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]

    def compute_fields(self) -> "LintResult":
        """Compute derived fields."""
        self.errors = [i.message for i in self.issues if i.severity == "ERROR"]
        self.passed = len(self.errors) == 0
        return self


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


class CrashReportDTO(BaseModel):
    """DTO for crash report in job store."""
    model_config = ConfigDict(from_attributes=True)

    keyword: str | None = None
    line: int | None = None
    message: str


class KPIsResponse(BaseModel):
    """Response with KPIs and plots."""
    model_config = ConfigDict(from_attributes=True)

    kpis: dict[str, Any]
    plots: dict[str, str]  # plot_name -> Plotly JSON (fig.to_json())


class SnapshotsResponse(BaseModel):
    """Response with ResInsight 3D snapshot export results."""
    model_config = ConfigDict(from_attributes=True)

    success: bool
    snapshots: list[str]  # PNG filenames, served at /results/{job_id}/snapshots/{name}
    error: str | None = None
    duration_s: float


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