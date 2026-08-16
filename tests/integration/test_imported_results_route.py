"""Integration tests for POST /api/imported-results."""
import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def _file_part(name: str, content: bytes):
    """Build a (field_name, (filename, content, mime)) tuple for files=[...]."""
    return ("files", (name, content, "application/octet-stream"))


def test_happy_path_creates_virtual_job(client):
    resp = client.post(
        "/api/imported-results",
        files=[_file_part("CASE.SMSPEC", b"smspec"), _file_part("CASE.UNSMRY", b"unsmry")],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_received"] == ["CASE.SMSPEC", "CASE.UNSMRY"]
    job_id = data["job_id"]

    # The virtual job must be reachable through /api/results/{id}
    # even though no simulation ever ran for it.
    response = client.get(f"/api/results/{job_id}")
    # Will be 400 (empty summary) — that's the right behaviour: the route
    # exists, the job is registered, it just has no real summary data.
    assert response.status_code in (200, 400)


def test_missing_smspec_returns_400(client):
    resp = client.post("/api/imported-results", files=[_file_part("CASE.UNSMRY", b"x")])
    assert resp.status_code == 400
    assert "SMSPEC" in resp.json()["detail"]


def test_esmry_alone_accepted(client):
    resp = client.post("/api/imported-results", files=[_file_part("CASE.ESMRY", b"x")])
    assert resp.status_code == 200


def test_optional_extensions_accepted(client):
    resp = client.post(
        "/api/imported-results",
        files=[
            _file_part("CASE.SMSPEC", b"x"),
            _file_part("CASE.UNSMRY", b"x"),
            _file_part("CASE.EGRID", b"x"),
            _file_part("CASE.UNRST", b"x"),
            _file_part("CASE.INIT", b"x"),
            _file_part("CASE.PRT", b"x"),
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()["files_received"]) == 6


def test_unsafe_filename_rejected(client):
    """Filenames with characters outside _SAFE_PATH_RE are rejected."""
    resp = client.post(
        "/api/imported-results",
        files=[
            _file_part("CASE.SMSPEC", b"x"),
            _file_part("CASE.UNSMRY", b"x"),
            _file_part("bad@file", b"x"),
        ],
    )
    assert resp.status_code == 400


def test_empty_file_rejected(client):
    resp = client.post(
        "/api/imported-results",
        files=[_file_part("CASE.SMSPEC", b""), _file_part("CASE.UNSMRY", b"x")],
    )
    assert resp.status_code == 400


def test_no_files_rejected(client):
    """Non-multipart request returns 415."""
    resp = client.post("/api/imported-results")
    assert resp.status_code == 415


def test_wrong_content_type_rejected(client):
    resp = client.post(
        "/api/imported-results",
        json={"files": ["CASE.SMSPEC"]},
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 415