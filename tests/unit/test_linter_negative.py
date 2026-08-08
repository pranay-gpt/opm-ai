"""Negative tests for linter: decks that SHOULD fail linting.

Originally documented defect #2 from STATUS.md (linter had no severity model and
downgraded real errors to warnings). Resolved in Stage 2: the linter now
implements the ERROR/WARNING/INFO model from 02-linter.md section 4.3, so these
tests assert real ERRORs and pass normally (xfail markers removed 2026-07-18).
"""
import pytest
import tempfile
from pathlib import Path

from opm_ai.linter import lint_deck


@pytest.mark.unit
def test_lint_deck_missing_required_runspec_dimension():
    """Deck missing DIMENS in RUNSPEC should fail linting (error, not warning)."""
    deck_content = """
RUNSPEC
-- Missing DIMENS keyword

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS

SCHEDULE
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERRORS, not just warnings - DIMENS is required in RUNSPEC
        assert not result.passed, "Deck missing DIMENS should not pass"
        assert len(result.errors) > 0, "Missing DIMENS should produce an error, not warning"
        # Check that the error is about DIMENS
        error_msgs = [str(e) for e in result.errors]
        assert any("DIMENS" in msg or "DIMENS" in msg for msg in error_msgs), \
            f"Expected DIMENS error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_missing_grid_keywords():
    """Deck missing required GRID keywords (DX, DY, DZ, TOPS, PORO, PERMX) should fail."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /

METRIC

GRID
-- Missing all required grid keywords

PROPS

SCHEDULE
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERRORS for missing required GRID keywords
        assert not result.passed, "Deck missing GRID keywords should not pass"
        assert len(result.errors) > 0, "Missing GRID keywords should produce errors"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_missing_props_for_phases():
    """Deck declaring OIL/GAS in RUNSPEC but missing PVTO/PVTG in PROPS should fail."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /
OIL
GAS
DISGAS

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS
-- Missing PVTO, PVTG, SWOF, SGOF for declared phases

SCHEDULE
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERRORS for missing companion keywords
        assert not result.passed, "Deck with phases but no PROPS should not pass"
        assert len(result.errors) > 0, "Missing companion keywords should produce errors"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_wellspecs_without_compdat():
    """Deck with WELSPECS but no COMPDAT should fail (error, not warning)."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /
OIL
WATER

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS
SWOF
  500*0.2 500*1*0 /
PVTO
  500*3000 500*1*1.0 /

SCHEDULE
WELSPECS
  'PROD1'  5  5  1  'OIL' /
/
-- COMPDAT is missing!
TSTEP
  100 /
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERROR for missing COMPDAT
        assert not result.passed, "Deck with WELSPECS but no COMPDAT should not pass"
        assert len(result.errors) > 0, "Missing COMPDAT should produce error"
        error_msgs = [str(e) for e in result.errors]
        assert any("COMPDAT" in msg for msg in error_msgs), \
            f"Expected COMPDAT error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_producers_without_wconprod():
    """Deck with producer wells but no WCONPROD should fail."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /
OIL
WATER

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS
SWOF
  500*0.2 500*1*0 /
PVTO
  500*3000 500*1*1.0 /

SCHEDULE
WELSPECS
  'PROD1'  5  5  1  'OIL' /
/
COMPDAT
  'PROD1'  1  1  1  5  'OPEN'  1*  1*  1*  1*  '1*' /
/
-- WCONPROD is missing for producer!
TSTEP
  100 /
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERROR for missing WCONPROD
        assert not result.passed, "Deck with producers but no WCONPROD should not pass"
        assert len(result.errors) > 0, "Missing WCONPROD should produce error"
        error_msgs = [str(e) for e in result.errors]
        assert any("WCONPROD" in msg for msg in error_msgs), \
            f"Expected WCONPROD error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_injectors_without_wconinje():
    """Deck with injector wells but no WCONINJE should fail."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /
OIL
WATER

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS
SWOF
  500*0.2 500*1*0 /
PVTO
  500*3000 500*1*1.0 /

SCHEDULE
WELSPECS
  'INJ1'  5  5  1  'WATER' /
/
COMPDAT
  'INJ1'  1  1  1  5  'OPEN'  1*  1*  1*  1*  '1*' /
/
-- WCONINJE is missing for injector!
TSTEP
  100 /
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERROR for missing WCONINJE
        assert not result.passed, "Deck with injectors but no WCONINJE should not pass"
        assert len(result.errors) > 0, "Missing WCONINJE should produce error"
        error_msgs = [str(e) for e in result.errors]
        assert any("WCONINJE" in msg for msg in error_msgs), \
            f"Expected WCONINJE error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_missing_schedule():
    """Deck completely missing SCHEDULE section should fail."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS
-- No SCHEDULE section at all
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERROR for missing SCHEDULE
        assert not result.passed, "Deck missing SCHEDULE should not pass"
        assert len(result.errors) > 0, "Missing SCHEDULE should produce error"
        error_msgs = [str(e) for e in result.errors]
        assert any("SCHEDULE" in msg for msg in error_msgs), \
            f"Expected SCHEDULE error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_missing_runspec():
    """Deck completely missing RUNSPEC section should fail."""
    deck_content = """
