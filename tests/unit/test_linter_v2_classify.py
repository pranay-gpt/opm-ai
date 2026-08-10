"""Unit tests for the v2 fixture classifier (opm_ai.linter.v2.classify)."""

from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.linter.v2.classify import (
    CATEGORIES,
    Classification,
    classify_corpus,
    classify_deck,
)


def test_minimal_classification():
    """A hand-written deck with no INCLUDE/EDIT/etc. and no n*value
    repetition is 'minimal'."""
    text = """\
RUNSPEC
DIMENS
  2 2 1 /
OIL
WATER
GRID
DX
  100 100 100 100 100 100 100 100 /
DY
  100 100 100 100 100 100 100 100 /
DZ
  10 10 10 10 10 10 10 10 /
PORO
  0.2 0.2 0.2 0.2 0.2 0.2 0.2 0.2 /
PERMX
  100 100 100 100 100 100 100 100 /
SCHEDULE
WELSPECS
  'W1' 'G' 1 1 1.0 'LIQ' /
COMPDAT
  'W1' 1 1 1 2 2 1 'OPEN' /
TSTEP
  30 30 30 30 30 30 30 30 30 30 /
END
"""
    path = Path("/tmp/MINIMAL.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert cls.primary == "minimal"
        assert "include" not in cls.secondary
        assert "udq" not in cls.secondary
        assert "repeat" not in cls.secondary
    finally:
        path.unlink()


def test_repeat_changes_primary():
    """The same deck with n*value repetition is 'repeat', not 'minimal'."""
    text = """\
RUNSPEC
DIMENS
  2 2 1 /
OIL
WATER
GRID
DX
  8*100 /
"""
    path = Path("/tmp/REPEAT_DECK.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert cls.primary == "repeat"
    finally:
        path.unlink()


def test_include_classification():
    text = """\
RUNSPEC
INCLUDE 'GRID.INC' /
DIMENS 2 2 1 /
"""
    path = Path("/tmp/INCLUDE.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert cls.primary == "include"
        assert "include" in cls.signals
    finally:
        path.unlink()


def test_udq_classification():
    text = """\
SUMMARY
FU_MYVAR
UDQ
DEFINE FU_MYVAR WWPR 'W1' * 1.0 /
"""
    path = Path("/tmp/UDQ.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert "udq" in [cls.primary, *cls.secondary]
        assert "fu_var" in cls.signals or "udq_stmt" in cls.signals
    finally:
        path.unlink()


def test_actionx_classification():
    text = """\
SCHEDULE
ACTIONX
  'MY_ACTION' 100 /
WWPR 'W1' > 1000 /
ENDACTIO
"""
    path = Path("/tmp/ACTIONX.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert "action" in [cls.primary, *cls.secondary]
    finally:
        path.unlink()


def test_repeat_classification():
    text = """\
RUNSPEC
DIMENS 10 10 3 /
GRID
DX
  300*100 /
"""
    path = Path("/tmp/REPEAT.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert "repeat" in [cls.primary, *cls.secondary]
    finally:
        path.unlink()


def test_region_classification():
    text = """\
REGIONS
FIPNUM
  100*1 /
"""
    path = Path("/tmp/REGION.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert "region" in [cls.primary, *cls.secondary]
    finally:
        path.unlink()


def test_edit_classification():
    text = """\
EDIT
EQUALS
  PERMX 1 1 1 1 1 1 1000 /
"""
    path = Path("/tmp/EDIT.DATA")
    path.write_text(text)
    try:
        cls = classify_deck(path)
        assert "edit" in [cls.primary, *cls.secondary]
    finally:
        path.unlink()


def test_spe_path_classification(tmp_path):
    """A deck under a spe1/... directory is 'spe' by path."""
    spe_dir = tmp_path / "spe1"
    spe_dir.mkdir()
    text = "RUNSPEC\nDIMENS 2 2 1 /\n"
    deck = spe_dir / "TEST.DATA"
    deck.write_text(text)
    cls = classify_deck(deck)
    # The path contains '/spe1/' so the SPE regex matches
    assert "spe" in [cls.primary, *cls.secondary], (
        f"expected 'spe' tag for path {deck}, got primary={cls.primary} "
        f"secondary={cls.secondary}"
    )


def test_categories_list_is_complete():
    """The 8 categories are all in CATEGORIES."""
    expected = {
        "minimal",
        "spe",
        "include",
        "edit",
        "udq",
        "repeat",
        "region",
        "action",
    }
    assert set(CATEGORIES) == expected


def test_classify_corpus_returns_dict():
    """classify_corpus returns a dict mapping Path -> Classification."""
    paths = []
    for d in ("/tmp/A.DATA", "/tmp/B.DATA"):
        p = Path(d)
        p.write_text("RUNSPEC\nDIMENS 2 2 1 /\n")
        paths.append(p)
    try:
        result = classify_corpus(paths)
        assert isinstance(result, dict)
        assert all(isinstance(v, Classification) for v in result.values())
    finally:
        for p in paths:
            p.unlink()
