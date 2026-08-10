"""Integration tests for the v2 linter oracle.

These are the regression tests for Phase 0. They assert:
1. The MANIFEST.yaml exists and is well-formed.
2. The 5 v1-known-bad fixtures (SPE1CASE1_IMPORT, SPE5CASE1,
   SPE9_CP_SHORT, ACTIONX_UDQ, UDT-1D-01B) are recognized as
   known-GOOD by Flow (i.e. the v1 linter's false positives on these
   decks are real Flow-acceptable decks).
3. The oracle correctly distinguishes known-good and known-bad
   fixtures in the manifest.

The integration tests are skipped if `flow` is not installed.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
import yaml

from opm_ai.linter.v2.build_manifest import build_manifest
from opm_ai.linter.v2.oracle import (
    OracleConfig,
    find_flow,
    run_flow,
)

pytestmark = pytest.mark.integration

FLOW_MISSING = find_flow() is None

# The 5 fixtures the v1 linter rejects but Flow accepts. These are the
# smoke-test for v2: when v2 is complete, the linter must accept these too.
V1_KNOWN_BAD_IN_V2 = [
    "spe1/SPE1CASE1_IMPORT.DATA",
    "spe5/SPE5CASE1.DATA",
    "spe9/SPE9_CP_SHORT.DATA",
    "udq_actionx/UDQ_ACTIONX.DATA",
    "udt/UDT-1D-01B.DATA",
]

# Path to the v1 known-good fixtures (must still pass in v2)
V1_KNOWN_GOOD_IN_V2 = [
    "spe1/SPE1CASE1.DATA",
    "spe1/SPE1CASE2.DATA",
    "spe3/SPE3CASE1.DATA",
    "spe9/SPE9.DATA",
]


@pytest.mark.skipif(FLOW_MISSING, reason="flow binary not installed")
def test_v1_known_bad_fixtures_pass_flow(tmp_path):
    """The v1 linter rejected these 5 fixtures. Flow accepts them.

    This is the *core regression test* for v2. When v2's INCLUDE resolver
    and grammar-based parser are complete, the linter must also accept
    these decks — but at the oracle level, Flow already accepts them.
    """
    config = OracleConfig(
        timeout_s=60,
        output_dir=tmp_path / "out",
        cwd=Path("tests/fixtures"),
    )
    failures = []
    for rel in V1_KNOWN_BAD_IN_V2:
        path = Path("tests/fixtures") / rel
        if not path.exists():
            continue
        verdict = run_flow(path, config)
        if not verdict.passed:
            failures.append(
                f"{rel}: {verdict.failure_reason} "
                f"(stderr tail: {verdict.stderr[-200:]})"
            )
    assert not failures, (
        "Flow rejected v1-known-bad fixtures (these must be Flow-good):\n"
        + "\n".join(failures)
    )


@pytest.mark.skipif(FLOW_MISSING, reason="flow binary not installed")
def test_v1_known_good_fixtures_pass_flow(tmp_path):
    """The v1 known-good fixtures must still pass Flow in v2.

    This is a sanity check that the v2 oracle agrees with v1.
    """
    config = OracleConfig(
        timeout_s=60,
        output_dir=tmp_path / "out",
        cwd=Path("tests/fixtures"),
    )
    failures = []
    for rel in V1_KNOWN_GOOD_IN_V2:
        path = Path("tests/fixtures") / rel
        if not path.exists():
            continue
        verdict = run_flow(path, config)
        if not verdict.passed:
            failures.append(
                f"{rel}: {verdict.failure_reason} "
                f"(stderr tail: {verdict.stderr[-200:]})"
            )
    assert not failures, (
        "Flow rejected v1-known-good fixtures:\n" + "\n".join(failures)
    )


@pytest.mark.slow
@pytest.mark.skipif(FLOW_MISSING, reason="flow binary not installed")
def test_manifest_is_buildable(tmp_path):
    """The MANIFEST.yaml must be buildable from the corpus in <5 minutes.

    This is the regression gate for Phase 0. If this takes too long, the
    per-deck timeout or worker count needs adjustment.
    """
    manifest_path = tmp_path / "MANIFEST.yaml"
    t0 = time.monotonic()
    manifest = build_manifest(
        fixtures_root=Path("tests/fixtures"),
        output=manifest_path,
        timeout_s=30,
        workers=4,
    )
    elapsed = time.monotonic() - t0

    assert manifest_path.exists()
    assert elapsed < 300, f"manifest build took {elapsed:.1f}s (max 300s)"

    with open(manifest_path) as f:
        loaded = yaml.safe_load(f)

    assert loaded["schema_version"] == 1
    assert loaded["summary"]["total"] >= 200, (
        f"expected 200+ known-good fixtures, got {loaded['summary']['known_good']}"
    )
    assert loaded["summary"]["known_good"] >= 200, (
        f"expected 200+ known-good; got {loaded['summary']['known_good']} "
        f"and {loaded['summary']['known_bad']} bad"
    )
    # The 5 v1-known-bad fixtures must be in known_good
    for rel in V1_KNOWN_BAD_IN_V2:
        assert rel in loaded["known_good"], (
            f"v1-known-bad fixture {rel} should be in known_good manifest"
        )


def test_manifest_yaml_schema_is_valid(tmp_path):
    """If a MANIFEST.yaml exists, it must have a valid schema.

    This test runs even without flow; it just validates an existing
    manifest file structure.
    """
    manifest_path = Path("opm_ai/linter/v2/fixtures/MANIFEST.yaml")
    if not manifest_path.exists():
        pytest.skip("MANIFEST.yaml not built yet (run build_manifest.py)")

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    assert manifest["schema_version"] == 1
    assert "summary" in manifest
    assert "known_good" in manifest
    assert "known_bad" in manifest
    assert "entries" in manifest
    assert manifest["summary"]["total"] == len(manifest["entries"])
    assert manifest["summary"]["known_good"] == len(manifest["known_good"])
    assert manifest["summary"]["known_bad"] == len(manifest["known_bad"])
    # by_any_tag should have non-zero counts for the most common categories
    by_any = manifest["summary"].get("by_any_tag", {})
    for cat in ("include", "edit", "repeat", "action"):
        assert by_any.get(cat, 0) > 0, (
            f"expected by_any_tag['{cat}'] > 0, got {by_any.get(cat)}"
        )
