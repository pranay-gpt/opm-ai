"""CI gate: every known_good fixture must lint cleanly (no errors).

Implements QC-1 from docs/personal/FUTURE_IMPLEMENTATION.md. The
threshold is `error_count() == 0` and `warning_count() <= 5` for
each fixture. The 5-warning allowance accommodates the audit-
confirmed true positives in
udq_actionx/ACTIONX_NE.DATA, udq_actionx/UDQ_REG-01.DATA,
udq_actionx/UDQ_REG-02.DATA, wtmult/WTMULT-01.DATA,
wtmult/WTMULT-02.DATA — fixtures where REGDIMS NTFIP is genuinely
under-allocated but OPM Flow's dynamic allocation still accepts.

Any PR that touches:
- opm_ai/linter/v2/catalogue/
- opm_ai/linter/v2/rules/
- opm_ai/linter/v2/parser.py
- opm_ai/linter/v2/resolver.py
- opm_ai/linter/v2/symbols.py
- opm_ai/linter/v2/validator.py
must keep this test green. If the threshold is exceeded, the
expected workflow is:
1. Investigate whether the new error/warning is a true positive
   or a regression (audit).
2. If regression → fix it.
3. If true positive → update the threshold and document the new
   acceptable warning in the test docstring.

Reference: docs/personal/LOGS.md 2026-08-13 entry, "Quality pass".
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from opm_ai.linter.v2.parser import parse_file
from opm_ai.linter.v2.resolver import resolve_deck
from opm_ai.linter.v2.validator import validate

MANIFEST_PATH = Path("opm_ai/linter/v2/fixtures/MANIFEST.yaml")

# Maximum errors allowed per fixture. v2 linter must produce 0
# errors on every known-good fixture in the manifest.
MAX_ERRORS_PER_FIXTURE = 0

# Maximum warnings allowed per fixture. Currently 5 true positives
# exist (see module docstring); allow up to 5 to gate regressions.
MAX_WARNINGS_PER_FIXTURE = 5


@pytest.mark.integration
def test_all_known_good_fixtures_lint_clean():
    """Every known-good fixture must lint with 0 errors and <=5 warnings."""
    if not MANIFEST_PATH.exists():
        pytest.skip(f"MANIFEST not built; run build_manifest.py")

    with open(MANIFEST_PATH) as f:
        manifest = yaml.safe_load(f)

    known_good = manifest["known_good"]
    assert len(known_good) >= 200, (
        f"Expected 200+ known-good fixtures, found {len(known_good)}"
    )

    fixtures_root = Path(manifest["fixtures_root"]).resolve()

    failures: list[tuple[str, int, int, list[str]]] = []
    parsed_count = 0

    for rel in known_good:
        path = fixtures_root / rel
        if not path.exists():
            continue
        parsed_count += 1
        text = path.read_text(errors="replace")
        try:
            deck = parse_file(text, source_file=path)
            resolve_deck(deck)
            result = validate(deck)
        except Exception as e:
            failures.append((rel, 1, 0, [f"v2 crashed: {type(e).__name__}: {e}"]))
            continue

        errs = result.error_count()
        warns = result.warning_count()

        if errs > MAX_ERRORS_PER_FIXTURE or warns > MAX_WARNINGS_PER_FIXTURE:
            messages = [
                f"[L{i.code}] {i.severity.value} L{i.source_line}: {i.message}"
                for i in result.issues
                if i.severity.value in {"ERROR", "WARNING"}
            ]
            failures.append((rel, errs, warns, messages))

    assert parsed_count >= 200, f"Only parsed {parsed_count} fixtures"
    assert failures == [], (
        f"{len(failures)} fixture(s) exceeded error/warning budget:\n"
        + "\n".join(
            f"  {rel}: errors={errs} warnings={warns}\n"
            + "\n".join(f"    {m}" for m in msgs[:3])
            for rel, errs, warns, msgs in failures[:10]
        )
    )


@pytest.mark.integration
def test_corpus_clean_summary():
    """Soft summary test: report clean-fixture percentage.

    Reports the current clean-fixture ratio so CI output surfaces
    regressions even when the hard threshold above is not yet
    crossed. The hard test above is the gate; this one is for
    visibility.
    """
    if not MANIFEST_PATH.exists():
        pytest.skip(f"MANIFEST not built; run build_manifest.py")

    with open(MANIFEST_PATH) as f:
        manifest = yaml.safe_load(f)

    fixtures_root = Path(manifest["fixtures_root"]).resolve()
    known_good = manifest["known_good"]

    clean = 0
    for rel in known_good:
        path = fixtures_root / rel
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        try:
            deck = parse_file(text, source_file=path)
            resolve_deck(deck)
            result = validate(deck)
        except Exception:
            continue
        if result.error_count() == 0 and result.warning_count() == 0:
            clean += 1

    total = sum(1 for rel in known_good if (fixtures_root / rel).exists())
    print(f"\n[corpus-clean] {clean}/{total} known-good fixtures are fully clean")
    # No assertion — this is informational. The hard test above is
    # the gate.