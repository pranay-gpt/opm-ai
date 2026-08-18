"""Catalogue version counter.

A monotonically-increasing integer. Bumped whenever `keywords.py` is
regenerated, so any LinterCache entry keyed against the old version is
implicitly stale.

The linter worker owns the bump — they edit this file in the same
commit that touches `keywords.py`. Today, it is set to a frozen constant
matching the commit that last regenerated the catalogue.

Exposed as a module-level mutable so tests can simulate a catalogue
bump without touching the real catalogue.
"""
from __future__ import annotations

_VERSION: int = 1


def catalogue_version() -> int:
    """Return the current catalogue version. Pure read; safe to call from any thread."""
    return _VERSION


def bump_catalogue_version() -> int:
    """Test-only: increment and return the new version.

    Do NOT call from production code. The linter worker is the only
    legitimate caller in normal operation, and they edit the file
    directly rather than calling this.
    """
    global _VERSION
    _VERSION += 1
    return _VERSION
