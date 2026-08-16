# OPM Flow `.DATA` Linter v2

A modern, grammar-based linter for OPM Flow simulation deck files.

## What it does

The v2 linter takes an OPM Flow `.DATA` file and produces a structured
list of lint issues with severity, rule code, source location, and
optional mechanical fix proposals. The full agentic self-heal pipeline
additionally runs each proposed fix through the OPM Flow binary and
ranks proposals by empirical confidence.

## Module layout

| File | Purpose |
|------|---------|
| `tokens.py` | Token kinds + `Token` dataclass |
| `tokenizer.py` | Lexer (character stream → tokens) |
| `parser.py` | Parser (tokens → AST) |
| `ast.py` | AST node types (Keyword, Record, Section, Deck) |
| `resolver.py` | INCLUDE/IMPORT resolution + symbol table |
| `validator.py` | Validation rules producing LintIssue list |
| `rules/` | Per-rule checkers (one file per rule family) |
| `catalogue/` | Keyword catalog (sections, formats, defaults) |
| `oracle.py` | `flow --enable-dry-run=true` wrapper |
| `fix_proposals.py` | Mechanical fix proposals (L231/L232/L234) |
| `calibration.py` | Empirical success-rate calibration loop |
| `self_heal.py` | Top-level API: lint + propose + verify + rank |
| `fix_proposals.py` | Mechanical fix-proposal registry |

## CLI

Three scripts are provided under `scripts/`:

```bash
# 1. Calibrate — measures empirical success rate of each proposal.
python scripts/run_calibration.py --sample-size 50 --workers 4

# 2. Self-heal — propose + verify + rank fixes for one deck.
python scripts/self_heal.py path/to/deck.DATA
python scripts/self_heal.py path/to/deck.DATA --json
```

## Programmatic API

```python
from pathlib import Path
from opm_ai.linter.v2 import parse_file, resolve_deck, validate
from opm_ai.linter.v2.self_heal import (
    load_calibration_report,
    self_heal_deck,
)

# Lint
deck = parse_file(text, source_file=Path("x.DATA"))
resolve_deck(deck)
result = validate(deck)
for issue in result.issues:
    print(f"L{issue.code} {issue.severity.value}: {issue.message}")

# Self-heal
calibration = load_calibration_report(Path("calibration_report.json"))
self_heal = self_heal_deck(
    text=text,
    source_file=Path("x.DATA"),
    calibration_report=calibration,
    use_llm=False,  # gate to env var
)
for proposal in self_heal.proposals:
    print(proposal.rule_code, proposal.confidence, proposal.verified)
```

## Lint rules

| Code | Description |
|------|-------------|
| L160 | Value token outside any keyword context |
| L170 | Section boundary in wrong place |
| L171 | Unknown keyword |
| L202 | ActionX inner-keyword placement |
| L221 | WELSPECS / WELSPECL references unknown well |
| L222 | WELSPECS duplicate well name |
| L224 | FU_ keyword declared but never read |
| L231 | TABDIMS NSSFUN exceeded |
| L232 | WELLDIMS MAXWELLS exceeded |
| L234 | REGDIMS NTFIP exceeded |

## Severity levels

- **ERROR** — Flow will reject this deck.
- **WARNING** — Flow may accept but produces an incorrect result.
- **INFO** — Diagnostic only; the deck is functionally correct.

## Calibration methodology

The calibration loop samples known_good fixtures from the manifest,
runs each through the linter, attempts a fix proposal for each issue,
then runs Flow on the patched deck. The patched deck passing Flow
indicates a successful proposal.

Per-rule success rates feed the self-heal confidence model. The
calibration report (`opm_ai/linter/v2/calibration_report.json`) is
the source of truth for "how often does this rule's proposal
actually fix the issue?"

## LLM fallback

For issues without a mechanical proposal, the self-heal module can
ask an LLM. This is **gated** by:

1. The `--use-llm` flag (or programmatic `use_llm=True`).
2. The `OPM_AI_USE_LLM_FIXES=1` environment variable.
3. An LLM provider being available.

LLM proposals are flagged and downweighted by the confidence model.
They are a last resort, never a default.

## Self-heal design philosophy

Self-heal is **conservative**: it never auto-applies. The user (or a
downstream agent) reviews each proposal. The output is a ranked list
of `ScoredProposal` objects with confidence and verification flags.

The confidence model blends:

- **Historical calibration rate** per rule (Bayesian-smoothed) — weight 0.4
- **Oracle verdict** on the patched deck — weight 0.4
- **Severity weighting** — weight 0.1
- **LLM penalty** — weight 0.1

Verified proposals are ranked above unverified ones.

## Testing

```bash
.venv/bin/python -m pytest tests/unit/test_linter_v2_*.py -q
```

The test suite covers all v2 modules and runs in under a second.