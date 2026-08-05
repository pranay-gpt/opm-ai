"""Tests for GET /api/keywords (editor autocomplete source)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.routes import keywords as keywords_route
from opm_ai.api.server import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _real_rm_path() -> Path:
    return REPO_ROOT / "opm_ai" / "linter" / "keywords_rm.json"


def _stub_rm_path() -> Path:
    return REPO_ROOT / "tests" / "fixtures" / "erm_params_stub.json"


@pytest.fixture
def client():
    """TestClient backed by the real (current) catalogues."""
    keywords_route.__dict__.pop("_CACHE", None)
    keywords_route._RM_PATH = _real_rm_path()  # type: ignore[attr-defined]
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def params_client():
    """TestClient whose ERM catalogue is the Stage 3.5 stub.

    The real ``keywords_rm.json`` does not yet carry the ``parameters``
    field that a separate agent is regenerating in parallel. To keep
    the new Stage 3.5 tests self-contained and independent of that
    commit's ordering, point the route module at
    ``tests/fixtures/erm_params_stub.json`` instead. The stub ships a
    single ``WELSPECS`` record with two parameter entries — enough to
    exercise the new contract.
    """
    stub = _stub_rm_path()
    assert stub.is_file(), f"ERM params stub missing: {stub}"
    keywords_route.__dict__.pop("_CACHE", None)
    keywords_route._RM_PATH = stub  # type: ignore[attr-defined]
    app = create_app()
    with TestClient(app) as client:
        yield client
    # Best-effort restore so subsequent tests see the real catalogue.
    keywords_route.__dict__.pop("_CACHE", None)
    keywords_route._RM_PATH = _real_rm_path()  # type: ignore[attr-defined]


@pytest.mark.integration
def test_get_keywords_returns_200(client):
    r = client.get("/api/keywords")
    assert r.status_code == 200
    body = r.json()
    assert "keyword_count" in body
    assert "keywords" in body
    assert body["keyword_count"] == len(body["keywords"])


@pytest.mark.integration
def test_get_keywords_includes_welspecs(client):
    r = client.get("/api/keywords")
    body = r.json()
    names = {k["name"] for k in body["keywords"]}
    assert "WELSPECS" in names, "WELSPECS must be in the merged catalogue"


@pytest.mark.integration
def test_get_keywords_welspecs_has_sections(client):
    r = client.get("/api/keywords")
    body = r.json()
    welspecs = next(k for k in body["keywords"] if k["name"] == "WELSPECS")
    # ERM union: SCHEDULE only (sections list is the authoritative flagtable)
    assert welspecs["sections"] == ["SCHEDULE"], (
        f"WELSPECS sections should be ['SCHEDULE'] from ERM, got {welspecs['sections']}"
    )


@pytest.mark.integration
def test_get_keywords_includes_erm_only_keyword(client):
    """DUALPORO is in the ERM catalogue but absent from the fixture
    catalogue. The union means it appears in /api/keywords with at
    least its authoritative section (RUNSPEC).
    """
    r = client.get("/api/keywords")
    body = r.json()
    dualporo = next((k for k in body["keywords"] if k["name"] == "DUALPORO"), None)
    assert dualporo is not None, "DUALPORO must be in the merged catalogue"
    assert "RUNSPEC" in dualporo["sections"]


@pytest.mark.integration
def test_get_keywords_includes_fixture_only_keyword(client):
    """A keyword only seen in fixtures (high count, no ERM section) is
    present in the union with at least its observational record.
    """
    r = client.get("/api/keywords")
    body = r.json()
    # NOECHO appears in 522 fixtures, in all 8 sections per the ERM
    # flagtable. The union record should have sections_observed populated.
    echo = next(k for k in body["keywords"] if k["name"] == "NOECHO")
    assert echo["sections_observed"], (
        "NOECHO should have non-empty sections_observed from fixture catalogue"
    )


@pytest.mark.integration
def test_get_keywords_sorted_by_name(client):
    r = client.get("/api/keywords")
    body = r.json()
    names = [k["name"] for k in body["keywords"]]
    assert names == sorted(names), "keywords must be sorted alphabetically"


@pytest.mark.integration
def test_get_keywords_minimum_count(client):
    """Union is at least as large as the fixture catalogue (1079)."""
    r = client.get("/api/keywords")
    body = r.json()
    assert body["keyword_count"] >= 1079, (
        f"keyword_count={body['keyword_count']} below fixture-only floor 1079"
    )


# ---------------------------------------------------------------------------
# Stage 3.5: per-keyword parameters
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_api_keywords_includes_parameters_field(params_client):
    """At least one catalogue record exposes a non-empty `parameters`
    list. The stub fixture provides WELSPECS with two entries.
    """
    r = params_client.get("/api/keywords")
    body = r.json()
    assert any(
        isinstance(k.get("parameters"), list) and len(k["parameters"]) > 0
        for k in body["keywords"]
    ), "expected at least one catalogue record with non-empty parameters"


@pytest.mark.integration
def test_api_keywords_parameters_have_name_and_brief(params_client):
    """For the WELSPECS record, the parameters field is a non-empty list
    of objects with a non-empty `name` (string) and a `brief` (string,
    allowed to be empty when the ERM doesn't provide one).
    """
    r = params_client.get("/api/keywords")
    body = r.json()
    welspecs = next(k for k in body["keywords"] if k["name"] == "WELSPECS")
    params = welspecs.get("parameters")
    assert isinstance(params, list) and params, (
        f"WELSPECS must have a non-empty parameters list, got: {params!r}"
    )
    for p in params:
        assert isinstance(p, dict), f"parameter item must be a dict, got {p!r}"
        assert isinstance(p.get("name"), str) and p["name"], (
            f"parameter name must be a non-empty string, got {p.get('name')!r}"
        )
        assert isinstance(p.get("brief"), str), (
            f"parameter brief must be a string (possibly empty), "
            f"got {p.get('brief')!r}"
        )