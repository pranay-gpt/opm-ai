"""Tests for the ResInsight snapshot bridge.

The bridge shells out to the ResInsight batch CLI, which needs the binary and
a live X display. The pure-logic paths (missing binary, missing display,
missing case file, PNG caching) are tested without ResInsight; the actual
render is exercised by a slow test that skips when ResInsight/display absent.
"""

import os
from pathlib import Path

import pytest

from opm_ai.postprocess import resinsight_bridge as rib
from opm_ai.settings import settings


def test_find_case_file_prefers_egrid(tmp_path):
    (tmp_path / "M.DATA").write_text("RUNSPEC\n")
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    assert rib.find_case_file(tmp_path).name == "M.EGRID"


def test_find_case_file_falls_back_to_data(tmp_path):
    (tmp_path / "M.DATA").write_text("RUNSPEC\n")
    assert rib.find_case_file(tmp_path).name == "M.DATA"


def test_find_case_file_none_when_empty(tmp_path):
    assert rib.find_case_file(tmp_path) is None


def test_export_no_case_file(tmp_path):
    res = rib.export_snapshots(tmp_path)
    assert res["success"] is False
    assert "No .EGRID or .DATA" in res["error"]
    assert res["snapshots"] == []


def test_export_missing_binary(tmp_path, monkeypatch):
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "no_such_ResInsight")
    monkeypatch.setenv("DISPLAY", ":0")
    res = rib.export_snapshots(tmp_path)
    assert res["success"] is False
    assert "not found" in res["error"]


def test_export_no_display(tmp_path, monkeypatch):
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    # Point at a real file so the binary check passes and we reach the display check.
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "M.EGRID")
    monkeypatch.delenv("DISPLAY", raising=False)
    res = rib.export_snapshots(tmp_path)
    assert res["success"] is False
    assert "display" in res["error"].lower()


def test_export_uses_cached_pngs(tmp_path, monkeypatch):
    """A pre-existing PNG in the snapshot dir is returned without launching ResInsight."""
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "M.EGRID")
    monkeypatch.setenv("DISPLAY", ":0")

    snap_dir = tmp_path / rib.SNAPSHOT_SUBDIR
    snap_dir.mkdir()
    (snap_dir / "cached.png").write_bytes(b"\x89PNG")

    def _boom(*a, **k):  # would run if the cache were ignored
        raise AssertionError("ResInsight should not launch when cache present")

    monkeypatch.setattr(rib.subprocess, "run", _boom)

    res = rib.export_snapshots(tmp_path)
    assert res["success"] is True
    assert [Path(p).name for p in res["snapshots"]] == ["cached.png"]


def test_is_available_reflects_binary_and_display(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "M")
    monkeypatch.setenv("DISPLAY", ":0")
    assert rib.is_resinsight_available() is False  # binary missing
    (tmp_path / "M").write_text("x")
    assert rib.is_resinsight_available() is True
    monkeypatch.delenv("DISPLAY", raising=False)
    assert rib.is_resinsight_available() is False  # no display


# --- Slow: actual render, only when ResInsight + display are present ---

_CASE_DIR = Path("/tmp/ri_smoke/results")
_RUNNABLE = (
    Path(settings.resinsight_executable).is_file()
    and os.environ.get("DISPLAY")
    and (_CASE_DIR / "SMOKE.EGRID").is_file()
)


@pytest.mark.skipif(not _RUNNABLE, reason="ResInsight, DISPLAY, or SMOKE case unavailable")
def test_export_real_snapshot(tmp_path):
    snap_dir = tmp_path / "snaps"
    res = rib.export_snapshots(_CASE_DIR, snapshot_dir=snap_dir, timeout_s=120)
    assert res["success"] is True, res["error"]
    assert res["snapshots"], "expected at least one PNG"
    for p in res["snapshots"]:
        assert Path(p).is_file()
        assert Path(p).stat().st_size > 1000
