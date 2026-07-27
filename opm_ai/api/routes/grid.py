"""Grid routes: GET /api/results/{job_id}/grid/* -> geometry, properties, wells.

Thin adapters over opm_ai.postprocess.grid3d / grid_mesh. Every handler runs
its parsing in a thread executor because resfo reads are CPU-bound and would
otherwise stall the event loop for the whole request.

Route order note: all paths here carry a literal "grid" segment, so none of
them can collide with the existing /results/{job_id}/snapshots/{filename} in
results.py, and /grid/property/range cannot be swallowed by /grid/property
(neither has a path parameter to absorb the extra segment). The router is
nevertheless registered before results.py in server.py so the more specific
paths are matched first regardless of future additions there.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request, Response

from opm_ai.api.routes.results import _completed_job_output_dir
from opm_ai.api.schemas import (
    GridBBox,
    GridInfoResponse,
    GridRangeResponse,
    GridTimeStep,
    WellCompletion,
    WellDTO,
    WellsResponse,
)
from opm_ai.postprocess import grid_mesh
from opm_ai.postprocess.grid3d import (
    CATEGORICAL,
    LENGTH_UNIT,
    STATIC_PREFERRED,
    EclipseGrid,
    GridError,
    derive_soil,
    find_case,
    statistics,
)

router = APIRouter()

# Bounded LRU caches. A Norne mesh is ~6 MB, so four of them is ~25 MB worst
# case; a range entry is three numbers. Keys carry the source file's mtime so
# a re-run of the same job invalidates without any explicit eviction call.
_MESH_CACHE_MAX = 4
_CELLS_CACHE_MAX = 4
_RANGE_CACHE_MAX = 32
_mesh_cache: OrderedDict[tuple, tuple[bytes, str]] = OrderedDict()
# Per-cell companion blob: ~30 bytes per active cell, so 1.3 MB for Norne.
_cells_cache: OrderedDict[tuple, tuple[bytes, str]] = OrderedDict()
_range_cache: OrderedDict[tuple, tuple[float, float, int]] = OrderedDict()
_cache_lock = Lock()

# Best-effort display units, keyed by unit system. Anything not listed is
# reported as "" rather than guessed, which the legend renders unlabelled.
_DIMENSIONLESS = {"PORO", "NTG", "SWAT", "SGAS", "SOIL", "SSOL", "SATNUM", "PVTNUM",
                  "EQLNUM", "FIPNUM", "IMBNUM", "ENDNUM", "FLUXNUM", "ROCKNUM"}
_UNITS: dict[str, dict[str, str]] = {
    "METRIC": {"PRESSURE": "bar", "TEMP": "degC", "PERMX": "mD", "PERMY": "mD",
               "PERMZ": "mD", "PORV": "rm3", "RS": "sm3/sm3", "RV": "sm3/sm3"},
    "FIELD": {"PRESSURE": "psia", "TEMP": "degF", "PERMX": "mD", "PERMY": "mD",
              "PERMZ": "mD", "PORV": "rb", "RS": "Mscf/stb", "RV": "stb/Mscf"},
}


def _cache_get(cache: OrderedDict, key: tuple) -> Any:
    with _cache_lock:
        if key not in cache:
            return None
        cache.move_to_end(key)
        return cache[key]


def _cache_put(cache: OrderedDict, key: tuple, value: Any, limit: int) -> None:
    with _cache_lock:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)


def _stamp(path: Path) -> int:
    """File mtime in ns, or 0 when the file is absent."""
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _case_stem(job_id: str) -> Path:
    """Case stem of a completed job, or 404 when the run produced no grid."""
    output_dir = _completed_job_output_dir(job_id)
    stem = find_case(output_dir)
    if stem is None:
        raise HTTPException(
            status_code=404, detail=f"No .EGRID file in the output of job {job_id}"
        )
    return stem


def _open_grid(stem: Path) -> EclipseGrid:
    """Parse a case, mapping the expected failures onto 404/422."""
    try:
        return EclipseGrid(stem)
    except GridError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Cannot read {stem.name}: {exc}"
        ) from exc


async def _in_thread(fn: Callable[[], Any]) -> Any:
    """Run a blocking parse off the event loop."""
    return await asyncio.get_event_loop().run_in_executor(None, fn)


def _order_static(names: list[str]) -> list[str]:
    """Preferred keywords first in ResInsight's order, then the rest sorted."""
    preferred = [n for n in STATIC_PREFERRED if n in names]
    rest = sorted(set(names) - set(preferred))
    return preferred + rest


