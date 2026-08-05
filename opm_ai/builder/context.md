# opm_ai/builder - Context

## Purpose
Natural language -> valid OPM Flow .DATA deck that lints clean and runs in Flow.
Spec: `docs/conversations/03-builder.md`.

## API
- `build_deck(desc, output_path=None, use_llm=False, fluid=None) -> tuple[str, LintResult]`
- `build_deck_from_spec(spec, output_path=None) -> tuple[str, LintResult>`
- `extract_parameters_offline(desc) -> ModelSpec` (regex/heuristics, no LLM)
- `extract_parameters_llm(desc, client=None) -> ModelSpec | None` (Stage B)

`use_llm=True` (Stage B): when `settings.active_llm_client` is not "offline",
build_deck calls `extract_parameters_llm`, which renders
`opm_ai/llm/prompts/extract_model_spec.j2` (embeds
`ModelSpec.model_json_schema()` plus few-shot examples), calls
`LLMClient.extract_json` (provider JSON mode via
`response_format={"type": "json_object"}`, one repair retry, never raises),
and validates with `ModelSpec.model_validate`. Any failure returns None and
build_deck falls back to the offline regex extractor, so CI/offline behavior
is unchanged. The extraction path taken is logged via loguru.

`ModelSpec.schedule: list[ScheduleEvent]` (Stage D): each event is a schedule
phase - `actions` (raw keyword blocks, e.g. a full WCONINJE record) rendered
verbatim, then a time advance: `date` emits a DATES block, else `tstep_days`
(float or list of floats) emits a TSTEP block. Events append after the
initial TSTEP in base.j2. An empty schedule renders byte-identical decks to
the pre-Stage-D template (md5-verified; existing tests depend on this).

Stage D also added ModelSpec initialization overrides, all optional and
FIELD-canonical (converted at render time for METRIC):
- `equil_datum_depth`, `equil_datum_pressure`, `equil_woc_depth`,
  `equil_goc_depth` -> EQUIL items 1/2/3/5. NOTE the template variable names
  are positional legacy: `equil_woc` is item 3 (WOC depth), `equil_goc` is
  item 4 (Pcow at WOC), `equil_owc_depth` is item 5 (GOC depth). The
  builder maps the honest ModelSpec names onto them.
- `pvdg_rows`: replaces the default methane-like PVDG rows (list of
  "psia  rb/Mscf  cP" strings). Used by CO2_EOR for a denser, more viscous
  injection gas while staying in the black-oil subset.

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
- Stage D scenario defaults (each renders a distinct, Flow-verified deck):
  - WAG: injector (1,1) water for 90 days (initial WCONINJE + timesteps),
    then 7 ScheduleEvents alternating GAS(3000 Mscf/d)/WATER at calendar
    quarters via DATES; 4 full cycles, 731 days total.
  - GAS_CAP: GOC placed at the base of layer 1 (top_depth + dz[0]) so layer
    1 initializes as gas cap; EQUIL datum at the GOC at bubble point
    (4014.7 psia, matching SPE1 PVTO Rs 1.27); producer completed k 2..nz.
  - CO2_EOR: gas injector (1,1,1) + `pvdg_rows` swapped to a CO2-like table
    (denser + more viscous than methane at every pressure). No
    compositional keywords; distinctness comes from PVDG + injection stream.
  - BUILDUP: uniform 50 md perm, single bottom-layer producer at 4000 stb/d
    for 180 days, then one ScheduleEvent: WCONPROD STOP ORAT 0 + short
    TSTEPs (0.25...8 d). WELOPEN 'SHUT'/'STOP' both zero the reported WBHP
    in Flow 2026.04; WCONPROD STOP ORAT 0 keeps WBHP reported (jumps to
    sandface pressure, then rises) - that is why buildup uses WCONPROD.
  - MULTILAYER: PERMX/PERMY 500/50/200 md cycled over nz, PERMZ = 0.1x
    (kv/kh 0.1), producer completed across all layers.
- DATES works after START in these decks (verified against Flow 2026.04);
  the OPM.md "Problem with keyword DATES" note applies to SKIPREST restart
  decks only.

## Preprocess Integration (Fluid-Specific PVT)
The builder now supports optional fluid-specific PVT tables via
`opm_ai.preprocess`. When a `FluidDescriptor` is passed to `build_deck()`
or attached to `ModelSpec.fluid`, the PROPS section is generated from
correlations instead of using hard-coded SPE1 tables.

