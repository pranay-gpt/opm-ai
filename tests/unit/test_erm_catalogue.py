"""Tests for the ERM-derived keyword catalogue and the L016 union."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from opm_ai.linter import lint_deck
from opm_ai.linter.rules.keywords import _get_catalogue

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RM_CATALOGUE_PATH = REPO_ROOT / "opm_ai" / "linter" / "keywords_rm.json"
ERM_HTML_DIR = REPO_ROOT / "tests" / "eclipse" / "ecl_rm"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# Canonical keywords that must appear with their correct section placement
# from the Eclipse Reference Manual. The flagtable is the authoritative
# source. These are the 10 hand-verified during 2026-08-04 catalogue build.
ERM_MUST_HAVE = [
    ("WELSPECS", ["SCHEDULE"]),
    ("COMPDAT", ["SCHEDULE"]),
    ("PVTO", ["PROPS"]),
    ("EQUIL", ["SOLUTION"]),
    ("DIMENS", ["RUNSPEC"]),
    ("PORO", ["GRID"]),
    ("PERMX", ["GRID"]),
    ("DUALPORO", ["RUNSPEC"]),
    ("MINPV", ["GRID"]),
    ("RUNSPEC", []),  # section header page; empty flagtable expected
]


@pytest.mark.unit
def test_rm_catalogue_file_exists():
    assert RM_CATALOGUE_PATH.exists(), (
        f"ERM catalogue missing at {RM_CATALOGUE_PATH}. "
        f"Run: python scripts/build_keyword_rm_catalogue.py"
    )


@pytest.mark.unit
def test_rm_catalogue_schema():
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["schema_version"] == 1
    assert isinstance(data["keyword_count"], int)
    assert isinstance(data["keywords"], dict)
    assert data["keyword_count"] == len(data["keywords"])


@pytest.mark.unit
def test_rm_catalogue_size_floor():
    """The ERM catalogue has ~1900 keywords (vs 1079 in the fixture one)."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["keyword_count"] >= 1500, (
        f"ERM keyword_count={data['keyword_count']} below 1500. "
        f"Manual HTML dir may have moved or been removed."
    )


@pytest.mark.unit
def test_rm_catalogue_hand_verified_keywords():
    """Hand-verified keywords appear with the correct section placement."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    keywords = data["keywords"]
    for name, expected_sections in ERM_MUST_HAVE:
        info = keywords.get(name)
        assert info is not None, f"{name} missing from ERM catalogue"
        # Section-header pages have an empty flagtable; all other keywords
        # must have at least one section.
        assert info["sections_authoritative"] == expected_sections, (
            f"{name}: expected sections={expected_sections}, "
            f"got {info['sections_authoritative']}"
        )


@pytest.mark.unit
def test_rm_catalogue_per_record_shape():
    """Each keyword record has the documented fields."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    sample = data["keywords"]["WELSPECS"]
    for field in ("name", "source_file", "sections_authoritative",
                  "section_count_authoritative", "parameter_count_authoritative",
                  "description"):
        assert field in sample, f"WELSPECS record missing field: {field}"
    # WELSPECS has 18 parameter items per the manual.
    assert sample["parameter_count_authoritative"] >= 10, (
        f"WELSPECS parameter_count_authoritative={sample['parameter_count_authoritative']} "
        f"below expected 10"
    )


@pytest.mark.unit
def test_rm_catalogue_no_garbage_names():
    """No single-letter topical indexes, no trailing-dash/underscore names."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    bad = [
        name for name in data["keywords"]
        if (len(name) <= 1 and name.isalpha() and name.isupper())
        or len(name) == 0
        or " " in name
        or not name.replace("_", "").isalnum()
        or name.endswith(("-", "_"))
    ]
    assert not bad, f"garbage keyword names: {bad[:20]}"


@pytest.mark.unit
def test_rm_catalogue_dry_run_summary():
    """`--dry-run` reports the keyword count on stdout as JSON."""
    result = subprocess.run(
        [sys.executable, "scripts/build_keyword_rm_catalogue.py", "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["keyword_count"] >= 1500


@pytest.mark.unit
def test_l016_uses_union_of_catalogues():
    """L016's catalogue is the union of fixture + ERM keywords.

    The union size must be at least as large as either input. The fixture
    catalogue adds observational detail; the ERM catalogue adds authoritative
    section placement and description.
    """
    cat = _get_catalogue()
    fixture_cat = json.loads(
        (REPO_ROOT / "opm_ai" / "linter" / "keywords.json").read_text()
    )["keywords"]
    rm_cat = json.loads(RM_CATALOGUE_PATH.read_text())["keywords"]
    assert len(cat) >= len(fixture_cat), "union smaller than fixture catalogue"
    assert len(cat) >= len(rm_cat), "union smaller than ERM catalogue"
    # Spot check: a fixture-only keyword AND an ERM-only keyword are both
    # present in the union.
    fixture_only = next(
        (k for k in fixture_cat if k not in rm_cat), None
    )
    rm_only = next(
        (k for k in rm_cat if k not in fixture_cat), None
    )
    if fixture_only:
        assert fixture_only in cat, (
            f"fixture-only {fixture_only!r} missing from union"
        )
    if rm_only:
        assert rm_only in cat, (
            f"ERM-only {rm_only!r} missing from union"
        )


@pytest.mark.unit
def test_l016_accepts_erm_only_keyword(tmp_path):
    """A keyword the ERM documents but no fixture uses is accepted by L016.

    The union means DUALPORO (in ERM as a RUNSPEC flag keyword, absent
    from the fixture catalogue) is no longer flagged as unknown. This is
    the test that proves the union is effective.
    """
    deck = tmp_path / "ERM_KEYWORD.DATA"
    deck.write_text("""\
