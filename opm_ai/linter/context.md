# opm_ai/linter - Context

## Purpose
Offline-first OPM Flow deck linter with deterministic rule engine and optional LLM enhancement.

## Offline-First Invariant
The linter **must** run in CI without any external dependencies (no OPM install, no LLM API key). The rule engine is pure Python; LLM enhancement is additive and degrades gracefully to `None`.

## Severity Model
| Severity | Affects `passed` | Typical Use |
|----------|-----------------|-------------|
| ERROR | Yes (`passed=False` if any) | Deck will not run: missing required keyword, cross-ref failure, negative PERMX, missing `/` terminator |
| WARNING | No | Deck runs but likely wrong: missing SOLUTION (conditional), missing SUMMARY, porosity out of range |
| INFO | No | Style/best practice: keyword order, INCLUDE depth |

## Rule Taxonomy (L001-L015)
- **L001** (general): Missing terminating `/` on keyword
- **L002** (runspec): Phase declared but missing PROPS companion (deprecated - superseded by L005)
- **L003** (grid): DIMENS product ≠ DX/DY/DZ count
- **L003b** (grid): Required GRID keyword missing (DX, DY, DZ, TOPS, PORO, PERMX)
- **L004** (grid): Negative permeability
- **L005** (props): Phase in RUNSPEC but missing PVT/sat table in PROPS (GAS accepts PVDG)
- **L006** (schedule): WELSPECS present but COMPDAT missing
- **L007** (schedule): Well in COMPDAT/WCONPROD/WCONINJE not in WELSPECS
- **L008** (schedule): WELSPECS group=AUTO but no GRUPTREE
- **L009** (solution): Missing SOLUTION (WARNING, ERROR if EQUIL/RPTRST present)
- **L010** (summary): Missing SUMMARY (WARNING)
- **L011** (grid): PORO outside (0, 1]
- **L012** (props): SATNUM region references beyond available SWOF tables
- **L013** (general): Keyword out of canonical order
- **L014** (general): INCLUDE depth > 2 or absolute path
- **L015** (runspec): Missing DIMENS in RUNSPEC

## Cross-Reference
Full spec in `docs/conversations/02-linter.md` sections 3, 4.1, 4.3, 4.4, 6.

## Key Implementation Files
- `deck.py`: Hand-rolled section splitter, preserves line numbers
- `models.py`: `LintIssue`, `LintResult` dataclasses
- `rules/registry.py`: Rule registry, `run_all(deck)` entry point
- `rules/*.py`: Individual rule implementations (pure functions)
- `linter.py`: Orchestrator `lint_deck(path) -> LintResult`
- `prompts/summarize.j2`: LLM summary template (optional)

## Test Contracts
- `tests/unit/test_linter.py`: 3 positive tests (SPE1 passes, sample deck passes)
- `tests/unit/test_linter_negative.py`: 11 negative tests (all xpass = rules fire correctly)