def _dynamic_with_soil(names: list[str]) -> tuple[list[str], list[str]]:
    """Add the derived SOIL to the restart keyword list when it is computable."""
    derived = ["SOIL"] if ({"SWAT", "SGAS"} & set(names)) and "SOIL" not in names else []
    return sorted(set(names) | set(derived)), derived


# ------------------------------------------------------------------------ info


@router.get("/results/{job_id}/grid/info", response_model=GridInfoResponse)
async def get_grid_info(job_id: str) -> GridInfoResponse:
    """Dimensions, property catalogue and time steps of the job's grid."""
    stem = _case_stem(job_id)

    def work() -> GridInfoResponse:
        grid = _open_grid(stem)
        origin = grid_mesh.surface_origin(grid)
        corners = grid_mesh.to_viewer(grid.active_corners().reshape(-1, 3), origin)

        static_names = _order_static(list(grid.static_properties()))
        dynamic_names, derived = _dynamic_with_soil(grid.dynamic_property_names())
        unit = grid.unit_system()

        return GridInfoResponse(
            nx=grid.nx, ny=grid.ny, nz=grid.nz,
            active_cells=grid.nactive,
            total_cells=grid.ncells,
            unit_system=unit,
            length_unit=LENGTH_UNIT.get(unit, ""),
            origin=[float(v) for v in origin],
            bbox=GridBBox(
                min=[float(v) for v in corners.min(axis=0)],
                max=[float(v) for v in corners.max(axis=0)],
            ),
            static_properties=static_names,
            dynamic_properties=dynamic_names,
            derived_properties=derived,
            time_steps=[
                GridTimeStep(index=s.index, report=s.report, days=s.days, date=s.date)
                for s in grid.time_steps()
            ],
            fault_face_count=int(grid.fault_faces().sum()),
            nnc_count=int(grid.nnc_pairs().shape[0]),
            has_wells=grid.has_wells(),
        )

    return await _in_thread(work)


# ------------------------------------------------------------------------ mesh


@router.get("/results/{job_id}/grid/mesh")
async def get_grid_mesh(
    job_id: str,
    request: Request,
    include_inactive: bool = Query(False, description="Mesh inactive cells too"),
) -> Response:
    """The drawable skin of the grid as the binary OPMG blob."""
    stem = _case_stem(job_id)
    key = (str(stem), _stamp(stem.with_suffix(".EGRID")),
           include_inactive, grid_mesh.MESH_FORMAT_VERSION)

    cached = _cache_get(_mesh_cache, key)
    if cached is None:
        def work() -> tuple[bytes, str]:
            grid = _open_grid(stem)
            surface = grid_mesh.build_surface(grid, include_inactive=include_inactive)
            blob = grid_mesh.pack_mesh(surface, grid_mesh.build_edges(surface))
            # The blob is a pure function of the key, so hashing the key is as
            # strong an ETag as hashing 6 MB of vertices and far cheaper.
            etag = '"%s"' % hashlib.sha256(repr(key).encode()).hexdigest()[:32]
            return blob, etag

        cached = await _in_thread(work)
        _cache_put(_mesh_cache, key, cached, _MESH_CACHE_MAX)

    blob, etag = cached
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"ETag": etag, "Cache-Control": "private, max-age=0, must-revalidate"},
    )


# ----------------------------------------------------------------------- cells


