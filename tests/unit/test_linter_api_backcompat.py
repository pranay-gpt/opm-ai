"""Pin output parity: LinterAPI.lint() == lint_deck_combined().

Both call sites must produce a LintResult whose:
- issues (sorted by (rule_id, line, message)) are identical
- passed flag is identical
- error_count / warning_count / info_count are identical
- lint_summary (if set) is identical
- deck_path is identical

If this test fails after a code change, you changed observable linter
behaviour. Revert it and rethink.
"""
from pathlib import Path

import pytest

from opm_ai.linter import lint_deck_combined
from opm_ai.linter.api import default_api


CLEAN_DECK = """\
RUNSPEC
DIMENS
  5 5 2 /
TABDIMS
  1 1 3 20 20 /
WELLDIMS
  1 10 1 10 /
GRID
DX
  50*100.0 /
DY
  50*100.0 /
DZ
  50*20.0 /
TOPS
  50*0.0 /
PORO
  50*0.2 /
PERMX
  50*100.0 /
PROPS
SWOF
  0.0 0.0 1.0 0.0
  1.0 1.0 0.0 0.0 /
SOLUTION
EQUIL
  100.0 100.0 0.0 0.0 0.0 0.0 /
SUMMARY
WOPR
/
SCHEDULE
WELSPECS
  'W1' 'G1' 1 1 5.0 'OIL' /
/
COMPDAT
  'W1' 1 1 1 1 'OPEN' /
/
WCONPROD
  'W1' 'OPEN' 'ORAT' 1000.0 1* 1* /
/
END
"""


@pytest.fixture
def clean_path(tmp_path: Path) -> Path:
    p = tmp_path / "clean.DATA"
    p.write_text(CLEAN_DECK, encoding="utf-8")
    return p


def _fingerprint(result):
    issues = sorted(
        ((i.rule_id or "", i.line or -1, i.severity, i.message or "")
         for i in result.issues),
        key=lambda t: (t[0], t[1], t[2], t[3]),
    )
    return {
        "deck_path": result.deck_path,
        "passed": result.passed,
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "info_count": len(result.info),
        "lint_summary": result.lint_summary,
        "issues": issues,
    }


def test_lint_parity_on_clean_deck(clean_path: Path):
    legacy = lint_deck_combined(clean_path)
    new = default_api.lint(clean_path)
    assert _fingerprint(legacy) == _fingerprint(new)
