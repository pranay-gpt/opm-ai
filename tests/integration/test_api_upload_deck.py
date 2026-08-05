"""Integration tests for POST /api/upload_deck.

The route accepts a multipart upload with a required .DATA part
and an optional set of include/ parts. Writes everything into a
fresh mkdtemp under the system temp dir and returns the deck's
server-side path so /api/run can consume it unchanged.

Tests:
  1. Deck-only happy path -> 200, deck_path returned, file exists,
     passes validate_deck_path.
  2. Deck + include/ folder (3 files in a nested layout) -> 200,
     all files written, include_dir populated, layout preserved.
  3. include/ path with leading "include/" prefix is stripped (so
     users whose browser hands over webkitRelativePath of
     "include/foo.GRDECL" end up with include/foo.GRDECL inside
     the upload dir).
  4. Missing deck part -> 400.
  5. Non-.DATA filename -> 400.
  6. Empty deck file -> 400.
  7. Include path with '..' -> 400.
  8. Include path with absolute root -> 400.
  9. Duplicate include paths -> 400.
 10. Non-multipart content type -> 415.
 11. validate_deck_path accepts the returned path (regression
     guard - the path contract is what /api/run depends on).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app
from opm_ai.api.paths import validate_deck_path


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


# ---- helpers --------------------------------------------------------


def _data_part(content: bytes, filename: str = "DECK.DATA"):
    """Build a (field_name, bytes, filename) tuple for files={...}."""
    return ("deck", (filename, content, "application/octet-stream"))


def _include_part(relpath: str, content: bytes):
    """Build an include part. The filename becomes webkitRelativePath."""
    return ("include", (relpath, content, "application/octet-stream"))


# ---- happy path -----------------------------------------------------


def test_upload_deck_alone(client):
    """A minimal upload with only the .DATA returns 200 and writes
    the file to a fresh mkdtemp under the system temp dir."""
    deck_bytes = b"RUNSPEC\nDIMENS\n 1 1 1 /\nGRID\n/"

    resp = client.post(
        "/api/upload_deck",
        files=[_data_part(deck_bytes)],
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"deck_path", "include_dir", "byte_count"}
    assert body["include_dir"] is None
    assert body["byte_count"] == len(deck_bytes)

    p = Path(body["deck_path"])
    assert p.exists()
    assert p.read_bytes() == deck_bytes
    assert p.parent.name.startswith("opm_ai_upload_")
    # include/ was created even though no include parts arrived.
    assert (p.parent / "include").is_dir()


def test_upload_deck_with_includes(client):
    """A deck + a nested include/ layout preserves the directory
    structure and writes every file."""
    deck_bytes = b"RUNSPEC\nINCLUDE\n 'include/A.GRDECL' /\n"
    include_a = b"A payload"
    include_b = b"B payload"
    include_nested = b"nested payload"

    resp = client.post(
        "/api/upload_deck",
        files=[
            _data_part(deck_bytes, "MODEL2_3MULTFLT.DATA"),
            _include_part("include/A.GRDECL", include_a),
            _include_part("include/sub/B.GRDECL", include_b),
            _include_part("include/sub/deep/C.GRDECL", include_nested),
        ],
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    deck_path = Path(body["deck_path"])
    assert deck_path.exists()
    assert deck_path.name == "MODEL2_3MULTFLT.DATA"
    assert deck_path.read_bytes() == deck_bytes

    assert (deck_path.parent / "include" / "A.GRDECL").read_bytes() == include_a
    assert (deck_path.parent / "include" / "sub" / "B.GRDECL").read_bytes() == include_b
    assert (
        deck_path.parent / "include" / "sub" / "deep" / "C.GRDECL"
    ).read_bytes() == include_nested

    assert body["include_dir"] is not None
    assert Path(body["include_dir"]).is_dir()
    assert body["byte_count"] == len(deck_bytes) + len(include_a) + len(include_b) + len(include_nested)


def test_upload_strips_leading_include_prefix(client):
    """webkitRelativePath typically starts with 'include/'. The
    route strips it so callers don't end up with include/include/."""
    deck_bytes = b"DECK"
    inc = b"data"

    resp = client.post(
        "/api/upload_deck",
        files=[
            _data_part(deck_bytes),
            _include_part("include/A.GRDECL", inc),
        ],
    )

    assert resp.status_code == 200, resp.text
    deck_path = Path(resp.json()["deck_path"])
    # Stripped: at <deck_path.parent>/include/A.GRDECL
    assert (deck_path.parent / "include" / "A.GRDECL").read_bytes() == inc
    # NOT at include/include/A.GRDECL (would be a doubled prefix)
    assert not (deck_path.parent / "include" / "include").exists()


