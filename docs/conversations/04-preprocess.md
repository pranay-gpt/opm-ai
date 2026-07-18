# Pre-Processing / PVT & Rock-Property Pipeline  (module: `opm_ai.preprocess`)

> Pure-Python correlation functions that emit OPM-format PROPS table blocks (PVTO, PVDG, PVTW, SWOF, SGOF, ROCK, DENSITY) as strings ready to paste into a deck PROPS section, plus an optional AI advisor that recommends a correlation from a fluid descriptor.

---

## 1. Role in the AIM

The AIM calls for "pre and post processing layers/workflow" so that students and researchers can describe a reservoir in plain English and get a runnable deck.  
Part 4 is the **pre-processing layer**: it turns a fluid description (API gravity, gas specific gravity, GOR, reservoir temperature, salinity, pressure range, unit system) into the PVT and relative-permeability tables that OPM Flow requires in the PROPS section.

Without this layer, the Builder (Part 3) must fall back to hard-coded SPE1 tables, which only teach one fluid type. With it, the chat can say "35 API oil, 0.75 gas gravity, 800 scf/stb GOR, 200 degF, 50 000 ppm salinity, FIELD units" and the Builder emits a deck that actually represents *that* fluid.

---

## 2. Position in build order

| Phase | Version | Part | Module | Depends on | Depended on by |
|-------|---------|------|--------|------------|----------------|
| 2 | v1.1 | **Part 4** | `opm_ai.preprocess` (`pvt_builder.py`) | Part 3 `opm_ai.builder` (ModelSpec, `build_deck`), Part 2 `opm_ai.linter` (validation rules) | Part 3 Builder (feeds PROPS), Part 6 API (`/api/build` -> `build_deck` -> `pvt_builder`) |

- Builder (Part 3) calls `pvt_builder.build_pvt_blocks(model_spec)` **before** rendering the Jinja2 template so the PROPS section is fluid-specific.
- Linter (Part 2) validates the emitted tables (monotonicity, endpoints, required columns). The linter rules are documented in **02-linter.md** section 4; this doc only defines the correlation outputs the linter will see.
- Phase 2 ordering: Postprocess (Part 5) and API/Frontend (Part 6) land **before** Preprocess in the plan, but Preprocess is a pure library with no external deps beyond `numpy`; it can be slotted in anytime after Builder exists.

---

## 3. Hard API contract (proposed - no test exists yet)

No test file asserts this module yet. The following signatures are the **proposed contract** that the Builder integration test (`tests/integration/test_builder.py`) will eventually assert.