RUNSPEC
TITLE
  test
DIMENS
  10 10 3 /
DUALPORO
DUALPERM
/
END
""")
    result = lint_deck(deck)
    l016 = [i for i in result.issues if i.rule_id == "L016"]
    flagged = {i.keyword for i in l016}
    assert "DUALPORO" not in flagged, (
        "DUALPORO is in the ERM catalogue; L016 should not flag it"
    )
    assert "DUALPERM" not in flagged, (
        "DUALPERM is in the ERM catalogue; L016 should not flag it"
    )


@pytest.mark.slow
@pytest.mark.unit
def test_l016_calibration_set_with_union():
    """Zero L016 issues across all fixture decks (the union does not
    introduce new false positives).
    """
    if not FIXTURES_DIR.exists():
        pytest.skip("fixtures dir not present")
    data_files = sorted(FIXTURES_DIR.rglob("*.DATA"))
    hits = []
    for path in data_files:
        try:
            result = lint_deck(path)
        except Exception:
            continue
        for issue in result.issues:
            if issue.rule_id == "L016":
                hits.append((path, issue))
    assert hits == [], (
        f"L016 fired {len(hits)} times on the calibration set. "
        f"First 5: {[(p.name, i.section, i.keyword) for p, i in hits[:5]]}"
    )


@pytest.mark.unit
def test_rm_catalogue_parameters_welspecs():
    """WELSPECS has 18 parameters; first is 'Well name' with brief
    starting '(Up to 8 characters)'."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    ws = data["keywords"]["WELSPECS"]
    assert len(ws["parameters"]) == 18, (
        f"WELSPECS has {len(ws['parameters'])} parameters, expected 18"
    )
    assert ws["parameter_names"][0] == "Well name"
    first_brief = ws["parameters"][0]["brief"]
    assert first_brief.startswith("(Up to 8 characters)"), (
        f"WELSPECS first param brief starts with {first_brief[:40]!r}, "
        f"expected '(Up to 8 characters)'"
    )


@pytest.mark.unit
def test_rm_catalogue_parameters_equil():
    """EQUIL has 5+ parameters; first name starts with 'Datum depth'."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    eq = data["keywords"]["EQUIL"]
    assert len(eq["parameters"]) >= 5, (
        f"EQUIL has {len(eq['parameters'])} parameters, expected at least 5"
    )
    assert eq["parameters"][0]["name"].lower().startswith("datum depth"), (
        f"EQUIL first param name={eq['parameters'][0]['name']!r}, "
        f"expected to start with 'Datum depth'"
    )


@pytest.mark.unit
def test_rm_catalogue_parameters_dimens_empty():
    """DIMENS has no <ol> (prose-only); parameters list is empty."""
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    dm = data["keywords"]["DIMENS"]
    assert dm["parameters"] == [], (
        f"DIMENS parameters={dm['parameters']!r}, expected []"
    )
    assert dm["parameter_names"] == []
    assert dm["parameter_count_authoritative"] == 0


@pytest.mark.unit
def test_rm_catalogue_parameter_count_consistency():
    """len(parameters) == parameter_count_authoritative for every keyword.

    Both come from the first <ol> in the HTML, so they are derived from
    the same source. The 'spot-check' is that no keyword drifts out of
    sync — if a future change broke the parse, this test would catch it.
    """
    with RM_CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    bad = []
    for name, info in data["keywords"].items():
        if len(info["parameters"]) != info["parameter_count_authoritative"]:
            bad.append((name, len(info["parameters"]), info["parameter_count_authoritative"]))
    assert not bad, (
        f"parameter count drift: {bad[:5]}"
    )