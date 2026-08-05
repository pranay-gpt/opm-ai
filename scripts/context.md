# scripts/ - Build-time catalogue generators and run helpers

## Purpose
Offline generators for the linter's keyword catalogue + dev convenience
shell scripts. Catalogue generators run once at build time (committed
artefact); the shell scripts are runtime helpers.

## Files

### build_keyword_catalogue.py (Stage 3.4, observational)
Walks `tests/fixtures/` for `.DATA` files, parses each via
`opm_ai.linter.deck.Deck`, emits `opm_ai/linter/keywords.json` with:
- `sections_observed`: dict[section_name, count]
- `deck_count`: how many decks use the keyword
- `first_token_count`: first record's token count (signature proxy)
- `arg_shape`: aggregated token counts across records

Usage: `python scripts/build_keyword_catalogue.py [--dry-run]`.
Re-run after adding fixtures. Calibration invariant: tokenisation
regex MUST match `opm_ai/linter/rules/keywords.py` (`r"^([A-Z][A-Z0-9_]*)\s*(?:--.*)?$"`)
or L016 will fire false positives.

### build_keyword_rm_catalogue.py (Stage 3.4, authoritative)
Walks `tests/eclipse/ecl_rm/` (2174 Eclipse Reference Manual HTML files,
CC-BY 4.0 MIT-compatible), extracts per-keyword data via ~240 lines of
stdlib regex:
- `sections_authoritative` from `<table class="flagtable">` (literal "x"
  marker in column 0; skip first 2 simulator-header rows)
- `parameter_count_authoritative` from first `<ol><li>` count
- `description` from first `<p>` after flagtable (truncated to 400 chars)
- `name` from `<h1 class="keyword">`

Filter rules (avoiding topical index noise): skip `_Examples.html`,
`_NOTES.html`, lowercase filenames, single-letter A-Z entries, names
with spaces / non-alphanumeric / trailing dash or underscore.

Emits `opm_ai/linter/keywords_rm.json` (1916 keywords). Used by both
`rules/keywords.py` (L016 catalogue) and `api/routes/keywords.py`
(`/api/keywords`).

### run.sh / smoke.sh / with-py.sh
Runtime helpers. `with-py.sh` activates the project's Python env
(`source .venv/bin/activate || exit 1`) before running the command —
used to make subprocess wrappers behave consistently.

## Test Contracts
- `tests/unit/test_catalogue.py`: 11 tests for the fixture generator
- `tests/unit/test_erm_catalogue.py`: 10 tests for the ERM generator
- `test_catalogue_json_is_in_sync` (slow tag): re-runs fixture
  generator and asserts no drift

## Future / Plan
- Argument-type inference from ERM table cells (numeric vs. character
  vs. keyword value) — currently we only know count and name, not type.
- L016 arg-count warning: compare record token count against
  `parameters_count_authoritative` (currently only the first record's
  count is checked; needs per-record range checks).
