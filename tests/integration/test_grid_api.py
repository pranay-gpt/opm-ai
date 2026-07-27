"""Integration tests for the 3D viewer's grid endpoints.

Wires a completed job into the real job store pointing at a fixture output
directory, the way tests/integration/test_api_hardening.py does, then drives
each endpoint through the FastAPI TestClient. No simulator run is needed:
the endpoints only ever read the EGRID/INIT/UNRST triple that the fixtures
already contain.
"""

import json
import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

from opm_ai.api.job_store import _job_store, create_job, set_job_completed, set_job_running
from opm_ai.api.routes import grid as grid_routes
from opm_ai.api.schemas import SimulationResultDTO
from opm_ai.api.server import create_app
from opm_ai.postprocess.grid3d import EclipseGrid
from opm_ai.postprocess.grid_mesh import to_viewer
from tests.conftest import FIXTURES_DIR
from tests.unit.test_grid3d import unpack_cells, unpack_mesh

SPE1_DIR = FIXTURES_DIR / "spe1"
NORNE_DIR = FIXTURES_DIR / "norne" / "opm-simulation-reference" / "flow_legacy"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as client:
        yield client


def _completed_job(job_id: str, output_dir) -> str:
    """Register a completed job whose output dir is a fixture directory."""
    if _job_store.get_job(job_id) is None:
        create_job(job_id)
        set_job_running(job_id)
        set_job_completed(job_id, SimulationResultDTO(
            success=True, output_dir=str(output_dir), returncode=0, duration_s=1.0,
        ))
    return job_id


@pytest.fixture(scope="module")
def spe1_job():
    return _completed_job("grid-spe1", SPE1_DIR)


