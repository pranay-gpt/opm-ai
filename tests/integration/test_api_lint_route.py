"""Integration tests for the /api/lint route (F2.6 audit fix).

The lint route used to raise HTTP 500 when the linter itself crashed
(a regex blowing up on a malformed deck, a rule referencing a
missing section, etc). The frontend then had to handle a 500
separately from a 200-with-errors response. F2.6 changes this to a
200 with a structured LintResult containing a synthetic LINT-000
issue, so the existing lint-UI code path renders the error like any
other lint failure.

Tests:
  1. Linter crash -> 200, passed=False, errors[0].rule_id == "LINT-000",
     lint_summary is None.
  2. ValueError on bad input -> 400 (regression: still surfaces as
     an HTTP error, not as a synthetic LINT-000).
  3. Successful lint on a valid deck -> 200, passed=True, the
     synthetic LINT-000 issue is NOT present (regression guard).
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app
from opm_ai.api.routes import lint as lint_route


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def spe1_deck_path():
    path = Path("tests/fixtures/spe1/SPE1CASE1.DATA")
    assert path.exists(), f"Fixture not found: {path}"
    return str(path)


def test_lint_route_returns_200_on_linter_crash(client, spe1_deck_path, monkeypatch):
    """When the linter raises, the route returns 200 with a synthetic
    LINT-000 issue so the frontend's existing lint-error UI renders it
    (F2.6 audit fix). The original trace is logged server-side."""

    def _boom(_path):
        raise RuntimeError("synthetic linter crash for test")

    # The route imports lint_deck_func by name; monkeypatch the symbol
    # the route module binds to, not the source module's, to match the
    # route's lookup path exactly.
    monkeypatch.setattr(lint_route, "lint_deck_func", _boom)

    response = client.post("/api/lint", json={"deck_path": spe1_deck_path})

    assert response.status_code == 200, (
        f"Expected 200 with structured error, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert data["passed"] is False
    assert data["lint_summary"] is None
    assert len(data["errors"]) == 1
    assert "Linter crashed" in data["errors"][0]
    assert "RuntimeError" in data["errors"][0]
    assert "synthetic linter crash for test" in data["errors"][0]
    # The synthetic issue must carry the LINT-000 rule_id so the
    # frontend can distinguish it from real lint findings.
    issues = data.get("issues", [])
    assert any(iss.get("rule_id") == "LINT-000" for iss in issues), (
        f"Expected at least one LINT-000 issue, got: {issues}"
    )


def test_lint_route_returns_400_on_value_error(client, spe1_deck_path, monkeypatch):
    """A ValueError from validation still surfaces as 400 (regression:
    the F2.6 fix is for unexpected linter crashes, not for input
    validation, which keeps its existing 400 contract)."""

    def _bad(_path):
        raise ValueError("invalid deck content")

    monkeypatch.setattr(lint_route, "lint_deck_func", _bad)

    response = client.post("/api/lint", json={"deck_path": spe1_deck_path})

    assert response.status_code == 400, (
        f"Expected 400 for ValueError, got {response.status_code}: {response.text}"
    )


def test_lint_route_returns_200_on_success(client, spe1_deck_path):
    """A real successful lint still returns 200 with passed=True and
    the synthetic LINT-000 issue is NOT present (regression guard)."""

    response = client.post("/api/lint", json={"deck_path": spe1_deck_path})

    assert response.status_code == 200, (
        f"Expected 200 on success, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert data["passed"] is True
    issues = data.get("issues", [])
    assert not any(iss.get("rule_id") == "LINT-000" for iss in issues), (
        f"Successful lint must not contain LINT-000 synthetic issue, got: {issues}"
    )
