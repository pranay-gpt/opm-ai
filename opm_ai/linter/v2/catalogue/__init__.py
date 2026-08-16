"""Hand-curated keyword catalogue for the v2 linter.

This package contains the minimal catalogue (Phase 2 deliverable
T2.4-substitute) and will host the full opm-common-backed catalogue
in Phase 2.5.

The catalogue is a dict mapping keyword name → KeywordSpec. Each
spec describes the keyword's size_kind, valid sections, per-column
item schema, and any whole-deck invariants.

See keywords.py for the actual specs.
"""

from .keywords import (
    KEYWORD_INDEX,
    get_keyword,
    known_keywords,
)

__all__ = ["KEYWORD_INDEX", "get_keyword", "known_keywords"]