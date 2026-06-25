"""KPI extraction from OPM Flow SUMMARY output.

Strategy
--------
1. Try ecl2df (Equinor's Eclipse DataFrame library) — works with both
   UNSMRY and ESMRY; returns a tidy DataFrame with DATE as index.
2. Fallback: minimal struct-based UNSMRY reader using only stdlib + numpy.
   This ensures the module works even without ecl2df installed.

All public functions return SummaryFrame or KPISet — never raw DataFrames.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import datetime

from .models import SummaryFrame, KPISet


# ─────────────────────────────────────────────────────────────────────────────
# Summary loading
# ─────────────────────────────────────────────────────────────────────────────

def load_summary_ecl2df(smspec_path: Path) -> SummaryFrame:
    """Load SUMMARY vectors using ecl2df.summary.df().

    ecl2df accepts the .SMSPEC path (or the base name without extension).
    It discovers .UNSMRY automatically.
    """
    import ecl2df  # type: ignore
    import pandas as pd

    # ecl2df expects the case basename (no extension)
    case = str(smspec_path.with_suffix(""))
    df = ecl2df.summary.df(case)          # returns DataFrame, DATE as column

    if "DATE" in df.columns:
        df = df.set_index("DATE")
    elif df.index.name != "DATE":
        pass  # best-effort: keep whatever index ecl2df returns

    vectors = [c for c in df.columns]
    dates = list(df.index) if hasattr(df.index, "__iter__") else []

    return SummaryFrame(
        df=df,
        dates=dates,
        vectors=vectors,
        case_name=smspec_path.stem,
    )


def load_summary_fallback(smspec_path: Path) -> SummaryFrame:
    """Minimal UNSMRY reader — no external dependencies beyond numpy.

    Reads the .SMSPEC (keyword WGNAMES, KEYWORDS, UNITS) and .UNSMRY
    (PARAMS keyword) to reconstruct a DataFrame.
    Falls back gracefully for unknown record types.
    """
    import struct
    import numpy as np
    try:
        import pandas as pd
    except ImportError:
        return SummaryFrame.empty()

    smspec = smspec_path.with_suffix(".SMSPEC")
    unsmry = smspec_path.with_suffix(".UNSMRY")
    if not smspec.exists() or not unsmry.exists():
        return SummaryFrame.empty()

    keywords, wgnames, units = _read_smspec(smspec)
    time_series = _read_unsmry(unsmry, len(keywords))

    if not time_series:
        return SummaryFrame.empty()

    # Build column names: "KEYWORD" or "KEYWORD:WGNAME"
    cols = []
    for kw, wg in zip(keywords, wgnames):
        wg = wg.strip()
        cols.append(f"{kw.strip()}:{wg}" if wg and wg not in ("", ":", " ") else kw.strip())

    data = np.array(time_series)  # shape (n_steps, n_vectors)
    df = pd.DataFrame(data, columns=cols)

    # TIME column → real dates (days since start)
    dates = []
    if "TIME" in df.columns:
        days = df["TIME"].values
        # Use a synthetic start date; real decks embed start date in STARTDAT in SMSPEC
        start = _read_startdat(smspec) or datetime.datetime(2000, 1, 1)
        dates = [start + datetime.timedelta(days=float(d)) for d in days]
        df.index = pd.DatetimeIndex(dates)
        df.index.name = "DATE"

    return SummaryFrame(
        df=df,
        dates=dates,
        vectors=list(df.columns),
        case_name=smspec_path.stem,
    )


# ─────────────────────────────────────────────────────────────────────────────
# KPI computation
# ─────────────────────────────────────────────────────────────────────────────

def extract_kpis(sf: SummaryFrame) -> KPISet:
    """Compute reservoir engineering KPIs from a loaded SummaryFrame."""
    if sf.empty or sf.df is None:
        return KPISet.empty()

    df = sf.df
    kpis = KPISet(available_vectors=sf.vectors)

    # ── Cumulative totals (last row = cumulative at end of run) ─────────────
    kpis.fopt = _last(df, "FOPT")
    kpis.fwpt = _last(df, "FWPT")
    kpis.fgpt = _last(df, "FGPT")
    kpis.fwit = _last(df, "FWIT")
    kpis.fgit = _last(df, "FGIT")

    # ── Peak oil rate ────────────────────────────────────────────────────────
    if "FOPR" in df.columns:
        idx = df["FOPR"].idxmax()
        kpis.peak_fopr = float(df["FOPR"].max())
        kpis.peak_fopr_date = idx if hasattr(idx, "year") else None

    # ── Peak water injection rate ────────────────────────────────────────────
    kpis.peak_fwir = _max(df, "FWIR")

    # ── Field average pressure ───────────────────────────────────────────────
    if "FPR" in df.columns:
        kpis.initial_fpr = float(df["FPR"].iloc[0])
        kpis.final_fpr = float(df["FPR"].iloc[-1])
        kpis.pressure_drop = kpis.initial_fpr - kpis.final_fpr

    # ── Water cut and breakthrough ───────────────────────────────────────────
    # Field WCT = FWPR / (FWPR + FOPR) — computed from rates, not a direct vector
    if "FWPR" in df.columns and "FOPR" in df.columns:
        total_liq = df["FWPR"] + df["FOPR"]
        fwct_series = df["FWPR"] / total_liq.where(total_liq > 0)
        kpis.final_field_wct = float(fwct_series.iloc[-1]) if not fwct_series.empty else None

        # Breakthrough: first timestep with WWCT > 0.05 across any well
        # Try per-well WWCT columns first; fall back to field-level WCT
        wwct_cols = [c for c in df.columns if c.startswith("WWCT")]
        bt_date = _find_breakthrough(df, wwct_cols, threshold=0.05)
        if bt_date is None:
            bt_date = _find_breakthrough_series(fwct_series, threshold=0.05)
        kpis.wct_breakthrough_date = bt_date
        if bt_date is not None and len(df.index) > 0:
            start = df.index[0]
            if hasattr(bt_date, "year") and hasattr(start, "year"):
                delta = (bt_date - start).days / 365.25
                kpis.wct_breakthrough_years = round(delta, 2)

    # ── Recovery factor ──────────────────────────────────────────────────────
    # Use FOIP at t=0 as proxy for STOIIP
    if "FOIP" in df.columns:
        foip0 = float(df["FOIP"].iloc[0])
        if foip0 > 0 and kpis.fopt is not None:
            kpis.foip_initial = foip0
            kpis.recovery_factor = round(kpis.fopt / foip0, 4)

    # ── Simulation performance ───────────────────────────────────────────────
    if "NEWTON" in df.columns:
        kpis.avg_newton_iters = float(df["NEWTON"].mean())
    if "NTS" in df.columns:
        kpis.total_timesteps = int(df["NTS"].iloc[-1])
    if "TCPU" in df.columns:
        kpis.total_cpu_seconds = float(df["TCPU"].iloc[-1])

    return kpis


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _last(df, col: str) -> Optional[float]:
    if col in df.columns and not df[col].empty:
        return float(df[col].iloc[-1])
    return None


def _max(df, col: str) -> Optional[float]:
    if col in df.columns and not df[col].empty:
        return float(df[col].max())
    return None


def _find_breakthrough(df, wwct_cols: list, threshold: float) -> Optional[datetime.datetime]:
    """Return earliest date any well WCT exceeds threshold."""
    earliest = None
    for col in wwct_cols:
        above = df.index[df[col] > threshold]
        if len(above) > 0:
            t = above[0]
            if earliest is None or t < earliest:
                earliest = t
    return earliest


def _find_breakthrough_series(series, threshold: float) -> Optional[datetime.datetime]:
    above = series.index[series > threshold]
    return above[0] if len(above) > 0 else None


def _read_smspec(path: Path):
    """Extract KEYWORDS, WGNAMES from .SMSPEC binary (Fortran unformatted)."""
    import struct

    keywords, wgnames, units = [], [], []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(16)
            if len(hdr) < 16:
                break
            try:
                name = hdr[:8].decode("ascii").strip()
                count = struct.unpack(">i", hdr[8:12])[0]
                dtype = hdr[12:16].decode("ascii").strip()
            except Exception:
                break

            record_size = count * _ecltype_size(dtype)
            # Read leading Fortran record length
            fl = f.read(4)
            if len(fl) < 4:
                break
            data = f.read(struct.unpack(">i", fl)[0])
            f.read(4)  # trailing record length

            if name == "KEYWORDS":
                keywords = [data[i*8:(i+1)*8].decode("ascii", errors="replace").strip()
                            for i in range(count)]
            elif name == "WGNAMES":
                wgnames = [data[i*8:(i+1)*8].decode("ascii", errors="replace").strip()
                           for i in range(count)]
            elif name == "UNITS":
                units = [data[i*8:(i+1)*8].decode("ascii", errors="replace").strip()
                         for i in range(count)]
    return keywords, wgnames, units


def _read_unsmry(path: Path, n_vectors: int) -> list:
    """Read PARAMS records from .UNSMRY; each PARAMS = one timestep."""
    import struct
    rows = []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(16)
            if len(hdr) < 16:
                break
            try:
                name = hdr[:8].decode("ascii").strip()
                count = struct.unpack(">i", hdr[8:12])[0]
                dtype = hdr[12:16].decode("ascii").strip()
            except Exception:
                break
            fl = f.read(4)
            if len(fl) < 4:
                break
            rec_len = struct.unpack(">i", fl)[0]
            data = f.read(rec_len)
            f.read(4)
            if name == "PARAMS" and dtype in ("REAL", "DOUB"):
                fmt = ">" + ("f" if dtype == "REAL" else "d") * count
                try:
                    vals = list(struct.unpack(fmt, data[:struct.calcsize(fmt)]))
                    rows.append(vals)
                except struct.error:
                    pass
    return rows


def _ecltype_size(dtype: str) -> int:
    return {"INTE": 4, "REAL": 4, "DOUB": 8, "LOGI": 4, "CHAR": 8}.get(dtype, 4)


def _read_startdat(smspec: Path) -> Optional[datetime.datetime]:
    """Try to extract STARTDAT record from SMSPEC."""
    import struct
    try:
        with open(smspec, "rb") as f:
            while True:
                hdr = f.read(16)
                if len(hdr) < 16:
                    break
                name = hdr[:8].decode("ascii", errors="replace").strip()
                count = struct.unpack(">i", hdr[8:12])[0]
                fl = f.read(4)
                if len(fl) < 4:
                    break
                data = f.read(struct.unpack(">i", fl)[0])
                f.read(4)
                if name == "STARTDAT" and count >= 3:
                    day, month, year = struct.unpack(">iii", data[:12])
                    return datetime.datetime(year, month, day)
    except Exception:
        pass
    return None
