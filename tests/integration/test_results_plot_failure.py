"""Tests for GET /api/results/{job_id} (KPIs + plots).

Covers:
- F1.5 audit fix: plot generation failure produces an EMPTY STRING in
  the `plots` dict, not a stringified `{"error": ...}` value. The
  client's Plotly JSON.parse used to silently succeed on the old shape
  (because it is valid JSON), then Plotly.newPlot failed downstream,
  leaving the user with an empty card and no diagnostic.
- Happy path: when both plots succeed, the dict contains valid Plotly
  JSON strings.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.job_store import create_job, set_job_completed, set_job_running
from opm_ai.api.schemas import SimulationResultDTO
from opm_ai.api.server import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _completed_job(tmp_path, name="results-plot-test") -> str:
    out = tmp_path / "out"
    out.mkdir()
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
        ),
    )
    return jid


class TestPlotFailureShape:
    """F1.5: backend must log + return empty string, not stringified JSON."""

    def test_plot_failure_returns_empty_string(self, monkeypatch, tmp_path, client):
        import pandas as pd

        monkeypatch.setattr(
            "opm_ai.api.routes.results.read_summary",
            lambda output_dir: pd.DataFrame({"FOPR": [1.0], "FWPR": [0.1]}),
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.extract_kpis",
            lambda df: {"oil_rate": 1.0},
        )

        def _exploding(df):
            raise RuntimeError("boom: cannot render chart for empty df")

        monkeypatch.setattr(
            "opm_ai.api.routes.results.plot_production", _exploding
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.plot_pressure", _exploding
        )

        jid = _completed_job(tmp_path)
        r = client.get(f"/api/results/{jid}")
        assert r.status_code == 200, r.text
        body = r.json()

        assert "production" in body["plots"]
        assert "pressure" in body["plots"]
        # The F1.5 contract: empty string (NOT stringified JSON).
        assert body["plots"]["production"] == ""
        assert body["plots"]["pressure"] == ""

    def test_plot_failure_does_not_look_like_plotly_json(
        self, monkeypatch, tmp_path, client
    ):
        """Regression guard: the OLD shape was '{"error": ...}' which is
        valid JSON and used to slip past JSON.parse on the client. The
        new contract is the empty string, which JSON.parse rejects."""
        import pandas as pd

        monkeypatch.setattr(
            "opm_ai.api.routes.results.read_summary",
            lambda output_dir: pd.DataFrame({"FOPR": [1.0]}),
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.extract_kpis",
            lambda df: {},
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.plot_production",
            lambda df: (_ for _ in ()).throw(RuntimeError("nope")),
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.plot_pressure",
            lambda df: (_ for _ in ()).throw(RuntimeError("nope")),
        )

        jid = _completed_job(tmp_path)
        body = client.get(f"/api/results/{jid}").json()

        # The old shape was '{"error": "..."}' - i.e. a valid JSON object
        # string. The new shape is '' which JSON.parse rejects.
        import json as _json
        with pytest.raises(_json.JSONDecodeError):
            _json.loads(body["plots"]["production"])


class TestPlotSuccessShape:
    """Happy path: when both plots succeed the entries are valid Plotly
    JSON strings (objects with `data` and `layout` keys)."""

    def test_plot_success_returns_plotly_json(self, monkeypatch, tmp_path, client):
        import pandas as pd

        monkeypatch.setattr(
            "opm_ai.api.routes.results.read_summary",
            lambda output_dir: pd.DataFrame({"FOPR": [1.0], "FWPR": [0.1]}),
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.extract_kpis",
            lambda df: {"oil_rate": 1.0},
        )

        def _stub_fig():
            class _F:
                @staticmethod
                def to_json():
                    return '{"data": [], "layout": {}}'

            return _F()

        monkeypatch.setattr(
            "opm_ai.api.routes.results.plot_production", lambda df: _stub_fig()
        )
        monkeypatch.setattr(
            "opm_ai.api.routes.results.plot_pressure", lambda df: _stub_fig()
        )

        jid = _completed_job(tmp_path)
        body = client.get(f"/api/results/{jid}").json()

        assert body["plots"]["production"] == '{"data": [], "layout": {}}'
        assert body["plots"]["pressure"] == '{"data": [], "layout": {}}'