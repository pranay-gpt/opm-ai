"""Unit tests for imported_results route validation helpers."""
import pytest

from opm_ai.api.routes.imported_results import (
    REQUIRED_FILES_HINT,
    _validate_imported_files,
)


def test_accepts_smspec_unsmry_pair(tmp_path):
    (tmp_path / "CASE.SMSPEC").write_bytes(b"x")
    (tmp_path / "CASE.UNSMRY").write_bytes(b"y")
    accepted, warnings = _validate_imported_files(tmp_path)
    assert accepted == ["CASE.SMSPEC", "CASE.UNSMRY"]
    assert warnings == []


def test_accepts_esmry_alone(tmp_path):
    (tmp_path / "CASE.ESMRY").write_bytes(b"x")
    accepted, warnings = _validate_imported_files(tmp_path)
    assert "CASE.ESMRY" in accepted


def test_rejects_no_summary(tmp_path):
    with pytest.raises(ValueError, match="SMSPEC"):
        _validate_imported_files(tmp_path)


def test_accepts_optional_extensions(tmp_path):
    (tmp_path / "CASE.SMSPEC").write_bytes(b"x")
    (tmp_path / "CASE.UNSMRY").write_bytes(b"y")
    (tmp_path / "CASE.EGRID").write_bytes(b"z")
    (tmp_path / "CASE.UNRST").write_bytes(b"z")
    (tmp_path / "CASE.INIT").write_bytes(b"z")
    accepted, warnings = _validate_imported_files(tmp_path)
    assert sorted(accepted) == ["CASE.EGRID", "CASE.INIT", "CASE.SMSPEC", "CASE.UNRST", "CASE.UNSMRY"]


def test_rejects_unsafe_filename(tmp_path):
    (tmp_path / "CASE.SMSPEC").write_bytes(b"x")
    (tmp_path / "CASE.UNSMRY").write_bytes(b"y")
    # Create a file with unsafe name (contains @ which is not in _SAFE_PATH_RE)
    (tmp_path / "bad@file").write_bytes(b"pwn")
    with pytest.raises(ValueError, match="unsafe"):
        _validate_imported_files(tmp_path)