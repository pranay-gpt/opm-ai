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
  10 10 5 /
GRID
DXV
  10*100.0 /
DYV
  10*100.0 /
DZV
  5*20.0 /
PORO
  500*0.2 /
PERMX
  500*100.0 /
SCHEDULE
WELSPECS
  'W1' 'G1' 1 1 5.0 'OIL' /
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
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "info_count": result.info_count,
        "lint_summary": result.lint_summary,
        "issues": issues,
    }


def test_lint_parity_on_clean_deck(clean_path: Path):
    legacy = lint_deck_combined(clean_path)
    new = default_api.lint(clean_path)
    assert _fingerprint(legacy) == _fingerprint(new)
