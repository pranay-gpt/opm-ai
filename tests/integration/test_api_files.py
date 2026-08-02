"""Tests for GET /api/files (server-side deck browse).

The endpoint exists so a deck with INCLUDE can be selected without being
detached from its include/ tree, which is what broke when the old Browse
button uploaded the .DATA bytes alone.
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MODEL2 = FIXTURES / "model2"


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def test_default_listing_is_a_deck_root_not_the_temp_dir(client):
    """The picker must land somewhere with decks, not the mkdtemp scratch dir."""
    resp = client.get("/api/files")
    assert resp.status_code == 200
    body = resp.json()
    assert body["roots"], "no browsable roots configured"
    assert body["root"] == body["roots"][0]
    assert body["root"] != str(Path(tempfile.gettempdir()).resolve())


@pytest.mark.skipif(not MODEL2.is_dir(), reason="model2 fixture not present")
def test_lists_decks_with_include_flag_and_real_paths(client):
    resp = client.get("/api/files", params={"path": str(MODEL2)})
    assert resp.status_code == 200
    body = resp.json()

    by_name = {d["name"]: d for d in body["decks"]}
    deck = by_name["3_MULTFLT_MODEL2.DATA"]

    # The path must be the real location, so relative INCLUDEs resolve when
    # flow runs. A copy into a temp dir is exactly the bug this replaces.
    assert Path(deck["path"]) == MODEL2 / "3_MULTFLT_MODEL2.DATA"
    assert Path(deck["path"]).exists()
    assert deck["has_includes"] is True
    assert deck["size"] > 0

    # include/ is a sibling directory, reachable from the same listing.
    assert "include" in body["dirs"]
    assert (MODEL2 / "include").is_dir()

    # Only .DATA files are offered.
    assert all(d["name"].upper().endswith(".DATA") for d in body["decks"])


def test_include_flag_is_false_for_a_self_contained_deck(client):
    """Guard against has_includes always returning True.

    Written under the system temp dir, which is allowlisted, so this needs no
    write into the fixtures tree.
    """
    with tempfile.TemporaryDirectory(prefix="opmai_files_test_") as td:
        deck = Path(td) / "PLAIN.DATA"
        deck.write_text("RUNSPEC\nTITLE\n plain /\n")
        resp = client.get("/api/files", params={"path": td})
        assert resp.status_code == 200
        entry = next(d for d in resp.json()["decks"] if d["name"] == "PLAIN.DATA")
        assert entry["has_includes"] is False


def test_include_detection_needs_the_keyword_to_open_a_line(tmp_path):
    """Only a line starting with INCLUDE counts, so a comment cannot trip it."""
    from opm_ai.api.routes.files import _has_includes

    mentioned = tmp_path / "C.DATA"
    mentioned.write_text("RUNSPEC\n-- INCLUDE the faults below\nGRID\n")
    assert _has_includes(mentioned) is False

    real = tmp_path / "R.DATA"
    real.write_text("GRID\nINCLUDE\n 'include/g.grdecl' /\n")
    assert _has_includes(real) is True

    # Leading whitespace is legal in a deck.
    indented = tmp_path / "I.DATA"
    indented.write_text("GRID\n  INCLUDE\n 'include/g.grdecl' /\n")
    assert _has_includes(indented) is True


def test_rejects_paths_outside_the_allowlist(client):
    assert client.get("/api/files", params={"path": "/etc"}).status_code == 400
    assert client.get(
        "/api/files", params={"path": f"{FIXTURES}/../../../../etc"}
    ).status_code == 400


@pytest.mark.skipif(not MODEL2.is_dir(), reason="model2 fixture not present")
def test_rejects_a_file_path(client):
    resp = client.get(
        "/api/files", params={"path": str(MODEL2 / "3_MULTFLT_MODEL2.DATA")}
    )
    assert resp.status_code == 400


@pytest.mark.skipif(not MODEL2.is_dir(), reason="model2 fixture not present")
def test_browsed_deck_path_is_accepted_by_run(client):
    """End to end contract: what /api/files returns, /api/run must accept.

    flow is not invoked; this asserts the path-validation contract only, which
    is where the old temp-copy path failed.
    """
    listing = client.get("/api/files", params={"path": str(MODEL2)}).json()
    deck = next(d for d in listing["decks"] if d["has_includes"])

    from opm_ai.api.paths import validate_deck_path

    validated = validate_deck_path(deck["path"])
    assert validated == Path(deck["path"])
    # The sibling include/ dir the deck needs sits beside the validated path.
    assert (validated.parent / "include").is_dir()
