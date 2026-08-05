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
  GAS accepts PVTG/PVDG; DISGAS requires PVTO; VAPOIL requires PVTG; WATER
  accepts PVTW or PVTWSALT (brine variant).
  Saturation functions follow ACTIVE phase pairs, in family I (SWOF/SGOF/SLGOF)
  or family II (SWFN/SGFN/SOF2/SOF3/SGWFN). A gas-water deck needs no oil table.
  L005 skips when PROPS contains INCLUDE (tables may come from included file).
- **INCLUDE/IMPORT (L003b, L015)**: v1 does not resolve includes or binary
  EGRID imports; if GRID contains INCLUDE/IMPORT or corner-point keywords
  (COORD/ZCORN/RADIAL), required-keyword checks are skipped. If RUNSPEC or
  top-level deck contains INCLUDE, missing-section checks downgrade to WARNING.
- **History controls**: WCONHIST/WCONINJH accepted as alternatives to
  WCONPROD/WCONINJE (L014/L015 schedule rules).
- **Incremental well declarations**: _extract_well_names scans ALL keyword
  occurrences (wells are added at later TSTEP via second WELSPECS blocks).
- **Comment lines in WELSPECS**: L008 skips `--` lines (column headers naming
  'AutoShut' triggered the AUTO-group check); AUTO now matched as word `\bAUTO\b`.
- **Flag keywords** (L001): THERMAL, BLACKOIL, TEMP, RADIAL, BRINE, NEWTRAN,
  ENDBOX, FILLEPS, NOINSPEC, NORSSPEC, SKIPREST take no data and no `/`.

## Regex Pitfall (recurring bug, now fixed everywhere)
Keyword-content extraction helpers use
`(?=^\s*[A-Z][A-Z0-9_]*\b|^\s*--|\Z)` as the end anchor. It must be `\Z`, NOT
`$`: under `re.MULTILINE`, `$` matches the first end-of-line, truncating
extraction to the first data row. Symptom was L007 claiming well 'PROD' (row 2
of WELSPECS) was undeclared. `_extract_well_names` is also record-aware: split
content on `/`, take the first quoted token per record (else `'G1'`/`'OPEN'`
count as well names).

## Rule Taxonomy (L001-L018)
- **L001** (general): Missing terminating `/` on keyword (skips SUMMARY; `/` mid-line counts)
- **L002** (runspec): Phase declared but missing PROPS companion. **Registered
  2026-08-05** (was unwired in `rules/registry.py` before that — see commit
  1171a05). Rules out OIL→PVTO, SWOF; GAS/DISGAS→{PVTG or PVDG}, SGOF;
  WATER→PVTW; VAPOIL→PVDO, SWOF. Dry-gas alternative (PVDG) is accepted for
  GAS/DISGAS because the builder's default depletion deck emits PVDG, not
  PVTG. Distinct from L005, which is keyword-family-aware (PVT tables for
  the active phase). L002 is the strict phase-→-PROPS-keyword check.
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

**L014 / L015 rule_id collision (2026-08-04 audit, real bug, FIXED 2026-08-05):**
`rules/registry.py` registered TWO rules with `rule_id="L014"` and TWO with
`rule_id="L015"`:
- L014: `general.rule_L014_include_depth` AND `schedule.rule_L014_producer_no_wconprod`
- L015: `runspec.rule_L015_missing_dimens` AND `schedule.rule_L015_injector_no_wconinje`

Both ran; lint output attributed issues to whichever was registered last
when the rule_id collided. Fixed by renaming the schedule variants to
L017 (producer) and L018 (injector). L017/L018 were free; L016 was already
the unknown-keyword rule, so the audit's original L016/L017 suggestion was
the wrong pick. Commit: 1171a05.
- **L016** (general): Unknown keyword (WARNING). Reads the merged catalogue
  from `rules/keywords._get_catalogue()` — fixture (`keywords.json`) ∪ ERM
  (`keywords_rm.json`), fixture record wins on overlap. Emits a "did you
  mean X?" suggestion via difflib.get_close_matches. Severity is WARNING by
  design: the fixture catalogue covers only what 722 test decks use, so a
  valid ECLIPSE keyword no fixture uses (e.g. DUALPORO) is a hint, not an
  error. The ERM union closes most of that gap (1916 keywords). Calibration
  invariant: zero L016 false positives across 730 fixtures (regression guard
  in `tests/unit/test_erm_catalogue.py::test_calibration_zero_false_positives`).
- **L017** (schedule): Producer well without WCONPROD (ERROR). Renamed
  from L014 to clear the rule_id collision with the general INCLUDE
  rule. Accepts WCONHIST as a history-matching alternative.
