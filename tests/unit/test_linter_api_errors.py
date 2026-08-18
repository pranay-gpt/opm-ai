"""LinterAPI error taxonomy tests."""
from pathlib import Path

import pytest

from opm_ai.linter.api import LinterAPI, LinterError


def test_missing_source_raises_file_not_found(tmp_path: Path):
    api = LinterAPI()
    with pytest.raises(FileNotFoundError):
        api.lint(tmp_path / "does_not_exist.DATA")


def test_non_data_extension_raises_linter_error(tmp_path: Path):
    p = tmp_path / "wrong.txt"
    p.write_text("not a deck", encoding="utf-8")
    api = LinterAPI()
    with pytest.raises(LinterError, match="unsupported source type"):
        api.lint(p)


def test_string_source_path_is_accepted(tmp_path: Path):
    p = tmp_path / "x.DATA"
    p.write_text("RUNSPEC\nEND\n", encoding="utf-8")
    api = LinterAPI()
    # No exception; just confirm we didn't crash.
    api.lint(str(p))
