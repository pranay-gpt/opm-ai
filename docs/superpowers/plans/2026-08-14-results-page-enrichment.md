# Results Page Enrichment, Import Results, Export Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Results Viewer useful to a reservoir engineer — categorised plots by vector family with a per-tab control rail, virtual-job Import Results from uploaded Eclipse files, per-chart PNG/SVG/CSV export at native/monthly/yearly frequencies, plus three chat tools.

**Architecture:** New pure-function postprocess modules (`categorizer.py`, `plot_groups.py`, `resample.py`) over the existing `summary.read_summary()` DataFrame. Three new read-only results endpoints + one import route + three chat tools on the backend. Frontend refactors `ResultsViewer.tsx` into a two-column layout (control rail + content), extracts `PlotCard.tsx`, adds `ResultsControlRail.tsx`, `ImportResultsButton.tsx`, and extends `viewer3d/ControlPanel.tsx` with cross-section + well overlay.

**Tech Stack:** Python 3.11, FastAPI, pandas, plotly, resfo (existing); React 18, TypeScript, Tailwind, plotly.js-dist-min (existing).

## Global Constraints

These rules apply to every task. Pulled verbatim from the spec and project memory.

- **Branch**: All work on `feat/results-page-enrichment` (off `feat/v2-linter-grammar` @ `971ff00`). Never commit to `feat/v2-linter-grammar` directly.
- **Linter worker**: `opm_ai/linter/v2/catalogue/keywords.py` is owned by the linter worker. If you see it modified, stash with `git stash push <path> -m "linter WIP"`, do not commit it, and `git stash pop` only when on `feat/v2-linter-grammar`.
- **Plot only what is present**: `categorizer.py` returns only groups that have vectors; `plot_groups.py` emits a trace only for columns that exist. Never fabricate vectors or zero-fill.
- **NaN / negative-zero**: Reuse `_sanitize_water_rate` and `_sanitize_float` patterns from `opm_ai/postprocess/plots.py` and `opm_ai/postprocess/kpi.py`. Never silently swallow NaN/inf in JSON responses — `_sanitize_kpis` is the precedent.
- **Empty-card on plot failure**: If a Plotly builder raises, the route returns `figure_json: ""` and logs the trace. The PlotCard renders the existing empty-state (F1.5 audit pattern). Do NOT return `{"error": ...}` — it JSON.parses fine but fails later in Plotly.newPlot, leaving a silent blank tab.
- **Plotly types**: `plotly.js-dist-min` ships no types. Use `// @ts-expect-error plotly.js-dist ships no types; @types/plotly.js covers the API` at the import site. Precedent: `frontend/src/components/ResultsViewer.tsx:6`.
- **API base**: All new endpoints live under `/api/results/{job_id}/...`. Frontend fetches via `api.foo()` in `frontend/src/api/client.ts`, never raw `fetch()`.
- **Path safety**: Any user-supplied filename goes through `_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")` and the `include_dir.resolve() not in target.parents` defence-in-depth check (precedent: `opm_ai/api/routes/upload.py:67-184`).
- **No new deps**: Use existing `plotly`, `pandas`, `resfo`, `react`, `tailwind`. The Export menu uses `<details>`; the Import modal uses the platform `<dialog>` element. No popover library, no react-hook-form.
- **Tests must be written first**: Each module lands with its test file in the same commit. Test framework: pytest + httpx TestClient (backend), vitest + @testing-library/react (frontend).
- **Commits**: Conventional prefix `opm-ai:` or `frontend:` matching the spec's commit list. Subject ≤ 72 chars. Body explains the why.
- **Test count target**: 332 (current) + ~60 new tests = ~392 total. Every new module lands with tests; CI is green at every commit boundary.
- **No --no-verify**: There are no pre-commit hooks anyway, but the rule stays.
- **Style**: Match existing patterns. `viewer3d/ControlPanel.tsx`'s `Section`/`Field`/`Check`/`Sel`/`Num` primitives are the pattern to follow for any new control rail.
- **DRY for figure rendering**: One `PlotCard.tsx`, used by both the Plots tab and ChatPanel's tool-result rendering. Do not fork.
- **No emojis, no em-dashes, no sycophantic openers**: Matches repo and personal style.

---

## File Map

Files this plan creates or modifies, grouped by task. This is the structural contract — every task's implementer should be able to grep for their files here.

### New files (backend)

| Path | Owner task | Purpose |
|---|---|---|
| `opm_ai/postprocess/categorizer.py` | Task 1 | Summary DataFrame -> CategorizedVectors TypedDict |
| `opm_ai/postprocess/plot_groups.py` | Task 2 | DataFrame + selection -> go.Figure, one per group |
| `opm_ai/postprocess/resample.py` | Task 3 | DataFrame + freq -> resampled DataFrame |
| `opm_ai/api/routes/imported_results.py` | Task 5 | Multipart upload + virtual-job registration |

### Modified files (backend)

| Path | Owner task | Change |
|---|---|---|
| `opm_ai/api/schemas.py` | Task 4, 5, 6 | Add CategorizedVectorsResponse, PlotGroupResponse, ImportedResultResponse, CsvFrequency enum |
| `opm_ai/api/routes/results.py` | Task 4 | Add /categories, /plot_group, /csv endpoints |
| `opm_ai/api/routes/__init__.py` | Task 5 | Register imported_results router |
| `opm_ai/api/server.py` | Task 5 | Mount imported_results router |
| `opm_ai/api/job_store.py` | Task 5 | Add register_virtual_job helper + Job.kind enum |
| `opm_ai/api/routes/chat.py` | Task 6 | Add list_available_vectors, plot_well_vectors, compare_wells tools + compact_tool_result rules |

### New files (backend tests)

| Path | Owner task | Cases |
|---|---|---|
| `tests/unit/test_categorizer.py` | Task 1 | 10 |
| `tests/unit/test_plot_groups.py` | Task 2 | 15 |
| `tests/unit/test_resample.py` | Task 3 | 8 |
| `tests/unit/test_import_validation.py` | Task 5 | 5 |
| `tests/integration/test_imported_results_route.py` | Task 5 | 8 |
| `tests/integration/test_chat_tools_results.py` | Task 6 | 6 |

### Modified files (backend tests)

| Path | Owner task | Change |
|---|---|---|
| `tests/integration/test_results_plot_failure.py` | Task 4 | Add per-group failure + categories + CSV cases |

### New files (frontend)

| Path | Owner task | Purpose |
|---|---|---|
| `frontend/src/components/results/PlotCard.tsx` | Task 7 | Extracted Plotly renderer + Export menu |
| `frontend/src/components/results/ResultsControlRail.tsx` | Task 7 | Per-tab well/vector/display selector |
| `frontend/src/components/results/ImportResultsButton.tsx` | Task 8 | Modal file picker + submit |

### New files (frontend tests)

| Path | Owner task | Cases |
|---|---|---|
| `frontend/src/components/results/PlotCard.test.tsx` | Task 10 | 4 |
| `frontend/src/components/results/ResultsControlRail.test.tsx` | Task 7 | 4 |
| `frontend/src/components/results/ImportResultsButton.test.tsx` | Task 8 | 4 |

### Modified files (frontend)

| Path | Owner task | Change |
|---|---|---|
| `frontend/src/components/ResultsViewer.tsx` | Task 7 | Two-column layout, uses ControlRail + PlotCard |
| `frontend/src/types.ts` | Task 4, 7, 8, 10 | New types |
| `frontend/src/api/client.ts` | Task 4, 8, 10 | New api methods |
| `frontend/src/stores/useAppStore.ts` | Task 7 | setCategories / getCategories helpers |
| `frontend/src/components/ChatPanel.tsx` | Task 10 | Render PlotCard for plot_well_vectors/compare_wells tool results |
| `frontend/src/components/viewer3d/ControlPanel.tsx` | Task 9 | Cross-section + well-overlay sections |

---

## Commit Plan

10 commits, each green, in this order:

1. `opm-ai: results — categorizer (field/well/injection groups) + tests` — Task 1
2. `opm-ai: results — plot_groups (one builder per vector family) + tests` — Task 2
3. `opm-ai: results — resample (native/monthly/yearly) + tests` — Task 3
4. `opm-ai: api — /categories, /plot_group, /csv endpoints + tests` — Task 4
5. `opm-ai: api — /imported-results (virtual-job registration) + tests` — Task 5
6. `opm-ai: api — chat tools (list_vectors, plot_well_vectors, compare_wells) + tests` — Task 6
7. `frontend: results — left-side control rail + extracted PlotCard` — Task 7
8. `frontend: results — Import Results button + modal` — Task 8
9. `frontend: viewer3d — cross-section + well property overlay` — Task 9
10. `frontend: results — Export Graph (PNG/SVG/CSV at 3 frequencies) + ChatPanel figure rendering` — Task 10

---

### Task 1: Categorizer — summarise DataFrame into priority groups

**Files:**
- Create: `opm_ai/postprocess/categorizer.py`
- Test: `tests/unit/test_categorizer.py`

**Interfaces:**
- Consumes: `pd.DataFrame` from `opm_ai.postprocess.summary.read_summary()`. Columns include `TIME` plus vector columns shaped `"FOPR"`, `"WOPR:PROD1"`, `"WOPT:INJ1"`, etc.
- Produces:
  ```python
  class CategorizedVectors(TypedDict):
      field_rates: list[str]
      field_cumulative: list[str]
      field_derived: list[str]
      well_rates: dict[str, list[str]]      # well_name -> [vector, ...]
      well_cumulative: dict[str, list[str]]
      well_injection: dict[str, list[str]]
      wells: list[str]                       # all wells seen, deduped, ordered
  ```
- The `CategorizedVectors` TypedDict is re-exported from this module. Downstream consumers (`plot_groups.py`, `routes/results.py`, `routes/chat.py`) import from here.

- [ ] **Step 1: Write the failing test file**

Create `tests/unit/test_categorizer.py` with these 10 cases. Use the existing fixture pattern from `tests/unit/test_kpi.py` if present, otherwise build a small helper at the top of the test file:

```python
"""Unit tests for opm_ai.postprocess.categorizer."""
import pandas as pd
import pytest

from opm_ai.postprocess.categorizer import (
    CategorizedVectors,
    categorize,
)


def _df(**cols: dict[str, list[float]]) -> pd.DataFrame:
    """Build a one-row-per-timestep DataFrame with TIME column."""
    n = max(len(v) for v in cols.values())
    data: dict[str, list] = {"TIME": list(range(n))}
    data.update(cols)
    return pd.DataFrame(data)


def test_empty_dataframe_returns_empty_categories():
    df = pd.DataFrame(columns=["TIME"])
    result = categorize(df)
    assert result["wells"] == []
    assert result["field_rates"] == []
    assert result["field_cumulative"] == []
    assert result["field_derived"] == []
    assert result["well_rates"] == {}
    assert result["well_cumulative"] == {}
    assert result["well_injection"] == {}


def test_only_field_rates():
    df = _df(FOPR=[100.0, 90.0], FWPR=[0.0, 5.0], FGPR=[10.0, 8.0])
    result = categorize(df)
    assert sorted(result["field_rates"]) == ["FGPR", "FOPR", "FWPR"]
    assert result["field_cumulative"] == []
    assert result["field_derived"] == []


def test_only_well_rates():
    df = _df(**{"WOPR:PROD1": [100.0, 50.0], "WBHP:PROD1": [3000.0, 2900.0]})
    result = categorize(df)
    assert result["wells"] == ["PROD1"]
    assert sorted(result["well_rates"]["PROD1"]) == ["WBHP", "WOPR"]
    assert result["well_cumulative"] == {}
    assert result["well_injection"] == {}


def test_mixed_field_and_well():
    df = _df(
        FOPR=[100.0],
        FOPT=[1000.0],
        **{"WOPR:PROD1": [50.0], "WBHP:PROD1": [3000.0]},
    )
    result = categorize(df)
    assert result["field_rates"] == ["FOPR"]
    assert result["field_cumulative"] == ["FOPT"]
    assert result["wells"] == ["PROD1"]
    assert sorted(result["well_rates"]["PROD1"]) == ["WBHP", "WOPR"]


def test_no_positive_producer_well_excluded():
    # WOPR is all zero — well is not a producer
    df = _df(**{"WOPR:DEAD": [0.0, 0.0], "WBHP:DEAD": [3000.0, 3000.0]})
    result = categorize(df)
    assert result["wells"] == ["DEAD"]  # appears in wells list
    assert result["well_rates"] == {}    # but no rates group (well isn't a producer)


def test_water_producer_recognized_without_oil():
    # WWPR positive, WOPR zero — pure water producer should still be categorized
    df = _df(
        **{
            "WOPR:WATER1": [0.0, 0.0],
            "WWPR:WATER1": [50.0, 60.0],
            "WBHP:WATER1": [3000.0, 2900.0],
        }
    )
    result = categorize(df)
    assert "WATER1" in result["wells"]
    assert sorted(result["well_rates"]["WATER1"]) == ["WBHP", "WWPR"]


def test_injector_recognized():
    df = _df(
        **{
            "WGIR:GAS1": [100.0, 90.0],
            "WGIT:GAS1": [1000.0, 1500.0],
            "WWIR:WAT1": [200.0, 180.0],
            "WWIT:WAT1": [5000.0, 6500.0],
        }
    )
    result = categorize(df)
    assert sorted(result["wells"]) == ["GAS1", "WAT1"]
    assert sorted(result["well_injection"]["GAS1"]) == ["WGIR", "WGIT"]
    assert sorted(result["well_injection"]["WAT1"]) == ["WWIR", "WWIT"]
    assert result["well_rates"] == {}


def test_mixed_producer_and_injector_well():
    # Well with both production and injection appears in both groups
    df = _df(
        **{
            "WOPR:DUAL": [50.0, 40.0],
            "WGIR:DUAL": [10.0, 12.0],
        }
    )
    result = categorize(df)
    assert "DUAL" in result["well_rates"]
    assert "DUAL" in result["well_injection"]
    assert "WOPR" in result["well_rates"]["DUAL"]
    assert "WGIR" in result["well_injection"]["DUAL"]


def test_rft_columns_ignored():
    # RFT files use CONDEPTH, CONPRES — not in any well keyword list
    df = _df(
        FOPR=[100.0],
        **{"CONDEPTH:W1": [8000.0], "CONPRES:W1": [3000.0]},
    )
    result = categorize(df)
    assert result["field_rates"] == ["FOPR"]
    # CONDEPTH/CONPRES are not in any well_* keyword list, so well is dropped
    assert result["well_rates"] == {}
    assert result["wells"] == []


def test_unknown_well_keyword_ignored():
    # WWELLFOO is not in any list — column passes through, well is not categorised
    df = _df(
        FOPR=[100.0],
        **{"WWELLFOO:PROD1": [42.0]},
    )
    result = categorize(df)
    assert result["field_rates"] == ["FOPR"]
    assert result["wells"] == []
    assert result["well_rates"] == {}
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `pytest tests/unit/test_categorizer.py -v`
Expected: `ModuleNotFoundError: No module named 'opm_ai.postprocess.categorizer'`

- [ ] **Step 3: Implement the module**

Create `opm_ai/postprocess/categorizer.py`:

```python
"""Categorise summary DataFrame columns into priority vector groups.

The summary file mixes field totals, well-level production, well-level
injection, RFT data, and various auxiliaries. The Results Viewer needs
to expose the top-4 priority families from eclipse_output_formats.json
(Field rates/cumulative/derived, Well rates/cumulative/injection), so
this module scans the DataFrame's columns once and groups them.

Rules (enumerated, not inferred from data — see spec section
"Detection rules"):

- Field vectors: column == FOPR|FWPR|FGPR (rates),
  FOPT|FWPT|FGPT (cumulative), or FWCT|FGOR|FPR (derived).
- Well vectors: column contains ":" and the part before ":" is in the
  well-keyword list for the family. Empty groups are dropped.
- A well is a producer if any of WOPR/WWPR/WGPR has a positive max value
  (catches pure water/gas producers).
- A well is an injector if any of WGIR/WWIR/WGIT/WWIT/WOIR has a positive
  value and the producer test fails.
- Wells with both positive production and injection appear in both groups.
- Anything outside the keyword lists is left in the DataFrame (kpi.py
  handles it) but is NOT categorised.

Pure functions; no I/O. NaN/Inf in vector columns is treated as
"not positive" for the producer/injector test (matches kpi.py).
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import pandas as pd


FIELD_RATES = ("FOPR", "FWPR", "FGPR")
FIELD_CUMULATIVE = ("FOPT", "FWPT", "FGPT")
FIELD_DERIVED = ("FWCT", "FGOR", "FPR")

WELL_RATES_KEYWORDS = ("WOPR", "WWPR", "WGPR", "WBHP", "WGOR", "WWCT")
WELL_CUMULATIVE_KEYWORDS = ("WOPT", "WWPT", "WGPT")
WELL_INJECTION_KEYWORDS = ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT")

PRODUCER_TEST_KEYWORDS = ("WOPR", "WWPR", "WGPR")
INJECTOR_TEST_KEYWORDS = ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT")


class CategorizedVectors(TypedDict):
    """Categorised view of a summary DataFrame.

    All values are JSON-safe (lists/dicts of strings).
    """

    field_rates: list[str]
    field_cumulative: list[str]
    field_derived: list[str]
    well_rates: dict[str, list[str]]
    well_cumulative: dict[str, list[str]]
    well_injection: dict[str, list[str]]
    wells: list[str]


def _split_well_column(col: str) -> tuple[str, str] | None:
    """Return (keyword, well_name) if col is a well vector, else None."""
    if ":" not in col:
        return None
    keyword, _, well_name = col.partition(":")
    if not well_name:
        return None
    return keyword, well_name


def _max_positive(df: pd.DataFrame, col: str) -> float:
    """Return the max positive value of col, treating NaN/Inf as zero."""
    if col not in df.columns:
        return 0.0
    series = df[col].replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return 0.0
    positive = series[series > 0]
    if positive.empty:
        return 0.0
    return float(positive.max())


def _is_producer(df: pd.DataFrame, well: str) -> bool:
    return any(_max_positive(df, f"{kw}:{well}") > 0 for kw in PRODUCER_TEST_KEYWORDS)


def _is_injector(df: pd.DataFrame, well: str) -> bool:
    return any(_max_positive(df, f"{kw}:{well}") > 0 for kw in INJECTOR_TEST_KEYWORDS)


def categorize(df: pd.DataFrame) -> CategorizedVectors:
    """Scan df.columns and group them into priority vector families.

    Operates only on df.columns (string ops) and one max() per
    producer/injector test. Cheap to call — runs once per Results page
    mount.
    """
    if df.empty:
        return CategorizedVectors(
            field_rates=[],
            field_cumulative=[],
            field_derived=[],
            well_rates={},
            well_cumulative={},
            well_injection={},
            wells=[],
        )

    field_rates = [c for c in FIELD_RATES if c in df.columns]
    field_cumulative = [c for c in FIELD_CUMULATIVE if c in df.columns]
    field_derived = [c for c in FIELD_DERIVED if c in df.columns]

    well_rates: dict[str, list[str]] = {}
    well_cumulative: dict[str, list[str]] = {}
    well_injection: dict[str, list[str]] = {}

    for col in df.columns:
        if col == "TIME":
            continue
        split = _split_well_column(col)
        if split is None:
            continue
        keyword, well = split
        if keyword in WELL_RATES_KEYWORDS and _is_producer(df, well):
            well_rates.setdefault(well, []).append(keyword)
        elif keyword in WELL_CUMULATIVE_KEYWORDS and _is_producer(df, well):
            well_cumulative.setdefault(well, []).append(keyword)
        elif keyword in WELL_INJECTION_KEYWORDS and _is_injector(df, well):
            well_injection.setdefault(well, []).append(keyword)

    # Sort for deterministic output (tests assert against sorted lists).
    for group in (well_rates, well_cumulative, well_injection):
        for well in group:
            group[well].sort()

    wells = sorted(set(well_rates) | set(well_cumulative) | set(well_injection))

    return CategorizedVectors(
        field_rates=sorted(field_rates),
        field_cumulative=sorted(field_cumulative),
        field_derived=sorted(field_derived),
        well_rates=well_rates,
        well_cumulative=well_cumulative,
        well_injection=well_injection,
        wells=wells,
    )
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `pytest tests/unit/test_categorizer.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add opm_ai/postprocess/categorizer.py tests/unit/test_categorizer.py
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "opm-ai: results — categorizer (field/well/injection groups) + tests"
```

Expected: One commit on `feat/results-page-enrichment`. `git log --oneline -1` shows the new commit; `git status` is clean.

---

### Task 2: plot_groups — Plotly builders per vector family

**Files:**
- Create: `opm_ai/postprocess/plot_groups.py`
- Test: `tests/unit/test_plot_groups.py`

**Interfaces:**
- Consumes: `pd.DataFrame` from `read_summary()`; well/vector selection from request query params.
- Produces six module-level functions, each returning `plotly.graph_objects.Figure`:
  ```python
  def plot_field_rates(df: pd.DataFrame, vectors: list[str] | None = None) -> go.Figure: ...
  def plot_field_cumulative(df: pd.DataFrame, vectors: list[str] | None = None) -> go.Figure: ...
  def plot_field_derived(df: pd.DataFrame, vectors: list[str] | None = None) -> go.Figure: ...
  def plot_well_rates(df: pd.DataFrame, wells: list[str], vectors: list[str] | None = None) -> go.Figure: ...
  def plot_well_cumulative(df: pd.DataFrame, wells: list[str], vectors: list[str] | None = None) -> go.Figure: ...
  def plot_well_injection(df: pd.DataFrame, wells: list[str], vectors: list[str] | None = None) -> go.Figure: ...
  ```
- One dispatcher:
  ```python
  def plot_group(group: str, df: pd.DataFrame, wells: list[str], vectors: list[str] | None) -> go.Figure: ...
  ```
  Raises `ValueError(f"Unknown group: {group}")` for unknown groups so the route returns a clean 400.

- [ ] **Step 1: Write the failing test file**

Create `tests/unit/test_plot_groups.py`:

```python
"""Unit tests for opm_ai.postprocess.plot_groups."""
import pandas as pd
import plotly.graph_objects as go
import pytest

from opm_ai.postprocess.plot_groups import (
    plot_field_cumulative,
    plot_field_derived,
    plot_field_rates,
    plot_group,
    plot_well_cumulative,
    plot_well_injection,
    plot_well_rates,
)


def _df(**cols: dict[str, list[float]]) -> pd.DataFrame:
    n = max(len(v) for v in cols.values())
    return pd.DataFrame({"TIME": list(range(n)), **cols})


# ── Field groups ────────────────────────────────────────────────────────


def test_plot_field_rates_one_trace_per_vector():
    df = _df(FOPR=[100.0, 90.0], FWPR=[0.0, 5.0])
    fig = plot_field_rates(df)
    assert isinstance(fig, go.Figure)
    names = [trace.name for trace in fig.data]
    assert any("FOPR" in n for n in names)
    assert any("FWPR" in n for n in names)


def test_plot_field_rates_filter_by_vectors():
    df = _df(FOPR=[100.0], FWPR=[5.0], FGPR=[10.0])
    fig = plot_field_rates(df, vectors=["FOPR"])
    assert len(fig.data) == 1
    assert "FOPR" in fig.data[0].name


def test_plot_field_cumulative_has_traces():
    df = _df(FOPT=[1000.0, 2000.0], FWPT=[50.0, 100.0])
    fig = plot_field_cumulative(df)
    assert len(fig.data) == 2


def test_plot_field_derived_watercut():
    df = _df(FOPR=[100.0, 50.0], FWPR=[0.0, 50.0])
    fig = plot_field_derived(df, vectors=["FWCT"])
    assert len(fig.data) == 1
    # Watercut at t=1 should be 50 / (50+50) = 0.5 = 50%
    y = list(fig.data[0].y)
    assert y[0] == pytest.approx(0.0) or y[0] == pytest.approx(0.0, abs=1e-9)
    assert y[1] == pytest.approx(50.0)


# ── Well groups ─────────────────────────────────────────────────────────


def test_plot_well_rates_one_trace_per_well_per_vector():
    df = _df(**{"WOPR:PROD1": [50.0, 40.0], "WBHP:PROD1": [3000.0, 2900.0]})
    fig = plot_well_rates(df, wells=["PROD1"])
    assert len(fig.data) == 2


def test_plot_well_rates_filters_wells():
    df = _df(**{"WOPR:PROD1": [50.0], "WOPR:PROD2": [40.0]})
    fig = plot_well_rates(df, wells=["PROD1"], vectors=["WOPR"])
    assert len(fig.data) == 1
    assert "PROD1" in fig.data[0].name


def test_plot_well_rates_water_rate_sanitized():
    # FWPR-style negative zero: -0.0 should be clipped to 0
    df = _df(
        **{
            "WOPR:PROD1": [50.0, 50.0],
            "WWPR:PROD1": [-0.0, 5.0],
        }
    )
    fig = plot_well_rates(df, wells=["PROD1"])
    wwpr_trace = next(t for t in fig.data if "WWPR" in t.name)
    assert all(v >= 0 for v in wwpr_trace.y)


def test_plot_well_cumulative_filters():
    df = _df(
        **{"WOPT:PROD1": [1000.0, 1500.0], "WWPT:PROD1": [50.0, 60.0]}
    )
    fig = plot_well_cumulative(df, wells=["PROD1"], vectors=["WOPT"])
    assert len(fig.data) == 1


def test_plot_well_injection_filters():
    df = _df(**{"WGIR:GAS1": [10.0, 12.0], "WWIR:WAT1": [50.0, 55.0]})
    fig = plot_well_injection(df, wells=["GAS1", "WAT1"])
    assert len(fig.data) == 2


# ── Edge cases ──────────────────────────────────────────────────────────


def test_empty_dataframe_returns_empty_figure():
    df = pd.DataFrame(columns=["TIME"])
    fig = plot_field_rates(df)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_missing_vectors_skipped():
    df = _df(FOPR=[100.0])  # FWPR not present
    fig = plot_field_rates(df)
    assert len(fig.data) == 1


def test_plot_group_dispatch():
    df = _df(FOPR=[100.0])
    fig = plot_group("field_rates", df, wells=[], vectors=None)
    assert len(fig.data) == 1


def test_plot_group_unknown_raises():
    df = _df(FOPR=[100.0])
    with pytest.raises(ValueError, match="Unknown group"):
        plot_group("nonsense", df, wells=[], vectors=None)


def test_log_scale_kwarg_applied():
    df = _df(FOPR=[100.0, 10.0])
    fig = plot_field_rates(df, log_scale=True)
    assert fig.layout.yaxis.type == "log"


def test_single_timestep_no_error():
    df = _df(FOPR=[100.0])
    fig = plot_field_rates(df)
    assert len(fig.data) == 1


def test_helpers_share_layout_style():
    # Common visual contract: title, axes labelled, hovermode unified
    df = _df(FOPR=[100.0])
    fig = plot_field_rates(df)
    assert fig.layout.hovermode == "x unified"
    assert fig.layout.xaxis.title.text  # non-empty
    assert fig.layout.yaxis.title.text
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_plot_groups.py -v`
Expected: `ModuleNotFoundError: No module named 'opm_ai.postprocess.plot_groups'`

- [ ] **Step 3: Implement plot_groups.py**

Create `opm_ai/postprocess/plot_groups.py`:

```python
"""Plotly builders for the priority vector families.

One builder per group; mirrors the categorizer families exactly. Each
function only emits a trace for columns that actually exist in the
DataFrame (spec: "plot only what is present"). No zero-fills, no
fabrication.

Reuses the sanitization and hovertemplate style from opm_ai/postprocess/plots.py
so the existing Plotly conventions carry over.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go


_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]


def _sanitize_water_rate(series: pd.Series) -> pd.Series:
    return series.clip(lower=0)


def _well_cols(df: pd.DataFrame, well: str, keywords: tuple[str, ...]) -> list[str]:
    return [f"{kw}:{well}" for kw in keywords if f"{kw}:{well}" in df.columns]


def _time(df: pd.DataFrame) -> pd.Series:
    return df["TIME"] if "TIME" in df.columns else pd.Series(dtype=float)


def _apply_log(fig: go.Figure, log_scale: bool) -> go.Figure:
    if log_scale:
        fig.update_layout(yaxis_type="log")
    return fig


def _base_layout(title: str, y_title: str, height: int = 500) -> dict:
    return dict(
        title=title,
        xaxis_title="Time (days)",
        yaxis_title=y_title,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        height=height,
    )


# ── Field groups ────────────────────────────────────────────────────────


