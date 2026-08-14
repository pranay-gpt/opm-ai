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

import numpy as np
import pandas as pd


Freq = Literal["native", "monthly", "yearly"]

# Pandas resample rule per freq. Use 'ME'/'YE' (month/year end) per pandas 2.x deprecation of 'M'/'Y'.
_RULE: dict[str, str] = {"monthly": "ME", "yearly": "YE"}

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
    """Return True if TIME column contains actual dates/timestamps, not step indices.

    Heuristics:
    - Already datetime64/Timestamp dtype -> True
    - String values that parse as dates -> True
    - Large numeric values (epoch seconds > 1e9 or ns > 1e12) -> True
    - Small integers/floats (< 100000) -> False (likely step indices)
    """
    first = series.iloc[0]
    # Already datetime-like
    if isinstance(first, (pd.Timestamp, pd.DatetimeIndex)):
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    # String that looks like a date
    if isinstance(first, str):
        try:
            pd.to_datetime(first)
            return True
        except (ValueError, TypeError):
            return False
    # Numeric: check magnitude
    if isinstance(first, (int, float, np.integer, np.floating)):
        val = float(first)
        # Large values: likely epoch timestamps (seconds > 1e9 ~ 2001, ns > 1e12)
        if val > 1e9:
            return True
        # Small values: likely step indices (days or report steps)
        return False
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