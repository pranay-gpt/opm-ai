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


# ---------------------------------------------------------------------------
# launch_resinsight: detach a real GUI without waiting on it.
# ---------------------------------------------------------------------------


def test_launch_missing_case_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "no_such_binary")
    monkeypatch.setenv("DISPLAY", ":0")
    res = rib.launch_resinsight(tmp_path / "no_case.EGRID")
    # Binary check fires before case-file check - both fail, but the error
    # message should mention the binary (the earlier guard).
    assert res["success"] is False
    assert "not found" in res["error"].lower()


def test_launch_missing_binary(tmp_path, monkeypatch):
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "no_such_binary")
    monkeypatch.setenv("DISPLAY", ":0")
    res = rib.launch_resinsight(tmp_path / "M.EGRID")
    assert res["success"] is False
    assert res["pid"] is None
    assert "not found" in res["error"]


def test_launch_no_display(tmp_path, monkeypatch):
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "M.EGRID")
    monkeypatch.delenv("DISPLAY", raising=False)
    res = rib.launch_resinsight(tmp_path / "M.EGRID")
    assert res["success"] is False
    assert "DISPLAY" in res["error"]


def test_launch_case_file_does_not_exist(tmp_path, monkeypatch):
    # Binary exists so we get past that check; case file does not.
    (tmp_path / "fakebinary").write_bytes(b"")
    monkeypatch.setattr(settings, "resinsight_executable", tmp_path / "fakebinary")
    monkeypatch.setenv("DISPLAY", ":0")
    res = rib.launch_resinsight(tmp_path / "no_such.EGRID")
    assert res["success"] is False
    assert "not found" in res["error"]


def test_launch_spawns_detached(tmp_path, monkeypatch):
    """Spawn succeeds, PID is captured, and start_new_session was used.

    We use a tiny script that detaches itself - the equivalent of
    `subprocess.Popen` here is the OS, not Python, so we verify
    start_new_session via the resulting PGID being different from ours.
    """
    script = tmp_path / "hold.sh"
    script.write_text("#!/bin/sh\nsleep 30 &\nwait\n")
    script.chmod(0o755)
    (tmp_path / "case.EGRID").write_bytes(b"\x00")  # bridge checks the file exists
    monkeypatch.setattr(settings, "resinsight_executable", script)
    monkeypatch.setenv("DISPLAY", ":0")

    res = rib.launch_resinsight(tmp_path / "case.EGRID")
    assert res["success"] is True, res["error"]
    assert res["pid"] is not None
    pid = res["pid"]

    try:
        # start_new_session=True makes the child its own session leader;
        # PGID == PID. The parent test process's PGID is its PID.
        parent_pgid = os.getpgrp()
        os.kill(pid, 0)  # raises if dead
        child_pgid = os.getpgid(pid)
        assert child_pgid == pid, "child should be its own session leader"
        assert child_pgid != parent_pgid, "child should not share our session"
    finally:
        # Clean up the sleep we left behind.
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
