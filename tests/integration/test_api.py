"""Integration tests for OPM-AI FastAPI backend.

Test coverage per docs/conversations/06-chat-and-api.md section 3:
1. POST /api/build with description -> deck with RUNSPEC/GRID/PROPS/SOLUTION/SCHEDULE, lint.passed == true
2. POST /api/lint with SPE1CASE1.DATA -> passed == true
3. POST /api/lint with nonexistent path -> 4xx or error response (graceful handling)
4. POST /api/run with valid deck -> returns job_id; poll GET /api/run/{job_id} until completed/failed; assert completed
5. GET /api/results/{job_id} after completed run -> kpis["days"] > 0, "production" in plots, plots["production"] parses as JSON with "data" key
6. GET /api/run/nonexistent-id -> 404
7. GET /api/results/nonexistent-id -> 404

All tests marked with @pytest.mark.integration and @pytest.mark.slow.
"""

import json
import time
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient for integration tests."""
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def spe1_deck_path():
    """Path to SPE1CASE1.DATA fixture."""
    path = Path("tests/fixtures/spe1/SPE1CASE1.DATA")
    assert path.exists(), f"Fixture not found: {path}"
    return str(path)


@pytest.fixture(scope="module")
def build_deck_path(tmp_path_factory):
    """Build a depletion deck and write to temp file for run tests."""
    tmp_dir = tmp_path_factory.mktemp("decks")
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/build", json={
            "description": "10x10x3 grid, one producer, 2 year depletion"
        })
        assert response.status_code == 200, f"Build failed: {response.text}"
        data = response.json()
        assert data["lint"]["passed"] is True, f"Build lint failed: {data['lint']['errors']}"
        deck_path = tmp_dir / "depletion.DATA"
        deck_path.write_text(data["deck"])
        return str(deck_path)


@pytest.fixture(scope="module")
def run_job_id(client, build_deck_path):
    """Start a simulation run and return job_id."""
    response = client.post("/api/run", json={
        "deck_path": build_deck_path,
        "timeout": 180
    })
    assert response.status_code == 200, f"Run failed: {response.text}"
    data = response.json()
    assert "job_id" in data
    return data["job_id"]


class TestBuildEndpoint:
    """Tests for POST /api/build"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_build_deck_returns_valid_deck_with_sections(self, client):
        """POST /api/build with description -> deck contains required sections, lint.passed == true."""
        response = client.post("/api/build", json={
            "description": "10x10x3 grid, one producer, 2 year depletion"
        })

        assert response.status_code == 200, f"Build failed: {response.text}"
        data = response.json()

        # Verify deck structure
        deck = data["deck"]
        assert "RUNSPEC" in deck, "Deck missing RUNSPEC section"
        assert "GRID" in deck, "Deck missing GRID section"
        assert "PROPS" in deck, "Deck missing PROPS section"
        assert "SOLUTION" in deck, "Deck missing SOLUTION section"
        assert "SCHEDULE" in deck, "Deck missing SCHEDULE section"

        # Verify lint passed
        lint = data["lint"]
        assert lint["passed"] is True, f"Lint failed: {lint.get('errors', [])}"
        assert lint["errors"] == [], f"Lint errors: {lint['errors']}"

    @pytest.mark.integration
    def test_build_deck_with_output_path(self, client, tmp_path):
        """POST /api/build with output_path writes file."""
        output_path = str(tmp_path / "test_deck.DATA")
        response = client.post("/api/build", json={
            "description": "Simple 10x10x1 depletion",
            "output_path": output_path
        })

        assert response.status_code == 200
        data = response.json()
        assert data["lint"]["passed"] is True
        assert Path(output_path).exists()
        deck_content = Path(output_path).read_text()
        assert "RUNSPEC" in deck_content
        assert "SCHEDULE" in deck_content

    @pytest.mark.integration
    @pytest.mark.slow
    def test_build_deck_with_fluid_descriptor_returns_pvto(self, client):
        """POST /api/build with fluid -> deck contains PVTO table (not hardcoded SPE1 Bo)."""
        response = client.post("/api/build", json={
            "description": "10x10x3 grid, one producer, 2 year depletion",
            "fluid": {
                "api_gravity": 35.0,
                "gas_specific_gravity": 0.75,
                "gor": 800,
                "reservoir_temp_f": 200,
                "salinity_ppm": 0,
                "pressure_range_psi": [14.7, 5000],
                "unit_system": "FIELD"
            }
        })

        assert response.status_code == 200, f"Build failed: {response.text}"
        data = response.json()

        # Verify deck structure
        deck = data["deck"]
        assert "RUNSPEC" in deck
        assert "GRID" in deck
        assert "PROPS" in deck
        assert "SOLUTION" in deck
        assert "SCHEDULE" in deck

        # Verify lint passed
        lint = data["lint"]
        assert lint["passed"] is True, f"Lint failed: {lint.get('errors', [])}"

        # Verify deck contains PVTO (not just default SPE1 values)
        assert "PVTO" in deck, "Deck missing PVTO section when fluid provided"

        # Verify it does NOT contain the hardcoded SPE1 Bo value (1.0620)
        assert "1.0620" not in deck, "Deck contains hardcoded SPE1 Bo value instead of generated PVTO table"

        # Verify PVTO table has multiple pressure entries (not just 1 row)
        pvto_section = deck[deck.find("PVTO"):]
        pvto_section = pvto_section[:pvto_section.find("/")]
        # Count numeric lines (data rows) in PVTO
        data_lines = [line for line in pvto_section.split('\n') if line.strip() and not line.strip().startswith('--') and not line.strip().startswith('PVTO')]
        # Should have more than 1 pressure entry
        assert len(data_lines) > 1, f"PVTO should have multiple pressure rows, got: {data_lines}"


