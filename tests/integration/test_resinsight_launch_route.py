"""Tests for POST /api/results/{job_id}/resinsight.

Exercises the route's gates and PID-tracking without launching a real
ResInsight process: launch_resinsight is monkeypatched so the route
thinks the spawn succeeded, and we assert the bookkeeping.
"""

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.job_store import create_job, set_job_completed, set_job_running
from opm_ai.api.routes.results import _launched_resinsight_pids
from opm_ai.api.schemas import SimulationResultDTO
from opm_ai.api.server import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _completed_job(tmp_path, name="job-launch-ok") -> str:
    """Seed a completed job whose output_dir has an .EGRID file."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "CASE.EGRID").write_bytes(b"\x00")
    jid = create_job(name)
    set_job_running(jid)
    set_job_completed(
        jid,
        SimulationResultDTO(
            success=True,
            output_dir=str(out),
            returncode=0,
            duration_s=1.0,
            stdout="",
            stderr="",
            warnings=[],
            summary_files={},
            prt_path=None,
        ),
    )
    return jid


@pytest.fixture(autouse=True)
def _clear_pids():
    """Each test starts with an empty PID dict - previous tests' launches
    do not poison the no-double-launch assertion."""
    _launched_resinsight_pids.clear()
    yield
    _launched_resinsight_pids.clear()


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch):
    """TestClient reports 'testserver' as the request host, not 127.0.0.1.
    Patch the gate so tests can drive the route without faking the
    connection. The 403 path is exercised by test_launch_non_loopback_403
    below, which does NOT apply this fixture.
    """
    monkeypatch.setattr(
        "opm_ai.api.routes.results._client_is_loopback",
        lambda request: True,
    )


def test_launch_unavailable_returns_503(client, tmp_path, monkeypatch):
    jid = _completed_job(tmp_path)
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: False
    )
    res = client.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 503, res.text
    assert "not available" in res.json()["detail"].lower()


def test_launch_non_loopback_returns_403(tmp_path, monkeypatch):
    """The loopback gate runs BEFORE the job check - a remote client
    must never learn whether job IDs exist.

    This test deliberately does NOT use the autouse _patch_loopback
    fixture: opt out via monkeypatch.setattr restoring the real function
    is implicit because the fixture is autouse, so we work around it by
    patching _client_is_loopback to return False inside the test body.
    """
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results._client_is_loopback",
        lambda request: False,
    )
    out = tmp_path / "out_nl"
    out.mkdir()
    (out / "CASE.EGRID").write_bytes(b"\x00")
    jid = create_job("job-nonloopback")
    set_job_running(jid)
    set_job_completed(
        jid,
        SimulationResultDTO(
            success=True, output_dir=str(out), returncode=0, duration_s=1.0,
            stdout="", stderr="", warnings=[], summary_files={}, prt_path=None,
        ),
    )
    app = create_app()
    with TestClient(app) as c:
        res = c.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 403
    assert "loopback" in res.json()["detail"].lower()


def test_launch_unknown_job_returns_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    res = client.post("/api/results/no_such_job/resinsight")
    assert res.status_code == 404, res.text


def test_launch_running_job_returns_400(client, tmp_path, monkeypatch):
    """A running job has no .EGRID yet - the route must reject before
    even trying to find a case file."""
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    jid = create_job("running-job")
    set_job_running(jid)
    res = client.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 400, res.text
    assert "not completed" in res.json()["detail"].lower()


def test_launch_no_case_file_returns_404(client, tmp_path, monkeypatch):
    """Completed job but its output dir contains no .EGRID/.DATA."""
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    out = tmp_path / "empty_out"
    out.mkdir()
    jid = create_job("no-case-job")
    set_job_running(jid)
    set_job_completed(
        jid,
        SimulationResultDTO(
            success=True, output_dir=str(out), returncode=0, duration_s=1.0,
            stdout="", stderr="", warnings=[], summary_files={}, prt_path=None,
        ),
    )
    res = client.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 404, res.text


def test_launch_happy_path_records_pid(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    fake_pid = 12345
    monkeypatch.setattr(
        "opm_ai.api.routes.results.launch_resinsight",
        lambda case_file: {"success": True, "pid": fake_pid, "error": None},
    )
    jid = _completed_job(tmp_path)
    res = client.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["launched"] is True
    assert body["pid"] == fake_pid
    assert body["reason"] is None
    assert _launched_resinsight_pids[jid] == fake_pid


def test_launch_already_running_no_double_spawn(client, tmp_path, monkeypatch):
    """A second click while the GUI is still up must NOT spawn another
    91MB process - it must return the existing PID with launched=False."""
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results._pid_alive", lambda pid: True
    )

    spawn_calls = []
    def fake_launch(case_file):
        spawn_calls.append(case_file)
        return {"success": True, "pid": 99999, "error": None}
    monkeypatch.setattr(
        "opm_ai.api.routes.results.launch_resinsight", fake_launch
    )

    jid = _completed_job(tmp_path)
    res1 = client.post(f"/api/results/{jid}/resinsight")
    res2 = client.post(f"/api/results/{jid}/resinsight")
    assert res1.status_code == 200 and res2.status_code == 200
    assert res1.json()["launched"] is True
    assert res2.json()["launched"] is False
    assert res2.json()["reason"] == "already running"
    assert len(spawn_calls) == 1, "second call must not have spawned"


def test_launch_dead_pid_respawns(client, tmp_path, monkeypatch):
    """If the previously-tracked PID is gone (user closed the GUI), a
    new click must launch again - not silently report 'already running'."""
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results._pid_alive", lambda pid: False
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results.launch_resinsight",
        lambda case_file: {"success": True, "pid": 77777, "error": None},
    )
    jid = _completed_job(tmp_path)
    # Pre-seed a stale PID.
    _launched_resinsight_pids[jid] = 1
    res = client.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 200
    assert res.json()["launched"] is True
    assert res.json()["pid"] == 77777


def test_launch_spawn_failure_returns_500(client, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results.launch_resinsight",
        lambda case_file: {"success": False, "pid": None, "error": "boom"},
    )
    jid = _completed_job(tmp_path)
    res = client.post(f"/api/results/{jid}/resinsight")
    assert res.status_code == 500
    assert res.json()["detail"] == "boom"


def test_get_results_reports_viewer_available(client, tmp_path, monkeypatch):
    """KPIsResponse carries viewer_available so the UI can disable the button."""
    monkeypatch.setattr(
        "opm_ai.api.routes.results.is_resinsight_available", lambda: True
    )
    # Existing fixtures have to provide summary files - simpler: stub
    # the data extraction and return an empty-but-valid result.
    import pandas as pd
    monkeypatch.setattr(
        "opm_ai.api.routes.results.read_summary",
        lambda output_dir: pd.DataFrame({"FOPR": [1.0], "FWPR": [0.1]}),
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results.extract_kpis",
        lambda df: {"oil_rate": 1.0},
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results.plot_production",
        lambda df: type("F", (), {"to_json": staticmethod(lambda: "{}")})(),
    )
    monkeypatch.setattr(
        "opm_ai.api.routes.results.plot_pressure",
        lambda df: type("F", (), {"to_json": staticmethod(lambda: "{}")})(),
    )
    out = tmp_path / "out2"
    out.mkdir()
    (out / "CASE.EGRID").write_bytes(b"\x00")
    jid = create_job("results-viewer")
    set_job_running(jid)
    set_job_completed(
        jid,
        SimulationResultDTO(
            success=True, output_dir=str(out), returncode=0, duration_s=1.0,
            stdout="", stderr="", warnings=[], summary_files={}, prt_path=None,
        ),
    )
    res = client.get(f"/api/results/{jid}")
    assert res.status_code == 200
    assert res.json()["viewer_available"] is True