- **L018** (schedule): Injector well without WCONINJE (ERROR). Renamed
  from L015 to clear the rule_id collision with the runspec DIMENS
  rule. Accepts WCONINJH as a history-matching alternative.

## Keyword Catalogue (L016 dependency, dual-source as of 2026-08-04)

L016 depends on two generated artefacts, merged in
`rules/keywords._get_catalogue()`:

1. `opm_ai/linter/keywords.json` — observational, derived from
   `tests/fixtures/`. Generator: `scripts/build_keyword_catalogue.py`.
   Walk 730 .DATA files, parse via `Deck`, emit per-keyword
   `sections_observed`, `deck_count`, `first_token_count`, `arg_shape`.
2. `opm_ai/linter/keywords_rm.json` — authoritative, derived from
   `tests/eclipse/ecl_rm/` (2174 Eclipse Reference Manual HTML files).
   Generator: `scripts/build_keyword_rm_catalogue.py` (~240 lines
   stdlib regex; well-formed DITA HTML). Per-keyword
   `sections_authoritative` (from `<table class="flagtable">`),
   `parameter_count_authoritative` (from `<ol><li>`),
   `description` (first `<p>` after flagtable), 1916 keywords.

Fixture record always wins on overlap (preserves observational
acceptance); ERM fills `sections`, `description`, `parameter_count`
where fixture lacks them. `source` field records `"fixture"`,
`"erm"`, or `"fixture+erm"`.

```json
{
  "schema_version": 1, "deck_count": 730, "keyword_count": 1079,
  "keywords": {
    "WELSPECS": {
      "sections_observed": {"SCHEDULE": 601}, "section_count": 1,
      "deck_count": 601, "record_count": 826,
      "first_token_count": 13, "arg_shape": {...}
    }
  }
}
```

Both catalogues are committed (fixture 340 KB, ERM ~18 KB compressed
JSON because the structure repeats) so the linter doesn't need to
rescan on every install. Generator tokenisation MUST match the
rule's tokenisation (both use `r"^([A-Z][A-Z0-9_]*)\s*(?:--.*)?$"`)
or the calibration will drift.
`test_catalogue_json_is_in_sync` (slow tag) re-runs the fixture
generator and asserts no drift — fail with a clear "regenerate"
message.

ERM parser filter rules (avoiding topical index noise): skip
`_Examples.html`, `_NOTES.html`, lowercase filenames (a.html, b.html),
single-letter A-Z entries from lowercase pages, names with spaces or
non-alphanumeric characters, names with trailing dash/underscore.

## Cross-Reference
Full spec in `docs/conversations/02-linter.md` sections 3, 4.1, 4.3, 4.4, 6.

## Key Implementation Files
- `deck.py`: Hand-rolled section splitter, preserves line numbers
- `keywords.json`: generated keyword catalogue (722 decks, 1079 keywords)
- `models.py`: `LintIssue`, `LintResult` dataclasses
- `rules/registry.py`: Rule registry, `run_all(deck)` entry point
- `rules/keywords.py`: L016 unknown-keyword rule, reads `keywords.json`
- `rules/*.py`: Individual rule implementations (pure functions)
- `linter.py`: Orchestrator `lint_deck(path) -> LintResult`; LLM summary gated on `LLMClient.available`
- `prompts/summarize.j2`: LLM summary template, rendered by `LLMClient.summarize_issues`

## Test Contracts
- `tests/unit/test_linter.py`: 3 positive tests (SPE1 passes, sample deck passes)
- `tests/unit/test_linter_negative.py`: 11 negative tests (rules fire correctly)
- `tests/unit/test_linter_unknown_keyword.py`: 9 tests for L016 (typos, no-match, severity, calibration)
- `tests/unit/test_catalogue.py`: 11 tests for the JSON artefact and build script
- `tests/integration/test_dataset_validation.py`: known-good fixtures must pass lint (false-positive guard)

## Future / Plan
- Resolve INCLUDE files (then re-enable L003b for included grids)
- Vendored rules from opm-flow-editor-support still pending (seed set is L001-L015)
- Deep parse via `opm.io.Parser` reserved behind `OPM_LINTER_DEEP` flag (unimplemented)
- **Stage 3.5 DONE (2026-08-04)**: per-keyword parameter extraction. Parser
  touches `<li>` for `{name, brief}`; flows through Pydantic
  `ParameterItem`, `/api/keywords`, and `opmCompletions.ts` `documentation`.
  Calibration invariant preserved. WELSPECS = 18 params, EQUIL = 11,
  DIMENS = `[]` (prose-only).
