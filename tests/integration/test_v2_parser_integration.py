"""Integration tests for the v2 parser.

T2-equivalent from FUTURE_IMPLEMENTATION.md: "Parse all 250+ Phase-0
known-good fixtures without crash." We use the same gate as Phase 1:
read MANIFEST.yaml, take the known-good list, parse each fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from opm_ai.linter.v2.parser import parse
from opm_ai.linter.v2.tokenizer import tokenize_file

MANIFEST_PATH = Path("opm_ai/linter/v2/fixtures/MANIFEST.yaml")


@pytest.mark.integration
def test_parse_all_known_good_fixtures():
    """Parse every known-good fixture; expect no crash and >=1 keyword."""
    if not MANIFEST_PATH.exists():
        pytest.skip(f"MANIFEST not built; run build_manifest.py")

    with open(MANIFEST_PATH) as f:
        manifest = yaml.safe_load(f)

    known_good = manifest["known_good"]
    assert len(known_good) >= 200

    fixtures_root = Path(manifest["fixtures_root"]).resolve()

    crashes: list[tuple[str, str]] = []
    empty: list[str] = []

    for rel in known_good:
        path = fixtures_root / rel
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        try:
            tokens = tokenize_file(text)
            deck = parse(tokens)
        except Exception as e:
            crashes.append((rel, f"{type(e).__name__}: {e}"))
            continue
        if deck.keyword_count() == 0:
            empty.append(rel)

    assert not crashes, (
        "parser crashed on these known-good fixtures:\n"
        + "\n".join(f"  {r}: {msg}" for r, msg in crashes[:10])
    )
    assert not empty, (
        "these known-good fixtures produced empty decks:\n"
        + "\n".join(f"  {r}" for r in empty[:10])
    )


@pytest.mark.integration
def test_minimal_fixture_parses_to_expected_shape():
    """The minimal hand-written fixture parses to a known-good shape."""
    path = Path("opm_ai/linter/v2/fixtures/tokenizer/minimal.DATA")
    if not path.exists():
        pytest.skip("minimal.DATA fixture not present")
    text = path.read_text()
    tokens = tokenize_file(text)
    deck = parse(tokens)

    # Expect all 6 sections that appear in the minimal deck
    section_names = [s.name.value for s in deck.sections.values()]
    assert "RUNSPEC" in section_names
    assert "GRID" in section_names
    assert "PROPS" in section_names
    assert "SCHEDULE" in section_names

    # DX should have one record with REPEAT 75*100
    for s in deck.sections.values():
        if s.name.value == "GRID":
            dx = next((k for k in s.keywords if k.name == "DX"), None)
            assert dx is not None, "DX keyword not found in GRID"
            assert len(dx.records) >= 1
            assert dx.records[0].column_count_total() == 75


@pytest.mark.integration
def test_stress_fixture_parses_with_unknown_keywords():
    """The stress fixture has FU_MYVAR and ACTIONX; parser handles both."""
    path = Path("opm_ai/linter/v2/fixtures/tokenizer/stress.DATA")
    if not path.exists():
        pytest.skip("stress.DATA fixture not present")
    text = path.read_text()
    tokens = tokenize_file(text)
    deck = parse(tokens)

    # ACTIONX should be parsed with 2 items (label, frequency)
    actionx = None
    for s in deck.sections.values():
        if s.name.value == "SCHEDULE":
            actionx = next((k for k in s.keywords if k.name == "ACTIONX"), None)
            break
    assert actionx is not None
    assert actionx.spec is not None
    # ACTIONX is LIST-kind: each record is a separate action block.
    assert actionx.spec.size_kind.value == "list"
    assert len(actionx.records) >= 1
    assert [t.text for t in actionx.records[0].items[:2]] == ["ACT-01", "1000"]
    assert actionx.records[0].items[1].kind.name == "INT"


@pytest.mark.integration
def test_spe1_fixture_parses_to_full_deck():
    """SPE1 (the canonical reference) parses to a full deck."""
    path = Path("tests/fixtures/spe1/SPE1CASE1.DATA")
    if not path.exists():
        pytest.skip("SPE1 fixture not present")
    text = path.read_text()
    tokens = tokenize_file(text)
    deck = parse(tokens)

    # SPE1 has at least RUNSPEC, GRID, PROPS, SOLUTION, SCHEDULE
    section_names = {s.name.value for s in deck.sections.values()}
    assert {"RUNSPEC", "GRID", "PROPS", "SOLUTION", "SCHEDULE"} <= section_names

    # SPE1 has 1 producer well
    welspecs_count = 0
    for s in deck.sections.values():
        for kw in s.keywords:
            if kw.name == "WELSPECS":
                welspecs_count += sum(len(r.items) // 6 for r in kw.records)
    assert welspecs_count >= 1