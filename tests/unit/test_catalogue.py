"""Tests for the keyword catalogue (the JSON artefact and its build script)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOGUE_PATH = REPO_ROOT / "opm_ai" / "linter" / "keywords.json"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# Common keywords the catalogue must contain (verified by hand against the
# 722-deck fixture set; these are the load-bearing keywords every deck uses).
MUST_HAVE_KEYWORDS = [
    "WELSPECS", "COMPDAT", "WCONPROD", "WCONINJE",
    "DIMENS", "DX", "DY", "DZ", "PORO", "PERMX", "PERMY", "PERMZ",
    "TOPS", "NTG", "COORD", "ZCORN",
    "EQUIL", "PRESSURE", "SGAS", "SWAT", "RS",
    "PVTO", "PVTW", "PVDO", "ROCK", "SWOF", "SGOF",
    "TSTEP", "DATES", "EQLDIMS", "TABDIMS", "WELLDIMS",
    "OIL", "GAS", "WATER", "DISGAS", "VAPOIL",
    "FIELD", "METRIC", "TITLE", "START",
]

# Tokens that look like keywords but are filtered (section headers and END).
MUST_NOT_HAVE_KEYWORDS = [
    "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
    "SOLUTION", "SUMMARY", "SCHEDULE", "ENDFIN", "END",
]


@pytest.mark.unit
def test_catalogue_file_exists():
    assert CATALOGUE_PATH.exists(), (
        f"catalogue missing at {CATALOGUE_PATH}. "
        f"Run: python scripts/build_keyword_catalogue.py"
    )


@pytest.mark.unit
def test_catalogue_schema():
    """Top-level keys and types are stable across regenerations."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["schema_version"] == 1
    assert isinstance(data["deck_count"], int)
    assert isinstance(data["keyword_count"], int)
    assert isinstance(data["keywords"], dict)
    assert data["keyword_count"] == len(data["keywords"])


@pytest.mark.unit
def test_catalogue_deck_count():
    """The catalogue has scanned the full fixture tree (~722 decks)."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["deck_count"] >= 600, (
        f"deck_count={data['deck_count']} below expected floor of 600; "
        f"fixture tree may have shrunk or the script skipped files."
    )


@pytest.mark.unit
def test_catalogue_keyword_count_floor():
    """Catalogue has at least 1000 distinct keywords (loose floor)."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["keyword_count"] >= 1000, (
        f"keyword_count={data['keyword_count']} below 1000; "
        f"the tree may have lost fixture diversity."
    )


@pytest.mark.unit
def test_catalogue_includes_well_known_keywords():
    """Required keywords are present with non-zero deck_count."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    keywords = data["keywords"]
    missing = [kw for kw in MUST_HAVE_KEYWORDS if kw not in keywords]
    assert not missing, f"required keywords missing from catalogue: {missing}"

    zero_count = [
        kw for kw in MUST_HAVE_KEYWORDS
        if kw in keywords and keywords[kw]["deck_count"] == 0
    ]
    assert not zero_count, f"required keywords have zero deck_count: {zero_count}"


@pytest.mark.unit
def test_catalogue_excludes_section_headers():
    """Section headers and END are filtered out of the keywords dict."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    keywords = data["keywords"]
    leaked = [kw for kw in MUST_NOT_HAVE_KEYWORDS if kw in keywords]
    assert not leaked, f"section headers must be filtered: {leaked}"


@pytest.mark.unit
def test_catalogue_per_keyword_record_shape():
    """Each keyword record has the documented fields."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    sample = data["keywords"]["WELSPECS"]
    for field in ("sections_observed", "section_count", "deck_count",
                  "record_count", "first_token_count", "arg_shape"):
        assert field in sample, f"WELSPECS record missing field: {field}"

    arg_shape = sample["arg_shape"]
    for field in ("min_tokens", "max_tokens", "example"):
        assert field in arg_shape, f"arg_shape missing field: {field}"


@pytest.mark.unit
def test_catalogue_arg_shape_welspecs():
    """WELSPECS first record has 13 tokens (well name + 12 args)."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    welspecs = data["keywords"]["WELSPECS"]
    assert welspecs["first_token_count"] == 13, (
        f"WELSPECS first_token_count={welspecs['first_token_count']}, expected 13"
    )


@pytest.mark.unit
def test_catalogue_flag_keyword_examples():
    """Flag keywords (NOECHO, ECHO) have first_token_count=0 and a clean example."""
    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    for kw in ("NOECHO", "ECHO"):
        info = data["keywords"][kw]
        assert info["first_token_count"] == 0, (
            f"{kw} first_token_count={info['first_token_count']}, expected 0"
        )
        assert info["arg_shape"]["max_tokens"] == 0


@pytest.mark.unit
def test_catalogue_dry_run_summary():
    """The --dry-run flag reports deck_count and keyword_count on stdout as JSON."""
    result = subprocess.run(
        [sys.executable, "scripts/build_keyword_catalogue.py", "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"catalogue script failed: {result.stderr}"
    )
    summary = json.loads(result.stdout)
    assert "deck_count" in summary
    assert "keyword_count" in summary
    assert summary["deck_count"] >= 600


@pytest.mark.slow
@pytest.mark.unit
def test_catalogue_json_is_in_sync():
    """The committed keywords.json matches the current fixture tree.

    If a developer adds a fixture but forgets to regenerate, this fails.
    """
    if not FIXTURES_DIR.exists():
        pytest.skip("fixtures dir not present")

    result = subprocess.run(
        [sys.executable, "scripts/build_keyword_catalogue.py", "--dry-run"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    fresh = json.loads(result.stdout)

    with CATALOGUE_PATH.open(encoding="utf-8") as fh:
        committed = json.load(fh)

    # Compare deck_count and keyword_count (the cheap proxy). A full diff
    # would be too strict for a regeneration cadence; the counts catch
    # 'added a new fixture' and 'lost a fixture' cases.
    assert committed["deck_count"] == fresh["deck_count"], (
        f"deck_count drift: committed={committed['deck_count']}, "
        f"fresh={fresh['deck_count']}. Regenerate: "
        f"python scripts/build_keyword_catalogue.py"
    )
    assert committed["keyword_count"] == fresh["keyword_count"], (
        f"keyword_count drift: committed={committed['keyword_count']}, "
        f"fresh={fresh['keyword_count']}. Regenerate: "
        f"python scripts/build_keyword_catalogue.py"
    )
