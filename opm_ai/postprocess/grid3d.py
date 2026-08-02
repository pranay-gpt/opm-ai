"""Corner-point grid geometry for the interactive 3D viewer.

Reads ECLIPSE EGRID/INIT/UNRST output with resfo and produces geometry and
property arrays the browser can render directly. This is the offline
replacement for the ResInsight bridge: the packaged ResInsight binary has no
gRPC and its snapshots need a live X display (see resinsight_bridge), so
nothing here shells out to it.

Geometry follows the ECLIPSE corner-point convention as implemented by
ResInsight (RifReaderEclipseOutput / RigCell):

    cell (i,j,k) corner e = kk*4 + jj*2 + ii   (ii,jj,kk in {0,1})
    z    = ZCORN[2k+kk, 2j+jj, 2i+ii]
    x,y  = linear interpolation along COORD pillar (j+jj, i+ii) at that z

Depth increases downward in ECLIPSE. Z is negated on export so +Z is up in
the viewer, matching ResInsight's display convention.

Verified against tests/fixtures: cell-centre depth reproduces the INIT DEPTH
array to 1.2e-4 ft on Norne (44431 active cells, corner-point with faults)
and exactly on SPE1 (cartesian).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import resfo

# Corner index bits: e = kk*4 + jj*2 + ii, so ii varies fastest.
#   0=(i,j,k)      1=(i+1,j,k)      2=(i,j+1,k)      3=(i+1,j+1,k)
#   4=(i,j,k+1)    5=(i+1,j,k+1)    6=(i,j+1,k+1)    7=(i+1,j+1,k+1)
#
# Faces are listed counter-clockwise seen from OUTSIDE the cell, in the
# exported coordinate system (Z already flipped to point up). Order matches
# ResInsight's cvf::StructGridInterface: POS_I, NEG_I, POS_J, NEG_J, POS_K,
# NEG_K -- reordered here as I-,I+,J-,J+,K-,K+ for readability.
FACE_CORNERS: tuple[tuple[int, int, int, int], ...] = (
    (0, 2, 6, 4),  # 0  I-  (low i)
    (1, 5, 7, 3),  # 1  I+
    (0, 4, 5, 1),  # 2  J-
    (2, 3, 7, 6),  # 3  J+
    (0, 1, 3, 2),  # 4  K-  (top / shallowest)
    (4, 6, 7, 5),  # 5  K+  (bottom / deepest)
)
FACE_NAMES = ("I-", "I+", "J-", "J+", "K-", "K+")

# Neighbour offset in (i,j,k) for each face above.
FACE_NEIGHBOUR_OFFSET = ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))

# Faces whose corners must match a neighbour's for the pair not to be a fault.
# Only lateral faces can fault; K faces are always conforming along a pillar.
# Maps face -> the opposing face on the neighbour cell.
OPPOSITE_FACE = (1, 0, 3, 2, 5, 4)

# Corner-pair correspondence when comparing face `f` of a cell with the
# opposing face of its neighbour: entry n of FACE_CORNERS[f] must coincide
# with the geometrically equivalent corner of the neighbour.
_FAULT_MATCH = {
    0: ((0, 1), (2, 3), (6, 7), (4, 5)),  # I- of cell vs I+ of i-1 neighbour
    2: ((0, 2), (4, 6), (5, 7), (1, 3)),  # J- of cell vs J+ of j-1 neighbour
}

UNIT_SYSTEMS = {1: "METRIC", 2: "FIELD", 3: "LAB", 4: "PVT-M"}

# Length unit per unit system, used to label axes in the viewer.
LENGTH_UNIT = {"METRIC": "m", "FIELD": "ft", "LAB": "cm", "PVT-M": "m"}

# Static results worth offering, in the order ResInsight lists them. Anything
# else numeric and cell-shaped in the INIT file is appended after these.
STATIC_PREFERRED = (
    "PORO", "PERMX", "PERMY", "PERMZ", "NTG", "PORV", "DEPTH", "DX", "DY", "DZ",
    "TRANX", "TRANY", "TRANZ", "MULTX", "MULTY", "MULTZ",
    "SATNUM", "PVTNUM", "EQLNUM", "FIPNUM", "IMBNUM", "ENDNUM", "FLUXNUM", "ROCKNUM",
)

# INIT keywords that are headers/tables rather than per-cell properties.
_NON_CELL_KEYWORDS = {
    "INTEHEAD", "LOGIHEAD", "DOUBHEAD", "TABDIMS", "TAB", "ACTNUM",
    "TRANNNC", "STARTSOL", "ENDSOL", "SEQNUM", "ENDGRID", "FILEHEAD",
    "GRIDHEAD", "GRIDUNIT", "MAPUNITS", "MAPAXES", "COORD", "ZCORN",
    "NNCHEAD", "NNC1", "NNC2", "IWEL", "ZWEL", "ICON", "OPM_XWEL", "XWEL",
    "SWEL", "SCON", "IGRP", "SGRP", "XGRP", "ZGRP", "HIDDEN", "ZTRACER",
    "LGR", "LGRNAME", "LGRHEADI", "LGRHEADQ", "LGRHEADD",
}

# Integer-valued results are drawn with a categorical palette, not a ramp.
CATEGORICAL = {"SATNUM", "PVTNUM", "EQLNUM", "FIPNUM", "IMBNUM", "ENDNUM",
               "FLUXNUM", "ROCKNUM", "OPERNUM", "ACTNUM"}

# Saturation triple used for the ternary display mode.
TERNARY_COMPONENTS = ("SOIL", "SGAS", "SWAT")

# ECLIPSE well type code, IWEL record index 6.
WELL_TYPES = {1: "producer", 2: "oil_injector", 3: "water_injector", 4: "gas_injector"}

# Field positions inside one IWEL record (length INTEHEAD[24], 11 on Norne).
# Verified against the Norne restart: head I/J agree with the WELSPECS entries
# in INCLUDE/BC0407_HIST01122006.SCH, and index 4 equals the number of ICON
# slots with a positive connection index for all 36 wells at every step.
IWEL_HEAD_I, IWEL_HEAD_J, IWEL_HEAD_K, IWEL_NCONN, IWEL_TYPE = 0, 1, 2, 4, 6

# Field positions inside one ICON record (length INTEHEAD[32], 15 on Norne).
ICON_INDEX, ICON_I, ICON_J, ICON_K, ICON_STATUS = 0, 1, 2, 3, 5


class GridError(Exception):
    """Raised when a case cannot be read as a corner-point grid."""


@dataclass(frozen=True)
class TimeStep:
    """One restart report step."""

    index: int
    report: int
    days: float
    date: str  # ISO yyyy-mm-dd


@dataclass(frozen=True)
class Completion:
    """One well connection to a grid cell, zero-based ijk."""

    i: int
    j: int
    k: int
    cell: int  # active cell index, -1 when the cell is inactive
    open: bool


@dataclass(frozen=True)
class Well:
    """A well as it stands at one restart step."""

    name: str
    type: str  # producer | oil_injector | water_injector | gas_injector | unknown
    i: int  # zero-based head cell, -1 when IWEL did not validate
    j: int
    k: int
    completions: list[Completion]


def _read_keywords(path: Path, wanted: set[str] | None = None) -> dict[str, np.ndarray]:
    """Return the first occurrence of each keyword in an ECLIPSE output file."""
    out: dict[str, np.ndarray] = {}
    for kw, arr in resfo.read(str(path)):
        name = kw.strip()
        if wanted is not None and name not in wanted:
            continue
        if name in out:
            continue
        if arr is None:
            continue
        out[name] = np.asarray(arr)
    return out


def find_case(output_dir: Path) -> Path | None:
    """Return the case stem (path without extension) for a simulation output dir."""
    output_dir = Path(output_dir)
    egrids = sorted(output_dir.glob("*.EGRID"))
    if not egrids:
        return None
    return egrids[0].with_suffix("")


class EclipseGrid:
    """Corner-point geometry plus the property files that go with a case.

    Construct with the case stem (path with no extension); the EGRID is
    required, INIT and UNRST are optional and looked up alongside it.
    """

    def __init__(self, case_stem: Path):
        self.stem = Path(case_stem)
        self.egrid_path = self.stem.with_suffix(".EGRID")
        if not self.egrid_path.is_file():
            raise GridError(f"No EGRID file at {self.egrid_path}")

        self.init_path = self.stem.with_suffix(".INIT")
        self.unrst_path = self.stem.with_suffix(".UNRST")

        eg = _read_keywords(self.egrid_path)
        if "GRIDHEAD" not in eg:
            raise GridError(f"{self.egrid_path.name} has no GRIDHEAD")
        gh = eg["GRIDHEAD"]
        if int(gh[0]) != 1:
            raise GridError(f"Unsupported grid type {int(gh[0])} (only corner-point is supported)")
        self.nx, self.ny, self.nz = int(gh[1]), int(gh[2]), int(gh[3])
        self.ncells = self.nx * self.ny * self.nz
        if self.ncells <= 0:
            raise GridError(f"Degenerate grid dimensions {self.nx}x{self.ny}x{self.nz}")

        for required in ("COORD", "ZCORN"):
            if required not in eg:
                raise GridError(f"{self.egrid_path.name} has no {required}")

        self._coord = np.asarray(eg["COORD"], dtype=np.float64)
        self._zcorn = np.asarray(eg["ZCORN"], dtype=np.float64)
        expect_coord = 6 * (self.nx + 1) * (self.ny + 1)
        expect_zcorn = 8 * self.ncells
        if self._coord.size != expect_coord:
            raise GridError(f"COORD has {self._coord.size} values, expected {expect_coord}")
        if self._zcorn.size != expect_zcorn:
            raise GridError(f"ZCORN has {self._zcorn.size} values, expected {expect_zcorn}")

        if "ACTNUM" in eg and eg["ACTNUM"].size == self.ncells:
            self.actnum = np.asarray(eg["ACTNUM"]).reshape(self.nz, self.ny, self.nx) > 0
        else:
            self.actnum = np.ones((self.nz, self.ny, self.nx), dtype=bool)
        self.nactive = int(self.actnum.sum())
        if self.nactive == 0:
            raise GridError("Grid has no active cells")

        self.grid_unit = (
            eg["GRIDUNIT"][0].decode(errors="replace").strip() if "GRIDUNIT" in eg else ""
        )
        self.mapaxes = (
            np.asarray(eg["MAPAXES"], dtype=np.float64) if "MAPAXES" in eg else None
        )

        # Non-neighbour connections (faults with throw, pinch-outs).
        self.nnc1 = np.asarray(eg["NNC1"], dtype=np.int64) - 1 if "NNC1" in eg else None
        self.nnc2 = np.asarray(eg["NNC2"], dtype=np.int64) - 1 if "NNC2" in eg else None

        # active_index[k,j,i] -> 0..nactive-1, or -1 when the cell is inactive.
        self.active_index = np.full((self.nz, self.ny, self.nx), -1, dtype=np.int32)
        self.active_index[self.actnum] = np.arange(self.nactive, dtype=np.int32)

        self._corners: np.ndarray | None = None

    # ---------------------------------------------------------------- geometry

    def corners(self) -> np.ndarray:
        """All cell corners, shape (nz, ny, nx, 8, 3), ECLIPSE corner order.

        Coordinates are raw grid coordinates with depth positive downward,
        exactly as stored in the file. Export flips Z and subtracts an origin.
        """
        if self._corners is not None:
            return self._corners

        nx, ny, nz = self.nx, self.ny, self.nz
        coord = self._coord.reshape(ny + 1, nx + 1, 6)
        zcorn = self._zcorn.reshape(2 * nz, 2 * ny, 2 * nx)

        top_x, top_y, top_z = coord[..., 0], coord[..., 1], coord[..., 2]
        bot_x, bot_y, bot_z = coord[..., 3], coord[..., 4], coord[..., 5]

        out = np.empty((nz, ny, nx, 8, 3), dtype=np.float64)
        for kk in range(2):
            for jj in range(2):
                for ii in range(2):
                    z = zcorn[kk::2, jj::2, ii::2]  # (nz, ny, nx)

                    # Pillar (j+jj, i+ii) sliced to align with cell (i,j).
                    px_t = top_x[jj:jj + ny, ii:ii + nx]
                    py_t = top_y[jj:jj + ny, ii:ii + nx]
                    pz_t = top_z[jj:jj + ny, ii:ii + nx]
                    px_b = bot_x[jj:jj + ny, ii:ii + nx]
                    py_b = bot_y[jj:jj + ny, ii:ii + nx]
                    pz_b = bot_z[jj:jj + ny, ii:ii + nx]

                    span = pz_b - pz_t
                    # A vertical pillar of zero length carries no x/y variation,
                    # so the interpolation parameter is irrelevant: use 0.
                    safe = np.where(np.abs(span) > 1e-12, span, 1.0)
                    t = np.where(np.abs(span) > 1e-12, (z - pz_t[None]) / safe[None], 0.0)

                    e = kk * 4 + jj * 2 + ii
                    out[..., e, 0] = px_t[None] + t * (px_b - px_t)[None]
                    out[..., e, 1] = py_t[None] + t * (py_b - py_t)[None]
                    out[..., e, 2] = z

        if self.mapaxes is not None:
            out = self._apply_mapaxes(out)

        self._corners = out
        return out

    def _apply_mapaxes(self, pts: np.ndarray) -> np.ndarray:
        """Rotate grid x/y into map coordinates using the MAPAXES triple."""
        ax = self.mapaxes
        if ax is None or ax.size < 6:
            return pts
        x1, y1, x0, y0, x2, y2 = ax[:6]
        # MAPAXES gives a point on the +y axis, the origin, and a point on +x.
        ux, uy = x2 - x0, y2 - y0
        vx, vy = x1 - x0, y1 - y0
        un = math.hypot(ux, uy)
        vn = math.hypot(vx, vy)
        if un < 1e-12 or vn < 1e-12:
            return pts
        ux, uy = ux / un, uy / un
        vx, vy = vx / vn, vy / vn
        gx = pts[..., 0].copy()
        gy = pts[..., 1].copy()
        pts[..., 0] = x0 + gx * ux + gy * vx
        pts[..., 1] = y0 + gx * uy + gy * vy
        return pts

    def active_corners(self) -> np.ndarray:
        """Corners of active cells only, shape (nactive, 8, 3), grid order."""
        return self.corners()[self.actnum]

    def cell_centres(self) -> np.ndarray:
        """Centroid of every active cell, shape (nactive, 3)."""
        return self.active_corners().mean(axis=1)

    def cell_volumes(self) -> np.ndarray:
        """Volume of every active cell by decomposition into tetrahedra.

        Each of the 6 quad faces is split around its own centre and joined to
        the cell centroid, which stays correct for the non-planar faces that
        corner-point grids routinely produce.
        """
        c = self.active_corners()
        centre = c.mean(axis=1)
        vol = np.zeros(c.shape[0], dtype=np.float64)
        for face in FACE_CORNERS:
            p = [c[:, idx, :] for idx in face]
            face_centre = (p[0] + p[1] + p[2] + p[3]) / 4.0
            for a, b in ((p[0], p[1]), (p[1], p[2]), (p[2], p[3]), (p[3], p[0])):
                v1 = a - face_centre
                v2 = b - face_centre
                v3 = centre - face_centre
                vol += np.abs(np.einsum("ij,ij->i", np.cross(v1, v2), v3)) / 6.0
        return vol

    def ijk_of_active(self) -> np.ndarray:
        """(nactive, 3) array of zero-based i, j, k for each active cell."""
        k, j, i = np.nonzero(self.actnum)
        return np.stack([i, j, k], axis=1).astype(np.int32)

    def bounding_box(self) -> tuple[np.ndarray, np.ndarray]:
        """Min and max corner of the active grid in raw grid coordinates."""
        c = self.active_corners().reshape(-1, 3)
        return c.min(axis=0), c.max(axis=0)

    # ------------------------------------------------------------------ faults

    def fault_faces(self) -> np.ndarray:
        """Boolean mask (nactive, 6): does this face sit on a geometric fault?

        A lateral face is faulted when its two shared corners do not coincide
        with the matching corners of the neighbouring cell, which is how
        ResInsight derives faults when no FAULTS keyword is present
        (RigMainGrid::calculateFaults). Tolerance scales with cell size.
        """
        corners = self.corners()
        nz, ny, nx = self.nz, self.ny, self.nx
        out = np.zeros((self.nactive, 6), dtype=bool)

        extent = float(np.ptp(self.active_corners().reshape(-1, 3), axis=0).max())
        tol = max(extent * 1e-7, 1e-6)

        for face, pairs in _FAULT_MATCH.items():
            di, dj, _ = FACE_NEIGHBOUR_OFFSET[face]
            # Cells that have a neighbour in this direction.
            src = (slice(None), slice(-dj, None) if dj else slice(None),
                   slice(-di, None) if di else slice(None))
            dst = (slice(None), slice(None, dj if dj else None) if dj else slice(None),
                   slice(None, di if di else None) if di else slice(None))

            here = corners[src]      # cells at (i,j)
            there = corners[dst]     # neighbour at (i-1,j) or (i,j-1)
            here_act = self.actnum[src]
            there_act = self.actnum[dst]

            mismatch = np.zeros(here.shape[:3], dtype=bool)
            for a, b in pairs:
                delta = np.abs(here[..., a, :] - there[..., b, :]).max(axis=-1)
                mismatch |= delta > tol

            faulted = mismatch & here_act & there_act
            idx_here = self.active_index[src][faulted]
            idx_there = self.active_index[dst][faulted]
            out[idx_here, face] = True
            out[idx_there, OPPOSITE_FACE[face]] = True

        return out

    def nnc_pairs(self) -> np.ndarray:
        """(n, 2) array of active-cell index pairs for non-neighbour connections."""
        if self.nnc1 is None or self.nnc2 is None:
            return np.zeros((0, 2), dtype=np.int32)
        flat = self.active_index.reshape(-1)
        valid = (
            (self.nnc1 >= 0) & (self.nnc1 < self.ncells)
            & (self.nnc2 >= 0) & (self.nnc2 < self.ncells)
        )
        a = flat[self.nnc1[valid]]
        b = flat[self.nnc2[valid]]
        keep = (a >= 0) & (b >= 0)
        return np.stack([a[keep], b[keep]], axis=1).astype(np.int32)

    # -------------------------------------------------------------- properties

    def static_properties(self) -> dict[str, np.ndarray]:
        """Per-active-cell arrays from the INIT file, keyed by keyword."""
        if not self.init_path.is_file():
            return {}
        out: dict[str, np.ndarray] = {}
        for name, arr in _read_keywords(self.init_path).items():
            if name in _NON_CELL_KEYWORDS:
                continue
            if arr.dtype.kind not in "fiu":
                continue
            values = np.asarray(arr)
            if values.size == self.nactive:
                out[name] = values.astype(np.float32)
            elif values.size == self.ncells:
                # PORV and friends are reported for every cell, active or not.
                out[name] = values.reshape(self.nz, self.ny, self.nx)[self.actnum].astype(np.float32)
        return out

    def unit_system(self) -> str:
        """Unit system name from INIT/UNRST INTEHEAD, or "" when unknown."""
        for path in (self.init_path, self.unrst_path):
            if not path.is_file():
                continue
            head = _read_keywords(path, {"INTEHEAD"}).get("INTEHEAD")
            if head is not None and head.size > 2:
                return UNIT_SYSTEMS.get(int(head[2]), "")
        return ""

    def _restart_index(self) -> tuple[list[TimeStep], dict[str, list[int]]]:
        """Scan the UNRST once, returning time steps and keyword occurrences.

        The occurrence map records, per keyword, which report-step slot each
        occurrence belongs to, so a later read can pick the right one without
        holding every array in memory.
        """
        steps: list[TimeStep] = []
        occurrences: dict[str, list[int]] = {}
        if not self.unrst_path.is_file():
            return steps, occurrences

        current = -1
        pending_days = 0.0
        pending_date = ""
        for kw, arr in resfo.read(str(self.unrst_path)):
            name = kw.strip()
            if name == "SEQNUM":
                current += 1
                report = int(np.asarray(arr)[0]) if arr is not None else current
                steps.append(TimeStep(index=current, report=report, days=0.0, date=""))
                pending_days, pending_date = 0.0, ""
                continue
            if current < 0:
                continue
            if name == "INTEHEAD" and arr is not None:
                head = np.asarray(arr)
                if head.size > 66:
                    day, month, year = int(head[64]), int(head[65]), int(head[66])
                    try:
                        pending_date = date(year, month, day).isoformat()
                    except ValueError:
                        pending_date = ""
                steps[current] = TimeStep(current, steps[current].report, pending_days, pending_date)
            elif name == "DOUBHEAD" and arr is not None:
                head = np.asarray(arr)
                if head.size > 0:
                    pending_days = float(head[0])
                steps[current] = TimeStep(current, steps[current].report, pending_days, pending_date)
            else:
                occurrences.setdefault(name, []).append(current)
        return steps, occurrences

    def time_steps(self) -> list[TimeStep]:
        """Report steps in the UNRST file, in file order."""
        return self._restart_index()[0]

    def dynamic_property_names(self) -> list[str]:
        """Restart keywords that carry one value per active cell."""
        if not self.unrst_path.is_file():
            return []
        names: set[str] = set()
        for kw, arr in resfo.read(str(self.unrst_path)):
            name = kw.strip()
            if name in _NON_CELL_KEYWORDS or arr is None:
                continue
            values = np.asarray(arr)
            if values.dtype.kind in "fiu" and values.size == self.nactive:
                names.add(name)
        return sorted(names)

    def read_dynamic_many(self, names: set[str], step: int) -> dict[str, np.ndarray]:
        """Read several restart arrays for one report step in a single pass.

        Deriving SOIL needs SWAT, SGAS and SSOL together; reading them one at
        a time would re-walk the whole UNRST once per keyword.
        """
        out: dict[str, np.ndarray] = {}
        if not self.unrst_path.is_file():
            return out
        seen = -1
        for kw, arr in resfo.read(str(self.unrst_path)):
            keyword = kw.strip()
            if keyword == "SEQNUM":
                seen += 1
                if seen > step:
                    break
                continue
            if seen != step or keyword not in names or arr is None or keyword in out:
                continue
            values = np.asarray(arr)
            if values.size == self.nactive:
                out[keyword] = values.astype(np.float32)
        return out

    def read_dynamic(self, name: str, step: int) -> np.ndarray | None:
        """Read one restart array for one report step, or None if absent."""
        return self.read_dynamic_many({name}, step).get(name)

    def dynamic_range(self, names: set[str]) -> tuple[dict[str, tuple[float, float]], int]:
        """Min/max of each named restart array over every step, in one pass.

        Returns the per-keyword range and the number of report steps scanned.
        A 72 MB Norne UNRST scans in ~0.06 s, so one pass per request would be
        tolerable; the point of doing all keywords at once is SOIL, which
        needs SWAT and SGAS to line up step by step.
        """
        ranges: dict[str, tuple[float, float]] = {}
        steps = 0
        if not self.unrst_path.is_file():
            return ranges, steps
        for kw, arr in resfo.read(str(self.unrst_path)):
            keyword = kw.strip()
            if keyword == "SEQNUM":
                steps += 1
                continue
            if keyword not in names or arr is None:
                continue
            values = np.asarray(arr)
            if values.size != self.nactive:
                continue
            finite = values[np.isfinite(values)]
            if finite.size == 0:
                continue
            lo, hi = float(finite.min()), float(finite.max())
            prev = ranges.get(keyword)
            ranges[keyword] = (lo, hi) if prev is None else (min(prev[0], lo), max(prev[1], hi))
        return ranges, steps

    def soil_range(self) -> tuple[tuple[float, float] | None, int]:
        """Range of the derived SOIL over every step.

        Computed per step rather than from the SWAT/SGAS extremes, since
        1 - min(SWAT) - min(SGAS) taken across different steps is not a value
        any cell ever held.
        """
        if not self.unrst_path.is_file():
            return None, 0
        lo, hi = math.inf, -math.inf
        steps = 0
        pending: dict[str, np.ndarray] = {}
        wanted = {"SWAT", "SGAS", "SSOL"}

        def flush() -> None:
            nonlocal lo, hi
            soil = derive_soil(pending.get("SWAT"), pending.get("SGAS"), pending.get("SSOL"))
            if soil is None:
                return
            finite = soil[np.isfinite(soil)]
            if finite.size:
                lo, hi = min(lo, float(finite.min())), max(hi, float(finite.max()))

        for kw, arr in resfo.read(str(self.unrst_path)):
            keyword = kw.strip()
            if keyword == "SEQNUM":
                flush()
                pending = {}
                steps += 1
                continue
            if keyword in wanted and arr is not None:
                values = np.asarray(arr)
                if values.size == self.nactive:
                    pending.setdefault(keyword, values.astype(np.float32))
        flush()
        return (None if lo > hi else (lo, hi)), steps


    # ------------------------------------------------------------------- wells

    def _restart_step_keywords(self, step: int, wanted: set[str]) -> dict[str, np.ndarray]:
        """Collect the requested keywords belonging to one report step."""
        out: dict[str, np.ndarray] = {}
        if not self.unrst_path.is_file():
            return out
        seen = -1
        for kw, arr in resfo.read(str(self.unrst_path)):
            name = kw.strip()
            if name == "SEQNUM":
                seen += 1
                if seen > step:
                    break
                out = {}
                continue
            if seen == step and name in wanted and arr is not None:
                out.setdefault(name, np.asarray(arr))
        return out if seen >= step else {}

    def wells(self, step: int) -> list[Well]:
        """Wells and their completions at one restart step.

        Reads the IWEL/ZWEL/ICON triple, whose record lengths come from
        INTEHEAD (nwells=16, ncwmax=17, niwelz=24, nzwelz=27, niconz=32) and
        are cross-checked against the actual array sizes. A well count of zero
        is normal for early steps: on Norne only 3 of the eventual 36 wells
        exist at step 0.

        Anything that does not validate degrades to fewer fields rather than
        to nonsense: an out-of-range completion is dropped, an implausible
        record length skips ICON entirely and leaves the well with a name,
        a type and no trajectory.
        """
        kws = self._restart_step_keywords(step, {"INTEHEAD", "IWEL", "ZWEL", "ICON"})
        head = kws.get("INTEHEAD")
        zwel, iwel = kws.get("ZWEL"), kws.get("IWEL")
        if head is None or head.size < 33 or zwel is None or iwel is None:
            return []

        nwells = int(head[16])
        if nwells <= 0 or zwel.size % nwells or iwel.size % nwells:
            return []
        nzwelz, niwelz = zwel.size // nwells, iwel.size // nwells
        if nzwelz < 1 or niwelz <= IWEL_TYPE:
            return []
        iwel_rec = iwel.reshape(nwells, niwelz)

        # ICON is optional: without a usable record length we still report the
        # wells, just with no completions and hence no trajectory.
        icon = kws.get("ICON")
        ncwmax = int(head[17])
        icon_rec = None
        if icon is not None and ncwmax > 0 and icon.size == nwells * ncwmax * int(head[32]):
            niconz = int(head[32])
            if niconz > ICON_STATUS:
                icon_rec = icon.reshape(nwells, ncwmax, niconz)

        out: list[Well] = []
        for w in range(nwells):
            raw = zwel[w * nzwelz]
            name = raw.decode(errors="replace").strip() if isinstance(raw, bytes) else str(raw).strip()
            if not name:
                continue
            rec = iwel_rec[w]
            hi, hj, hk = int(rec[IWEL_HEAD_I]) - 1, int(rec[IWEL_HEAD_J]) - 1, int(rec[IWEL_HEAD_K]) - 1
            if not (0 <= hi < self.nx and 0 <= hj < self.ny):
                hi = hj = hk = -1

            completions: list[Completion] = []
            if icon_rec is not None:
                for c in range(ncwmax):
                    conn = icon_rec[w, c]
                    if int(conn[ICON_INDEX]) <= 0:
                        continue
                    i = int(conn[ICON_I]) - 1
                    j = int(conn[ICON_J]) - 1
                    k = int(conn[ICON_K]) - 1
                    if not (0 <= i < self.nx and 0 <= j < self.ny and 0 <= k < self.nz):
                        continue
                    completions.append(Completion(
                        i=i, j=j, k=k,
                        cell=int(self.active_index[k, j, i]),
                        open=int(conn[ICON_STATUS]) > 0,
                    ))

            out.append(Well(
                name=name,
                type=WELL_TYPES.get(int(rec[IWEL_TYPE]), "unknown"),
                i=hi, j=hj, k=hk,
                completions=completions,
            ))
        return out

    def has_wells(self) -> bool:
        """True when any restart step carries a well definition."""
        if not self.unrst_path.is_file():
            return False
        for kw, arr in resfo.read(str(self.unrst_path)):
            if kw.strip() == "ZWEL" and arr is not None and np.asarray(arr).size:
                return True
        return False


def derive_soil(swat: np.ndarray | None, sgas: np.ndarray | None,
                ssol: np.ndarray | None = None) -> np.ndarray | None:
    """Oil saturation as ResInsight computes it: SOIL = 1 - SWAT - SGAS - SSOL.

    Returns None when neither water nor gas saturation is available, since
    a constant 1.0 would be misleading rather than merely approximate.
    """
    parts = [p for p in (swat, sgas, ssol) if p is not None]
    if not parts:
        return None
    soil = np.ones_like(parts[0], dtype=np.float32)
    for part in parts:
        soil -= part
    return soil


def statistics(values: np.ndarray) -> dict[str, float | list]:
    """Min/max/mean/p10/p90 plus a 50-bin histogram, ignoring non-finite values.

    p10/p90 follow ResInsight's convention: p10 is the value exceeded by 10%
    of cells (the 90th percentile of the sorted data), p90 likewise.
    """
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "p10": 0.0, "p90": 0.0,
                "sum": 0.0, "count": 0, "histogram": [], "bin_edges": []}
    vmin = float(finite.min())
    vmax = float(finite.max())
    hist, edges = np.histogram(finite, bins=50, range=(vmin, vmax) if vmax > vmin else (vmin - 0.5, vmin + 0.5))
    return {
        "min": vmin,
        "max": vmax,
        "mean": float(finite.mean()),
        "p10": float(np.percentile(finite, 90)),
        "p90": float(np.percentile(finite, 10)),
        "sum": float(finite.sum()),
        "count": int(finite.size),
        "histogram": hist.astype(int).tolist(),
        "bin_edges": edges.astype(float).tolist(),
    }
