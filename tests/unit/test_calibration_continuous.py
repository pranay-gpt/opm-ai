"""Phase 7 — Continuous calibration tests.

The continuous_scan script runs against 730 fixtures; we don't want
to re-run the whole thing in unit tests. Instead we test that the
script runs without crashing and produces sensible output for a
small in-memory fixture set.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from scripts.calibration import continuous_scan


@pytest.mark.unit
def test_continuous_scan_runs_on_synthetic_fixtures(tmp_path, monkeypatch):
    """The continuous_scan script can be invoked on a small fixture set.

    We monkeypatch FIXTURES to point at tmp_path, write 2 minimal
    decks, run the script, and confirm it produces output.
    """
    # Create two minimal decks: one valid, one missing WELLDIMS.
    good = tmp_path / "good.DATA"
    good.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
WELLDIMS
  1 1 1 1 0 0 0 0 0 0 0 0 /
""")
    bad = tmp_path / "bad.DATA"
    bad.write_text("""\\
RUNSPEC
DIMENS
  5 5 3 /
""")

    # Point the script at tmp_path.
    monkeypatch.setattr(continuous_scan, "FIXTURES", tmp_path)
    monkeypatch.setattr(continuous_scan, "THRESHOLD", 5)

    # Capture output by patching print.
    from io import StringIO
    captured = StringIO()
    monkeypatch.setattr("builtins.print", lambda *a, **kw: captured.write(" ".join(str(x) for x in a) + "\n"))

    rc = continuous_scan.main()
    out = captured.getvalue()
    assert rc in (0, 1), f"main() should return 0 or 1, got {rc}"
    assert "Continuous calibration" in out
    assert "WELLDIMS" in out
    assert "DIMENS" in out


@pytest.mark.unit
def test_continuous_scan_handles_zero_fixtures(tmp_path, monkeypatch):
    """An empty fixture dir produces a clean 'no fixtures' message."""
    monkeypatch.setattr(continuous_scan, "FIXTURES", tmp_path)
    from io import StringIO
    captured = StringIO()
    monkeypatch.setattr("builtins.print", lambda *a, **kw: captured.write(" ".join(str(x) for x in a) + "\n"))
    rc = continuous_scan.main()
    out = captured.getvalue()
    assert rc == 1
    assert "No fixtures found" in out