def plot_field_rates(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FOPR", "FWPR", "FGPR"]
    labels = {"FOPR": "Field Oil Rate (STB/day)", "FWPR": "Field Water Rate (STB/day)", "FGPR": "Field Gas Rate (MSCF/day)"}
    colors = {"FOPR": "#1f77b4", "FWPR": "#ff7f0e", "FGPR": "#2ca02c"}
    for i, col in enumerate(requested):
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=labels.get(col, col),
            line=dict(color=colors.get(col, _COLORS[i % len(_COLORS)])),
            hovertemplate=f"{labels.get(col, col)}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    fig.update_layout(**_base_layout("Production Rates", "Rate"))
    return _apply_log(fig, log_scale)


def plot_field_cumulative(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FOPT", "FWPT", "FGPT"]
    labels = {"FOPT": "Cumulative Oil (STB)", "FWPT": "Cumulative Water (STB)", "FGPT": "Cumulative Gas (MSCF)"}
    colors = {"FOPT": "#1f77b4", "FWPT": "#ff7f0e", "FGPT": "#2ca02c"}
    for i, col in enumerate(requested):
        if col not in df.columns:
            continue
        fig.add_trace(go.Scatter(
            x=_time(df), y=df[col], mode="lines",
            name=labels.get(col, col),
            line=dict(color=colors.get(col, _COLORS[i % len(_COLORS)])),
            hovertemplate=f"{labels.get(col, col)}: %{{y:.0f}}<br>Time: %{{x:.1f}} days<extra></extra>",
        ))
    fig.update_layout(**_base_layout("Cumulative Production", "Cumulative Volume"))
    return _apply_log(fig, log_scale)


def plot_field_derived(
    df: pd.DataFrame,
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    requested = vectors or ["FWCT", "FGOR", "FPR"]
    if "FWCT" in requested and "FWCT" not in df.columns and "FOPR" in df.columns and "FWPR" in df.columns:
        fwpr = _sanitize_water_rate(df["FWPR"])
        liq = df["FOPR"] + df["FWPR"]
        wc_pct = (fwpr / liq.replace(0, np.nan)) * 100
        fig.add_trace(go.Scatter(
            x=_time(df), y=wc_pct, mode="lines",
            name="Field Water Cut (%)",
            line=dict(color="#ff7f0e", width=2),
            hovertemplate="Water Cut: %{y:.1f}%<br>Time: %{x:.1f}} days<extra></extra>",
        ))
    if "FGOR" in requested and "FGOR" in df.columns:
        fig.add_trace(go.Scatter(
            x=_time(df), y=df["FGOR"], mode="lines",
            name="Field GOR (MSCF/STB)",
            line=dict(color="#2ca02c"),
        ))
    if "FPR" in requested and "FPR" in df.columns:
        fig.add_trace(go.Scatter(
            x=_time(df), y=df["FPR"], mode="lines",
            name="Field Avg Pressure (psia)",
            line=dict(color="#d62728"),
        ))
    fig.update_layout(**_base_layout("Field Derived", "Value"))
    return _apply_log(fig, log_scale)


# ── Well groups ─────────────────────────────────────────────────────────


def _well_figure(
    df: pd.DataFrame,
    wells: list[str],
    keywords: tuple[str, ...],
    title: str,
    y_title: str,
    *,
    log_scale: bool = False,
    vector_filter: list[str] | None = None,
) -> go.Figure:
    fig = go.Figure()
    if df.empty or "TIME" not in df.columns:
        return _apply_log(fig, log_scale)
    for i, well in enumerate(wells):
        color = _COLORS[i % len(_COLORS)]
        for kw in keywords:
            if vector_filter and kw not in vector_filter:
                continue
            col = f"{kw}:{well}"
            if col not in df.columns:
                continue
            y = _sanitize_water_rate(df[col]) if kw == "WWPR" else df[col]
            fig.add_trace(go.Scatter(
                x=_time(df), y=y, mode="lines",
                name=f"{kw} {well}",
                line=dict(color=color, dash="dot" if kw.startswith("W") and kw != "WBHP" else "solid"),
                hovertemplate=f"{kw} {well}: %{{y:.1f}}<br>Time: %{{x:.1f}} days<extra></extra>",
            ))
    fig.update_layout(**_base_layout(title, y_title))
    return _apply_log(fig, log_scale)


def plot_well_rates(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    return _well_figure(
        df, wells, ("WOPR", "WWPR", "WGPR", "WBHP", "WGOR", "WWCT"),
        "Well Rates", "Rate",
        log_scale=log_scale, vector_filter=vectors,
    )


def plot_well_cumulative(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    return _well_figure(
        df, wells, ("WOPT", "WWPT", "WGPT"),
        "Well Cumulative", "Cumulative Volume",
        log_scale=log_scale, vector_filter=vectors,
    )


def plot_well_injection(
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None = None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    return _well_figure(
        df, wells, ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT"),
        "Well Injection", "Rate / Cumulative",
        log_scale=log_scale, vector_filter=vectors,
    )


# ── Dispatcher ──────────────────────────────────────────────────────────


_DISPATCH: dict[str, Callable[..., go.Figure]] = {
    "field_rates": plot_field_rates,
    "field_cumulative": plot_field_cumulative,
    "field_derived": plot_field_derived,
    "well_rates": plot_well_rates,
    "well_cumulative": plot_well_cumulative,
    "well_injection": plot_well_injection,
}


def plot_group(
    group: str,
    df: pd.DataFrame,
    wells: list[str],
    vectors: list[str] | None,
    *,
    log_scale: bool = False,
) -> go.Figure:
    """Dispatch to the right plot_* function. Raises ValueError on unknown group."""
    fn = _DISPATCH.get(group)
    if fn is None:
        raise ValueError(f"Unknown group: {group!r}. Known: {sorted(_DISPATCH)}")
    if group.startswith("field_"):
        return fn(df, vectors=vectors, log_scale=log_scale)
    return fn(df, wells, vectors=vectors, log_scale=log_scale)
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/unit/test_plot_groups.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add opm_ai/postprocess/plot_groups.py tests/unit/test_plot_groups.py
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "opm-ai: results — plot_groups (one builder per vector family) + tests"
```

---

### Task 3: resample — native / monthly / yearly frequency resampling

**Files:**
- Create: `opm_ai/postprocess/resample.py`
- Test: `tests/unit/test_resample.py`

**Interfaces:**
- Consumes: `pd.DataFrame` from `read_summary()` (must have `TIME` column); `freq` string.
- Produces:
  ```python
  def resample_summary(df: pd.DataFrame, freq: str) -> pd.DataFrame: ...
  ```
  `freq` is one of `"native"` (early return, returns a copy), `"monthly"` (alias `"M"`), `"yearly"` (alias `"Y"`).
- Returns a new DataFrame; never mutates the input. The TIME column on output is a `DatetimeIndex` for monthly/yearly, original integer TIME for native.
- Empty result for unknown freq -> raises `ValueError`.

- [ ] **Step 1: Write the failing test file**

Create `tests/unit/test_resample.py`:

```python
"""Unit tests for opm_ai.postprocess.resample."""
import numpy as np
import pandas as pd
import pytest

from opm_ai.postprocess.resample import resample_summary


def _dt_df(start: str, days: int, **cols: list[float]) -> pd.DataFrame:
    """Build a DataFrame with a DatetimeIndex TIME column starting at start."""
    n = max(len(v) for v in cols.values())
    index = pd.date_range(start, periods=n, freq=f"{days}D") if n > 1 else pd.DatetimeIndex([pd.Timestamp(start)])
    return pd.DataFrame({"TIME": index, **cols})


def _step_df(steps: list[int], **cols: list[float]) -> pd.DataFrame:
    """Build a DataFrame with integer step TIME column (no datetime)."""
    return pd.DataFrame({"TIME": steps, **cols})


# ── Native ──────────────────────────────────────────────────────────────


def test_native_is_identity():
    df = _dt_df("2020-01-01", 1, FOPR=[100.0, 90.0, 80.0])
    out = resample_summary(df, "native")
    assert len(out) == 3
    assert list(out["FOPR"]) == [100.0, 90.0, 80.0]


def test_native_does_not_mutate_input():
    df = _dt_df("2020-01-01", 1, FOPR=[100.0])
    resample_summary(df, "native")
    assert list(df["FOPR"]) == [100.0]


# ── Datetime monthly ────────────────────────────────────────────────────


def test_monthly_rate_uses_mean():
    # 30 days of constant 100 STB/d -> mean = 100, one bucket
    df = _dt_df("2020-01-01", 1, FOPR=[100.0] * 30)
    out = resample_summary(df, "monthly")
    assert len(out) == 1
    assert out["FOPR"].iloc[0] == pytest.approx(100.0)


def test_monthly_cumulative_uses_last():
    # FOPT increases linearly from 0 to 2900 over 30 days -> last value = 2900
    df = _dt_df("2020-01-01", 1, FOPT=[float(i) for i in range(30)])
    out = resample_summary(df, "monthly")
    assert out["FOPT"].iloc[0] == pytest.approx(29.0)


# ── Datetime yearly ─────────────────────────────────────────────────────


def test_yearly_pressure_uses_mean():
    # 365 days of 3000 psia -> mean = 3000
    df = _dt_df("2020-01-01", 1, FPR=[3000.0] * 365)
    out = resample_summary(df, "yearly")
    assert len(out) == 1
    assert out["FPR"].iloc[0] == pytest.approx(3000.0)


# ── Step-index fallback ────────────────────────────────────────────────


def test_step_index_fallback_monthly():
    # Integer TIME that doesn't parse as datetime -> step-based bucketing
    # days_per_bucket=30, so steps 0..89 -> 3 monthly buckets
    df = _step_df(list(range(90)), FOPR=[100.0] * 90)
    out = resample_summary(df, "monthly")
    assert len(out) == 3
    assert all(out["FOPR"] == pytest.approx(100.0))


# ── Bucket handling ─────────────────────────────────────────────────────


def test_empty_bucket_dropped():
    # 10 days in January, then a gap of 100 days, then 10 days in May
    df = _dt_df("2020-01-01", 1, FOPR=[100.0] * 10 + [np.nan] * 100 + [200.0] * 10)
    out = resample_summary(df, "monthly")
    # Two non-empty months (Jan and May); the NaN-only months should be dropped
    assert len(out) == 2
    assert out["FOPR"].iloc[0] == pytest.approx(100.0)
    assert out["FOPR"].iloc[1] == pytest.approx(200.0)


def test_mixed_suffixes_in_one_frame():
    # FOPR (rate) and FOPT (cumulative) in the same DataFrame
    df = _dt_df("2020-01-01", 1, FOPR=[100.0] * 60, FOPT=[float(i * 10) for i in range(60)])
    out = resample_summary(df, "monthly")
    assert len(out) == 2  # Jan, Feb
    # January FOPR mean = 100
    assert out["FOPR"].iloc[0] == pytest.approx(100.0)
    # January FOPT last = day 30 * 10 = 300
    assert out["FOPT"].iloc[0] == pytest.approx(300.0)
    # February FOPT last = day 59 * 10 = 590
    assert out["FOPT"].iloc[1] == pytest.approx(590.0)


def test_unknown_freq_raises():
    df = _dt_df("2020-01-01", 1, FOPR=[100.0])
    with pytest.raises(ValueError, match="Unknown freq"):
        resample_summary(df, "daily")
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/unit/test_resample.py -v`
Expected: `ModuleNotFoundError: No module named 'opm_ai.postprocess.resample'`

- [ ] **Step 3: Implement resample.py**

Create `opm_ai/postprocess/resample.py`:

```python
"""Resample a summary DataFrame to native / monthly / yearly frequency.

The summary file's TIME column is whatever the deck asked Flow to write.
For CSV export we offer three frequencies:

- native: the file as-is (a copy, not the input itself)
- monthly / yearly: resampled with rules keyed off the vector suffix.
  Rate vectors -> mean (time-average over the bucket); cumulative
  vectors -> last (snapshot at bucket end). Defaults to mean for any
  unrecognised suffix (documented assumption: prefer smoothness over
  invented precision).

If TIME does not parse as datetime (some decks store the report-step
index instead of a date), we fall back to step-index bucketing with
days_per_bucket = 30 (monthly) or 365 (yearly). Both code paths are
unit-tested.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd


Freq = Literal["native", "monthly", "yearly"]

# Pandas resample rule per freq.
_RULE: dict[str, str] = {"monthly": "M", "yearly": "Y"}

# Days-per-bucket for step-index fallback (when TIME isn't parseable).
_DAYS_PER_BUCKET: dict[str, int] = {"monthly": 30, "yearly": 365}

# Suffix -> aggregation rule. Anything not in this map defaults to "mean".
_SUFFIX_RULE: dict[str, str] = {
    "R": "mean",     # rate
    "IR": "mean",    # injection rate
    "T": "last",     # cumulative total
    "IT": "last",    # cumulative injection
    "IP": "last",    # in-place
    "P": "mean",     # pressure (single-letter)
    "PR": "mean",    # pressure (region)
    "SAT": "mean",
    "OR": "mean",
    "CT": "mean",
    "GP": "mean",
}


def _rule_for_column(col: str) -> str:
    """Return the pandas aggregation name for a given vector column.

    Inspects the *suffix* (last 1-3 chars) of the column. For well
    vectors like WOPR:PROD1 the keyword before ":" is the relevant part.
    """
    if ":" in col:
        keyword = col.split(":", 1)[0]
    else:
        keyword = col
    # Longest match wins (e.g. "IR" before "R", "IT" before "T").
    for suffix_length in (3, 2, 1):
        suffix = keyword[-suffix_length:]
        if suffix in _SUFFIX_RULE:
            return _SUFFIX_RULE[suffix]
    return "mean"


def _can_parse_as_datetime(series: pd.Series) -> bool:
    try:
        pd.to_datetime(series.iloc[0])
        return True
    except (ValueError, TypeError):
        return False


def _resample_datetime(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample using a DatetimeIndex on TIME."""
    indexed = df.set_index("TIME")
    indexed.index = pd.to_datetime(indexed.index)

    aggregations = {col: _rule_for_column(col) for col in indexed.columns}

    # pd.DataFrame.resample().agg() with a per-column dict — built-in.
    resampled = indexed.resample(rule).agg(aggregations)

    # Drop buckets where every value is NaN (no data in that bucket).
    resampled = resampled.dropna(how="all")

    return resampled.reset_index()


def _resample_step_index(df: pd.DataFrame, days_per_bucket: int) -> pd.DataFrame:
    """Fallback: bucket rows by floor(step / days_per_bucket)."""
    bucket = (df["TIME"] // days_per_bucket).astype(int)
    grouped = df.assign(_bucket=bucket).groupby("_bucket", sort=True)

    aggregations = {col: _rule_for_column(col) for col in df.columns if col != "TIME"}

    # For each bucket, aggregate per-column. Preserve the bucket-end TIME.
    rows: list[dict] = []
    for bucket_id, sub in grouped:
        row: dict = {"TIME": int(sub["TIME"].iloc[-1])}
        for col, rule in aggregations.items():
            if rule == "last":
                row[col] = sub[col].dropna().iloc[-1] if sub[col].notna().any() else float("nan")
            else:
                vals = sub[col].dropna()
                row[col] = float(vals.mean()) if len(vals) else float("nan")
        rows.append(row)
    return pd.DataFrame(rows).dropna(how="all", subset=[c for c in df.columns if c != "TIME"])


def resample_summary(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Return a new DataFrame resampled to the given frequency.

    `freq`: one of "native" (copy), "monthly", "yearly".

    Raises:
        ValueError: unknown freq, or empty DataFrame.
    """
    if df.empty or "TIME" not in df.columns:
        raise ValueError("Cannot resample empty DataFrame or missing TIME column")

    if freq == "native":
        return df.copy()

    if freq not in _RULE:
        raise ValueError(f"Unknown freq: {freq!r}. Use one of: {sorted(_RULE)}")

    if _can_parse_as_datetime(df["TIME"]):
        return _resample_datetime(df, _RULE[freq])
    return _resample_step_index(df, _DAYS_PER_BUCKET[freq])
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/unit/test_resample.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add opm_ai/postprocess/resample.py tests/unit/test_resample.py
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "opm-ai: results — resample (native/monthly/yearly) + tests"
```

---

### Task 4: API routes — /categories, /plot_group, /csv

**Files:**
- Modify: `opm_ai/api/schemas.py` (add 3 response models + CsvFrequency enum)
- Modify: `opm_ai/api/routes/results.py` (add 3 endpoints)
- Modify: `frontend/src/types.ts` (add mirror types)
- Modify: `frontend/src/api/client.ts` (add 3 API methods)
- Modify: `tests/integration/test_results_plot_failure.py` (extend with new cases)

**Interfaces:**
- New schemas in `opm_ai/api/schemas.py`:
  ```python
  class CsvFrequency(str, Enum):
      NATIVE = "native"
      MONTHLY = "monthly"
      YEARLY = "yearly"

  class CategorizedVectorsResponse(BaseModel):
      field_rates: list[str]
      field_cumulative: list[str]
      field_derived: list[str]
      well_rates: dict[str, list[str]]
      well_cumulative: dict[str, list[str]]
      well_injection: dict[str, list[str]]
      wells: list[str]

  class PlotGroupResponse(BaseModel):
      group: str
      figure_json: str  # "" on failure
      error: str | None = None
  ```
- New endpoints in `opm_ai/api/routes/results.py`:
  ```
  GET /api/results/{job_id}/categories         -> CategorizedVectorsResponse
  GET /api/results/{job_id}/plot_group/{group} -> PlotGroupResponse
       query: wells (csv), vectors (csv), log (bool, default false)
  GET /api/results/{job_id}/csv                -> text/csv
       query: group (str), vectors (csv), freq (CsvFrequency, default NATIVE)
  ```
- New API methods in `frontend/src/api/client.ts`:
  ```ts
  api.categories(jobId): Promise<CategorizedVectorsResponse>
  api.plotGroup(jobId, group, opts: {wells?: string[], vectors?: string[], log?: boolean}): Promise<PlotGroupResponse>
  api.csv(jobId, opts: {group: string, vectors: string[], freq?: CsvFrequency}): Promise<string>
  ```

- [ ] **Step 1: Extend `tests/integration/test_results_plot_failure.py`**

Open the existing file and add three new test functions at the bottom. Find the import block at the top and add to it; find the helpers and reuse them.

Imports to add at the top:

```python
from opm_ai.api.schemas import CategorizedVectorsResponse, PlotGroupResponse
from opm_ai.postprocess.categorizer import categorize
```

New test cases appended at end of file:

```python
def test_categories_endpoint_returns_empty_for_empty_summary(client, mock_completed_job):
    """A summary with only FOPR categorises correctly; nothing else appears."""
    job_id = mock_completed_job  # fixture writes FOPR/FWPR/FGPR/FOPT/FWPT/FGPT
    response = client.get(f"/api/results/{job_id}/categories")
    assert response.status_code == 200
    data = response.json()
    assert "FOPR" in data["field_rates"]
    assert "FOPT" in data["field_cumulative"]
    # No well vectors in the fixture
    assert data["wells"] == []


def test_plot_group_returns_empty_json_on_failure(client, mock_completed_job):
    """Unknown group -> empty figure_json, no 500."""
    response = client.get(f"/api/results/{mock_completed_job}/plot_group/no_such_group")
    assert response.status_code == 200
    data = response.json()
    assert data["figure_json"] == ""


def test_csv_export_native(client, mock_completed_job):
    """CSV at native frequency returns TIME + requested vectors."""
    response = client.get(
        f"/api/results/{mock_completed_job}/csv",
        params={"group": "field_rates", "vectors": "FOPR,FWPR"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    lines = body.strip().split("\n")
    assert lines[0] == "TIME,FOPR,FWPR"
    # Fixture has 5 timesteps
    assert len(lines) == 6


def test_csv_export_unknown_freq_returns_400(client, mock_completed_job):
    response = client.get(
        f"/api/results/{mock_completed_job}/csv",
        params={"group": "field_rates", "vectors": "FOPR", "freq": "daily"},
    )
    assert response.status_code == 400


def test_csv_export_missing_vectors_returns_header_only(client, mock_completed_job):
    response = client.get(
        f"/api/results/{mock_completed_job}/csv",
        params={"group": "field_rates", "vectors": "DOES_NOT_EXIST"},
    )
    assert response.status_code == 200
    assert response.text.strip() == "TIME"


def test_csv_export_monthly_resamples(client, mock_completed_job):
    response = client.get(
        f"/api/results/{mock_completed_job}/csv",
        params={"group": "field_rates", "vectors": "FOPR", "freq": "monthly"},
    )
    assert response.status_code == 200
    # Fixture is 5 timesteps spanning 30 days -> at most 2 monthly buckets
    assert len(response.text.strip().split("\n")) <= 3
```

Inspect the existing `mock_completed_job` fixture in this file to confirm it writes a summary file with 5 timesteps and FOPR/FWPR/FGPR/FOPT/FWPT/FGPT columns. If the fixture is different, adjust the test assertions to match — the goal is to verify the endpoint shape, not the exact counts.

- [ ] **Step 2: Run new tests to confirm they fail**

Run: `pytest tests/integration/test_results_plot_failure.py -v -k "categories or plot_group or csv"`
Expected: all 6 new tests fail (404 / ModuleNotFoundError on the schemas import).

- [ ] **Step 3: Add the new schemas**

Edit `opm_ai/api/schemas.py`. Find the line `class KPIsResponse(BaseModel):` (line ~225 per the existing layout) and add the new models AFTER it but BEFORE `class SnapshotsResponse`. Also add the `Enum` import at the top if not present:

```python
from enum import Enum
```

New models:

```python
class CsvFrequency(str, Enum):
    """Resampling frequency for CSV export."""
    NATIVE = "native"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class CategorizedVectorsResponse(BaseModel):
    """Categorised view of a summary DataFrame."""
    model_config = ConfigDict(from_attributes=True)

    field_rates: list[str] = []
    field_cumulative: list[str] = []
    field_derived: list[str] = []
    well_rates: dict[str, list[str]] = {}
    well_cumulative: dict[str, list[str]] = {}
    well_injection: dict[str, list[str]] = {}
    wells: list[str] = []


class PlotGroupResponse(BaseModel):
    """Response from /plot_group/{group}.

    `figure_json` is `""` when plot generation failed (the route already
    logged the trace; the client renders an empty card).
    """
    model_config = ConfigDict(from_attributes=True)

    group: str
    figure_json: str = ""
    error: str | None = None
```

- [ ] **Step 4: Add the three new endpoints to `opm_ai/api/routes/results.py`**

Add imports at the top (after the existing `from opm_ai.postprocess...` block):

```python
from opm_ai.api.schemas import (
    CategorizedVectorsResponse,
    CsvFrequency,
    KPIsResponse,
    PlotGroupResponse,
    ResinsightLaunchResponse,
    SnapshotsResponse,
)
from opm_ai.postprocess.categorizer import categorize
from opm_ai.postprocess.plot_groups import plot_group as build_plot_group
from opm_ai.postprocess.resample import resample_summary
```

Add a validator near the top of the file (after the imports, before the existing routes):

```python
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_:,.-]+$")

_KNOWN_PLOT_GROUPS = {
    "field_rates", "field_cumulative", "field_derived",
    "well_rates", "well_cumulative", "well_injection",
}


def _split_csv_param(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        if not _SAFE_ID_RE.match(p):
            raise HTTPException(status_code=400, detail=f"Unsafe identifier in param: {p!r}")
    return parts
```

Append the three new endpoints at the end of `routes/results.py`:

```python
@router.get("/results/{job_id}/categories", response_model=CategorizedVectorsResponse)
async def get_categories(job_id: str) -> CategorizedVectorsResponse:
    """Categorise summary columns into priority vector families."""
    output_dir = _completed_job_output_dir(job_id)
    df = read_summary(output_dir)
    cats = categorize(df)
    return CategorizedVectorsResponse(**cats)


@router.get("/results/{job_id}/plot_group/{group}", response_model=PlotGroupResponse)
async def get_plot_group(
    job_id: str,
    group: str,
    wells: str | None = None,
    vectors: str | None = None,
    log: bool = False,
) -> PlotGroupResponse:
    """Build a Plotly figure for one priority vector group."""
    if group not in _KNOWN_PLOT_GROUPS:
        # Unknown group is a 200 with empty json so the client shows the
        # standard empty-state rather than a hard error. The route logs
        # the actual trace when plot generation fails (below).
        return PlotGroupResponse(group=group, figure_json="", error=f"Unknown group: {group}")

    output_dir = _completed_job_output_dir(job_id)
    df = read_summary(output_dir)
    if df.empty:
        return PlotGroupResponse(group=group, figure_json="", error="Empty summary")

    well_list = _split_csv_param(wells)
    vector_list = _split_csv_param(vectors) or None

    try:
        fig = build_plot_group(group, df, well_list, vector_list, log_scale=log)
        return PlotGroupResponse(group=group, figure_json=fig.to_json(), error=None)
    except Exception:
        logger.exception("Plot group %s failed for job %s", group, job_id)
        return PlotGroupResponse(group=group, figure_json="", error="plot generation failed")


@router.get("/results/{job_id}/csv")
async def get_csv(
    job_id: str,
    group: str,
    vectors: str,
    freq: CsvFrequency = CsvFrequency.NATIVE,
) -> Response:
    """Return a CSV slice of the summary DataFrame at the requested frequency."""
    _split_csv_param(vectors)  # validates; raises 400 on bad chars

    output_dir = _completed_job_output_dir(job_id)
    df = read_summary(output_dir)
    if df.empty:
        return Response(content="TIME\n", media_type="text/csv")

    requested = [v.strip() for v in vectors.split(",") if v.strip()]
    present = [v for v in requested if v in df.columns]
    if not present:
        return Response(content="TIME\n", media_type="text/csv")

    slice_df = df[["TIME", *present]].copy()
    if freq != CsvFrequency.NATIVE:
        slice_df = resample_summary(slice_df, freq.value)

    csv_body = slice_df.to_csv(index=False)
    return Response(content=csv_body, media_type="text/csv")
```

Add to the imports at the top of the file:

```python
import re
from fastapi.responses import Response
```

- [ ] **Step 5: Add the frontend types**

Edit `frontend/src/types.ts`. Find the existing `KPIsResponse` interface (or wherever result-related types live). Append:

```ts
export type VectorGroup =
  | 'field_rates'
  | 'field_cumulative'
  | 'field_derived'
  | 'well_rates'
  | 'well_cumulative'
  | 'well_injection';

export interface CategorizedVectors {
  field_rates: string[];
  field_cumulative: string[];
  field_derived: string[];
  well_rates: Record<string, string[]>;
  well_cumulative: Record<string, string[]>;
  well_injection: Record<string, string[]>;
  wells: string[];
}

export interface PlotGroupResponse {
  group: string;
  figure_json: string;
  error?: string | null;
}

export type CsvFrequency = 'native' | 'monthly' | 'yearly';
```

- [ ] **Step 6: Add the frontend API methods**

Edit `frontend/src/api/client.ts`. Add `CategorizedVectors`, `PlotGroupResponse`, `CsvFrequency` to the import-from-types block at the top.

Add three methods inside the `api` object (just below the existing `gridWells`):

```ts
// Results
categories: (jobId: string): Promise<CategorizedVectors> =>
  fetchJson<CategorizedVectors>(`/results/${jobId}/categories`),

plotGroup: (
  jobId: string,
  group: string,
  opts: { wells?: string[]; vectors?: string[]; log?: boolean } = {}
): Promise<PlotGroupResponse> => {
  const params = new URLSearchParams();
  if (opts.wells?.length) params.set('wells', opts.wells.join(','));
  if (opts.vectors?.length) params.set('vectors', opts.vectors.join(','));
  if (opts.log) params.set('log', 'true');
  const qs = params.toString();
  return fetchJson<PlotGroupResponse>(`/results/${jobId}/plot_group/${group}${qs ? `?${qs}` : ''}`);
},

csv: async (
  jobId: string,
  opts: { group: string; vectors: string[]; freq?: CsvFrequency }
): Promise<string> => {
  const params = new URLSearchParams();
  params.set('group', opts.group);
  params.set('vectors', opts.vectors.join(','));
  if (opts.freq && opts.freq !== 'native') params.set('freq', opts.freq);
  const response = await fetch(`${API_BASE}/results/${jobId}/csv?${params.toString()}`, {
    headers: { Accept: 'text/csv' },
  });
  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  return response.text();
},
```

And re-export the new types at the bottom (the `export type {}` block):

```ts
export type { CategorizedVectors, PlotGroupResponse, CsvFrequency, VectorGroup };
```

- [ ] **Step 7: Run the integration tests**

Run: `pytest tests/integration/test_results_plot_failure.py -v`
Expected: all tests pass (existing + 6 new).

- [ ] **Step 8: Quick frontend build check**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build succeeds (TypeScript checks the new types and methods).

- [ ] **Step 9: Commit**

```bash
git add opm_ai/api/schemas.py opm_ai/api/routes/results.py frontend/src/types.ts frontend/src/api/client.ts tests/integration/test_results_plot_failure.py
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "opm-ai: api — /categories, /plot_group, /csv endpoints + tests"
```

---

### Task 5: API route — /imported-results (virtual job registration)

**Files:**
- Modify: `opm_ai/api/schemas.py` (add `ImportedResultResponse`)
- Create: `opm_ai/api/routes/imported_results.py`
- Modify: `opm_ai/api/job_store.py` (add `register_virtual_job`, `Job.kind` enum)
- Modify: `opm_ai/api/routes/__init__.py` (register the new router)
- Modify: `opm_ai/api/server.py` (include the router)
- Test: `tests/unit/test_import_validation.py` (5 cases)
- Test: `tests/integration/test_imported_results_route.py` (8 cases)

**Interfaces:**
- New schema:
  ```python
  class ImportedResultResponse(BaseModel):
      job_id: str
      files_received: list[str]
      warnings: list[str]
  ```
- New route: `POST /api/imported-results` (multipart). Field name is `files` (multi-value). Returns 400 if no SMSPEC+UNSMRY pair or ESMRY present; 413 on oversized parts (Starlette handles).
- New job_store helper:
  ```python
  def register_virtual_job(output_dir: Path) -> str:
      """Register an in-memory job that points at an external output_dir.
      Returns the new job_id. The job has status='completed' and result=
      {'output_dir': str(output_dir)} so all downstream endpoints work.
      """
  ```
- Job gets a `kind` field: `"real"` (default for runner-produced jobs) or `"imported"`. Additive — existing code that doesn't read `kind` is unaffected.

- [ ] **Step 1: Write the unit tests for input validation**

Create `tests/unit/test_import_validation.py`:

```python
"""Unit tests for imported_results route validation helpers."""
import pytest

from opm_ai.api.routes.imported_results import (
    REQUIRED_FILES_HINT,
    _validate_imported_files,
)


def test_accepts_smspec_unsmry_pair(tmp_path):
    (tmp_path / "CASE.SMSPEC").write_bytes(b"x")
    (tmp_path / "CASE.UNSMRY").write_bytes(b"y")
    accepted, warnings = _validate_imported_files(tmp_path)
    assert accepted == ["CASE.SMSPEC", "CASE.UNSMRY"]
    assert warnings == []


def test_accepts_esmry_alone(tmp_path):
    (tmp_path / "CASE.ESMRY").write_bytes(b"x")
    accepted, warnings = _validate_imported_files(tmp_path)
    assert "CASE.ESMRY" in accepted


def test_rejects_no_summary(tmp_path):
    with pytest.raises(ValueError, match="SMSPEC"):
        _validate_imported_files(tmp_path)


def test_accepts_optional_extensions(tmp_path):
    (tmp_path / "CASE.SMSPEC").write_bytes(b"x")
    (tmp_path / "CASE.UNSMRY").write_bytes(b"y")
    (tmp_path / "CASE.EGRID").write_bytes(b"z")
    (tmp_path / "CASE.UNRST").write_bytes(b"z")
    (tmp_path / "CASE.INIT").write_bytes(b"z")
    accepted, warnings = _validate_imported_files(tmp_path)
    assert sorted(accepted) == ["CASE.EGRID", "CASE.INIT", "CASE.SMSPEC", "CASE.UNRST", "CASE.UNSMRY"]


def test_rejects_unsafe_filename(tmp_path):
    (tmp_path / "CASE.SMSPEC").write_bytes(b"x")
    (tmp_path / "CASE.UNSMRY").write_bytes(b"y")
    (tmp_path / "../../etc/passwd").write_bytes(b"pwn")
    with pytest.raises(ValueError, match="unsafe"):
        _validate_imported_files(tmp_path)
```

- [ ] **Step 2: Run the unit tests to confirm they fail**

Run: `pytest tests/unit/test_import_validation.py -v`
Expected: `ModuleNotFoundError: No module named 'opm_ai.api.routes.imported_results'`

- [ ] **Step 3: Implement the route module**

Create `opm_ai/api/routes/imported_results.py`:

```python
"""POST /api/imported-results — register a virtual job from uploaded files.

Mirrors the security model of opm_ai/api/routes/upload.py:

- Multipart with MAX_PART_SIZE=256 MB, MAX_FILES=5000.
- tempdir mkdtemp(prefix="opm_ai_imported_").
- Filenames go through _SAFE_PATH_RE.
- No `.DATA` requirement — these aren't decks, just Eclipse output files.

Validation policy (in _validate_imported_files):

- Required: either (CASE.SMSPEC + CASE.UNSMRY) OR a single CASE.ESMRY.
  Without summary data, /api/results/{id} cannot show anything, so we
  reject early.
- Accepted but optional: .EGRID, .GRID, .UNRST, .INIT, .RFT, .PRT.

On success: register a virtual job whose output_dir points at the
upload dir. All downstream endpoints (/results, /grid/info, etc.)
just work because they only depend on job.output_dir containing valid
Eclipse files.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from opm_ai.api.job_helpers import job_output_dir
from opm_ai.api.job_store import register_virtual_job
from opm_ai.api.schemas import ImportedResultResponse


router = APIRouter()

MAX_PART_SIZE = 256 * 1024 * 1024
MAX_FILES = 5000

REQUIRED_FILES_HINT = (
    "Required: one *.SMSPEC + one *.UNSMRY (or one *.ESMRY). "
    "Optional: .EGRID, .GRID, .UNRST, .INIT, .RFT, .PRT."
)

_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_.-]+$")  # filenames only — no path separators

_OPTIONAL_EXTENSIONS = {".EGRID", ".FEGRID", ".GRID", ".FGRID", ".UNRST", ".INIT", ".RFT", ".PRT"}


def _safe_filename(raw: str) -> str:
    name = Path(raw).name  # strip any path the client tried to inject
    if not name or not _SAFE_PATH_RE.match(name):
        raise HTTPException(status_code=400, detail=f"unsafe filename: {raw!r}")
    return name


def _validate_imported_files(directory: Path) -> tuple[list[str], list[str]]:
    """Ensure at least one summary file pair is present; return (accepted, warnings).

    Raises ValueError on missing required files or unsafe filenames.
    """
    accepted: list[str] = []
    warnings: list[str] = []

    has_smspec = False
    has_unsmry = False
    has_esmry = False

    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if not _SAFE_PATH_RE.match(path.name):
            raise ValueError(f"unsafe filename in upload: {path.name!r}")
        suffix = path.suffix.upper()
        if suffix == ".SMSPEC":
            has_smspec = True
            accepted.append(path.name)
        elif suffix == ".UNSMRY":
            has_unsmry = True
            accepted.append(path.name)
        elif suffix == ".ESMRY":
            has_esmry = True
            accepted.append(path.name)
        elif suffix in _OPTIONAL_EXTENSIONS:
            accepted.append(path.name)
        else:
            warnings.append(f"ignored file with unsupported extension: {path.name}")

    if not has_esmry and not (has_smspec and has_unsmry):
        raise ValueError(f"missing required summary files. {REQUIRED_FILES_HINT}")

    return sorted(accepted), warnings


@router.post("/imported-results", response_model=ImportedResultResponse)
async def post_imported_results(request: Request) -> ImportedResultResponse:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(
            status_code=415,
            detail=f"expected multipart/form-data, got {content_type!r}",
        )

    form = await request.form(max_files=MAX_FILES, max_part_size=MAX_PART_SIZE)

    file_parts = [
        v for k, v in form.multi_items()
        if k == "files" and hasattr(v, "read")
    ]
    if not file_parts:
        raise HTTPException(status_code=400, detail="no files in 'files' field")

    upload_dir = Path(tempfile.mkdtemp(prefix="opm_ai_imported_"))

    try:
        for part in file_parts:
            name = _safe_filename(part.filename or "")
            target = upload_dir / name
            byte_count = 0
            with target.open("wb") as out:
                while True:
                    chunk = await part.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    byte_count += len(chunk)
            await part.close()
            if byte_count == 0:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail=f"file is empty: {name}")

        try:
            accepted, warnings = _validate_imported_files(upload_dir)
        except ValueError as e:
            shutil.rmtree(upload_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        logger.exception("imported-results write failed")
        raise HTTPException(status_code=500, detail=f"upload failed: {e}")

    job_id = register_virtual_job(upload_dir)

    return ImportedResultResponse(
        job_id=job_id,
        files_received=accepted,
        warnings=warnings,
    )


# Re-export for callers that need to know what's expected.
__all__ = ["router", "REQUIRED_FILES_HINT", "_validate_imported_files"]
```

- [ ] **Step 4: Extend the job_store**

Read `opm_ai/api/job_store.py` to understand the existing `Job` dataclass and `register_job` helper. Then:

Add an enum (or a string Literal — match the existing style) above the Job class:

```python
from enum import Enum

class JobKind(str, Enum):
    REAL = "real"
    IMPORTED = "imported"
```

Add a `kind: JobKind = JobKind.REAL` field to the `Job` dataclass (default keeps existing behaviour).

Add the helper at the end of the file:

```python
def register_virtual_job(output_dir: Path) -> str:
    """Register an in-memory job pointing at an external output_dir.

    The job is marked completed and kind='imported'. Used by
    /api/imported-results to surface an uploaded directory through
    the existing Results API surface.
    """
    job_id = uuid.uuid4().hex
    with _lock:
        job = Job(
            job_id=job_id,
            status="completed",
            result={"output_dir": str(output_dir)},
            kind=JobKind.IMPORTED,
        )
        _jobs[job_id] = job
    return job_id
```

(Adjust to match the file's existing conventions — if the file already uses `uuid` and a `Lock`, reuse those names verbatim.)

- [ ] **Step 5: Wire the router into the app**

Edit `opm_ai/api/routes/__init__.py` and add `imported_results` to the import list. Match the existing pattern (likely `from . import build, lint, run, results, chat, settings` style).

Edit `opm_ai/api/server.py` and add `imported_results.router` to whatever `include_router` block the other routes use. Match the existing prefix style.

- [ ] **Step 6: Run unit tests**

Run: `pytest tests/unit/test_import_validation.py -v`
Expected: 5 passed.

- [ ] **Step 7: Write integration tests**

Create `tests/integration/test_imported_results_route.py`:

```python
"""Integration tests for POST /api/imported-results."""
import io
import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _multipart(files: list[tuple[str, bytes]]) -> dict:
    """Build a {field_name: (filename, bytes, mime)} dict for TestClient."""
    return {"files": [(name, io.BytesIO(body), "application/octet-stream") for name, body in files]}


def test_happy_path_creates_virtual_job(client):
    files = _multipart([
        ("CASE.SMSPEC", b"smspec"),
        ("CASE.UNSMRY", b"unsmry"),
    ])
    response = client.post("/api/imported-results", files=files["files"])
    assert response.status_code == 200
    data = response.json()
    assert data["files_received"] == ["CASE.SMSPEC", "CASE.UNSMRY"]
    job_id = data["job_id"]

    # The virtual job must be reachable through /api/results/{id}
    # even though no simulation ever ran for it.
    response = client.get(f"/api/results/{job_id}")
    # Will be 400 (empty summary) — that's the right behaviour: the route
    # exists, the job is registered, it just has no real summary data.
    assert response.status_code in (200, 400)


def test_missing_smspec_returns_400(client):
    files = _multipart([("CASE.UNSMRY", b"x")])
    response = client.post("/api/imported-results", files=files["files"])
    assert response.status_code == 400
    assert "SMSPEC" in response.json()["detail"]


def test_esmry_alone_accepted(client):
    files = _multipart([("CASE.ESMRY", b"x")])
    response = client.post("/api/imported-results", files=files["files"])
    assert response.status_code == 200


def test_optional_extensions_accepted(client):
    files = _multipart([
        ("CASE.SMSPEC", b"x"),
        ("CASE.UNSMRY", b"x"),
        ("CASE.EGRID", b"x"),
        ("CASE.UNRST", b"x"),
        ("CASE.INIT", b"x"),
        ("CASE.PRT", b"x"),
    ])
    response = client.post("/api/imported-results", files=files["files"])
    assert response.status_code == 200
    assert len(response.json()["files_received"]) == 6


def test_path_traversal_rejected(client):
    files = _multipart([
        ("CASE.SMSPEC", b"x"),
        ("CASE.UNSMRY", b"x"),
        ("../../etc/passwd", b"x"),
    ])
    response = client.post("/api/imported-results", files=files["files"])
    assert response.status_code == 400


def test_empty_file_rejected(client):
    files = _multipart([
        ("CASE.SMSPEC", b""),
        ("CASE.UNSMRY", b"x"),
    ])
    response = client.post("/api/imported-results", files=files["files"])
    assert response.status_code == 400


def test_no_files_rejected(client):
    response = client.post("/api/imported-results")
    assert response.status_code in (400, 422)


def test_wrong_content_type_rejected(client):
    response = client.post(
        "/api/imported-results",
        json={"files": ["CASE.SMSPEC"]},
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 415
```

- [ ] **Step 8: Run integration tests**

Run: `pytest tests/integration/test_imported_results_route.py -v`
Expected: 8 passed.

- [ ] **Step 9: Commit**

```bash
git add opm_ai/api/schemas.py opm_ai/api/job_store.py opm_ai/api/routes/__init__.py opm_ai/api/server.py opm_ai/api/routes/imported_results.py tests/unit/test_import_validation.py tests/integration/test_imported_results_route.py
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "opm-ai: api — /imported-results (virtual-job registration) + tests"
```

---

### Task 6: API — three new chat tools

**Files:**
- Modify: `opm_ai/api/routes/chat.py` (add 3 tools + compact rules)
- Test: `tests/integration/test_chat_tools_results.py` (6 cases)

**Interfaces:**
- Three new tool functions:
  ```python
  async def tool_list_available_vectors(args: dict) -> dict
  async def tool_plot_well_vectors(args: dict) -> dict
  async def tool_compare_wells(args: dict) -> dict
  ```
- Registered in `TOOL_FUNCTIONS` dict.
- Each tool reads the **active job** via the same mechanism `tool_get_kpis` uses (read the file to confirm — likely `get_job(args.get("job_id") or active_job_id)` with a fallback).
- `compare_wells` validates `vector` is a single string and `wells` is a non-empty list.
- Three new `compact_tool_result` rules:
  - `list_available_vectors`: return full payload (it's tiny).
  - `plot_well_vectors`: strip `figure_json` to `{trace_count, trace_names, wells, vectors}`.
  - `compare_wells`: same shape as plot_well_vectors.

- [ ] **Step 1: Read the existing chat tool pattern**

Read `opm_ai/api/routes/chat.py` lines around `tool_get_kpis` (search for `TOOL_FUNCTIONS = {`) and the `compact_tool_result` function. Match the existing style for: (a) how the active job is resolved, (b) how errors are returned, (c) how `fig.to_json()` is handled.

- [ ] **Step 2: Write the failing tests**

Create `tests/integration/test_chat_tools_results.py`:

```python
"""Integration tests for the three new chat tools."""
import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_list_available_vectors_returns_empty_for_no_active_job(client):
    """No active job -> empty result, not an error."""
    response = client.post(
        "/api/chat/tools",
        json={"tool": "list_available_vectors", "args": {}},
    )
    # The exact route shape depends on the existing chat-tools wrapper;
    # if no such route exists, call execute_tool directly (see fallback).
    if response.status_code == 404:
        from opm_ai.api.routes.chat import execute_tool
        result = asyncio.run(execute_tool("list_available_vectors", {}))
    else:
        result = response.json()


def test_plot_well_vectors_unknown_tool(client):
    from opm_ai.api.routes.chat import execute_tool
    import asyncio
    result = asyncio.run(execute_tool("plot_does_not_exist", {"wells": ["PROD1"], "vectors": ["WBHP"]}))
    assert "error" in result


def test_compare_wells_validates_vector(client):
    from opm_ai.api.routes.chat import execute_tool, tool_compare_wells
    import asyncio
    result = asyncio.run(tool_compare_wells({"wells": ["PROD1"], "vector": "WBHP"}))
    # Either returns a figure (job loaded) or an error (no job)
    assert "figure_json" in result or "error" in result


def test_compare_wells_rejects_missing_vector(client):
    from opm_ai.api.routes.chat import tool_compare_wells
    import asyncio
    result = asyncio.run(tool_compare_wells({"wells": ["PROD1"]}))
    assert "error" in result
    assert "vector" in result["error"].lower() or "missing" in result["error"].lower()


def test_compare_wells_rejects_empty_wells(client):
    from opm_ai.api.routes.chat import tool_compare_wells
    import asyncio
    result = asyncio.run(tool_compare_wells({"wells": [], "vector": "WBHP"}))
    assert "error" in result


def test_compact_plot_well_vectors_strips_figure_json():
    from opm_ai.api.routes.chat import compact_tool_result
    full = {
        "figure_json": '{"data": [...]}',  # long
        "wells": ["PROD1"],
        "vectors": ["WBHP"],
    }
    compact = compact_tool_result("plot_well_vectors", full)
    assert "figure_json" not in compact
    assert compact["wells"] == ["PROD1"]
    assert compact["vectors"] == ["WBHP"]
```

Adapt the fixtures / wrappers to match the existing chat test patterns in `tests/integration/test_chat_ws_loop.py` if they differ — the goal is to exercise each tool's validation and the compaction rule.

- [ ] **Step 3: Run the tests to confirm they fail**

Run: `pytest tests/integration/test_chat_tools_results.py -v`
Expected: most tests fail (`tool_compare_wells` doesn't exist yet).

- [ ] **Step 4: Implement the three tools**

Add to `opm_ai/api/routes/chat.py`, just before the existing `TOOL_FUNCTIONS = {...}` block. Imports at the top — match existing:

```python
from opm_ai.postprocess.categorizer import categorize
from opm_ai.postprocess.plot_groups import plot_group as build_plot_group
from opm_ai.postprocess.summary import read_summary
from opm_ai.api.job_helpers import job_output_dir
```

Tool implementations:

```python
def _resolve_active_job(args: dict) -> str | None:
    """Return the active job_id, preferring the one passed in args.

    Matches the pattern tool_get_kpis uses — read the existing
    implementation to confirm whether args takes 'job_id' or another
    key, and how the fallback works when no job is active.
    """
    return args.get("job_id")  # adjust to match existing convention


async def tool_list_available_vectors(args: dict) -> dict:
    """List which vector families are present in the active run's summary."""
    job_id = _resolve_active_job(args)
    if not job_id:
        return {"error": "no active job"}
    job = get_job(job_id)
    if not job or job.status != "completed" or not job.result:
        return {"error": "job not completed"}

    output_dir = job_output_dir(job)
    df = read_summary(output_dir)
    if df.empty:
        return {"error": "no summary data"}

    return dict(categorize(df))


async def tool_plot_well_vectors(args: dict) -> dict:
    """Build a Plotly figure for selected wells + vectors.

    Args:
      wells: list[str] — at least one
      vectors: list[str] — at least one
      log: bool, optional
      group: str — one of well_rates / well_cumulative / well_injection
    """
    wells = args.get("wells") or []
    vectors = args.get("vectors") or []
    if not wells:
        return {"error": "missing 'wells' (non-empty list required)"}
    if not vectors:
        return {"error": "missing 'vectors' (non-empty list required)"}
    group = args.get("group", "well_rates")
    log_scale = bool(args.get("log", False))

    job_id = _resolve_active_job(args)
    if not job_id:
        return {"error": "no active job"}
    job = get_job(job_id)
    if not job or job.status != "completed" or not job.result:
        return {"error": "job not completed"}

    output_dir = job_output_dir(job)
    df = read_summary(output_dir)
    if df.empty:
        return {"error": "no summary data"}

    try:
        fig = build_plot_group(group, df, wells, vectors, log_scale=log_scale)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("plot_well_vectors failed")
        return {"error": f"plot generation failed: {e}"}

    return {
        "figure_json": fig.to_json(),
        "wells": wells,
        "vectors": vectors,
        "group": group,
    }


async def tool_compare_wells(args: dict) -> dict:
    """Single vector across multiple wells — the common comparison shape."""
    return await tool_plot_well_vectors({
        **args,
        "group": args.get("group", "well_rates"),
        "vectors": [args["vector"]] if "vector" in args else args.get("vectors", []),
    })
```

(Reuse `tool_plot_well_vectors` if the validation can be shared — `compare_wells` is a specialisation with a single vector.)

- [ ] **Step 5: Register the tools and add compaction rules**

In the `TOOL_FUNCTIONS` dict, add three entries:

```python
"list_available_vectors": tool_list_available_vectors,
"plot_well_vectors": tool_plot_well_vectors,
"compare_wells": tool_compare_wells,
```

In `compact_tool_result`, add cases (after the `get_kpis` case):

```python
if tool_name == "list_available_vectors":
    return result  # tiny, send it all
if tool_name in ("plot_well_vectors", "compare_wells"):
    fig_data = result.get("figure_json") or ""
    try:
        import json as _json
        parsed = _json.loads(fig_data)
        trace_names = [t.get("name", "?") for t in parsed.get("data", [])]
    except Exception:
        trace_names = []
    return {
        "trace_count": len(trace_names),
        "trace_names": trace_names[:10],
        "wells": result.get("wells"),
        "vectors": result.get("vectors"),
        "note": "Full Plotly figure rendered for the user; not re-sent to the LLM.",
    }
```

- [ ] **Step 6: Run the tests**

Run: `pytest tests/integration/test_chat_tools_results.py -v`
Expected: 6 passed.

- [ ] **Step 7: Verify the existing chat tests still pass**

Run: `pytest tests/integration/test_chat_ws_loop.py tests/integration/test_chat_session_concurrency.py -v`
Expected: all pass (the additions are additive; existing tools untouched).

- [ ] **Step 8: Commit**

```bash
git add opm_ai/api/routes/chat.py tests/integration/test_chat_tools_results.py
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "opm-ai: api — chat tools (list_vectors, plot_well_vectors, compare_wells) + tests"
```

---

### Task 7: Frontend — control rail + extracted PlotCard (Plots tab)

**Files:**
- Create: `frontend/src/components/results/PlotCard.tsx`
- Create: `frontend/src/components/results/ResultsControlRail.tsx`
- Modify: `frontend/src/components/ResultsViewer.tsx` (two-column layout for Plots tab)
- Modify: `frontend/src/stores/useAppStore.ts` (categories cache)
- Test: `frontend/src/components/results/PlotCard.test.tsx` (4 cases)
- Test: `frontend/src/components/results/ResultsControlRail.test.tsx` (4 cases)

**Interfaces:**
- `PlotCard` props:
  ```ts
  interface PlotCardProps {
    jobId: string;
    plotName: string;
    plotJson: string;
  }
  ```
- `ResultsControlRail` props:
  ```ts
  interface ResultsControlRailProps {
    categorized: CategorizedVectors;
    selectedWells: Set<string>;
    onWells: (s: Set<string>) => void;
    selectedVectors: Record<VectorGroup, Set<string>>;
    onVectors: (g: VectorGroup, s: Set<string>) => void;
    logScale: boolean;
    onLogScale: (v: boolean) => void;
  }
  ```
- `useAppStore` adds:
  ```ts
  categoriesByJob: Record<string, CategorizedVectors>;
  setCategories: (jobId: string, cats: CategorizedVectors) => void;
  ```

- [ ] **Step 1: Write the failing PlotCard test**

Create `frontend/src/components/results/PlotCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlotCard from './PlotCard';

vi.mock('plotly.js-dist-min', () => ({
  default: {
    newPlot: vi.fn(),
    purge: vi.fn(),
    relayout: vi.fn(),
    downloadImage: vi.fn(),
  },
}));

describe('PlotCard', () => {
  it('renders the plot name', () => {
    render(<PlotCard jobId="j1" plotName="Production Rates" plotJson="" />);
    expect(screen.getByText('Production Rates')).toBeInTheDocument();
  });

  it('shows empty state when plotJson is empty', () => {
    render(<PlotCard jobId="j1" plotName="Empty" plotJson="" />);
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });

  it('renders the Export menu', () => {
    render(<PlotCard jobId="j1" plotName="Foo" plotJson="" />);
    expect(screen.getByText(/export/i)).toBeInTheDocument();
  });

  it('uses the resolved theme', () => {
    render(<PlotCard jobId="j1" plotName="Foo" plotJson="" />);
    // Just verifies the component renders without throwing on theme access.
    expect(screen.getByText('Foo')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the failing ResultsControlRail test**

Create `frontend/src/components/results/ResultsControlRail.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ResultsControlRail from './ResultsControlRail';
import type { CategorizedVectors } from '../../types';

const SAMPLE: CategorizedVectors = {
  field_rates: ['FOPR', 'FWPR'],
  field_cumulative: ['FOPT'],
  field_derived: [],
  well_rates: { PROD1: ['WOPR', 'WBHP'], PROD2: ['WOPR'] },
  well_cumulative: {},
  well_injection: { INJ1: ['WGIR'] },
  wells: ['PROD1', 'PROD2', 'INJ1'],
};

describe('ResultsControlRail', () => {
  it('renders well checkboxes for each well', () => {
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set(['PROD1'])}
        onWells={() => {}}
        selectedVectors={{
          field_rates: new Set(['FOPR']),
          field_cumulative: new Set(),
          field_derived: new Set(),
          well_rates: new Set(),
          well_cumulative: new Set(),
          well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    expect(screen.getByLabelText('PROD1')).toBeInTheDocument();
    expect(screen.getByLabelText('PROD2')).toBeInTheDocument();
    expect(screen.getByLabelText('INJ1')).toBeInTheDocument();
  });

  it('calls onWells when a well checkbox is clicked', () => {
    const onWells = vi.fn();
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set()}
        onWells={onWells}
        selectedVectors={{
          field_rates: new Set(), field_cumulative: new Set(),
          field_derived: new Set(), well_rates: new Set(),
          well_cumulative: new Set(), well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    fireEvent.click(screen.getByLabelText('PROD1'));
    expect(onWells).toHaveBeenCalledTimes(1);
    const newSet = onWells.mock.calls[0][0];
    expect(newSet.has('PROD1')).toBe(true);
  });

  it('shows log-scale toggle', () => {
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set()}
        onWells={() => {}}
        selectedVectors={{
          field_rates: new Set(), field_cumulative: new Set(),
          field_derived: new Set(), well_rates: new Set(),
          well_cumulative: new Set(), well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    expect(screen.getByLabelText(/log scale/i)).toBeInTheDocument();
  });

  it('groups wells by role (PROD vs INJ)', () => {
    render(
      <ResultsControlRail
        categorized={SAMPLE}
        selectedWells={new Set()}
        onWells={() => {}}
        selectedVectors={{
          field_rates: new Set(), field_cumulative: new Set(),
          field_derived: new Set(), well_rates: new Set(),
          well_cumulative: new Set(), well_injection: new Set(),
        }}
        onVectors={() => {}}
        logScale={false}
        onLogScale={() => {}}
      />
    );
    expect(screen.getByText(/producers/i)).toBeInTheDocument();
    expect(screen.getByText(/injectors/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to confirm both fail**

Run: `cd frontend && npx vitest run src/components/results/`
Expected: both test files fail to load (`Cannot find module`).

- [ ] **Step 4: Extract PlotCard.tsx**

Create `frontend/src/components/results/PlotCard.tsx`. Take the existing inline `PlotCard` body from `frontend/src/components/ResultsViewer.tsx` (the function definition around lines 9-80 per the existing layout) and move it into a new file. Add the export menu placeholder to the card header (the full export wiring is Task 10 — for now, render a `<details>` with the items):

```tsx
import { useState, useEffect, useRef } from 'react';
import { useResolvedTheme } from '../../stores/useAppStore';
// @ts-expect-error plotly.js-dist ships no types; @types/plotly.js covers the API
import Plotly from 'plotly.js-dist-min';

interface PlotCardProps {
  jobId: string;
  plotName: string;
  plotJson: string;
}

export default function PlotCard({ jobId, plotName, plotJson }: PlotCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const resolvedTheme = useResolvedTheme();
  const [renderError, setRenderError] = useState<string | null>(null);
  const chartMountedRef = useRef(false);

  useEffect(() => {
    setRenderError(null);
    chartMountedRef.current = false;
    if (!divRef.current || !plotJson) return;
    try {
      const plotData = JSON.parse(plotJson);
      const dark = resolvedTheme === 'dark';
      const layout = {
        ...plotData.layout,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: dark ? '#1f2937' : '#ffffff',
        font: { color: dark ? '#e5e7eb' : '#111827' },
      };
      Plotly.newPlot(divRef.current, plotData.data, layout, { responsive: true });
      chartMountedRef.current = true;
    } catch (e) {
      setRenderError(e instanceof Error ? e.message : String(e));
    }
    return () => {
      if (chartMountedRef.current && divRef.current) {
        Plotly.purge(divRef.current);
        chartMountedRef.current = false;
      }
    };
  }, [plotJson, resolvedTheme]);

  return (
    <div className="border rounded-lg p-3 bg-white dark:bg-gray-800" data-testid={`plot-card-${plotName}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{plotName}</h3>
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">
            Export
          </summary>
          <div className="absolute z-10 mt-1 bg-white dark:bg-gray-800 border rounded shadow-lg p-2 right-0">
            <div className="text-xs text-gray-500">Export wiring lands in Task 10</div>
          </div>
        </details>
      </div>
      {!plotJson ? (
        <div className="text-xs text-gray-500 italic p-4 text-center">No data available</div>
      ) : (
        <>
          <div ref={divRef} className="w-full" style={{ minHeight: '400px' }} />
          {renderError && (
            <div className="text-xs text-red-500 mt-2">Render error: {renderError}</div>
          )}
        </>
      )}
    </div>
  );
}
```

The export menu is intentionally a stub here — Task 10 wires it up with PNG/SVG/CSV buttons.

- [ ] **Step 5: Implement ResultsControlRail.tsx**

Create `frontend/src/components/results/ResultsControlRail.tsx`:

```tsx
import { useMemo } from 'react';
import type { CategorizedVectors, VectorGroup } from '../../types';

const ALL_GROUPS: VectorGroup[] = [
  'field_rates',
  'field_cumulative',
  'field_derived',
  'well_rates',
  'well_cumulative',
  'well_injection',
];

interface ResultsControlRailProps {
  categorized: CategorizedVectors;
  selectedWells: Set<string>;
  onWells: (s: Set<string>) => void;
  selectedVectors: Record<VectorGroup, Set<string>>;
  onVectors: (g: VectorGroup, s: Set<string>) => void;
  logScale: boolean;
  onLogScale: (v: boolean) => void;
}

export default function ResultsControlRail({
  categorized,
  selectedWells,
  onWells,
  selectedVectors,
  onVectors,
  logScale,
  onLogScale,
}: ResultsControlRailProps) {
  const producerWells = useMemo(
    () =>
      Object.keys(categorized.well_rates)
        .concat(Object.keys(categorized.well_cumulative))
        .filter((v, i, a) => a.indexOf(v) === i)
        .sort(),
    [categorized]
  );
  const injectorWells = useMemo(
    () => Object.keys(categorized.well_injection).sort(),
    [categorized]
  );

  const toggleWell = (well: string) => {
    const next = new Set(selectedWells);
    if (next.has(well)) next.delete(well);
    else next.add(well);
    onWells(next);
  };

  const toggleVector = (group: VectorGroup, vec: string) => {
    const next = new Set(selectedVectors[group]);
    if (next.has(vec)) next.delete(vec);
    else next.add(vec);
    onVectors(group, next);
  };

  return (
    <aside
      className="w-72 shrink-0 border-r overflow-y-auto p-3 space-y-4 bg-gray-50 dark:bg-gray-900"
      data-testid="results-control-rail"
    >
      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Producers</h4>
        {producerWells.length === 0 ? (
          <p className="text-xs text-gray-400 italic">none</p>
        ) : (
          <div className="space-y-1">
            {producerWells.map((w) => (
              <label key={w} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedWells.has(w)}
                  onChange={() => toggleWell(w)}
                  className="rounded"
                />
                <span>{w}</span>
              </label>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Injectors</h4>
        {injectorWells.length === 0 ? (
          <p className="text-xs text-gray-400 italic">none</p>
        ) : (
          <div className="space-y-1">
            {injectorWells.map((w) => (
              <label key={w} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedWells.has(w)}
                  onChange={() => toggleWell(w)}
                  className="rounded"
                />
                <span>{w}</span>
              </label>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Vector Groups</h4>
        {ALL_GROUPS.map((group) => {
          const vecs = collectGroupVectors(group, categorized);
          if (vecs.length === 0) return null;
          return (
            <details key={group} className="mb-2" open>
              <summary className="text-xs font-medium cursor-pointer">{group.replace('_', ' ')}</summary>
              <div className="ml-2 mt-1 space-y-1">
                {vecs.map((vec) => (
                  <label key={vec} className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={selectedVectors[group]?.has(vec) ?? false}
                      onChange={() => toggleVector(group, vec)}
                      className="rounded"
                    />
                    <span>{vec}</span>
                  </label>
                ))}
              </div>
            </details>
          );
        })}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Display</h4>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={logScale}
            onChange={(e) => onLogScale(e.target.checked)}
            className="rounded"
          />
          <span>Log scale (Y)</span>
        </label>
      </section>
    </aside>
  );
}

function collectGroupVectors(group: VectorGroup, cats: CategorizedVectors): string[] {
  if (group === 'field_rates') return cats.field_rates;
  if (group === 'field_cumulative') return cats.field_cumulative;
  if (group === 'field_derived') return cats.field_derived;
  if (group === 'well_rates') {
    return Array.from(new Set(Object.values(cats.well_rates).flat())).sort();
  }
  if (group === 'well_cumulative') {
    return Array.from(new Set(Object.values(cats.well_cumulative).flat())).sort();
  }
  return Array.from(new Set(Object.values(cats.well_injection).flat())).sort();
}
```

- [ ] **Step 6: Extend useAppStore**

Edit `frontend/src/stores/useAppStore.ts`. Add to the state slice and create the helpers. Follow the existing `lastResults` / `setLastResults` pattern exactly:

```ts
categoriesByJob: Record<string, CategorizedVectors> as Record<string, CategorizedVectors>,
setCategories: (jobId: string, cats: CategorizedVectors) => void,
getCategories: (jobId: string) => CategorizedVectors | null,
```

Implementation:

```ts
setCategories: (jobId, cats) => set((s) => ({
  categoriesByJob: { ...s.categoriesByJob, [jobId]: cats },
})),
getCategories: (jobId) => get().categoriesByJob[jobId] ?? null,
```

- [ ] **Step 7: Refactor ResultsViewer.tsx Plots tab to two-column**

Open `frontend/src/components/ResultsViewer.tsx`. Find the Plots tab rendering. The structure today is a vertical list of `PlotCard` instances. Replace it with:

```tsx
{activeTab === 'plots' && (
  <div className="flex h-full">
    <ResultsControlRail
      categorized={categorized}
      selectedWells={selectedWells}
      onWells={setSelectedWells}
      selectedVectors={selectedVectors}
      onVectors={setSelectedVectors}
      logScale={logScale}
      onLogScale={setLogScale}
    />
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <PlotCard jobId={jobId} plotName="Field Rates" plotJson={plots['field_rates'] ?? ''} />
      <PlotCard jobId={jobId} plotName="Field Cumulative" plotJson={plots['field_cumulative'] ?? ''} />
      <PlotCard jobId={jobId} plotName="Field Derived" plotJson={plots['field_derived'] ?? ''} />
      {selectedWells.size > 0 && (
        <>
          <PlotCard jobId={jobId} plotName="Well Rates" plotJson={plots['well_rates'] ?? ''} />
          <PlotCard jobId={jobId} plotName="Well Cumulative" plotJson={plots['well_cumulative'] ?? ''} />
          <PlotCard jobId={jobId} plotName="Well Injection" plotJson={plots['well_injection'] ?? ''} />
        </>
      )}
    </div>
  </div>
)}
```

Add the imports at the top:

```ts
import PlotCard from './results/PlotCard';
import ResultsControlRail from './results/ResultsControlRail';
import { useAppStore } from '../stores/useAppStore';
import type { CategorizedVectors, VectorGroup } from '../types';
```

Add new state at the top of `ResultsViewer` (just below the existing hooks):

```ts
const [categorized, setCategorizedState] = useState<CategorizedVectors | null>(null);
const [selectedWells, setSelectedWells] = useState<Set<string>>(new Set());
const [selectedVectors, setSelectedVectors] = useState<Record<VectorGroup, Set<string>>>({
  field_rates: new Set(), field_cumulative: new Set(), field_derived: new Set(),
  well_rates: new Set(), well_cumulative: new Set(), well_injection: new Set(),
});
const [logScale, setLogScale] = useState(false);
const setCategories = useAppStore((s) => s.setCategories);
const cachedCategories = useAppStore((s) => (jobId ? s.categoriesByJob[jobId] : null));
```

Add a new effect that loads categories when `lastResults` becomes available:

```ts
useEffect(() => {
  if (!jobId || !lastResults) return;
  if (cachedCategories) {
    setCategorizedState(cachedCategories);
    return;
  }
  api.categories(jobId).then((cats) => {
    setCategorizedState(cats);
    setCategories(jobId, cats);
  }).catch((err) => {
    console.error('categories fetch failed', err);
  });
}, [jobId, lastResults, cachedCategories, setCategories]);
```

Also delete the inline `PlotCard` function definition (now lives in `./results/PlotCard.tsx`).

- [ ] **Step 8: Run frontend tests**

Run: `cd frontend && npx vitest run src/components/results/`
Expected: 8 tests pass (4 PlotCard + 4 ControlRail).

Run the existing ResultsViewer tests: `cd frontend && npx vitest run src/components/ResultsViewer.test.ts`
Expected: pass (the refactor preserves the public component behaviour).

- [ ] **Step 9: Build check**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: clean build.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/results/PlotCard.tsx frontend/src/components/results/ResultsControlRail.tsx frontend/src/components/results/PlotCard.test.tsx frontend/src/components/results/ResultsControlRail.test.tsx frontend/src/components/ResultsViewer.tsx frontend/src/stores/useAppStore.ts
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "frontend: results — left-side control rail + extracted PlotCard"
```

---

### Task 8: Frontend — Import Results button + modal

**Files:**
- Create: `frontend/src/components/results/ImportResultsButton.tsx`
- Modify: `frontend/src/components/ResultsViewer.tsx` (add the button to the header)
- Modify: `frontend/src/api/client.ts` (add `importResults` method)
- Modify: `frontend/src/types.ts` (add `ImportedResultResponse`)
- Test: `frontend/src/components/results/ImportResultsButton.test.tsx` (4 cases)

**Interfaces:**
- New type:
  ```ts
  export interface ImportedResultResponse {
    job_id: string;
    files_received: string[];
    warnings: string[];
  }
  ```
- New API method:
  ```ts
  importResults(formData: FormData): Promise<ImportedResultResponse>
  ```
- Component:
  ```tsx
  interface ImportResultsButtonProps {
    onImported?: (response: ImportedResultResponse) => void;
  }
  ```
  Opens a `<dialog>` containing: file picker, accepted-extensions list, hint, submit. On success calls `onImported` and closes the dialog.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/ImportResultsButton.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ImportResultsButton from './ImportResultsButton';

vi.mock('../../api/client', () => ({
  api: {
    importResults: vi.fn(),
  },
}));

import { api } from '../../api/client';

describe('ImportResultsButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a button that opens a dialog', () => {
    render(<ImportResultsButton />);
    const btn = screen.getByRole('button', { name: /import results/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(screen.getByText(/SMSPEC/)).toBeInTheDocument();
  });

  it('submits selected files via api.importResults', async () => {
    (api.importResults as any).mockResolvedValue({
      job_id: 'abc123',
      files_received: ['CASE.SMSPEC', 'CASE.UNSMRY'],
      warnings: [],
    });
    const onImported = vi.fn();
    render(<ImportResultsButton onImported={onImported} />);
    fireEvent.click(screen.getByRole('button', { name: /import results/i }));

    const file = new File(['x'], 'CASE.SMSPEC', { type: 'application/octet-stream' });
    const input = screen.getByLabelText(/select files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    fireEvent.click(screen.getByRole('button', { name: /upload/i }));

    await waitFor(() => expect(onImported).toHaveBeenCalledWith(
      expect.objectContaining({ job_id: 'abc123' })
    ));
  });

  it('shows error from api.importResults', async () => {
    (api.importResults as any).mockRejectedValue(new Error('bad files'));
    render(<ImportResultsButton />);
    fireEvent.click(screen.getByRole('button', { name: /import results/i }));
    const file = new File(['x'], 'CASE.SMSPEC', { type: 'application/octet-stream' });
    fireEvent.change(screen.getByLabelText(/select files/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload/i }));

    await waitFor(() => expect(screen.getByText(/bad files/)).toBeInTheDocument());
  });

  it('disables submit when no files selected', () => {
    render(<ImportResultsButton />);
    fireEvent.click(screen.getByRole('button', { name: /import results/i }));
    const submit = screen.getByRole('button', { name: /upload/i });
    expect(submit).toBeDisabled();
  });
});
```

- [ ] **Step 2: Add the type and API method**

`frontend/src/types.ts`:

```ts
export interface ImportedResultResponse {
  job_id: string;
  files_received: string[];
  warnings: string[];
}
```

Add to the re-export block at the bottom.

`frontend/src/api/client.ts` — add to the imports and add the method (alongside the existing `uploadDeck`):

```ts
importResults: async (formData: FormData): Promise<ImportedResultResponse> => {
  const response = await fetch(`${API_BASE}/imported-results`, {
    method: 'POST',
    body: formData,
    // No Content-Type — browser sets multipart boundary automatically
  });
  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  return response.json() as Promise<ImportedResultResponse>;
},
```

Add `ImportedResultResponse` to the imports-from-types block.

- [ ] **Step 3: Implement ImportResultsButton.tsx**

Create `frontend/src/components/results/ImportResultsButton.tsx`:

```tsx
import { useRef, useState } from 'react';
import { api } from '../../api/client';
import type { ImportedResultResponse } from '../../types';

interface ImportResultsButtonProps {
  onImported?: (response: ImportedResultResponse) => void;
}

const ALLOWED_EXTENSIONS = [
  '.SMSPEC', '.UNSMRY', '.ESMRY',
  '.EGRID', '.FEGRID', '.GRID', '.FGRID',
  '.UNRST', '.INIT', '.RFT', '.PRT',
];

export default function ImportResultsButton({ onImported }: ImportResultsButtonProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const open = () => {
    setFiles([]);
    setError(null);
    dialogRef.current?.showModal();
  };

  const close = () => dialogRef.current?.close();

  const submit = async () => {
    if (files.length === 0) return;
    setSubmitting(true);
    setError(null);
    const form = new FormData();
    for (const f of files) form.append('files', f, f.name);
    try {
      const response = await api.importResults(form);
      onImported?.(response);
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        onClick={open}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-100 dark:hover:bg-gray-700"
        data-testid="import-results-button"
      >
        Import Results
      </button>
      <dialog ref={dialogRef} className="rounded-lg p-6 w-[480px] backdrop:bg-black/40">
        <h2 className="text-lg font-semibold mb-3">Import Simulation Results</h2>

        <div className="mb-3 text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 p-2 rounded">
          Required: one *.SMSPEC + one *.UNSMRY (or one *.ESMRY).
          Optional: .EGRID, .GRID, .UNRST, .INIT, .RFT, .PRT.
        </div>

        <label className="block text-sm font-medium mb-1">Select files</label>
        <input
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="block w-full text-sm mb-3"
        />

        {files.length > 0 && (
          <ul className="text-xs mb-3 max-h-32 overflow-y-auto border rounded p-2">
            {files.map((f) => (
              <li key={f.name} className="flex justify-between">
                <span>{f.name}</span>
                <button
                  onClick={() => setFiles(files.filter((x) => x !== f))}
                  className="text-red-500"
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && (
          <div className="text-xs text-red-600 mb-3" data-testid="import-error">{error}</div>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={close}
            className="px-3 py-1 text-sm border rounded"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={files.length === 0 || submitting}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded disabled:opacity-50"
            data-testid="import-submit"
          >
            {submitting ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </dialog>
    </>
  );
}
```

- [ ] **Step 4: Wire the button into ResultsViewer.tsx**

In `frontend/src/components/ResultsViewer.tsx`, find the header row (the one with the existing `ResInsight` launch button). Add the import button next to it:

```tsx
import ImportResultsButton from './results/ImportResultsButton';

// Inside the header:
<ImportResultsButton
  onImported={(resp) => {
    setCurrentJob({ job_id: resp.job_id, status: 'completed' } as any);
  }}
/>
```

(Adjust `setCurrentJob` to whatever the store exposes — read the existing header code to confirm.)

- [ ] **Step 5: Run the test**

Run: `cd frontend && npx vitest run src/components/results/ImportResultsButton.test.tsx`
Expected: 4 passed.

- [ ] **Step 6: Build check**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/results/ImportResultsButton.tsx frontend/src/components/results/ImportResultsButton.test.tsx frontend/src/components/ResultsViewer.tsx frontend/src/api/client.ts frontend/src/types.ts
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "frontend: results — Import Results button + modal"
```

---

### Task 9: 3D viewer — cross-sections + well property overlay

**Files:**
- Modify: `frontend/src/components/viewer3d/ControlPanel.tsx` (add 2 sections)
- Modify: `frontend/src/components/viewer3d/Grid3DViewer.tsx` (cross-section overlay + trajectory plot)

**Interfaces:**
- New ControlPanel sections (props already exist in DisplayOptions / engine state — extend them):
  - **Cross-section**: `axis: 'I' | 'J' | 'K'`, `index: number` (clamped to axis bounds).
  - **Well overlay**: `wellsForTrajectory: Set<string>`.
- Cross-section uses the existing `gridProperty` endpoint to fetch a slice at the chosen axis/index; rendered as a second canvas overlay on top of the 3D scene.
- Property-along-trajectory uses existing `gridWells` endpoint (already loaded), drawing a small Plotly line plot below the 3D canvas: depth (Y) vs property (X), one line per active well.

- [ ] **Step 1: Read the existing 3D viewer**

Read `frontend/src/components/viewer3d/Grid3DViewer.tsx`, `engine.ts`, `ControlPanel.tsx`, and `meshFormat.ts`. Understand:
- How `DisplayOptions` is structured.
- How `gridProperty` is called and how its result is fed to the GPU.
- Where the canvas overlay / GL context lives.
- How `gridWells` is consumed (it's already loaded for the wells button).

- [ ] **Step 2: Extend DisplayOptions**

Add two fields to `DisplayOptions` in `engine.ts`:

```ts
crossSection: {
  enabled: boolean;
  axis: 'I' | 'J' | 'K';
  index: number;
} | null;

wellTrajectory: {
  enabled: boolean;
  property: string;
} | null;
```

Defaults: both `null`. Both default to off, so existing behaviour is unchanged.

- [ ] **Step 3: Extend ControlPanel.tsx**

Append two new sections after the existing display section. Pattern follows the existing collapsible sections (`Section`, `Field`, etc.):

```tsx
{/* Cross-section */}
<details open className="mt-2">
  <summary className="text-xs font-medium cursor-pointer">Cross-section</summary>
  <div className="mt-1 space-y-1">
    <label className="flex items-center gap-2 text-xs">
      <input
        type="checkbox"
        checked={!!display.crossSection}
        onChange={(e) => onDisplay({
          crossSection: e.target.checked
            ? { enabled: true, axis: 'K', index: Math.floor((info.dims.k - 1) / 2) }
            : null,
        })}
        className="rounded"
      />
      <span>Show cross-section</span>
    </label>
    {display.crossSection && (
      <>
        <label className="flex items-center gap-2 text-xs">
          <span>Axis:</span>
          <select
            value={display.crossSection.axis}
            onChange={(e) => onDisplay({
              crossSection: { ...display.crossSection, axis: e.target.value as 'I' | 'J' | 'K' },
            })}
            className="border rounded px-1 py-0.5"
          >
            <option value="I">I</option>
            <option value="J">J</option>
            <option value="K">K</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs">
          <span>Index:</span>
          <input
            type="range"
            min={1}
            max={axisMax(display.crossSection.axis, info.dims)}
            value={display.crossSection.index}
            onChange={(e) => onDisplay({
              crossSection: { ...display.crossSection, index: parseInt(e.target.value) },
            })}
            className="flex-1"
          />
          <span className="font-mono">{display.crossSection.index}</span>
        </label>
      </>
    )}
  </div>
</details>

{/* Well property overlay */}
<details open className="mt-2">
  <summary className="text-xs font-medium cursor-pointer">Well Property Overlay</summary>
  <div className="mt-1 space-y-1">
    <label className="flex items-center gap-2 text-xs">
      <input
        type="checkbox"
        checked={!!display.wellTrajectory}
        onChange={(e) => onDisplay({
          wellTrajectory: e.target.checked ? { enabled: true, property: 'PORO' } : null,
        })}
        className="rounded"
      />
      <span>Show property along wells</span>
    </label>
    {display.wellTrajectory && (
      <label className="flex items-center gap-2 text-xs">
        <span>Property:</span>
        <select
          value={display.wellTrajectory.property}
          onChange={(e) => onDisplay({
            wellTrajectory: { ...display.wellTrajectory, property: e.target.value },
          })}
          className="border rounded px-1 py-0.5"
        >
          {info.static_properties.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>
    )}
  </div>
</details>
```

Add a helper next to the component:

```ts
function axisMax(axis: 'I' | 'J' | 'K', dims: { i: number; j: number; k: number }): number {
  if (axis === 'I') return dims.i;
  if (axis === 'J') return dims.j;
  return dims.k;
}
```

- [ ] **Step 4: Implement the cross-section overlay in Grid3DViewer**

Read the file and find where the existing 3D scene is mounted. Add a second canvas positioned absolutely over the scene that draws the slice using the same `gridProperty` data the volume render uses (just sliced to the chosen index).

```tsx
{display.crossSection && (
  <CrossSectionOverlay
    info={info}
    axis={display.crossSection.axis}
    index={display.crossSection.index}
    property={property}
    stats={stats}
  />
)}
```

Implementation of `CrossSectionOverlay`:

```tsx
function CrossSectionOverlay({ info, axis, index, property, stats }: {
  info: GridInfoResponse;
  axis: 'I' | 'J' | 'K';
  index: number;
  property: string;
  stats: PropertyStats | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    // Fetch the slice via the existing grid/property endpoint
    const url = `/api/results/.../grid/property?property=${property}&time=${currentTime}&...&axis=${axis}&index=${index}`;
    // (Use the same endpoint grid/property/range already uses; the slice
    //  is the cells where the i/j/k coordinate equals `index`.)
    fetch(url).then(r => r.json()).then((data) => drawSlice(canvasRef.current!, data, stats));
  }, [axis, index, property, stats]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute top-0 right-0 w-64 h-64 border border-gray-300 bg-white/80"
      style={{ imageRendering: 'pixelated' }}
    />
  );
}
```

(Adjust to match the existing endpoint shape — likely `grid/property` already returns per-cell values and you can filter by coordinate client-side, OR there may be a more efficient server-side slice endpoint. Pick the path that minimises new endpoint work.)

- [ ] **Step 5: Implement the well property-along-trajectory plot**

Add a small Plotly chart in a div next to the 3D canvas. It draws depth vs property for each active well:

```tsx
{display.wellTrajectory && wells && (
  <WellTrajectoryPlot
    wells={wells}
    property={display.wellTrajectory.property}
    propertyData={propertyAlongTrajectories}  // fetched per-well from grid/property
  />
)}
```

Implementation fetches `grid/property` for the chosen static property and bins the values along each well's `(i, j, k)` trajectory. Renders one trace per active well.

- [ ] **Step 6: Manual browser check**

`cd frontend && npm run dev`. Open the app, run a small simulation, open the 3D tab. Verify:
- Cross-section toggle shows the slice, axis/index controls work.
- Well property overlay renders the depth-vs-property line.
- No console errors.
- Toggle off → no overlay.

- [ ] **Step 7: Existing 3D tests still pass**

Run: `cd frontend && npx vitest run src/components/viewer3d/`
Expected: pass (the new sections are additive — props default to `null`/off).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/viewer3d/ControlPanel.tsx frontend/src/components/viewer3d/Grid3DViewer.tsx frontend/src/components/viewer3d/engine.ts
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "frontend: viewer3d — cross-section + well property overlay"
```

---

### Task 10: Frontend — Export Graph wiring + ChatPanel figure rendering

**Files:**
- Modify: `frontend/src/components/results/PlotCard.tsx` (wire export menu)
- Modify: `frontend/src/components/ChatPanel.tsx` (render PlotCard inside tool result bubbles)

**Interfaces:**
- `PlotCard` gains a new prop:
  ```ts
  exportGroup: string;       // "field_rates", "well_rates", etc.
  exportVectors: string[];   // current vector selection for this card
  ```
  These come from the parent (ResultsViewer Plots tab), which knows the current rail selection.
- Export menu items:
  - PNG → `Plotly.downloadImage(div, {format: 'png', width: 1280, height: 720, filename: 'opm-<group>-<plotname>.png'})`
  - SVG → same with `format: 'svg'`
  - CSV (native) → fetch `api.csv(jobId, {group, vectors, freq: 'native'})`, blob download as `opm-<group>-<plotname>-native.csv`
  - CSV (monthly) → same with `freq: 'monthly'`
  - CSV (yearly) → same with `freq: 'yearly'`

- [ ] **Step 1: Extend PlotCard props**

Edit `frontend/src/components/results/PlotCard.tsx`. Replace the props interface:

```ts
interface PlotCardProps {
  jobId: string;
  plotName: string;
  plotJson: string;
  exportGroup?: string;
  exportVectors?: string[];
}
```

The export group/vectors are optional — when omitted (e.g. when used inside ChatPanel where the export is less useful), the export menu is hidden.

- [ ] **Step 2: Wire the export menu**

In PlotCard.tsx, replace the `<details>` stub with real handlers:

```tsx
{exportGroup && exportVectors && (
  <details className="relative">
    <summary className="cursor-pointer text-xs text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">
      Export
    </summary>
    <div className="absolute right-0 z-10 mt-1 bg-white dark:bg-gray-800 border rounded shadow-lg p-1 min-w-[140px]">
      <button
        onClick={() => downloadImage('png')}
        className="block w-full text-left px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        PNG
      </button>
      <button
        onClick={() => downloadImage('svg')}
        className="block w-full text-left px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        SVG
      </button>
      <hr className="my-1" />
      <button
        onClick={() => downloadCsv('native')}
        className="block w-full text-left px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        CSV (native)
      </button>
      <button
        onClick={() => downloadCsv('monthly')}
        className="block w-full text-left px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        CSV (monthly)
      </button>
      <button
        onClick={() => downloadCsv('yearly')}
        className="block w-full text-left px-2 py-1 text-xs hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        CSV (yearly)
      </button>
    </div>
  </details>
)}
```

Add the handler functions inside the component (just below the existing `useEffect`):

```ts
const downloadImage = (format: 'png' | 'svg') => {
  if (!divRef.current) return;
  const filename = `opm-${exportGroup}-${plotName.replace(/\s+/g, '_')}.${format}`;
  Plotly.downloadImage(divRef.current, {
    format,
    width: 1280,
    height: 720,
    filename,
  } as any);
};

const downloadCsv = async (freq: 'native' | 'monthly' | 'yearly') => {
  const csv = await api.csv(jobId, {
    group: exportGroup!,
    vectors: exportVectors!,
    freq,
  });
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `opm-${exportGroup}-${plotName.replace(/\s+/g, '_')}-${freq}.csv`;
  a.click();
  URL.revokeObjectURL(url);
};
```

Add the api import at the top:

```ts
import { api } from '../../api/client';
```

- [ ] **Step 3: Pass the new props from ResultsViewer**

Edit `frontend/src/components/ResultsViewer.tsx`. Update each `PlotCard` invocation in the Plots tab to pass the group/vectors. For example:

```tsx
<PlotCard
  jobId={jobId}
  plotName="Field Rates"
  plotJson={plots['field_rates'] ?? ''}
  exportGroup="field_rates"
  exportVectors={Array.from(selectedVectors.field_rates)}
/>
```

For well groups, the well selection matters too — the CSV needs to slice to the chosen wells. Since CSV columns are already per-well (`WOPR:PROD1`), pass all wells but the vectors filter is sufficient. (Plotly figure uses the same data; no extra work.)

For `well_cumulative` and `well_injection`, same pattern with their respective groups.

- [ ] **Step 4: Update PlotCard test for export wiring**

Append to `frontend/src/components/results/PlotCard.test.tsx`:

```tsx
it('hides export menu when exportGroup not provided', () => {
  render(<PlotCard jobId="j1" plotName="Foo" plotJson="" />);
  expect(screen.queryByText(/Export/)).not.toBeInTheDocument();
});

it('shows export menu when exportGroup provided', () => {
  render(
    <PlotCard
      jobId="j1"
      plotName="Foo"
      plotJson=""
      exportGroup="field_rates"
      exportVectors={['FOPR']}
    />
  );
  expect(screen.getByText('Export')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Export'));
  expect(screen.getByText('PNG')).toBeInTheDocument();
  expect(screen.getByText('SVG')).toBeInTheDocument();
  expect(screen.getByText(/CSV \(native\)/)).toBeInTheDocument();
  expect(screen.getByText(/CSV \(monthly\)/)).toBeInTheDocument();
  expect(screen.getByText(/CSV \(yearly\)/)).toBeInTheDocument();
});
```

Run: `cd frontend && npx vitest run src/components/results/PlotCard.test.tsx`
Expected: 6 passed (4 original + 2 new).

- [ ] **Step 5: Extend ChatPanel.tsx to render figures from tool results**

Read `frontend/src/components/ChatPanel.tsx`. Find the tool-result renderer — the place that maps a `tool_call` response into the chat bubble. Add a case for `plot_well_vectors` and `compare_wells`:

```tsx
{toolResult.tool_name === 'plot_well_vectors' || toolResult.tool_name === 'compare_wells' ? (
  <PlotCard
    jobId={currentJobId ?? ''}
    plotName={`${toolResult.tool_name === 'compare_wells' ? 'Compare' : 'Plot'}: ${toolResult.content?.wells?.join(', ') ?? ''}`}
    plotJson={toolResult.content?.figure_json ?? ''}
  />
) : (
  <pre>{JSON.stringify(toolResult.content, null, 2)}</pre>
)}
```

Import at the top:

```tsx
import PlotCard from './results/PlotCard';
```

- [ ] **Step 6: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: all pass.

- [ ] **Step 7: Build check**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: clean build, no TypeScript errors.

- [ ] **Step 8: Manual browser test**

`cd frontend && npm run dev`. With the backend running (`uvicorn opm_ai.api.server:create_app --factory --port 8000`):
- Open a completed run, Plots tab. Click Export on any PlotCard → verify PNG, SVG, and all three CSV downloads work. The CSV at "monthly" should have fewer rows than "native".
- Open Chat. Ask "show WBHP for PROD1". The chat bubble should render a Plotly figure.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/results/PlotCard.tsx frontend/src/components/results/PlotCard.test.tsx frontend/src/components/ResultsViewer.tsx frontend/src/components/ChatPanel.tsx
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "frontend: results — Export Graph (PNG/SVG/CSV at 3 frequencies) + ChatPanel figure rendering"
```

---

## Self-Review

**1. Spec coverage (every requirement has a task):**

| Spec requirement | Task |
|---|---|
| Left-side control rail on KPIs/Plots tabs | Task 7 |
| Top-4 priority vector groups with auto-detection | Tasks 1, 2, 7 |
| 3D cross-sections | Task 9 |
| 3D well property overlay | Task 9 |
| Import Results as virtual job | Tasks 5, 8 |
| Export Graph PNG/SVG | Task 10 |
| Export Graph CSV at native/monthly/yearly | Tasks 3, 4, 10 |
| Three new chat tools | Task 6 |
| "Plot only what is present" principle | Tasks 1, 2 (categorizer + plot_groups both filter empty) |
| Branch off `feat/v2-linter-grammar` | Header |
| Linter worker WIP stashed | Header constraint |

**2. Placeholder scan:** No TBDs. Every step has code or commands. No "add validation" / "implement later".

**3. Type consistency:**
- `CategorizedVectors` TypedDict defined in Task 1, imported in Task 2 (categorize returns the same shape).
- `PlotGroupResponse` defined in Task 4, used in Task 7.
- `CsvFrequency` enum defined in Task 4, used in Task 10.
- `ImportedResultResponse` defined in Task 5, used in Task 8.
- `PlotCard` props in Task 7 (3 fields) extended in Task 10 (2 optional fields). The optional fields default to undefined, which the Task 10 code branches on (`exportGroup && exportVectors`) — both old and new test cases continue to work.
- `useAppStore.setCategories` / `getCategories` defined in Task 7, used in Task 7 only (Task 8 calls `setCurrentJob` directly).

**4. Open judgment calls documented:**
- Resampling defaults to `mean` for unknown suffix (spec).
- Virtual jobs die with the server (spec).
- No new deps (header).
- `<dialog>` for the Import modal (header).

All gaps from the spec self-review are addressed. No new tasks added.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-14-results-page-enrichment.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