```python
# opm_ai/preprocess/pvt_builder.py

from pathlib import Path
from dataclasses import dataclass
from typing import Literal, Optional

UnitSystem = Literal["FIELD", "METRIC"]
CorrelationName = Literal["Standing", "VasquezBeggs", "AlMarhoun", "Corey", "LET"]

@dataclass(frozen=True)
class FluidDescriptor:
    """User-facing fluid description (matches Builder's ModelSpec.fluid)."""
    api_gravity: float                    # degrees API, > 0
    gas_specific_gravity: float           # air = 1.0, > 0
    gor: float                            # solution GOR, scf/stb (FIELD) or sm3/sm3 (METRIC)
    reservoir_temp_f: float | None = None # degF if FIELD, degC if METRIC; None -> infer from unit_system
    reservoir_temp_c: float | None = None
    salinity_ppm: float = 0.0             # ppm NaCl equiv; 0 = fresh
    pressure_range_psi: tuple[float, float] | None = None  # (p_min, p_max) for table range
    unit_system: UnitSystem = "FIELD"

@dataclass(frozen=True)
class PVTBlocks:
    """Rendered PROPS blocks as strings ready for Jinja2 template."""
    pvt_oil: str          # PVTO table block
    pvdg: str             # PVDG table block
    pvt_water: str        # PVTW table block
    rock: str             # ROCK block
    density: str          # DENSITY block
    swof: str             # SWOF table block
    sgof: str             # SGOF table block

# --- Public API ---

def build_pvt_blocks(fluid: FluidDescriptor,
                     correlations: dict[str, CorrelationName] | None = None,
                     relperm_endpoints: dict[str, float] | None = None) -> PVTBlocks:
    """
    Main entry point. Selects correlations (or uses AI advisor if correlations=None),
    computes tables, returns rendered PROPS blocks.

    correlations keys: "pvt_oil" (Standing|VasquezBeggs|AlMarhoun),
                       "relperm_water_oil" (Corey|LET),
                       "relperm_gas_oil" (Corey|LET)
    relperm_endpoints: Swc, Sorw, Sorg, Krw@Sorw, Kro@Swc, Krg@Sorg, ...
    """

def recommend_correlation(fluid: FluidDescriptor,
                          region: str | None = None) -> tuple[CorrelationName, str]:
    """
    AI advisor (optional, offline-degradable).
    Returns (chosen_correlation, explanation_string).
    If LLM unavailable or offline, returns a deterministic rule-of-thumb
    (Standing for most black-oil, AlMarhoun for Middle East carbonate, etc.)
    and explanation="offline fallback".
    Never raises.
    """

# --- Correlation primitives (pure functions, unit-testable) ---

def standing_rs_bubble(api: float, gas_grav: float, temp_f: float, p_res: float) -> tuple[float, float]:
    """Returns (Rs_scf_stb, Pb_psia) at reservoir conditions."""
    ...

def vasquez_beggs_bo(api: float, gas_grav: float, temp_f: float, rs: float) -> float:
    """Oil FVF Bo (rb/stb) at solution GOR rs using Vasquez-Beggs (1980)."""
    ...

def almarhoun_bo(api: float, gas_grav: float, temp_f: float, rs: float, p: float) -> float:
    """Undersaturated oil FVF at pressure p > Pb using Al-Marhoun (1988)."""
    ...

def corey_swof(sw: float, swc: float, sorw: float,
               krw_max: float, kro_max: float,
               nw: float, no: float) -> tuple[float, float]:
    """Returns (krw, kro) for water-oil system at saturation sw."""
    ...

def let_swof(sw: float, swc: float, sorw: float,
             krw_max: float, kro_max: float,
             l_w: float, e_w: float, t_w: float,
             l_o: float, e_o: float, t_o: float) -> tuple[float, float]:
    """LET relative permeability (Lomeland et al. 2005)."""
    ...

# --- Validators (called by linter rules; see 02-linter.md) ---

def validate_pvt_blocks(blocks: PVTBlocks, unit_system: UnitSystem) -> list[str]:
    """
    Returns list of error strings (empty = valid).
    Checks: Bo monotonic with Rs, Rs >= 0, Bg > 0, Sw monotonic in SWOF/SGOF,
    endpoints within [0,1], SUM(Kr) constraints, etc.
    """
    ...
```

**Integration points the Builder will assert** (to be added to `tests/integration/test_builder.py`):

```python
# In test_builder.py, after build_deck renders a deck:
from opm_ai.preprocess import pvt_builder, FluidDescriptor

fluid = FluidDescriptor(api_gravity=35, gas_specific_gravity=0.75, gor=800,
                        reservoir_temp_f=200, salinity_ppm=50000,
                        pressure_range_psi=(14.7, 5000), unit_system="FIELD")
blocks = pvt_builder.build_pvt_blocks(fluid)
assert "PVTO" in blocks.pvt_oil and "PVDG" in blocks.pvdg
assert pvt_builder.validate_pvt_blocks(blocks, "FIELD") == []
```

---

## 4. Key design decisions

