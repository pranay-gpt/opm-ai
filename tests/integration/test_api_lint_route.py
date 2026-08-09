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


def test_lint_route_attaches_explanations(client, spe1_deck_path):
    """Phase 5: each issue in the response carries an `explanation` field.

    The explainer is wired into lint_deck; every rule_id that has a
    registered explainer (L2.* and the modern L-prefix) gets a
    non-empty Markdown explanation. Rule-ids without a registered
    explainer (legacy L-prefix) gracefully fall back to None — the
    test only asserts that *known* issues have explanations.
    """
    # Trigger a deliberate failure to get a known L2 issue. Use a
    # minimal deck in tmp_path that has a missing WELLDIMS.
    import tempfile, json as _json
    with tempfile.NamedTemporaryFile(mode="w", suffix=".DATA", delete=False) as f:
        f.write("""\\
RUNSPEC
DIMENS
  5 5 3 /
""")
        tmp_deck = f.name

    response = client.post("/api/lint", json={"deck_path": tmp_deck})
    assert response.status_code == 200
    data = response.json()

    # Find the WELLDIMS.required issue.
    welldims_issues = [
        i for i in data.get("issues", [])
        if i.get("rule_id") == "L2.WELLDIMS.required"
    ]
    assert len(welldims_issues) == 1
    exp = welldims_issues[0].get("explanation")
    assert exp, f"L2.WELLDIMS.required must have a non-empty explanation, got: {welldims_issues[0]}"
    assert "WELLDIMS" in exp
    assert "**Fix**" in exp
