# opm_ai/builder - Context

## Purpose
Natural language -> valid OPM Flow .DATA deck that lints clean and runs in Flow.
Spec: `docs/conversations/03-builder.md`.

## API
- `build_deck(desc, output_path=None, use_llm=False, fluid=None) -> tuple[str, LintResult]`
- `build_deck_from_spec(spec, output_path=None) -> tuple[str, LintResult>`
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

## Preprocess Integration (Fluid-Specific PVT)
The builder now supports optional fluid-specific PVT tables via
`opm_ai.preprocess`. When a `FluidDescriptor` is passed to `build_deck()`
or attached to `ModelSpec.fluid`, the PROPS section is generated from
correlations instead of using hard-coded SPE1 tables.

Integration flow:
1. If `spec.fluid` is set, `_compute_template_context()` calls
   `build_pvt_blocks(fluid)` to generate all 7 PROPS blocks.
2. Validates via `validate_pvt_blocks(blocks, "FIELD"|"METRIC")` - errors raise `ValueError`.
3. Computes `rsvd_rs` (Rs at EQUIL datum pressure 4800 psia) using Standing
   correlation, clamped to the max Rs in the generated PVTO table so RSVD
   stays within the table range.
4. Injects `pvt_blocks` and `rsvd_rs` into Jinja2 context.
5. Template `base.j2` uses `{% if pvt_blocks %}` to emit fluid tables,
   otherwise falls back to hard-coded SPE1 tables.
6. RSVD lines use `{{ rsvd_rs }}` (defaults to 1.270 when no fluid).

Guard: if `fluid.pressure_range` max < 4800 psia, raises `ValueError` because
the default EQUIL datum (4800 psia) must lie within the PVTO/PVDG pressure range.

Usage:
```python
from opm_ai.preprocess import FluidDescriptor
from opm_ai.builder import build_deck

fluid = FluidDescriptor(api_gravity=35, gas_specific_gravity=0.75, gor=800,
                        reservoir_temp_f=200, salinity_ppm=50000,
                        pressure_range_psi=(14.7, 5000), unit_system="FIELD")
deck, lint = build_deck("10x10x3 grid, simple depletion, one producer", fluid=fluid)
```

## Validation Ground Truth
- Deck validation: `flow --enable-dry-run=true --output-dir=DIR DECK`, exit 0.
  Bare `flow --check` does NOT work in Flow 2026.04 (--check requires a value).
- Full run: `flow --output-dir=DIR DECK`; Flow writes output next to the deck
  unless `--output-dir` is given (cwd is irrelevant).

## Test Contracts
- `tests/integration/test_builder.py`: extraction + deck structure
- `tests/integration/test_builder_roundtrip.py`: 4 roundtrip tests (dry-run x3, full run x1)
- `tests/integration/test_dataset_validation.py`: 9 scenario descriptions must lint clean and pass dry-run
- `tests/integration/test_preprocess.py`: fluid-specific PVT block generation + builder integration + Flow dry-run/full-run

## Future / Plan
- Phase 2: LLM extraction path (function calling) behind `use_llm=True`
- Scenario-specific templates (WAG cycles via WCONINJE schedule changes,
  gas-cap EQUIL variants, CO2 via GAS injector with CO2 stream) - currently
  all scenarios render through the single SPE1-style base.j2