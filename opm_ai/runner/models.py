"""Runner models for simulation jobs and results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SimulationJob:
    """Configuration for a simulation run."""

    deck_path: Path
    output_dir: Path
    timeout: int = 3600  # seconds
    flow_binary: str = "/usr/bin/flow"

    def __post_init__(self):
        self.deck_path = Path(self.deck_path)
        self.output_dir = Path(self.output_dir)


@dataclass
class CrashReport:
    """Simulation crash report."""

    exit_code: int
    stderr: str
    stdout: str
    error_type: str = "UNKNOWN"  # UNKNOWN, INPUT_ERROR, NUMERICAL, CRASH, TIMEOUT


@dataclass
class SimulationResult:
    """Result of a simulation run."""

    success: bool
    job: SimulationJob
    output_dir: Path
    crash_report: Optional[CrashReport] = None
    smspec_path: Optional[Path] = None
    unrst_path: Optional[Path] = None

    def __post_init__(self):
        self.output_dir = Path(self.output_dir)
        if self.smspec_path:
            self.smspec_path = Path(self.smspec_path)
        if self.unrst_path:
            self.unrst_path = Path(self.unrst_path)

    def __bool__(self) -> bool:
        return self.success