@router.get("/results/{job_id}/grid/cells")
async def get_grid_cells(job_id: str, request: Request) -> Response:
    """Per-active-cell i/j/k, centres, fault faces and NNC pairs as OPMC.

    The mesh only carries a flat active-cell index, so without this the client
    cannot range-filter on I/J/K, label a pick, shade faults, or draw NNCs.
    Independent of include_inactive: everything is keyed by active cell.
    """
    stem = _case_stem(job_id)
    key = (str(stem), _stamp(stem.with_suffix(".EGRID")),
           grid_mesh.CELLS_FORMAT_VERSION)

    cached = _cache_get(_cells_cache, key)
    if cached is None:
        def work() -> tuple[bytes, str]:
            grid = _open_grid(stem)
            blob = grid_mesh.pack_cells(grid_mesh.build_cells(grid))
            # Same reasoning as the mesh ETag: the blob is a pure function of
            # the key, so hashing the key is as strong and far cheaper.
            etag = '"%s"' % hashlib.sha256(repr(key).encode()).hexdigest()[:32]
            return blob, etag

        cached = await _in_thread(work)
        _cache_put(_cells_cache, key, cached, _CELLS_CACHE_MAX)

    blob, etag = cached
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=blob,
        media_type="application/octet-stream",
        headers={"ETag": etag, "Cache-Control": "private, max-age=0, must-revalidate"},
    )


# -------------------------------------------------------------------- property


def _resolve_property(grid: EclipseGrid, name: str, step: int) -> tuple[np.ndarray, str]:
    """Values and kind for one property, raising 404/400 for the bad cases."""
    static = grid.static_properties()
    if name in static:
        return static[name], "static"

    steps = grid.time_steps()
    dynamic_names, derived = _dynamic_with_soil(grid.dynamic_property_names())
    if name not in dynamic_names:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown property {name!r}; available: "
                   f"{', '.join(_order_static(list(static)) + dynamic_names)}",
        )
    if not steps:
        raise HTTPException(status_code=404, detail=f"No restart data for {name!r}")
    if not 0 <= step < len(steps):
        raise HTTPException(
            status_code=400,
            detail=f"Step {step} out of range: this case has {len(steps)} report steps",
        )

    if name in derived:  # SOIL
        parts = grid.read_dynamic_many({"SWAT", "SGAS", "SSOL"}, step)
        values = derive_soil(parts.get("SWAT"), parts.get("SGAS"), parts.get("SSOL"))
        if values is None:
            raise HTTPException(
                status_code=404, detail=f"Cannot derive SOIL at step {step}: no saturations"
            )
        return values, "derived"

    values = grid.read_dynamic(name, step)
    if values is None:
        raise HTTPException(
            status_code=404, detail=f"Property {name!r} is absent from step {step}"
        )
    return values, "dynamic"


@router.get("/results/{job_id}/grid/property")
async def get_grid_property(
    job_id: str,
    name: str = Query(..., description="Property keyword, e.g. PORO or SOIL"),
    step: int = Query(0, ge=0, description="Report step; ignored for static properties"),
) -> Response:
    """One per-active-cell array plus its statistics, as the binary OPMP blob."""
    stem = _case_stem(job_id)

    def work() -> bytes:
        grid = _open_grid(stem)
        values, kind = _resolve_property(grid, name, step)
        stats = statistics(values)
        unit_system = grid.unit_system()
        meta = {
            "name": name,
            "step": 0 if kind == "static" else step,
            "count": int(values.size),
            "kind": kind,
            "categorical": name in CATEGORICAL,
            "unit": "" if name in _DIMENSIONLESS else _UNITS.get(unit_system, {}).get(name, ""),
            "min": stats["min"], "max": stats["max"], "mean": stats["mean"],
            "p10": stats["p10"], "p90": stats["p90"], "sum": stats["sum"],
            "count_finite": stats["count"],
            "histogram": stats["histogram"], "bin_edges": stats["bin_edges"],
        }
        payload = json.dumps(meta).encode()
        pad = (-len(payload)) % 4
        header = np.array([1, len(payload)], dtype="<u4")
        return b"".join([
            b"OPMP", header.tobytes(), payload, b"\x00" * pad, grid_mesh.pack_values(values)
        ])

    return Response(content=await _in_thread(work), media_type="application/octet-stream")


