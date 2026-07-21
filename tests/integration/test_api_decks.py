"""Tests for POST /api/decks (save deck text) and the SPA deep-link fallback."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from opm_ai.api.server import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


MINIMAL_DECK = "RUNSPEC\nTITLE\n test /\n"


def test_save_deck_returns_usable_path(client):
    resp = client.post("/api/decks", json={"content": MINIMAL_DECK})
    assert resp.status_code == 200
    deck_path = resp.json()["deck_path"]
    p = Path(deck_path)
    assert p.exists()
    assert p.name == "DECK.DATA"
    assert p.read_text() == MINIMAL_DECK
    # The saved path must be accepted by /api/lint (allowlisted temp dir).
    lint = client.post("/api/lint", json={"deck_path": deck_path})
    assert lint.status_code == 200


def test_save_deck_custom_filename(client):
    resp = client.post("/api/decks", json={"content": MINIMAL_DECK, "filename": "MY.DATA"})
    assert resp.status_code == 200
    assert resp.json()["deck_path"].endswith("/MY.DATA")


def test_save_deck_rejects_bad_input(client):
    assert client.post("/api/decks", json={"content": "  "}).status_code == 400
    assert client.post(
        "/api/decks", json={"content": "x", "filename": "../evil.DATA"}
    ).status_code == 400
    assert client.post(
        "/api/decks", json={"content": "x", "filename": "no_suffix.txt"}
    ).status_code == 400
    assert client.post(
        "/api/decks", json={"content": "A" * (2 * 1024 * 1024 + 1)}
    ).status_code == 413


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html").exists(),
    reason="frontend/dist not built",
)
def test_spa_fallback_serves_index_for_client_routes(client):
    index = client.get("/").text
    for route in ("/linter", "/deck-builder", "/results"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert resp.text == index, route
    # API 404s must NOT fall back to the SPA.
    assert client.get("/api/run/nonexistent-job").status_code == 404
