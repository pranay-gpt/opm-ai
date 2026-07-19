"""Runner models for simulation jobs and results."""

from pathlib import Path
from pydantic import BaseModel


class CrashReport(BaseModel):
    """Simulation crash report with keyword, line, and message."""

    keyword: str | None = None
    line: int | None = None
    message: str

    def __str__(self) -> str:
        """Format the crash report for readable display in f-strings."""
        parts = []
        if self.keyword:
            parts.append(f"keyword={self.keyword}")
        if self.line is not None:
            parts.append(f"line={self.line}")
        parts.append(self.message)
        return " ".join(parts)


class SimulationJob(BaseModel):
    """Configuration for a simulation run."""

    deck_path: Path
    output_dir: Path
    timeout: int


class SimulationResult(BaseModel):
    """Result of a simulation run.

    Contract fields (01-runner.md section 3): success, crash_report, output_dir.
    The remaining fields are non-contract extras used by postprocess/API.
    """

    success: bool
    output_dir: Path | None = None
    crash_report: CrashReport | None = None
    returncode: int | None = None
    timed_out: bool = False
    duration_s: float = 0.0
    stdout: str = ""
    stderr: str = ""
    warnings: list[str] = []
    summary_files: dict[str, Path] = {}
    prt_path: Path | None = None