@router.get("/results/{job_id}/grid/property/range", response_model=GridRangeResponse)
async def get_grid_property_range(
    job_id: str,
    name: str = Query(..., description="Property keyword to scan"),
) -> GridRangeResponse:
    """Value range of one property across every report step."""
    stem = _case_stem(job_id)
    key = (str(stem), _stamp(stem.with_suffix(".UNRST")),
           _stamp(stem.with_suffix(".INIT")), name)

    cached = _cache_get(_range_cache, key)
    if cached is None:
        def work() -> tuple[float, float, int]:
            grid = _open_grid(stem)
            static = grid.static_properties()
            if name in static:
                stats = statistics(static[name])
                return float(stats["min"]), float(stats["max"]), 1

            dynamic_names, derived = _dynamic_with_soil(grid.dynamic_property_names())
            if name not in dynamic_names:
                raise HTTPException(
                    status_code=404, detail=f"Unknown property {name!r} for this case"
                )
            if name in derived:  # SOIL, recomputed per step
                span, steps = grid.soil_range()
            else:
                ranges, steps = grid.dynamic_range({name})
                span = ranges.get(name)
            if span is None:
                raise HTTPException(
                    status_code=404, detail=f"No finite values of {name!r} in any step"
                )
            return span[0], span[1], steps

        cached = await _in_thread(work)
        _cache_put(_range_cache, key, cached, _RANGE_CACHE_MAX)

    vmin, vmax, steps = cached
    return GridRangeResponse(name=name, min=vmin, max=vmax, steps_scanned=steps)


# ----------------------------------------------------------------------- wells


@router.get("/results/{job_id}/grid/wells", response_model=WellsResponse)
async def get_grid_wells(
    job_id: str,
    step: int = Query(0, ge=0, description="Report step to read the well state from"),
) -> WellsResponse:
    """Wells and trajectories at one report step, in mesh coordinates."""
    stem = _case_stem(job_id)

    def work() -> WellsResponse:
        grid = _open_grid(stem)
        steps = grid.time_steps()
        if steps and not 0 <= step < len(steps):
            raise HTTPException(
                status_code=400,
                detail=f"Step {step} out of range: this case has {len(steps)} report steps",
            )

        # Exactly the transform build_surface applies to the mesh vertices, via
        # the same two helpers, so wells and grid share one coordinate frame.
        origin = grid_mesh.surface_origin(grid)
        corners = grid.corners()
        centres = corners.mean(axis=3)  # (nz, ny, nx, 3), grid coordinates

        # Lift the head this far above the shallowest completion so the stem is
        # visible above the reservoir. Scaled to the model so it works for a
        # 30 ft SPE1 layer and a 300 m Norne column alike.
        zs = grid.active_corners()[..., 2]
        lift = max(float(zs.max() - zs.min()) * 0.05, 1e-6)

        out: list[WellDTO] = []
        for well in grid.wells(step):
            points = [centres[c.k, c.j, c.i] for c in well.completions]
            if not points and 0 <= well.i < grid.nx and 0 <= well.j < grid.ny:
                # No usable ICON record: fall back to the top active cell of the
                # head column so the well at least shows in the right place.
                column = np.nonzero(grid.actnum[:, well.j, well.i])[0]
                if column.size:
                    points = [centres[int(column[0]), well.j, well.i]]

            trajectory: list[list[float]] = []
            head: list[float] = []
            if points:
                # Shallowest first: depth is positive downward in grid coords.
                ordered = sorted(points, key=lambda p: float(p[2]))
                top = np.array(ordered[0], dtype=np.float64)
                top[2] -= lift
                view = grid_mesh.to_viewer(np.array([top, *ordered]), origin)
                trajectory = view.tolist()
                head = trajectory[0]

            out.append(WellDTO(
                name=well.name,
                type=well.type,
                head=head,
                i=well.i, j=well.j, k=well.k,
                trajectory=trajectory,
                completions=[
                    WellCompletion(
                        i=c.i, j=c.j, k=c.k, cell=c.cell,
                        center=grid_mesh.to_viewer(centres[c.k, c.j, c.i], origin).tolist(),
                        open=c.open,
                    )
                    for c in well.completions
                ],
            ))
        return WellsResponse(step=step, wells=out)

    return await _in_thread(work)
