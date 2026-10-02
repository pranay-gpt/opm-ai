"""Stage 5 tests: the context-aware interview and file ingestion routes.

Covers the never-breaks invariant over HTTP, the skip/advance semantics,
the blocking finish contract, and the paste-vs-upload byte-equality.
"""

import io

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app


pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


DESC = "10x10x3 depletion, one producer"


def _walk(client, answers=None):
    """Drive the interview to completion, returning the final answers."""
    answers = dict(answers or {})
    while True:
        r = client.post(
            "/api/interview/next",
            json={"description": DESC, "answers": answers},
        )
        assert r.status_code == 200, r.text
        q = r.json()["question"]
        if q is None:
            break
        answers[q["id"]] = q["default"]
    return answers


class TestInterviewNext:
    def test_first_question_is_scenario(self, client):
        r = client.post(
            "/api/interview/next",
            json={"description": DESC, "answers": {}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["question"]["id"] == "intent.scenario"
        assert body["progress"]["answered"] == 0
        assert body["progress"]["total"] > 0

    def test_one_answer_advances(self, client):
        r1 = client.post(
            "/api/interview/next",
            json={"description": DESC, "answers": {}},
        )
        q1 = r1.json()["question"]
        r2 = client.post(
            "/api/interview/next",
            json={"description": DESC, "answers": {q1["id"]: q1["default"]}},
        )
        assert r2.status_code == 200
        assert r2.json()["question"]["id"] != q1["id"]

    def test_skip_all_reaches_complete(self, client):
        answers: dict = {}
        while True:
            r = client.post(
                "/api/interview/next",
                json={"description": DESC, "answers": answers},
            )
            assert r.status_code == 200
            q = r.json()["question"]
            if q is None:
                break
            answers[q["id"]] = None  # skip
        assert r.json()["progress"]["answered"] == r.json()["progress"]["total"]

    def test_unknown_answer_ids_are_ignored(self, client):
        r = client.post(
            "/api/interview/next",
            json={"description": DESC, "answers": {"bogus.question": 1}},
        )
        assert r.json()["question"]["id"] == "intent.scenario"


class TestInterviewFinish:
    def test_finish_returns_lint_passing_deck(self, client):
        r = client.post(
            "/api/interview/finish",
            json={"description": DESC, "answers": _walk(client)},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["lint"]["passed"]
        assert "DIMENS" in body["deck"]

    def test_finish_refuses_with_block(self, client):
        # A completion below the last layer is a block: the user answered
        # a question wrongly rather than skipping it, so finish refuses.
        r = client.post(
            "/api/interview/finish",
            json={
                "description": DESC,
                "answers": {"wells[0].k2": 99},
            },
        )
        assert r.status_code == 422
        assert "k2" in r.json()["detail"]

    def test_skip_all_finishes(self, client):
        # Never-breaks: skipping every question still builds a deck.
        r = client.post(
            "/api/interview/finish",
            json={"description": DESC, "answers": {}},
        )
        assert r.status_code == 200
        assert r.json()["lint"]["passed"]


class TestIngestParse:
    def test_grdecl_poro(self, client):
        r = client.post(
            "/api/ingest/parse",
            json={"text": "PORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["detected"] == "grdecl"
        assert body["patch"]["porosity"] == 0.25
        assert body["findings"] == []

    def test_per_cell_variation_refused(self, client):
        r = client.post(
            "/api/ingest/parse",
            json={
                "text": "PORO\n 0.20 0.21 0.22 0.19 0.23 0.18 /\nDIMENS\n 2 1 3 /\n"
            },
        )
        body = r.json()
        assert "porosity" not in body["patch"]
        assert any("PORO" in f for f in body["findings"])

    def test_arithmetic_keyword_refused(self, client):
        r = client.post(
            "/api/ingest/parse",
            json={
                "text": "EQUALREG\n PERMX 0.5 /\n/\nPORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n"
            },
        )
        body = r.json()
        assert "porosity" not in body["patch"]
        assert any("flatten" in f for f in body["findings"])

    def test_unknown_format(self, client):
        r = client.post("/api/ingest/parse", json={"text": "hello world"})
        assert r.json()["detected"] == "unknown"

    def test_empty_text_is_400(self, client):
        r = client.post("/api/ingest/parse", json={"text": ""})
        assert r.status_code == 400


class TestIngestUpload:
    def test_upload_matches_paste_byte_equal(self, client):
        paste = "PORO\n 300*0.25 /\nPERMX\n 500.0 50.0 200.0 /\nDIMENS\n 10 10 3 /\n"
        p = client.post("/api/ingest/parse", json={"text": paste})
        u = client.post(
            "/api/ingest/upload",
            files={"file": ("model.GRDECL", io.BytesIO(paste.encode()), "text/plain")},
        )
        assert p.status_code == 200 and u.status_code == 200
        assert p.json()["patch"] == u.json()["patch"]
        assert p.json()["detected"] == u.json()["detected"]

    def test_upload_empty_is_400(self, client):
        r = client.post(
            "/api/ingest/upload",
            files={"file": ("empty.GRDECL", io.BytesIO(b""), "text/plain")},
        )
        assert r.status_code == 400