| # | Decision | Rationale | Alternatives considered | Consequences |
|---|----------|-----------|------------------------|--------------|
| D1 | **Pure Python + `numpy` only** (no `scipy` in Phase 1) | `scipy` not in `pyproject.toml`; `numpy` is. Correlations are closed-form; no optimisation/root-finding needed. | Add `scipy` dep; use `scipy.optimize.brentq` for bubble-point iteration. | If a correlation later needs iterative solution (e.g. `Rs` at `p > Pb`), we add `scipy` then (Phase 2+). Marked UNVERIFIED: verify `AlMarhoun` doesn't need iteration. |
| D2 | **Emit string blocks, not structured objects** | Builder's Jinja2 template expects PROPS section as text; string blocks paste directly. Avoids a second serialization step. | Return `dict` of `list[dict]` (columnar) and let template iterate. | Template stays simple; linter must parse text (already does section parsing). If template engine changes, block renderer changes in one place. |
| D3 | **Correlations as standalone pure functions** | Unit-testable against published worked examples (Ahmed Handbook). Swappable, no hidden state. | Class hierarchy with `Correlation.compute()`. | Simpler testing; AI advisor just picks a function name string. |
| D4 | **AI advisor optional, offline-degradable** | Chat must work without API key (CI, classrooms). Advisor returns `(correlation, explanation)`; if LLM missing, deterministic fallback + `"offline fallback"` tag. | Require LLM for correlation selection. | Zero hard dependency on `opm_ai.llm`; advisor is imported lazily inside `recommend_correlation`. |
| D5 | **User chooses when multiple correlations apply** | GUIDE 1: "ask the user to choose" when ambiguous. `build_pvt_blocks` accepts explicit `correlations` dict; if omitted, calls `recommend_correlation` and returns its pick (or raises `AmbiguityError` listing options` if >1 equally valid). | Auto-pick silently. | Explicit is better than implicit for teaching; student sees *why* a correlation was chosen. |
| D6 | **Unit system flows from `FluidDescriptor.unit_system`** | SPE1 uses FIELD; METRIC decks exist in fixtures. All correlations have FIELD coefficients; METRIC conversion happens at table emission (pressure in bar, volumes in m3, Rs in sm3/sm3). | Separate METRIC coefficient sets. | Single coefficient source (Ahmed uses FIELD); conversion at emission avoids dual-maintenance. UNVERIFIED: confirm Ahmed gives METRIC equivalents or conversion factors are standard. |
| D7 | **Relative permeability: Corey + LET only** | GUIDE 3 Part 4 lists these two. Corey = 2 exponents; LET = 3 params per phase, more flexible for history matching. | Stone I/II for three-phase (deferred). | Three-phase relperm is a Phase 3+ feature; Corey/LET cover water-oil and gas-oil two-phase tables (SWOF, SGOF) needed for black-oil. |
| D8 | **Salinity only affects PVTW (water FVF/viscosity)** | Black-oil PVTW depends on salinity; oil/gas correlations in GUIDE 3 don't include salinity terms. | Add salinity to oil correlations (some newer ones do). | Keep scope tight; extend when a cited correlation explicitly includes salinity. |

---

## 5. Toolchain grounding

| Item | Path / Version / Spec | Source | Status |
|------|----------------------|--------|--------|
| Python | 3.12 (system) | `BUILD_GUIDE.md` section 7 | Verified |
| numpy | `>=1.26` (in `pyproject.toml`) | `BUILD_GUIDE.md` section 2 | Verified |
| scipy | **NOT in `pyproject.toml`** | `BUILD_GUIDE.md` section 2 | **UNVERIFIED** - add only if a correlation needs it |
| Ahmed Reservoir Engineering Handbook | Correlations: Standing (1947), Vasquez-Beggs (1980), Al-Marhoun (1988), Corey (1954), LET (Lomeland 2005) | GUIDE 3 Part 4 | **UNVERIFIED** - coefficient tables must be transcribed from the Handbook at implementation time |
| OPM Flow PROPS format | `PVTO`, `PVDG`, `PVTW`, `SWOF`, `SGOF`, `ROCK`, `DENSITY` keyword syntax | `OPM.md`, SPE1 deck | Verified (see SPE1 fixture) |
| SPE1 reference deck | `tests/fixtures/spe1/SPE1CASE1.DATA` | `BUILD_GUIDE.md` section 6 | Verified - contains hand-authored PVTO/PVDG/SWOF/SGOF for validation |
| Linter rules for PVT | `02-linter.md` section 4 (monotonicity, endpoints, required columns) | This repo | Verified (linter doc exists) |
| Builder integration point | `opm_ai.builder.builder.build_deck` -> calls `pvt_builder.build_pvt_blocks` | `03-builder.md` (to be written) | **UNVERIFIED** - will be the integration test gate |

**What to check at implementation time**:
1. `scipy` import - if any correlation needs root-finding, add `scipy` to `pyproject.toml` (Phase 2).
2. Ahmed Handbook coefficient tables - copy exactly; mark each table with page/equation reference in code comments.
3. METRIC unit conversions - verify against OPM Flow manual (pressure bar, volume m3, Rs sm3/sm3).
4. SPE1 deck values - use as regression: `build_pvt_blocks(FluidDescriptor(...SPE1 fluid...))` should produce tables *close to* SPE1's hand tables (within rounding).

---

## 6. Implementation approach (ordered steps)

### Step 1 - Module skeleton and data classes
**Files**: `opm_ai/preprocess/__init__.py`, `opm_ai/preprocess/pvt_builder.py`, `opm_ai/preprocess/context.md`
- Define `FluidDescriptor`, `PVTBlocks`, `UnitSystem`, `CorrelationName` (as above).
- `context.md` per CLAUDE.md folder rule: one-paragraph purpose + key types.

### Step 2 - Correlation primitives (pure functions + unit tests)
**File**: `opm_ai/preprocess/correlations.py` (new) + `tests/unit/test_correlations.py` (new)
- Implement: `standing_rs_bubble`, `vasquez_beggs_bo`, `almarhoun_bo`, `corey_swof`, `let_swof`, plus `corey_sgof`, `let_sgof`.
- Each function has a docstring citing the equation source (Ahmed page/eqn).
- Unit tests: hard-code 2-3 worked examples from Ahmed per function; assert relative error < 1%.
- **No external deps beyond `numpy`**.

### Step 3 - Table builders and block renderers
**File**: `opm_ai/preprocess/tables.py` (new)
- `build_pvt_oil_table(fluid, correlation) -> list[dict]`: rows with keys `RS`, `P`, `BO`, `MUO`.
- `build_pvdg_table(fluid) -> list[dict]`: gas FVF + viscosity vs pressure (use ideal gas + Carr-Kobayashi viscosity correlation from Ahmed).
- `build_pvt_water_table(fluid) -> list[dict]`: water FVF/viscosity vs pressure (Ahmed Ch. 3, salinity correction).
- `build_rock_table(fluid) -> list[dict]`: single-row ROCK from fluid.reservoir_temp + compressibility correlation.
- `build_density_block(fluid) -> str`: surface densities from API + gas gravity.
- `build_swof_table(fluid, endpoints, correlation) -> list[dict]`: Sw, Krw, Kro, Pcow (Pcow=0 for now).
- `build_sgof_table(fluid, endpoints, correlation) -> list[dict]`: Sg, Krg, Kro, Pcog (Pcog=0).
- Renderers: `render_pvto(table) -> str`, `render_pvdg(table) -> str`, etc. producing exact OPM keyword blocks with `/` terminators.

### Step 4 - Main entry point + AI advisor
**File**: `opm_ai/preprocess/pvt_builder.py` (complete)
- `build_pvt_blocks(fluid, correlations=None, relperm_endpoints=None) -> PVTBlocks`:
  - If `correlations` provided, use them.
  - Else call `recommend_correlation(fluid)` for oil and relperm separately.
  - If advisor returns multiple equally-valid picks, raise `AmbiguousCorrelation(options)` so caller (Builder) can ask user.
  - Build all tables, render blocks, return `PVTBlocks`.
- `recommend_correlation(fluid, region=None) -> tuple[CorrelationName, str]`:
  - Try `from opm_ai.llm import LLMClient`; if import fails or `client.available is False`, use deterministic fallback:
    - `api > 30 and gas_grav < 0.8` -> `Standing`
    - `api <= 30` -> `VasquezBeggs`
    - `region in ("middle_east", "carbonate")` -> `AlMarhoun`
    - Relperm: `Corey` default, `LET` if user asks for "history match" or "flexible".
  - If LLM available, prompt: "Given fluid: {fluid}, recommend PVT correlation and explain in 2 sentences." Parse reply for correlation name.
  - Never raises; on any error return fallback + `"error: {e}"`.

### Step 5 - Validators (for linter integration)
**File**: `opm_ai/preprocess/validate.py` (new)
- `validate_pvt_blocks(blocks, unit_system) -> list[str]`: returns error strings.
  - PVTO: `RS` non-decreasing, `BO` >= 1.0, `MUO` > 0.
  - PVDG: `BG` > 0, `MUG` > 0, pressure increasing.
  - PVTW: `BW` > 0, `MUW` > 0.
  - SWOF: `Sw` strictly increasing, `Krw` in [0,1], `Kro` in [0,1], endpoints match `endpoints` dict.
  - SGOF: `Sg` strictly increasing, `Krg` in [0,1], `Kro` in [0,1].
  - DENSITY: three positive numbers.
- Unit tests in `tests/unit/test_validate.py` (new): feed good/bad tables, assert error list.

### Step 6 - Integration with Builder (cross-ref 03-builder.md)
- Builder's `build_deck` receives `ModelSpec.fluid: FluidDescriptor`.
- Before rendering template, call `pvt_builder.build_pvt_blocks(model_spec.fluid)`.
- Inject `PVTBlocks` into Jinja2 context; template uses `{{ pvt_blocks.pvt_oil }}` etc.
- After render, call `lint_deck` (Part 2) which internally calls `validate_pvt_blocks`.

### Step 7 - Fixtures and regression test
**File**: `tests/integration/test_preprocess.py` (new)
- Load SPE1 fluid descriptor from deck comments (API, gas_grav, GOR, temp, salinity).
- `build_pvt_blocks(spe1_fluid)` -> blocks.
- `validate_pvt_blocks(blocks, "FIELD") == []`.
- Spot-check: PVTO Rs values within 2% of SPE1 deck's PVTO table.

---

## 7. Risks and open questions

| Risk / Question | Impact | Mitigation / Who decides |
|-----------------|--------|--------------------------|
| Al-Marhoun correlation may need iterative solve for `Rs` at `p > Pb` | Would require `scipy` (not in deps) | Check Ahmed eqn 4.3.12 at impl time; if iterative, add `scipy` in Phase 2 and mark UNVERIFIED now. |
| METRIC unit coefficients not in Ahmed (only FIELD) | METRIC decks emit wrong tables | Verify OPM Flow manual for METRIC PVTO/PVDG column units; apply standard conversions (psi->bar, rb->m3, scf->sm3) at render time. |
| Salinity effect on oil FVF/viscosity | Some newer correlations include it; ours don't | Document as limitation; extend when a cited correlation adds salinity term. |
| Three-phase relperm (Stone I/II) | Needed for gas-oil-water simultaneous flow | Deferred to Phase 3; black-oil SWOF+SGOF suffices for SPE1/SPE9 waterflood and depletion. |
| Linter rule set for PVT not yet written | Invalid tables could reach Flow | 02-linter.md section 4 lists required rules; implement there in parallel. |
| AI advisor prompt parsing fragile | Wrong correlation picked silently | Fallback is deterministic; log advisor output; add integration test with mocked LLM. |
| SPE1 PVTO has undersaturated rows (last two rows at 9014.7 psia) | Our table builder must emit undersat rows for max Rs | `build_pvt_oil_table` must append undersat extension at max Rs for p > Pb (per OPM requirement noted in SPE1 comments). |

---

## 8. Verification and done-criteria

**No existing test gates this part.** The following will be the acceptance criteria when the module lands:

| Criterion | How verified |
|-----------|--------------|
| `opm_ai.preprocess` imports cleanly with only `numpy` (no `scipy`) | `python -c "import opm_ai.preprocess; print('ok')"` |
| All correlation primitives pass worked-example tests | `pytest tests/unit/test_correlations.py -v` |
| `build_pvt_blocks` emits all 7 PROPS blocks with correct keywords | `pytest tests/integration/test_preprocess.py::test_all_blocks_present -v` |
| SPE1 fluid descriptor -> tables pass `validate_pvt_blocks` | `pytest tests/integration/test_preprocess.py::test_spe1_regression -v` |
| AI advisor returns fallback when offline | `pytest tests/unit/test_advisor.py::test_offline_fallback -v` (mock `LLMClient.available=False`) |
| Builder integration: `build_deck` with fluid spec produces deck that lints clean | `pytest tests/integration/test_builder.py -v` (after Builder updated) |

**Manual smoke test** (run after Step 6):
```bash
cd /home/parallels/opm-ai
python -c "
from opm_ai.preprocess import pvt_builder, FluidDescriptor
fluid = FluidDescriptor(api_gravity=35, gas_specific_gravity=0.75, gor=800,
                        reservoir_temp_f=200, salinity_ppm=50000,
                        pressure_range_psi=(14.7, 5000), unit_system='FIELD')
blocks = pvt_builder.build_pvt_blocks(fluid)
print(blocks.pvt_oil[:200])
print('---')
print(blocks.swof[:200])
errors = pvt_builder.validate_pvt_blocks(blocks, 'FIELD')
print('Validation errors:', errors)
"
```
Expected: prints PVTO and SWOF blocks, `Validation errors: []`.

---

## 9. Future extensions (Phase 3+)

- **EOS / compositional PVT**: replace black-oil tables with PR/EOS flash calculations (needs `opm.io` EOS interface).
- **Three-phase relative permeability**: Stone I/II, Baker, or improved Stone (needs three-phase saturation functions).
- **PVT from lab data fitting**: regression helpers that fit correlation coefficients to user-supplied lab points (least-squares via `scipy.optimize`).
- **Uncertainty quantification**: Monte Carlo on correlation coefficients -> ensemble of PVT tables -> ensemble simulation (Part 1 runner already supports batch).
- **Co2brinepvt integration**: for CO2 storage decks, call `/usr/bin/co2brinepvt` (already installed per `OPM.md`) and parse its output into PVTW/PVDG blocks.
- **Teaching mode**: annotate each table row with "this row controls..." explanations for the Explainer (Part 7).

---

## Appendix A. Correlation equation references (to transcribe at implementation)

| Correlation | Source (Ahmed Handbook) | Equation | Coefficients table |
|-------------|------------------------|----------|-------------------|
| Standing Rs / Pb | Ch. 4, Eq. 4.2.1 / 4.2.2 | `Rs = gas_grav * ((p/18.2 + 1.4)*10^(0.0125*API - 0.00091*T))^1.2048` | `a=0.0125, b=-0.00091, c=1.2048` (verify page) |
| Vasquez-Beggs Bo | Ch. 4, Eq. 4.3.10 | `Bo = 1.0 + C1*Rs + C2*T + C3*API` (three sets of C by API range) | Table 4.3 (C1..C3 for API<30, 30-40, >40) - **UNVERIFIED** |
| Al-Marhoun Bo | Ch. 4, Eq. 4.3.12 | `Bo = a * Rs^b * gas_grav^c * API^d * T^e` (undersat) | Table 4.4 (a..e) - **UNVERIFIED** |
| Corey relperm | Ch. 5, Eq. 5.2.1 | `krw = krw_max * ((Sw-Swc)/(1-Swc-Sorw))^nw` | Exponents from endpoints |
| LET relperm | Lomeland et al. 2005 (SPE 94476) | `kr = k_max * (L*S^E) / (L*S^E + T*(1-S)^E)` | L, E, T per phase from history match |

---

## Appendix B. Sibling document index (for cross-referencing)

| Doc | Part | Module(s) | One-line summary |
|-----|------|-----------|------------------|
| 00-overview-and-architecture.md | 0 | `opm_ai`, `settings` | AIM, architecture, stack decisions, Stage 0 foundation |
| 01-runner.md | 1 | `opm_ai.runner` | Wrap `/usr/bin/flow` as subprocess; structured `SimulationResult`, never raises |
| 02-linter.md | 2 | `opm_ai.linter` | Offline `Deck` parser + rule engine; `lint_deck` returns `LintResult` |
| **04-preprocess.md** | **4** | **`opm_ai.preprocess`** | **PVT/relperm correlations to PROPS blocks; AI advisor; validators** |
| 03-builder.md | 3 | `opm_ai.builder`, `llm`, `cli` | NL -> ModelSpec -> Jinja2 deck; auto-lint; LLM client; click CLI |
| 05-postprocess.md | 5 | `opm_ai.postprocess` | `resfo` summary -> KPIs -> Plotly; optional `rips` ResInsight 3D |
| 06-chat-and-api.md | 6 | `opm_ai.api`, `frontend/` | FastAPI backend exposing modules as `/api/*`; React+Vite SPA |
| 07-explainer.md | 7 | `opm_ai.explainer` | Deferred RAG explainer (chromadb/llama-index); Phase 3 |
| 08-deployment.md | 8 | `docker/`, `README.md`, CI | `docker compose up`; Dockerfile with Flow/ResInsight; GitHub Actions |

---

*End of 04-preprocess.md*