@pytest.fixture(scope="module")
def norne_job():
    return _completed_job("grid-norne", NORNE_DIR)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Keep cache state from leaking between tests that assert on it."""
    grid_routes._mesh_cache.clear()
    grid_routes._cells_cache.clear()
    grid_routes._range_cache.clear()
    yield


def unpack_property(blob: bytes) -> tuple[dict, np.ndarray]:
    """Independent reader for the OPMP layout, per the contract table."""
    assert blob[:4] == b"OPMP"
    version, json_len = struct.unpack_from("<2I", blob, 4)
    assert version == 1
    meta = json.loads(blob[12:12 + json_len].decode())
    off = 12 + json_len + ((-json_len) % 4)
    values = np.frombuffer(blob, dtype="<f4", offset=off)
    return meta, values


# ---------------------------------------------------------------------- info


def test_info_spe1(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/info")
    assert r.status_code == 200, r.text
    data = r.json()
    assert (data["nx"], data["ny"], data["nz"]) == (10, 10, 3)
    assert data["active_cells"] == 300
    assert data["total_cells"] == 300
    assert data["unit_system"] == "FIELD"
    assert data["length_unit"] == "ft"
    assert len(data["origin"]) == 3
    assert len(data["bbox"]["min"]) == 3 and len(data["bbox"]["max"]) == 3
    assert all(lo < hi for lo, hi in zip(data["bbox"]["min"], data["bbox"]["max"]))
    assert data["static_properties"][:2] == ["PORO", "PERMX"]
    assert "PRESSURE" in data["dynamic_properties"]
    assert data["fault_face_count"] == 0
    assert data["has_wells"] is True
    assert len(data["time_steps"]) == 121
    assert data["time_steps"][0] == {"index": 0, "report": 0, "days": 0.0,
                                     "date": "2015-01-01"}


def test_info_lists_soil_as_derived(client, spe1_job):
    data = client.get(f"/api/results/{spe1_job}/grid/info").json()
    assert "SOIL" in data["dynamic_properties"]
    assert data["derived_properties"] == ["SOIL"]
    # TERNARY is a display mode, never a property.
    assert "TERNARY" not in data["dynamic_properties"]


@pytest.mark.slow
def test_info_norne(client, norne_job):
    data = client.get(f"/api/results/{norne_job}/grid/info").json()
    assert (data["nx"], data["ny"], data["nz"]) == (46, 112, 22)
    assert data["active_cells"] == 44431
    assert data["unit_system"] == "METRIC" and data["length_unit"] == "m"
    assert data["fault_face_count"] == 17720
    assert data["nnc_count"] == 15349
    assert len(data["time_steps"]) == 65
    assert data["has_wells"] is True


def test_info_unknown_job_404(client):
    assert client.get("/api/results/no-such-job/grid/info").status_code == 404


def test_info_job_without_egrid_404(client, tmp_path_factory):
    empty = tmp_path_factory.mktemp("no_grid")
    job = _completed_job("grid-empty", empty)
    r = client.get(f"/api/results/{job}/grid/info")
    assert r.status_code == 404
    assert "EGRID" in r.json()["detail"]


def test_info_unparseable_egrid_422(client, tmp_path_factory):
    bad = tmp_path_factory.mktemp("bad_grid")
    (bad / "JUNK.EGRID").write_bytes(b"not an eclipse file at all")
    job = _completed_job("grid-bad", bad)
    r = client.get(f"/api/results/{job}/grid/info")
    assert r.status_code == 422, r.text
    assert r.json()["detail"]


def test_grid_routes_do_not_shadow_snapshots(client, spe1_job):
    """The pre-existing snapshot route must still resolve on its own path."""
    r = client.get(f"/api/results/{spe1_job}/snapshots/nope.png")
    assert r.status_code == 404
    assert "Snapshot not found" in r.json()["detail"]


# ---------------------------------------------------------------------- mesh


def test_mesh_spe1_parses_and_matches_info(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/mesh")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"

    mesh = unpack_mesh(r.content)
    assert mesh["version"] == 1
    assert mesh["positions"].shape == (320 * 4, 3)
    assert mesh["indices"].size == 320 * 2 * 3
    assert mesh["edges"].size == 320 * 4 * 2
    assert mesh["cell_ids"].max() < 300
    assert set(np.unique(mesh["face_ids"])) <= {0, 1, 2, 3, 4, 5}

    info = client.get(f"/api/results/{spe1_job}/grid/info").json()
    assert np.allclose(mesh["origin"], info["origin"])
    assert np.allclose(mesh["positions"].min(axis=0), info["bbox"]["min"], atol=1e-3)
    assert np.allclose(mesh["positions"].max(axis=0), info["bbox"]["max"], atol=1e-3)


def test_mesh_etag_and_304(client, spe1_job):
    first = client.get(f"/api/results/{spe1_job}/grid/mesh")
    etag = first.headers["etag"]
    assert etag

    again = client.get(f"/api/results/{spe1_job}/grid/mesh",
                       headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag

    stale = client.get(f"/api/results/{spe1_job}/grid/mesh",
                       headers={"If-None-Match": '"stale"'})
    assert stale.status_code == 200
    assert stale.content == first.content


def test_mesh_include_inactive_is_a_distinct_cached_entry(client, spe1_job):
    a = client.get(f"/api/results/{spe1_job}/grid/mesh?include_inactive=false")
    b = client.get(f"/api/results/{spe1_job}/grid/mesh?include_inactive=true")
    assert a.headers["etag"] != b.headers["etag"]
    # SPE1 has no inactive cells, so the geometry is identical either way...
    assert unpack_mesh(a.content)["positions"].shape == \
        unpack_mesh(b.content)["positions"].shape
    # ...and crucially the origin must not move.
    assert np.array_equal(unpack_mesh(a.content)["origin"],
                          unpack_mesh(b.content)["origin"])
    assert len(grid_routes._mesh_cache) == 2


def test_mesh_cache_is_bounded(client, spe1_job, norne_job):
    for i in range(grid_routes._MESH_CACHE_MAX + 3):
        grid_routes._cache_put(grid_routes._mesh_cache, (i,), (b"", ""),
                               grid_routes._MESH_CACHE_MAX)
    assert len(grid_routes._mesh_cache) == grid_routes._MESH_CACHE_MAX


@pytest.mark.slow
def test_mesh_norne_size_and_shape(client, norne_job):
    r = client.get(f"/api/results/{norne_job}/grid/mesh")
    assert r.status_code == 200
    mesh = unpack_mesh(r.content)
    assert mesh["positions"].shape == (36324 * 4, 3)
    assert mesh["cell_ids"].max() < 44431
    # Origin-shifted coordinates must stay small enough for float32 precision.
    assert np.abs(mesh["positions"]).max() < 1e5


def test_mesh_unknown_job_404(client):
    assert client.get("/api/results/no-such-job/grid/mesh").status_code == 404


# --------------------------------------------------------------------- cells


def test_cells_spe1_matches_info_and_mesh(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/cells")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/octet-stream"

    cells = unpack_cells(r.content)
    info = client.get(f"/api/results/{spe1_job}/grid/info").json()
    assert cells["version"] == 1
    assert cells["ijk"].shape == (info["active_cells"], 3)
    assert cells["centers"].shape == (info["active_cells"], 3)
    assert cells["fault_faces"].shape == (info["active_cells"], 6)
    assert cells["nnc"].shape == (info["nnc_count"], 2)
    assert int(cells["fault_faces"].sum()) == info["fault_face_count"]
    assert np.allclose(cells["origin"], info["origin"])

    # i,j,k must span the declared dimensions and be in grid (k, j, i) order.
    assert cells["ijk"][:, 0].max() == info["nx"] - 1
    assert cells["ijk"][:, 1].max() == info["ny"] - 1
    assert cells["ijk"][:, 2].max() == info["nz"] - 1
    assert cells["ijk"][0].tolist() == [0, 0, 0]
    assert cells["ijk"][-1].tolist() == [info["nx"] - 1, info["ny"] - 1, info["nz"] - 1]


def test_cells_share_the_mesh_origin(client, spe1_job):
    """Every centre must land inside its own cell, in the mesh's frame.

    This is the assertion that catches an origin mismatch or a missed Z flip:
    both would push the centres out of the grid entirely, which is what makes
    NNC lines float away from the model.

    The box has to come from the cell's full eight corners, not from its
    vertices in the mesh: an interior cell contributes only the faces that
    survive culling, so a cell with just its K- top drawn has a mesh footprint
    that is flat in Z and its centre correctly sits half a cell below it.
    """
    grid = EclipseGrid(SPE1_DIR / "SPE1CASE1")
    mesh = unpack_mesh(client.get(f"/api/results/{spe1_job}/grid/mesh").content)
    cells = unpack_cells(client.get(f"/api/results/{spe1_job}/grid/cells").content)
    assert np.array_equal(np.asarray(cells["origin"]), np.asarray(mesh["origin"]))

    corners = to_viewer(grid.active_corners(), np.asarray(mesh["origin"]))
    lo, hi = corners.min(axis=1), corners.max(axis=1)
    centres = cells["centers"]
    outside = np.nonzero(
        np.any(centres < lo - 1e-3, axis=1) | np.any(centres > hi + 1e-3, axis=1)
    )[0]
    assert outside.size == 0, (
        f"{outside.size} centres outside their own cell, first is cell "
        f"{outside[0]}: {centres[outside[0]]} not in {lo[outside[0]]}..{hi[outside[0]]}"
    )


def test_cells_centres_sit_inside_the_mesh_bbox(client, spe1_job):
    mesh = unpack_mesh(client.get(f"/api/results/{spe1_job}/grid/mesh").content)
    cells = unpack_cells(client.get(f"/api/results/{spe1_job}/grid/cells").content)
    lo, hi = mesh["positions"].min(axis=0), mesh["positions"].max(axis=0)
    assert np.all(cells["centers"] >= lo - 1e-3)
    assert np.all(cells["centers"] <= hi + 1e-3)


@pytest.mark.slow
def test_cells_fault_mask_expands_onto_the_mesh_quads(client, norne_job):
    """The client-side join the TS `expandFaultMask` performs, in Python.

    Per-cell x per-face is only useful if (cell, face) off the mesh indexes it,
    so assert that join lands on real fault faces and finds some.
    """
    mesh = unpack_mesh(client.get(f"/api/results/{norne_job}/grid/mesh").content)
    cells = unpack_cells(client.get(f"/api/results/{norne_job}/grid/cells").content)

    quad_cell = mesh["cell_ids"][::4]
    quad_face = mesh["face_ids"][::4]
    per_quad = cells["fault_faces"][quad_cell, quad_face]
    assert per_quad.shape == quad_cell.shape
    # Norne has 17720 fault faces; not all of them are drawn (a fault face is
    # always drawn, so in fact all of them are), and nothing else may be.
    assert per_quad.sum() == 17720
    assert set(np.unique(per_quad)) <= {0, 1}


def test_cells_etag_and_304(client, spe1_job):
    first = client.get(f"/api/results/{spe1_job}/grid/cells")
    etag = first.headers["etag"]
    assert etag

    again = client.get(f"/api/results/{spe1_job}/grid/cells",
                       headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag

    stale = client.get(f"/api/results/{spe1_job}/grid/cells",
                       headers={"If-None-Match": '"stale"'})
    assert stale.status_code == 200
    assert stale.content == first.content


def test_cells_is_cached_and_bounded(client, spe1_job):
    assert len(grid_routes._cells_cache) == 0
    client.get(f"/api/results/{spe1_job}/grid/cells")
    assert len(grid_routes._cells_cache) == 1
    client.get(f"/api/results/{spe1_job}/grid/cells")
    assert len(grid_routes._cells_cache) == 1

    for i in range(grid_routes._CELLS_CACHE_MAX + 3):
        grid_routes._cache_put(grid_routes._cells_cache, (i,), (b"", ""),
                               grid_routes._CELLS_CACHE_MAX)
    assert len(grid_routes._cells_cache) == grid_routes._CELLS_CACHE_MAX


def test_cells_unknown_job_404(client):
    assert client.get("/api/results/no-such-job/grid/cells").status_code == 404


@pytest.mark.slow
def test_cells_norne(client, norne_job):
    cells = unpack_cells(client.get(f"/api/results/{norne_job}/grid/cells").content)
    assert cells["ijk"].shape == (44431, 3)
    assert cells["nnc"].shape == (15349, 2)
    assert int(cells["fault_faces"].sum()) == 17720
    # Origin-shifted centres must stay in float32 range, as the mesh does.
    assert np.abs(cells["centers"]).max() < 1e5


@pytest.mark.slow
def test_cells_norne_centres_inside_the_grid_bbox(client, norne_job):
    """The strongest registration check on a real faulted corner-point grid."""
    info = client.get(f"/api/results/{norne_job}/grid/info").json()
    lo = np.array(info["bbox"]["min"])
    hi = np.array(info["bbox"]["max"])
    cells = unpack_cells(client.get(f"/api/results/{norne_job}/grid/cells").content)
    assert np.all(cells["centers"] >= lo - 1e-3)
    assert np.all(cells["centers"] <= hi + 1e-3)


# ------------------------------------------------------------------ property


def test_property_static(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/property?name=PORO")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/octet-stream"
    meta, values = unpack_property(r.content)
    assert meta["name"] == "PORO"
    assert meta["kind"] == "static"
    assert meta["count"] == 300 == values.size
    assert meta["categorical"] is False
    assert meta["unit"] == ""
    assert meta["min"] == pytest.approx(0.3) and meta["max"] == pytest.approx(0.3)
    assert len(meta["histogram"]) == 50 and len(meta["bin_edges"]) == 51
    assert np.allclose(values, 0.3)


def test_property_categorical_flag(client, spe1_job):
    meta, _ = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=SATNUM").content
    )
    assert meta["categorical"] is True


def test_property_dynamic_step_changes_values(client, spe1_job):
    a, va = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=PRESSURE&step=0").content
    )
    b, vb = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=PRESSURE&step=100").content
    )
    assert a["kind"] == "dynamic" and a["step"] == 0
    assert b["step"] == 100
    assert a["unit"] == "psia"  # SPE1 is FIELD
    assert not np.allclose(va, vb)
    assert va.size == vb.size == 300


def test_property_soil_is_derived_and_consistent(client, spe1_job):
    meta, soil = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=SOIL&step=50").content
    )
    assert meta["kind"] == "derived"
    assert meta["name"] == "SOIL" and meta["step"] == 50
    _, swat = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=SWAT&step=50").content
    )
    _, sgas = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=SGAS&step=50").content
    )
    assert np.allclose(soil + swat + sgas, 1.0, atol=1e-5)
    assert meta["min"] == pytest.approx(float(soil.min()), rel=1e-6)


def test_property_statistics_agree_with_the_values(client, spe1_job):
    meta, values = unpack_property(
        client.get(f"/api/results/{spe1_job}/grid/property?name=PERMX").content
    )
    assert meta["min"] == pytest.approx(float(values.min()))
    assert meta["max"] == pytest.approx(float(values.max()))
    assert meta["mean"] == pytest.approx(float(values.mean()), rel=1e-6)
    assert meta["sum"] == pytest.approx(float(values.sum()), rel=1e-5)
    assert meta["count_finite"] == 300
    assert sum(meta["histogram"]) == 300


def test_property_unknown_name_404(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/property?name=NOTAPROP")
    assert r.status_code == 404
    assert "NOTAPROP" in r.json()["detail"]


def test_property_step_out_of_range_400(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/property?name=PRESSURE&step=9999")
    assert r.status_code == 400
    assert "out of range" in r.json()["detail"]


def test_property_negative_step_422(client, spe1_job):
    """FastAPI's own ge=0 validation catches this before the handler."""
    assert client.get(
        f"/api/results/{spe1_job}/grid/property?name=PRESSURE&step=-1"
    ).status_code == 422


