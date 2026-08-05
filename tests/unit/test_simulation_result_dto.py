"""Tests for SimulationResultDTO / CrashReportDTO from_runner classmethods.

Covers the F4.2 / F4.7 audit fix: the routes used to inline 12 lines of
field-by-field conversion from runner.SimulationResult to
api.schemas.SimulationResultDTO, with two near-identical copies (success
and failure branches). Now the DTO owns the conversion and the route
just calls it.

These tests pin the conversion contract: Path -> str, list -> copy,
None passed through unchanged.
"""

from __future__ import annotations

from pathlib import Path

from opm_ai.api.schemas import CrashReportDTO, SimulationResultDTO
from opm_ai.runner.models import CrashReport, SimulationResult


def _make_runner_result(**overrides) -> SimulationResult:
    """Build a runner SimulationResult with sensible defaults for round-trip tests."""
    base = dict(
        success=True,
        output_dir=Path("/tmp/out"),
        crash_report=None,
        returncode=0,
        timed_out=False,
        duration_s=1.5,
        stdout="STDOUT",
        stderr="STDERR",
        warnings=["warn1", "warn2"],
        summary_files={"summary.csv": Path("/tmp/out/summary.csv")},
        prt_path=Path("/tmp/out/CASE.PRT"),
    )
    base.update(overrides)
    return SimulationResult(**base)


class TestSimulationResultDTOFromRunner:
    """F4.2 audit fix coverage."""

    def test_basic_round_trip(self):
        runner_result = _make_runner_result()
        dto = SimulationResultDTO.from_runner(runner_result)

        assert dto.success is True
        assert dto.output_dir == "/tmp/out"  # Path -> str
        assert dto.returncode == 0
        assert dto.duration_s == 1.5
        assert dto.stdout == "STDOUT"
        assert dto.stderr == "STDERR"
        assert dto.warnings == ["warn1", "warn2"]

    def test_path_fields_are_stringified(self):
        """Path -> str contract: the DTO is JSON-serializable."""
        runner_result = _make_runner_result(
            output_dir=Path("/some/very/long/path"),
            prt_path=Path("/some/very/long/path/CASE.PRT"),
            summary_files={"a": Path("/x/a"), "b": Path("/x/b")},
        )
        dto = SimulationResultDTO.from_runner(runner_result)

        assert isinstance(dto.output_dir, str)
        assert isinstance(dto.prt_path, str)
        assert all(isinstance(v, str) for v in dto.summary_files.values())

    def test_none_crash_report_round_trips(self):
        runner_result = _make_runner_result(crash_report=None)
        dto = SimulationResultDTO.from_runner(runner_result)
        assert dto.crash_report is None

    def test_crash_report_round_trips(self):
        runner_result = _make_runner_result(
            success=False,
            crash_report=CrashReport(
                keyword="DIMPES",
                line=42,
                message="Missing required section",
            ),
        )
        dto = SimulationResultDTO.from_runner(runner_result)

        assert isinstance(dto.crash_report, CrashReportDTO)
        assert dto.crash_report.keyword == "DIMPES"
        assert dto.crash_report.line == 42
        assert dto.crash_report.message == "Missing required section"

    def test_warnings_list_is_a_copy_not_a_reference(self):
        """F4.7 audit guard: the conversion must not hand out the same
        list object. If the route mutates dto.warnings (e.g. appends a
        post-completion note) we don't want that mutation to bleed
        back into the runner model."""
        runner_result = _make_runner_result()
        dto = SimulationResultDTO.from_runner(runner_result)
        dto.warnings.append("appended-after-conversion")
        assert "appended-after-conversion" not in runner_result.warnings

    def test_dto_is_json_serializable(self):
        """Regression guard: the conversion must produce a model that
        Pydantic can serialize to JSON without errors."""
        import json

        runner_result = _make_runner_result()
        dto = SimulationResultDTO.from_runner(runner_result)
        # If output_dir/prt_path are still Path, json.dumps raises TypeError
        json.dumps(dto.model_dump(mode="json"))


class TestCrashReportDTOFromRunner:
    """F4.7 audit fix coverage."""

    def test_none_returns_none(self):
        """CrashReportDTO.from_runner(None) returns None so callers can
        chain without an extra `if` guard in the route."""
        assert CrashReportDTO.from_runner(None) is None

    def test_basic_round_trip(self):
        runner = CrashReport(keyword="DIMPES", line=10, message="oops")
        dto = CrashReportDTO.from_runner(runner)

        assert dto.keyword == "DIMPES"
        assert dto.line == 10
        assert dto.message == "oops"

    def test_optional_fields_default_in_runner_carry_through(self):
        runner = CrashReport(message="only message")
        dto = CrashReportDTO.from_runner(runner)

        assert dto.keyword is None
        assert dto.line is None
        assert dto.message == "only message"