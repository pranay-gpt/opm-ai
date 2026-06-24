# opm_ai/runner/models.py
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Optional


class SimulationStatus(str, Enum):
    SUCCESS = "success"
    FAILED  = "failed"
    RUNNING = "running"


@dataclass
class SimulationJob:
    """Input contract for a simulation run."""
    deck_path: Path                          # absolute path to .DATA file
    output_dir: Optional[Path] = None        # defaults to deck_path parent
    timeout_seconds: int = 300               # max run time in seconds


@dataclass
class CrashReport:
    """A single OPM error/warning parsed from stderr."""
    severity: str                            # "ERROR" | "WARNING" | "INFO"
    message: str
    keyword: Optional[str] = None
    line: Optional[int] = None


@dataclass
class SimulationResult:
    """Output contract from a completed simulation run."""
    job: SimulationJob
    status: SimulationStatus
    elapsed_seconds: float
    summary_file: Optional[Path] = None     # .SMSPEC path if run succeeded
    restart_file: Optional[Path] = None     # .UNRST path if run succeeded
    crash_reports: list[CrashReport] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == SimulationStatus.SUCCESS

    @property
    def errors(self) -> list[CrashReport]:
        return [r for r in self.crash_reports if r.severity == "ERROR"]

    @property
    def warnings(self) -> list[CrashReport]:
        return [r for r in self.crash_reports if r.severity == "WARNING"]
