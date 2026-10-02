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

# ---------- Regressions found by code review on 2026-10-03 --------------------

class TestScenarioGatingNoDeadlock:
    """Picking a scenario must make that scenario's questions reachable.

    Question applicability is a predicate over the spec, and /next used to
    evaluate the catalog against the extraction-only spec. Answering
    "gas cap" therefore never offered the GOC question, while the R04
    block demanded one - finish 422'd forever with no answer available.
    """

    def _walk(self, client, scenario, description="10x10x3 reservoir, one producer"):
        answers, offered = {}, []
        for _ in range(60):
            r = client.post("/api/interview/next", json={
                "description": description, "answers": answers, "use_llm": False,
            })
            assert r.status_code == 200, r.text
            q = r.json()["question"]
            if q is None:
                break
            offered.append(q["id"])
            answers[q["id"]] = scenario if q["id"] == "intent.scenario" else q["default"]
        return answers, offered

    def test_gas_cap_offers_the_goc_question(self, client):
        answers, offered = self._walk(client, "gas_cap")
        assert "equil.goc_depth" in offered, (
            f"gas cap never asked for a GOC; offered {offered}"
        )

    def test_gas_cap_finishes_with_a_passing_deck(self, client):
        answers, _ = self._walk(client, "gas_cap")
        r = client.post("/api/interview/finish", json={
            "description": "10x10x3 reservoir, one producer",
            "answers": answers, "use_llm": False,
        })
        assert r.status_code == 200, r.text
        assert r.json()["lint"]["passed"] is True

    @pytest.mark.parametrize("scenario", [
        "depletion", "5spot_waterflood", "gas_cap", "co2_eor", "wag",
        "multilayer", "buildup",
    ])
    def test_every_scenario_reaches_a_buildable_terminal_state(self, client, scenario):
        # The never-breaks invariant, stated over every scenario the user
        # can pick: answering every question with its default must finish.
        # 5spot needs a description that actually extracts an injector -
        # a waterflood with no injector is a genuine contradiction the
        # user has to resolve, not a dead end.
        desc = ("20x20x5 five spot waterflood with 4 injectors and 1 producer"
                if scenario == "5spot_waterflood"
                else "10x10x3 reservoir, one producer")
        answers, _ = self._walk(client, scenario, desc)
        r = client.post("/api/interview/finish", json={
            "description": desc,
            "answers": answers, "use_llm": False,
        })
        assert r.status_code == 200, f"{scenario}: {r.text}"
        assert r.json()["lint"]["passed"] is True

    def test_resolved_snapshot_reflects_collected_answers(self, client):
        # /next returned the raw extraction, so the UI's running display
        # contradicted what the user had already typed.
        r = client.post("/api/interview/next", json={
            "description": "10x10x3 depletion, one producer",
            "answers": {"rock.porosity": 0.11}, "use_llm": False,
        })
        assert r.status_code == 200, r.text
        assert r.json()["resolved"]["porosity"] == pytest.approx(0.11)

    def test_bad_csv_number_is_a_400_not_a_500(self, client):
        # kind=csv_number reached float() unguarded; a stray token surfaced
        # as an unexplained 500 instead of a message naming the token.
        r = client.post("/api/interview/finish", json={
            "description": "10x10x3 depletion, one producer",
            "answers": {"grid.dz": "50,abc,20"}, "use_llm": False,
        })
        assert r.status_code == 400, r.text
        assert "abc" in r.json()["detail"]


class TestIngestFormatSniffing:
    def test_one_value_per_line_grdecl_is_not_a_numeric_grid(self, client):
        # Real GRDECL exports write one value per line. Sniffing numbers
        # before the keyword made that a "numeric grid", which wrote
        # permeability into porosity - a 100.0 porosity that still linted
        # clean because the linter only warns on the range.
        text = "PERMX\n100.0\n100.0\n100.0\n"
        r = client.post("/api/ingest/parse", json={"text": text})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["detected"] == "grdecl"
        assert "permx" in body["patch"]
        assert "porosity" not in body["patch"]

    def test_bare_numeric_grid_still_detects(self, client):
        r = client.post("/api/ingest/parse", json={"text": "0.1 0.2 0.3\n0.4 0.5 0.6\n"})
        assert r.json()["detected"] == "numeric_grid"

    def test_header_comment_containing_a_result_keyword_still_parses(self, client):
        # "INIT" is a prefix of "initial", so "-- initial porosity
        # estimate" was refused as an unreadable EGRID result file.
        text = "-- initial porosity estimate for the reservoir\nPORO\n0.3 0.3 0.3 0.3\n"
        r = client.post("/api/ingest/parse", json={"text": text})
        assert r.json()["detected"] == "grdecl"

    def test_real_result_file_is_still_rejected(self, client):
        r = client.post("/api/ingest/parse", json={"text": "EGRID\nFILEVERSION 2 0\n"})
        assert r.json()["detected"] == "unknown"
