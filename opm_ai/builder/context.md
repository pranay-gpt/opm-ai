# opm_ai/builder - Context

## Purpose
Natural language -> valid OPM Flow .DATA deck that lints clean and runs in Flow.
Spec: `docs/conversations/03-builder.md`.

## API
- `build_deck(desc, output_path=None, use_llm=False) -> tuple[str, LintResult]`
- `build_deck_from_spec(spec, output_path=None) -> tuple[str, LintResult]`
- `extract_parameters_offline(desc) -> ModelSpec` (regex/heuristics, no LLM)

`use_llm=True` is still a stub (Phase 2); it currently falls through to the
offline extractor.

## Pipeline
`desc -> extract_parameters_offline -> ModelSpec -> base.j2 render -> lint_deck -> (deck, LintResult)`

The builder auto-lints its own output. Because linter ERRORs flip `passed`,
builder correctness is coupled to linter calibration - see
`opm_ai/linter/context.md` "Strictness Calibration Invariant".

## Template Invariants (base.j2)
Learned the hard way; each of these broke `flow` when violated:
- The template must contain ONLY deck text. A leading Jinja comment `{# ... #}`
  is fine; a Python-style docstring line renders into the deck and Flow rejects
  it ("String not formatted as valid keyword") - STATUS.md defect #1.
- GRID arrays are layer-major: emit `nx*ny` copies of the layer value per
  layer for DZ/PERMX/PERMY/PERMZ. DX/DY/TOPS/PORO are uniform, so a flat
  `nx*ny*nz` repeat is correct for them.
- PVTO is a multi-record table: each Rs record ends with `/`, and the TABLE
  needs a final bare `/` after the last record.
- SUMMARY mnemonics that take well lists (WBHP/WGOR/WGIR) close with `/`;
  BPR needs one line per cell block, then a closing `/`.
- TSTEP is one record: all step values then a single `/`.
- Well names in WELSPECS/COMPDAT/WCONPROD/WCONINJE must cross-reference
  exactly (linter L007; Flow is also strict about undeclared wells).

## Extraction Heuristics (extract.py)
- Grid regex `(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)`. When nz is overridden,
  dz/permx/permy/permz are re-expanded to nz entries by cycling the SPE1
  pattern (dz 20/30/50, perm 500/50/200) - a 10x10x5 request must produce
  5 layer values, not 3.
- Scenario keywords: depletion / five spot / line drive / wag / gas cap /
  co2 / multilayer / buildup. Default: depletion.
- Wells: depletion = producer at (nx,ny) completed k1..nz; SPE1-like
  (injector+producer) = GAS injector (1,1,1) + producer (nx,ny,nz);
  5-spot = WATER injector center + 4 corner producers.

## Validation Ground Truth
- Deck validation: `flow --enable-dry-run=true --output-dir=DIR DECK`, exit 0.
  Bare `flow --check` does NOT work in Flow 2026.04 (Check requires a value).
- Full run: `flow --output-dir=DIR DECK`; Flow writes output next to the deck
  unless `--output-dir` is given (cwd is irrelevant).

## Test Contracts
- `tests/integration/test_builder.py`: extraction + deck structure
- `tests/integration/test_builder_roundtrip.py`: 4 roundtrip tests (dry-run x3, full run x1)
- `tests/integration/test_dataset_validation.py`: 9 scenario descriptions must lint clean and pass dry-run

## Future / Plan
- Phase 2: LLM extraction path (function calling) behind `use_llm=True`
- Scenario-specific templates (WAG cycles via WCONINJE schedule changes,
  gas-cap EQUIL variants, CO2 via GAS injector with CO2 stream) - currently
  all scenarios render through the single SPE1-style base.j2
- Preprocess integration: replace hard-coded SPE1 PROPS tables with
  build_pvt_blocks() output (04-preprocess.md)