-- No RUNSPEC section

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS

SCHEDULE
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERROR for missing RUNSPEC
        assert not result.passed, "Deck missing RUNSPEC should not pass"
        assert len(result.errors) > 0, "Missing RUNSPEC should produce error"
        error_msgs = [str(e) for e in result.errors]
        assert any("RUNSPEC" in msg for msg in error_msgs), \
            f"Expected RUNSPEC error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_missing_grid():
    """Deck completely missing GRID section should fail."""
    deck_content = """
RUNSPEC
DIMENS
  10 10 5 /

METRIC

-- No GRID section

PROPS

SCHEDULE
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERROR for missing GRID
        assert not result.passed, "Deck missing GRID should not pass"
        assert len(result.errors) > 0, "Missing GRID should produce error"
        error_msgs = [str(e) for e in result.errors]
        assert any("GRID" in msg for msg in error_msgs), \
            f"Expected GRID error, got: {error_msgs}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_empty_file():
    """Completely empty deck file should fail."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write("")
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERRORS for missing required sections
        assert not result.passed, "Empty deck should not pass"
        assert len(result.errors) > 0, "Empty deck should produce errors"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_deck_only_comments():
    """Deck with only comments (no sections) should fail."""
    deck_content = """
-- This is a comment
-- Another comment
-- No sections at all
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck_content)
        deck_path = Path(f.name)

    try:
        result = lint_deck(deck_path)
        # Should have ERRORS for missing required sections
        assert not result.passed, "Comment-only deck should not pass"
        assert len(result.errors) > 0, "Comment-only deck should produce errors"
    finally:
        deck_path.unlink()


def _make_deck_with_pvt_tables(pvt_block: str) -> str:
    """Build a minimal deck that declares OIL/GAS/DISGAS + DIMENS + GRID
    and includes a customizable PVT block in PROPS. Used to test L002
    phase-mismatch against alternative PVT keywords."""
    return f"""
RUNSPEC
DIMENS
  10 10 5 /
OIL
GAS
DISGAS

METRIC

GRID
DX
  500*100 /
DY
  500*100 /
DZ
  500*10 /
TOPS
  500*3000 /
PORO
  500*0.2 /
PERMX
  500*100 /

PROPS
{pvt_block}
SGOF
0  0  1  0
1  0  0  0 /

SCHEDULE
"""


@pytest.mark.unit
def test_lint_l002_accepts_pvto_for_oil():
    """L002: OIL -> PVTO is satisfied (with SWOF). GAS/DISGAS also
    need PVTG/PVDG + SGOF."""
    deck = _make_deck_with_pvt_tables(
        "PVTO\n  500*3000 500*1*1.0 /\nSWOF\n  500*0.2 500*1*0 /\n"
        "PVDG\n  14.7 166.0 0.008 /\n"
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck)
        deck_path = Path(f.name)
    try:
        result = lint_deck(deck_path)
        l002_errors = [e for e in result.error_issues if e.rule_id == "L002"]
        assert l002_errors == [], f"PVTO+SWOF+PVDG should satisfy L002, got {l002_errors}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_l002_accepts_pvdg_as_dry_gas_alternative():
    """L002: GAS/DISGAS -> PVTG OR PVDG is satisfied (with SGOF).
    The builder's default depletion deck emits PVDG, not PVTG, so the
    rule must accept the dry-gas alternative."""
    deck = _make_deck_with_pvt_tables(
        "PVTO\n  500*3000 500*1*1.0 /\nSWOF\n  500*0.2 500*1*0 /\n"
        "PVDG\n  14.7 166.0 0.008 /\n"
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck)
        deck_path = Path(f.name)
    try:
        result = lint_deck(deck_path)
        l002_errors = [e for e in result.error_issues if e.rule_id == "L002"]
        assert l002_errors == [], f"PVDG should satisfy L002 for GAS, got {l002_errors}"
    finally:
        deck_path.unlink()


@pytest.mark.unit
def test_lint_l002_errors_when_neither_pvtg_nor_pvdg():
    """L002: GAS/DISGAS declared but neither PVTG nor PVTG/PVDG present."""
    deck = _make_deck_with_pvt_tables(
        "PVTO\n  500*3000 500*1*1.0 /\nSWOF\n  500*0.2 500*1*0 /\n"
    )
    with tempfile.NamedTemporaryFile(mode='w', suffix='.DATA', delete=False) as f:
        f.write(deck)
        deck_path = Path(f.name)
    try:
        result = lint_deck(deck_path)
        # `.errors` is the wire-format list of error messages; the
        # rich issue list (with .rule_id / .section) lives on
        # `.error_issues` after the dataclass-to-Pydantic unification
        # in F4.1.
        l002_errors = [e for e in result.error_issues if e.rule_id == "L002"]
        assert len(l002_errors) > 0, "missing PVTG+PVDG should fire L002"
        assert any("GAS" in e.message for e in l002_errors)
        assert any("DISGAS" in e.message for e in l002_errors)
    finally:
        deck_path.unlink()