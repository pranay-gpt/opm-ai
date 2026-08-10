"""Integration test: tokenizer handles all Phase-0 known-good fixtures.

T1.12 from FUTURE_IMPLEMENTATION.md: "Tokenize all 250+ Phase-0
known-good fixtures without crash."

This test reads MANIFEST.yaml, picks the known-good fixtures, and
runs `tokenize_file()` on each. Failure modes:
  - tokenizer raises on a particular deck
  - a known-good fixture has zero non-EOL tokens (parser can't work
    on an empty token stream)

This test is gated on MANIFEST.yaml being present; if not, it's
skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from opm_ai.linter.v2.tokenizer import tokenize_file

MANIFEST_PATH = Path("opm_ai/linter/v2/fixtures/MANIFEST.yaml")


@pytest.mark.integration
def test_tokenize_all_known_good_fixtures():
    """Tokenize every known-good fixture; expect no crash and >0 tokens."""
    if not MANIFEST_PATH.exists():
        pytest.skip(
            f"MANIFEST not built; run build_manifest.py to create "
            f"{MANIFEST_PATH}"
        )

    with open(MANIFEST_PATH) as f:
        manifest = yaml.safe_load(f)

    known_good = manifest["known_good"]
    assert len(known_good) >= 200, (
        f"need 200+ known-good fixtures; manifest has {len(known_good)}"
    )

    fixtures_root = Path(manifest["fixtures_root"])
    if not fixtures_root.is_absolute():
        fixtures_root = fixtures_root.resolve()

    crashes: list[tuple[str, str]] = []
    empty: list[str] = []

    for rel in known_good:
        path = fixtures_root / rel
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        try:
            tokens = tokenize_file(text)
        except Exception as e:
            crashes.append((rel, f"{type(e).__name__}: {e}"))
            continue
        non_eol = [t for t in tokens if t.kind.name != "EOL"]
        if not non_eol:
            empty.append(rel)

    assert not crashes, (
        "tokenizer crashed on these known-good fixtures:\n"
        + "\n".join(f"  {r}: {msg}" for r, msg in crashes[:10])
    )
    assert not empty, (
        "these known-good fixtures produced only EOL tokens (parser can't "
        "operate on empty streams):\n" + "\n".join(f"  {r}" for r in empty[:10])
    )


@pytest.mark.integration
def test_handwritten_minimal_fixture_tokenizes():
    """The hand-written minimal.DATA fixture produces a clean AST shape."""
    path = Path("opm_ai/linter/v2/fixtures/tokenizer/minimal.DATA")
    if not path.exists():
        pytest.skip("minimal.DATA fixture not present")
    text = path.read_text()
    tokens = tokenize_file(text)

    section_headers = [t for t in tokens if t.kind.name == "SECTION_HEADER"]
    # Minimal deck has 7 sections (RUNSPEC, GRID, PROPS, SOLUTION, SUMMARY,
    # SCHEDULE) — actually 6 if we don't count TITLE.
    assert {t.text for t in section_headers} >= {
        "RUNSPEC",
        "GRID",
        "PROPS",
        "SOLUTION",
        "SUMMARY",
        "SCHEDULE",
    }

    keywords = [t for t in tokens if t.kind.name == "KEYWORD"]
    assert "DIMENS" in {t.text for t in keywords}
    assert "WELSPECS" in {t.text for t in keywords}
    assert "WCONPROD" in {t.text for t in keywords}
    assert "END" in {t.text for t in keywords}

    # The deck has 75*100 (DX/DY), 75*20 (DZ), 75*0.20 (PORO),
    # 75*100 (PERMX), 10*30 (TSTEP). All are REPEAT_N_VALUE with
    # column_count 75 or 10.
    repeats = [t for t in tokens if t.kind.name == "REPEAT_N_VALUE"]
    counts = {r.column_count for r in repeats}
    assert 75 in counts
    assert 10 in counts


@pytest.mark.integration
def test_handwritten_stress_fixture_tokenizes():
    """The stress fixture exercises comments, FU_VAR, ACTIONX, and more."""
    path = Path("opm_ai/linter/v2/fixtures/tokenizer/stress.DATA")
    if not path.exists():
        pytest.skip("stress.DATA fixture not present")
    text = path.read_text()
    tokens = tokenize_file(text)

    fu_vars = [t for t in tokens if t.kind.name == "FU_VAR"]
    assert any(t.text == "FU_MYVAR" for t in fu_vars)

    # The ACTIONX block uses a quoted label (the common Eclipse form).
    # Verify the STRING token for the label is recognized.
    action_label_strings = [
        t for t in tokens
        if t.kind.name == "STRING" and t.text == "ACT-01"
    ]
    assert len(action_label_strings) == 1, (
        "ACTIONX label 'ACT-01' should be a STRING token"
    )

    # The "-- a comment between keywords" line should produce a COMMENT.
    comments = [t for t in tokens if t.kind.name == "COMMENT"]
    assert any("comment between keywords" in t.raw for t in comments)