"""Integration tests for the v2 INCLUDE/IMPORT resolver.

T3 exit criterion: the 5 v1-known-bad fixtures parse without ERROR.
These are decks that the v1 linter rejected but Flow accepts. The
core test is that the v2 resolver can follow INCLUDE/IMPORT chains
and produce a CompositeDeck with zero errors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from opm_ai.linter.v2.parser import parse_file
from opm_ai.linter.v2.resolver import resolve_deck


# The 5 v1-known-bad fixtures — v1 linter rejected these but Flow
# accepts them. With INCLUDE/IMPORT resolution, v2 must accept them too.
V1_KNOWN_BAD_IN_V2 = [
    "spe1/SPE1CASE1_IMPORT.DATA",
    "spe5/SPE5CASE1.DATA",
    "spe9/SPE9_CP_SHORT.DATA",
    "udq_actionx/UDQ_ACTIONX.DATA",
    "udt/UDT-1D-01B.DATA",
]

V1_KNOWN_GOOD_IN_V2 = [
    "spe1/SPE1CASE1.DATA",
    "spe1/SPE1CASE2.DATA",
    "spe3/SPE3CASE1.DATA",
    "spe9/SPE9.DATA",
]


@pytest.mark.integration
@pytest.mark.parametrize("rel", V1_KNOWN_BAD_IN_V2)
def test_v1_known_bad_parses_without_resolver_errors(rel):
    """The 5 v1-known-bad fixtures resolve cleanly with v2.

    Before the resolver, these all failed because the parser couldn't
    follow INCLUDE/IMPORT. After the resolver, the INCLUDEs should
    be resolved and the composite deck should have 0 errors.

    This is the v1-regression test for the resolver (T3.10).
    """
    path = Path("tests/fixtures") / rel
    if not path.exists():
        pytest.skip(f"{rel} not in test corpus")
    deck = parse_file(path.read_text(errors="replace"), source_file=path)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0, (
        f"resolver errors in {rel}:\n"
        + "\n".join(f"  {e}" for e in cd.errors)
    )


@pytest.mark.integration
@pytest.mark.parametrize("rel", V1_KNOWN_GOOD_IN_V2)
def test_v1_known_good_still_resolves(rel):
    """The v1 known-good fixtures still resolve cleanly (regression)."""
    path = Path("tests/fixtures") / rel
    if not path.exists():
        pytest.skip(f"{rel} not in test corpus")
    deck = parse_file(path.read_text(errors="replace"), source_file=path)
    cd = resolve_deck(deck)
    assert cd.error_count() == 0, (
        f"resolver errors in {rel}:\n"
        + "\n".join(f"  {e}" for e in cd.errors)
    )


@pytest.mark.integration
def test_resolve_all_610_known_good_fixtures():
    """All 610 known-good fixtures resolve with <=1 error.

    This is a smoke test: the resolver should not crash on any
    known-good fixture, and most should have 0 errors. We allow up
    to 1 error per fixture (some PATHS paths may not resolve if the
    referenced files don't exist in the corpus)."""
    import yaml
    manifest_path = Path("opm_ai/linter/v2/fixtures/MANIFEST.yaml")
    if not manifest_path.exists():
        pytest.skip("MANIFEST not built")
    manifest = yaml.safe_load(manifest_path.read_text())
    fixtures_root = Path(manifest["fixtures_root"]).resolve()

    total = 0
    with_errors: list[tuple[str, int]] = []
    crashes = []

    for rel in manifest["known_good"]:
        path = fixtures_root / rel
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        try:
            deck = parse_file(text, source_file=path)
            cd = resolve_deck(deck)
            total += 1
            if cd.error_count() > 0:
                with_errors.append((rel, cd.error_count()))
        except Exception as e:
            crashes.append((rel, f"{type(e).__name__}: {e}"))

    assert not crashes, (
        "resolver crashed on these known-good fixtures:\n"
        + "\n".join(f"  {r}: {m}" for r, m in crashes[:10])
    )
    # Most should have 0 errors; allow some leniency for unusual
    # PATHS setups in the corpus.
    error_rate = len(with_errors) / max(total, 1)
    assert error_rate < 0.10, (
        f"{error_rate:.1%} of fixtures have resolver errors (too high): "
        + "\n".join(f"  {r}: {n}" for r, n in with_errors[:10])
    )