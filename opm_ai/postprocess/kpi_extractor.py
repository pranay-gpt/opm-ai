"""KPI extraction from OPM Flow SUMMARY output.

Strategy
--------
1. Try ecl2df (Equinor’s Eclipse DataFrame library) — works with both
   UNSMRY and ESMRY; returns a tidy DataFrame with DATE as index.
2. Fallback: minimal struct-based UNSMRY reader using only stdlib + numpy.

All public functions return SummaryFrame or KPISet — never raw DataFrames.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import datetime

from .models import SummaryFrame, KPISet


def load_summary_ecl2df(smspec_path: Path) -> SummaryFrame:
    import ecl2df  # type: ignore
    case = str(smspec_path.with_suffix(""))
    df = ecl2df.summary.df(case)
    if "DATE" in df.columns:
        df = df.set_index("DATE")
    vectors = list(df.columns)
    dates = list(df.index) if hasattr(df.index, "__iter__") else []
    return SummaryFrame(df=df, dates=dates, vectors=vectors, case_name=smspec_path.stem)


def load_summary_fallback(smspec_path: Path) -> SummaryFrame:
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

    cols = []
    for kw, wg in zip(keywords, wgnames):
        wg = wg.strip()
        cols.append(f"{kw.strip()}:{wg}" if wg and wg not in ("", ":", " ") else kw.strip())

    import numpy as np
    data = np.array(time_series)
    df = pd.DataFrame(data, columns=cols)

    dates = []
    if "TIME" in df.columns:
        days = df["TIME"].values
        start = _read_startdat(smspec) or datetime.datetime(2000, 1, 1)
        dates = [start + datetime.timedelta(days=float(d)) for d in days]
        df.index = pd.DatetimeIndex(dates)
        df.index.name = "DATE"

    return SummaryFrame(df=df, dates=dates, vectors=list(df.columns), case_name=smspec_path.stem)


# ─────────────────────────────────────────────────────────────────────────────
# KPI computation
# ─────────────────────────────────────────────────────────────────────────────

def extract_kpis(sf: SummaryFrame) -> KPISet:
    """Compute reservoir engineering KPIs from a loaded SummaryFrame."""
    if sf.is_empty or sf.df is None:
        return KPISet.empty()

    df = sf.df
    kpis = KPISet(available_vectors=sf.vectors)

    kpis.fopt = _last(df, "FOPT")
    kpis.fwpt = _last(df, "FWPT")
    kpis.fgpt = _last(df, "FGPT")
    kpis.fwit = _last(df, "FWIT")
    kpis.fgit = _last(df, "FGIT")

    if "FOPR" in df.columns:
        idx = df["FOPR"].idxmax()
        kpis.peak_fopr = float(df["FOPR"].max())
        kpis.peak_fopr_date = idx if hasattr(idx, "year") else None

    kpis.peak_fwir = _max(df, "FWIR")

    if "FPR" in df.columns:
        kpis.initial_fpr = float(df["FPR"].iloc[0])
        kpis.final_fpr = float(df["FPR"].iloc[-1])
        kpis.pressure_drop = kpis.initial_fpr - kpis.final_fpr

    if "FWPR" in df.columns and "FOPR" in df.columns:
        total_liq = df["FWPR"] + df["FOPR"]
        fwct_series = df["FWPR"] / total_liq.where(total_liq > 0)
        kpis.final_field_wct = float(fwct_series.iloc[-1]) if not fwct_series.empty else None

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

    if "FOIP" in df.columns:
        foip0 = float(df["FOIP"].iloc[0])
        if foip0 > 0 and kpis.fopt is not None:
            kpis.foip_initial = foip0
            kpis.recovery_factor = round(kpis.fopt / foip0, 4)

    if "NEWTON" in df.columns:
        kpis.avg_newton_iters = float(df["NEWTON"].mean())
    if "NTS" in df.columns:
        kpis.total_timesteps = int(df["NTS"].iloc[-1])
    if "TCPU" in df.columns:
        kpis.total_cpu_seconds = float(df["TCPU"].iloc[-1])

    return kpis


def _last(df, col: str) -> Optional[float]:
    if col in df.columns and not df[col].empty:
        return float(df[col].iloc[-1])
    return None


def _max(df, col: str) -> Optional[float]:
    if col in df.columns and not df[col].empty:
        return float(df[col].max())
    return None


def _find_breakthrough(df, wwct_cols: list, threshold: float) -> Optional[datetime.datetime]:
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
            fl = f.read(4)
            if len(fl) < 4:
                break
            data = f.read(struct.unpack(">i", fl)[0])
            f.read(4)
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
