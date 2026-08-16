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
  value (independent of producer status).
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

ALL_WELL_KEYWORDS = WELL_RATES_KEYWORDS + WELL_CUMULATIVE_KEYWORDS + WELL_INJECTION_KEYWORDS

PRODUCER_TEST_KEYWORDS = ("WOPR", "WWPR", "WGPR")
INJECTOR_TEST_KEYWORDS = ("WGIR", "WWIR", "WOIR", "WGIT", "WWIT")

# Human-readable labels for vector short codes.
# Used in UI to show "Oil Rate" instead of "FOPR"/"WOPR".
VECTOR_LABELS: dict[str, str] = {
    # Field rates
    "FOPR": "Oil Rate",
    "FWPR": "Water Rate",
    "FGPR": "Gas Rate",
    # Field cumulative
    "FOPT": "Oil Cumulative",
    "FWPT": "Water Cumulative",
    "FGPT": "Gas Cumulative",
    # Field derived
    "FWCT": "Water Cut",
    "FGOR": "GOR",
    "FPR": "Avg Pressure",
    # Well rates
    "WOPR": "Oil Rate",
    "WWPR": "Water Rate",
    "WGPR": "Gas Rate",
    "WBHP": "BHP",
    "WGOR": "GOR",
    "WWCT": "Water Cut",
    # Well cumulative
    "WOPT": "Oil Cumulative",
    "WWPT": "Water Cumulative",
    "WGPT": "Gas Cumulative",
    # Well injection
    "WGIR": "Gas Injection Rate",
    "WWIR": "Water Injection Rate",
    "WOIR": "Oil Injection Rate",
    "WGIT": "Gas Injection Cumulative",
    "WWIT": "Water Injection Cumulative",
}


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
    vector_labels: dict[str, str]


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
            vector_labels={},
        )

    field_rates = [c for c in FIELD_RATES if c in df.columns]
    field_cumulative = [c for c in FIELD_CUMULATIVE if c in df.columns]
    field_derived = [c for c in FIELD_DERIVED if c in df.columns]

    # First pass: collect all wells that have any recognized well keyword
    all_wells: set[str] = set()
    for col in df.columns:
        if col == "TIME":
            continue
        split = _split_well_column(col)
        if split is None:
            continue
        keyword, well = split
        if keyword in ALL_WELL_KEYWORDS:
            all_wells.add(well)

    well_rates: dict[str, list[str]] = {}
    well_cumulative: dict[str, list[str]] = {}
    well_injection: dict[str, list[str]] = {}

    # Second pass: for each well, determine producer/injector status and
    # collect keywords with positive max values
    for well in all_wells:
        is_prod = _is_producer(df, well)
        is_inj = _is_injector(df, well)

        if is_prod:
            rates = []
            for kw in WELL_RATES_KEYWORDS:
                col = f"{kw}:{well}"
                if col in df.columns and _max_positive(df, col) > 0:
                    rates.append(kw)
            if rates:
                well_rates[well] = sorted(rates)

            cum = []
            for kw in WELL_CUMULATIVE_KEYWORDS:
                col = f"{kw}:{well}"
                if col in df.columns and _max_positive(df, col) > 0:
                    cum.append(kw)
            if cum:
                well_cumulative[well] = sorted(cum)

        if is_inj:
            inj = []
            for kw in WELL_INJECTION_KEYWORDS:
                col = f"{kw}:{well}"
                if col in df.columns and _max_positive(df, col) > 0:
                    inj.append(kw)
            if inj:
                well_injection[well] = sorted(inj)

    wells = sorted(all_wells)

    # Build vector_labels for all keywords present in this categorization
    all_keywords = set()
    all_keywords.update(field_rates)
    all_keywords.update(field_cumulative)
    all_keywords.update(field_derived)
    for kw_list in well_rates.values():
        all_keywords.update(kw_list)
    for kw_list in well_cumulative.values():
        all_keywords.update(kw_list)
    for kw_list in well_injection.values():
        all_keywords.update(kw_list)

    vector_labels = {kw: VECTOR_LABELS.get(kw, kw) for kw in all_keywords}

    return CategorizedVectors(
        field_rates=sorted(field_rates),
        field_cumulative=sorted(field_cumulative),
        field_derived=sorted(field_derived),
        well_rates=well_rates,
        well_cumulative=well_cumulative,
        well_injection=well_injection,
        wells=wells,
        vector_labels=vector_labels,
    )