def test_property_static_ignores_step(client, spe1_job):
    a = client.get(f"/api/results/{spe1_job}/grid/property?name=PORO&step=0")
    b = client.get(f"/api/results/{spe1_job}/grid/property?name=PORO&step=77")
    assert a.content == b.content


@pytest.mark.slow
def test_property_norne(client, norne_job):
    meta, values = unpack_property(
        client.get(f"/api/results/{norne_job}/grid/property?name=PRESSURE&step=0").content
    )
    assert values.size == 44431 == meta["count"]
    assert meta["unit"] == "bar"  # Norne is METRIC


# ------------------------------------------------------------- property range


def test_range_static_is_the_single_step_range(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/property/range?name=PORO")
    assert r.status_code == 200
    data = r.json()
    assert data == {"name": "PORO", "min": pytest.approx(0.3),
                    "max": pytest.approx(0.3), "steps_scanned": 1}


def test_range_dynamic_spans_every_step(client, spe1_job):
    data = client.get(
        f"/api/results/{spe1_job}/grid/property/range?name=PRESSURE"
    ).json()
    assert data["steps_scanned"] == 121
    assert data["min"] < data["max"]

    # Must bracket the single-step range at both ends of the history.
    for step in (0, 60, 120):
        meta, _ = unpack_property(client.get(
            f"/api/results/{spe1_job}/grid/property?name=PRESSURE&step={step}"
        ).content)
        assert data["min"] <= meta["min"] and data["max"] >= meta["max"]


def test_range_soil(client, spe1_job):
    data = client.get(f"/api/results/{spe1_job}/grid/property/range?name=SOIL").json()
    assert data["name"] == "SOIL"
    assert data["steps_scanned"] == 121
    assert data["min"] <= data["max"]


def test_range_is_cached(client, spe1_job):
    assert len(grid_routes._range_cache) == 0
    first = client.get(f"/api/results/{spe1_job}/grid/property/range?name=PRESSURE")
    assert len(grid_routes._range_cache) == 1
    second = client.get(f"/api/results/{spe1_job}/grid/property/range?name=PRESSURE")
    assert first.json() == second.json()
    assert len(grid_routes._range_cache) == 1


def test_range_cache_key_includes_mtime(client, spe1_job):
    """A re-run of the same job must not serve the previous run's range."""
    stem = grid_routes.find_case(SPE1_DIR)
    key_now = (str(stem), grid_routes._stamp(stem.with_suffix(".UNRST")),
               grid_routes._stamp(stem.with_suffix(".INIT")), "PRESSURE")
    client.get(f"/api/results/{spe1_job}/grid/property/range?name=PRESSURE")
    assert key_now in grid_routes._range_cache


def test_range_unknown_property_404(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/property/range?name=NOPE")
    assert r.status_code == 404


def test_range_route_is_not_shadowed_by_property(client, spe1_job):
    """/grid/property/range must not be parsed as /grid/property."""
    r = client.get(f"/api/results/{spe1_job}/grid/property/range?name=PORO")
    assert r.headers["content-type"].startswith("application/json")


@pytest.mark.slow
def test_range_norne_pressure(client, norne_job):
    data = client.get(
        f"/api/results/{norne_job}/grid/property/range?name=PRESSURE"
    ).json()
    assert data["steps_scanned"] == 65
    assert data["min"] == pytest.approx(67.33113, rel=1e-5)
    assert data["max"] == pytest.approx(612.75916, rel=1e-5)


# --------------------------------------------------------------------- wells


def test_wells_spe1(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/wells?step=120")
    assert r.status_code == 200
    data = r.json()
    assert data["step"] == 120
    wells = {w["name"]: w for w in data["wells"]}
    assert set(wells) == {"PROD", "INJ"}

    prod = wells["PROD"]
    assert prod["type"] == "producer"
    assert (prod["i"], prod["j"], prod["k"]) == (9, 9, 2)
    assert len(prod["completions"]) == 1
    assert prod["completions"][0]["cell"] == 299  # last active cell
    assert prod["completions"][0]["open"] is True
    assert wells["INJ"]["type"] == "gas_injector"


def test_wells_empty_at_step_zero(client, spe1_job):
    """SPE1 declares no wells in the initial restart record; that is not an error."""
    r = client.get(f"/api/results/{spe1_job}/grid/wells?step=0")
    assert r.status_code == 200
    assert r.json() == {"step": 0, "wells": []}


def test_wells_trajectory_is_head_to_toe(client, spe1_job):
    well = client.get(
        f"/api/results/{spe1_job}/grid/wells?step=120"
    ).json()["wells"][0]
    traj = well["trajectory"]
    assert len(traj) == len(well["completions"]) + 1  # head point prepended
    assert traj[0] == well["head"]
    # Viewer Z points up, so the trajectory descends monotonically.
    zs = [p[2] for p in traj]
    assert zs == sorted(zs, reverse=True)
    # The head sits strictly above the shallowest completion.
    assert traj[0][2] > well["completions"][0]["center"][2]
    # ...and directly over it in plan view.
    assert traj[0][:2] == pytest.approx(traj[1][:2])


def test_wells_share_the_mesh_origin(client, spe1_job):
    """A completion centre must land inside the meshed cell's bounding box."""
    mesh = unpack_mesh(client.get(f"/api/results/{spe1_job}/grid/mesh").content)
    wells = client.get(f"/api/results/{spe1_job}/grid/wells?step=120").json()["wells"]

    for well in wells:
        for comp in well["completions"]:
            verts = mesh["positions"][mesh["cell_ids"] == comp["cell"]]
            assert verts.size, f"cell {comp['cell']} is not in the mesh"
            lo, hi = verts.min(axis=0), verts.max(axis=0)
            centre = np.array(comp["center"])
            assert np.all(centre >= lo - 1e-3) and np.all(centre <= hi + 1e-3), (
                f"{well['name']} completion at {centre} is outside cell box {lo}..{hi}"
            )


def test_wells_step_out_of_range_400(client, spe1_job):
    r = client.get(f"/api/results/{spe1_job}/grid/wells?step=9999")
    assert r.status_code == 400
    assert "out of range" in r.json()["detail"]


def test_wells_unknown_job_404(client):
    assert client.get("/api/results/nope/grid/wells").status_code == 404


@pytest.mark.slow
def test_wells_norne_grow_over_time(client, norne_job):
    early = client.get(f"/api/results/{norne_job}/grid/wells?step=0").json()
    late = client.get(f"/api/results/{norne_job}/grid/wells?step=64").json()
    assert len(early["wells"]) == 3
    assert len(late["wells"]) == 36

    names = [w["name"] for w in late["wells"]]
    assert {"C-4H", "B-2H", "D-1H"} <= set(names)
    assert len(set(names)) == 36

    for well in late["wells"]:
        assert well["completions"]
        assert len(well["trajectory"]) == len(well["completions"]) + 1
        zs = [p[2] for p in well["trajectory"]]
        assert zs == sorted(zs, reverse=True)
        assert all(c["cell"] >= 0 for c in well["completions"])


@pytest.mark.slow
def test_wells_norne_sit_inside_the_mesh_bbox(client, norne_job):
    """The strongest registration check: wells must live inside the drawn grid."""
    info = client.get(f"/api/results/{norne_job}/grid/info").json()
    lo = np.array(info["bbox"]["min"])
    hi = np.array(info["bbox"]["max"])
    wells = client.get(f"/api/results/{norne_job}/grid/wells?step=64").json()["wells"]
    assert wells

    for well in wells:
        for comp in well["completions"]:
            centre = np.array(comp["center"])
            assert np.all(centre >= lo) and np.all(centre <= hi), (
                f"{well['name']} completion {centre} outside grid bbox {lo}..{hi}"
            )
        # Only the lifted head point may exceed the top of the grid, and only
        # in Z: a well that drifted in X/Y would be a coordinate-frame bug.
        head = np.array(well["head"])
        assert np.all(head[:2] >= lo[:2]) and np.all(head[:2] <= hi[:2])
        assert head[2] > lo[2]