class TestLintEndpoint:
    """Tests for POST /api/lint"""

    @pytest.mark.integration
    def test_lint_valid_deck_passes(self, client, spe1_deck_path):
        """POST /api/lint with valid SPE1 deck -> passed == true."""
        response = client.post("/api/lint", json={
            "deck_path": spe1_deck_path
        })

        assert response.status_code == 200, f"Lint failed: {response.text}"
        data = response.json()
        assert data["passed"] is True, f"Lint failed: {data.get('errors', [])}"
        assert data["deck_path"] == spe1_deck_path

    @pytest.mark.integration
    def test_lint_nonexistent_path_returns_error(self, client):
        """POST /api/lint with nonexistent path -> 4xx or error response (graceful handling)."""
        response = client.post("/api/lint", json={
            "deck_path": "/nonexistent/path/does_not_exist.DATA"
        })

        # Should return 4xx (404 or 500 with error detail) - graceful handling
        assert response.status_code >= 400, f"Expected 4xx error, got {response.status_code}"
        data = response.json()
        # Should have error detail, not crash
        assert "detail" in data or "error" in data, f"Expected error detail: {data}"


class TestRunEndpoint:
    """Tests for POST /api/run and GET /api/run/{job_id}"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_run_returns_job_id(self, client, build_deck_path):
        """POST /api/run with valid deck -> returns job_id."""
        response = client.post("/api/run", json={
            "deck_path": build_deck_path,
            "timeout": 180
        })

        assert response.status_code == 200, f"Run failed: {response.text}"
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert isinstance(data["job_id"], str) and len(data["job_id"]) > 0

    @pytest.mark.integration
    @pytest.mark.slow
    def test_run_poll_until_completed(self, client, run_job_id):
        """Poll GET /api/run/{job_id} until status in ('completed', 'failed'); assert completed."""
        job_id = run_job_id
        max_wait = 180  # seconds
        poll_interval = 3
        start = time.monotonic()

        while time.monotonic() - start < max_wait:
            response = client.get(f"/api/run/{job_id}")
            assert response.status_code == 200, f"Status check failed: {response.text}"
            data = response.json()

            assert data["job_id"] == job_id
            status = data["status"]

            if status == "completed":
                # Verify result structure
                assert data["result"] is not None
                assert data["result"]["success"] is True
                assert "output_dir" in data["result"]
                return  # Test passed
            elif status == "failed":
                pytest.fail(f"Job failed: {data.get('error', 'Unknown error')}")
            elif status in ("pending", "running"):
                time.sleep(poll_interval)
                continue
            else:
                pytest.fail(f"Unknown status: {status}")

        pytest.fail(f"Job {job_id} did not complete within {max_wait}s")

    @pytest.mark.integration
    def test_run_nonexistent_deck_returns_404(self, client):
        """POST /api/run with nonexistent deck -> 404."""
        response = client.post("/api/run", json={
            "deck_path": "/nonexistent/deck.DATA",
            "timeout": 60
        })

        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


class TestResultsEndpoint:
    """Tests for GET /api/results/{job_id}"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_results_after_completed_run(self, client, run_job_id):
        """GET /api/results/{job_id} after completed run -> kpis, plots with production data."""
        job_id = run_job_id

        # Wait for completion (re-use polling logic)
        max_wait = 180
        poll_interval = 3
        start = time.monotonic()

        while time.monotonic() - start < max_wait:
            status_resp = client.get(f"/api/run/{job_id}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            if status_data["status"] == "completed":
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Job failed: {status_data.get('error')}")
            time.sleep(poll_interval)
        else:
            pytest.fail(f"Job {job_id} did not complete in time")

        # Now fetch results
        response = client.get(f"/api/results/{job_id}")
        assert response.status_code == 200, f"Results failed: {response.text}"
        data = response.json()

        # Verify KPIs
        assert "kpis" in data
        kpis = data["kpis"]
        assert "days" in kpis, f"KPIs missing 'days': {kpis}"
        assert kpis["days"] > 0, f"KPIs days should be > 0, got {kpis['days']}"

        # Verify plots
        assert "plots" in data
        plots = data["plots"]
        assert "production" in plots, f"Plots missing 'production': {list(plots.keys())}"

        # Verify production plot parses as JSON with "data" key
        production_plot = plots["production"]
        assert isinstance(production_plot, str), "Production plot should be JSON string"
        plot_data = json.loads(production_plot)
        assert "data" in plot_data, f"Production plot JSON missing 'data' key: {list(plot_data.keys())}"
        assert isinstance(plot_data["data"], list), "Production plot 'data' should be a list"

        # Also verify pressure plot exists and parses
        assert "pressure" in plots, f"Plots missing 'pressure': {list(plots.keys())}"
        pressure_plot = json.loads(plots["pressure"])
        assert "data" in pressure_plot

    @pytest.mark.integration
    def test_results_nonexistent_job_returns_404(self, client):
        """GET /api/results/nonexistent-id -> 404."""
        response = client.get("/api/results/nonexistent-job-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


class TestRunStatusNotFound:
    """Tests for GET /api/run/{job_id} with invalid job"""

    @pytest.mark.integration
    def test_run_status_nonexistent_job_returns_404(self, client):
        """GET /api/run/nonexistent-id -> 404."""
        response = client.get("/api/run/nonexistent-job-id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """GET /health -> 200 with status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestBuildFluidValidation:
    """Tests for fluid descriptor validation in build endpoint."""

    @pytest.mark.integration
    def test_build_metric_fluid_rejected(self, client):
        """POST /api/build with METRIC fluid -> 400 (METRIC not supported end-to-end)."""
        response = client.post("/api/build", json={
            "description": "10x10x3 grid, one producer, 2 year depletion",
            "fluid": {
                "api_gravity": 35.0,
                "gas_specific_gravity": 0.75,
                "gor": 800,
                "reservoir_temp_c": 93.33,
                "salinity_ppm": 50000,
                "pressure_range_psi": [1.01325, 344.74],  # 14.7 psi, 5000 psi in bar (>= 4800 psi = 330 bar)
                "unit_system": "METRIC"
            }
        })

        assert response.status_code == 400, f"Expected 400 for METRIC fluid, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "METRIC" in data["detail"].upper(), f"Error should mention METRIC: {data['detail']}"

    @pytest.mark.integration
    def test_build_fluid_bad_pressure_range_400(self, client):
        """POST /api/build with pressure_range_psi max < 4800 -> 400 not 500."""
        response = client.post("/api/build", json={
            "description": "10x10x3 grid, one producer, 2 year depletion",
            "fluid": {
                "api_gravity": 35.0,
                "gas_specific_gravity": 0.75,
                "gor": 800,
                "reservoir_temp_f": 200,
                "salinity_ppm": 50000,
                "pressure_range_psi": [14.7, 3000],  # max < 4800
                "unit_system": "FIELD"
            }
        })

        assert response.status_code == 400, f"Expected 400 for bad pressure range, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "4800" in data["detail"] or "pressure" in data["detail"].lower()

    @pytest.mark.integration
    def test_build_fluid_both_temps_422(self, client):
        """POST /api/build with both reservoir_temp_f and reservoir_temp_c -> 422."""
        response = client.post("/api/build", json={
            "description": "10x10x3 grid, one producer, 2 year depletion",
            "fluid": {
                "api_gravity": 35.0,
                "gas_specific_gravity": 0.75,
                "gor": 800,
                "reservoir_temp_f": 200,
                "reservoir_temp_c": 93.33,  # Both provided - should fail
                "salinity_ppm": 50000,
                "pressure_range_psi": [14.7, 5000],
                "unit_system": "FIELD"
            }
        })

        assert response.status_code == 422, f"Expected 422 for both temps, got {response.status_code}: {response.text}"
        data = response.json()
        # FastAPI validation error format
        assert "detail" in data