# ---- rejection cases -----------------------------------------------


def test_upload_missing_deck_part(client):
    """An upload with only include parts (no deck) is rejected."""
    resp = client.post(
        "/api/upload_deck",
        files=[_include_part("include/A.GRDECL", b"data")],
    )
    assert resp.status_code == 400
    assert "deck" in resp.json()["detail"].lower()


def test_upload_non_data_filename(client):
    """A deck part whose filename doesn't end in .DATA is rejected.
    OPM Flow only runs .DATA files; renaming would just fail at run
    time with a less helpful error."""
    resp = client.post(
        "/api/upload_deck",
        files=[_data_part(b"content", filename="DECK.TXT")],
    )
    assert resp.status_code == 400
    assert ".DATA" in resp.json()["detail"]


def test_upload_empty_deck(client):
    """An empty .DATA file is rejected (would fail at run time too,
    but rejecting early gives a clearer error)."""
    resp = client.post(
        "/api/upload_deck",
        files=[_data_part(b"", filename="EMPTY.DATA")],
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_upload_include_path_traversal(client):
    """An include path containing '..' is rejected. The route must
    never let a malicious (or buggy) client write outside the
    upload dir."""
    resp = client.post(
        "/api/upload_deck",
        files=[
            _data_part(b"deck"),
            _include_part("../etc/passwd", b"x"),
        ],
    )
    assert resp.status_code == 400
    assert ".." in resp.json()["detail"] or "unsafe" in resp.json()["detail"].lower()


def test_upload_include_absolute_path(client):
    """An include path starting with '/' is rejected (absolute)."""
    resp = client.post(
        "/api/upload_deck",
        files=[
            _data_part(b"deck"),
            _include_part("/etc/passwd", b"x"),
        ],
    )
    assert resp.status_code == 400
    assert "absolute" in resp.json()["detail"].lower()


def test_upload_include_duplicate_paths(client):
    """Two include parts with the same relative path are rejected.
    This is the only way to get duplicates in a single upload (the
    browser won't emit them) so it points at a buggy client."""
    resp = client.post(
        "/api/upload_deck",
        files=[
            _data_part(b"deck"),
            _include_part("include/A.GRDECL", b"first"),
            _include_part("include/A.GRDECL", b"second"),
        ],
    )
    assert resp.status_code == 400
    assert "duplicate" in resp.json()["detail"].lower()


def test_upload_non_multipart_content_type(client):
    """A non-multipart request (e.g. raw JSON) is rejected with 415
    rather than silently 400. Matches HTTP semantics."""
    resp = client.post(
        "/api/upload_deck",
        json={"deck_path": "/tmp/x.DATA"},
    )
    assert resp.status_code == 415


# ---- path contract -------------------------------------------------


def test_upload_returned_path_passes_validate(client):
    """The deck_path returned by the route must pass validate_deck_path.
    /api/run uses validate_deck_path on its input, so if the upload
    route returned a path the allowlist rejects, the run would 400.

    This is a regression guard: it pins the contract between the
    new upload route and the existing /api/run route.
    """
    resp = client.post(
        "/api/upload_deck",
        files=[_data_part(b"deck")],
    )
    assert resp.status_code == 200, resp.text
    path = resp.json()["deck_path"]

    # Should not raise.
    validate_deck_path(path)