Integration flow:
1. If `spec.fluid` is set, `_compute_template_context()` calls
   `build_pvt_blocks(fluid)` to generate all 7 PROPS blocks.
   `build_pvt_blocks` honors `fluid.correlation` (default "Standing";
   Standing/VasquezBeggs/AlMarhoun) via `_select_oil_correlation`.
2. Validates via `validate_pvt_blocks(blocks, "FIELD"|"METRIC")` - errors raise `ValueError`.
3. Computes `rsvd_rs` (Rs at EQUIL datum pressure 4800 psia) using Standing
   correlation, clamped to the max Rs in the generated PVTO table so RSVD
   stays within the table range. The RSVD clamp call also uses
   `fluid.correlation` (line 110 area) so the user's correlation choice
   is reflected in the Rs clamp value.
4. NOTE: the `standing_rs_bubble` call near the rsvd block uses Standing
   unconditionally - that is by design. Standing has a closed-form
   Pb(Rs) inversion; VasquezBeggs and AlMarhoun do not, and a numerical
   root-find is out of scope. So Standing stays on for the rsvd
   inversion even when the user picks a different oil correlation.
5. Injects `pvt_blocks` and `rsvd_rs` into Jinja2 context.
6. Template `base.j2` uses `{% if pvt_blocks %}` to emit fluid tables,
   otherwise falls back to hard-coded SPE1 tables.
7. RSVD lines use `{{ rsvd_rs }}` (defaults to 1.270 when no fluid).

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

## Unit System Support
The builder now supports both FIELD and METRIC unit systems end-to-end.
When a FluidDescriptor with `unit_system="METRIC"` is provided:
- The RUNSPEC section emits `METRIC` instead of `FIELD`
- Grid dimensions (DX, DY, DZ, TOPS) are converted from ft to m (factor 0.3048)
- EQUIL depths and pressures are converted (ft->m, psia->bar, factor 0.0689476)
- RSVD Rs values are converted from scf/stb to sm3/sm3 (factor 0.17811)
- Well reference depths and BHP limits are converted to metric units
- PVT tables are generated in METRIC units by the preprocess module

The reservoir spec (ModelSpec/ReservoirSpec) still stores values in FIELD units
canonically; conversions happen in `_compute_template_context()` when the fluid
requests METRIC. This keeps FIELD behavior byte-identical to before.

Guard: `fluid.pressure_range` max must still be >= 4800 psia (EQUIL datum).
For METRIC fluids, the pressure_range_psi should be provided in bar (e.g.,
1.01325 to 344.74 for 14.7-5000 psia), and the code converts to psia for the
4800 psia check.

Usage:
```python
from opm_ai.preprocess import FluidDescriptor
from opm_ai.builder import build_deck

fluid = FluidDescriptor(api_gravity=35, gas_specific_gravity=0.75, gor=800,
                        reservoir_temp_c=93.33, salinity_ppm=50000,
                        pressure_range_psi=(1.01325, 344.74), unit_system="METRIC")
deck, lint = build_deck("10x10x3 grid, simple depletion, one producer", fluid=fluid)
```

## Test Contracts
- `tests/integration/test_builder.py`: extraction + deck structure
- `tests/integration/test_builder_roundtrip.py`: 4 roundtrip tests (dry-run x3, full run x1)
- `tests/integration/test_dataset_validation.py`: 14 scenario descriptions must lint clean and pass dry-run
- `tests/unit/test_scenario_templates.py`: Stage D deck-text assertions (WAG alternation, gas-cap EQUIL, CO2 PVDG, buildup shut-in, multilayer contrast, distinctness, schedule rendering)
- `tests/integration/test_scenario_runs.py`: Stage D Flow runs + physics sanity (buildup WBHP rise, gas-cap FGOR, WAG both-fluid injection)
- `tests/integration/test_preprocess.py`: fluid-specific PVT block generation + builder integration + Flow dry-run/full-run

## Future / Plan
- Stage D DONE (2026-07-21): schedule events consumed by base.j2; WAG /
  GAS_CAP / CO2_EOR / BUILDUP / MULTILAYER render distinct decks, all
  Flow-verified (dry-run + real run) with physics-sanity tests
  (tests/unit/test_scenario_templates.py, tests/integration/
  test_scenario_runs.py, dataset sweep extended).
- Possible follow-ups: LLM extraction emitting schedule/EQUIL/PVDG fields
  directly; WAG cycle count/length parsed from the description.