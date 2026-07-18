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

## Strictness Calibration Invariant
Because ERROR flips `passed`, every ERROR rule must be calibrated against what
Flow actually accepts, or the linter blocks valid decks (the builder refuses to
return them). Ground truth: `flow --enable-dry-run=true --output-dir=DIR DECK`
exit 0. Regression guard: `tests/integration/test_dataset_validation.py`
asserts known-good fixtures (SPE1 variants, SPE3, SPE9, WCONPROD family) pass
lint. When adding or tightening a rule, run that test first.

False positives fixed during calibration (do not reintroduce):
- **Terminator detection**: `/` terminates a record ANYWHERE on the line;
  Eclipse ignores trailing text (`8300.0 1.270 / RS VS DEPTH` is terminated).
  Strip quoted strings and `--` comments before searching for `/`.
- **TITLE** consumes one free-text line; its text (e.g. `SPE 9`) must not be
  parsed as a keyword.
- **SUMMARY section** mnemonics (`ALL`, `RUNSUM`, `FGPR`, ...) are bare flags;
  L001 skips the whole section.
- **Phase/PROPS coupling (L005)**: OIL accepts any of PVTO/PVDO/PVCDO/PVCO;
  GAS accepts PVTG/PVDG; DISGAS requires PVTO; VAPOIL requires PVTG.
  Saturation functions follow ACTIVE phase pairs, in family I (SWOF/SGOF/SLGOF)
  or family II (SWFN/SGFN/SOF2/SOF3/SGWFN). A gas-water deck needs no oil table.
- **INCLUDE (L003b)**: v1 does not resolve includes; if GRID contains INCLUDE
  or corner-point keywords (COORD/ZCORN), required-keyword checks are skipped.

## Regex Pitfall (recurring bug, now fixed everywhere)
Keyword-content extraction helpers use
`(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|\Z)` as the end anchor. It must be `\Z`, NOT
`$`: under `re.MULTILINE`, `$` matches the first end-of-line, truncating
extraction to the first data row. Symptom was L007 claiming well 'PROD' (row 2
of WELSPECS) was undeclared. `_extract_well_names` is also record-aware: split
content on `/`, take the first quoted token per record (else `'G1'`/`'OPEN'`
count as well names).

## Rule Taxonomy (L001-L015)
- **L001** (general): Missing terminating `/` on keyword (skips SUMMARY; `/` mid-line counts)
- **L002** (runspec): Phase declared but missing PROPS companion (deprecated - superseded by L005)
- **L003** (grid): DIMENS product ≠ DX/DY/DZ count
- **L003b** (grid): Required GRID keyword missing (DX, DY, DZ, TOPS, PORO, PERMX); skipped for INCLUDE/corner-point grids
- **L004** (grid): Negative permeability
- **L005** (props): Active phase lacks PVT table or saturation function (family I and II accepted)
- **L006** (schedule): WELSPECS present but COMPDAT missing
- **L007** (schedule): Well in COMPDAT/WCONPROD/WCONINJE not in WELSPECS
- **L008** (schedule): WELSPECS group=AUTO but no GRUPTREE
- **L009** (solution): Missing SOLUTION (WARNING, ERROR if EQUIL/RPTRST present)
- **L010** (summary): Missing SUMMARY (WARNING)
- **L011** (grid): PORO outside (0, 1]
- **L012** (props): SATNUM region references beyond available SWOF tables (handles `N*V` multipliers)
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
- `linter.py`: Orchestrator `lint_deck(path) -> LintResult`; LLM summary gated on `LLMClient.available`
- `prompts/summarize.j2`: LLM summary template, rendered by `LLMClient.summarize_issues`

## Test Contracts
- `tests/unit/test_linter.py`: 3 positive tests (SPE1 passes, sample deck passes)
- `tests/unit/test_linter_negative.py`: 11 negative tests (rules fire correctly)
- `tests/integration/test_dataset_validation.py`: known-good fixtures must pass lint (false-positive guard)

## Future / Plan
- Resolve INCLUDE files (then re-enable L003b for included grids)
- Vendored rules from opm-flow-editor-support still pending (seed set is L001-L015)
- Deep parse via `opm.io.Parser` reserved behind `OPM_LINTER_DEEP` flag (unimplemented)
