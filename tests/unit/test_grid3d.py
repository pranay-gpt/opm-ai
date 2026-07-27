"""Geometry and packing checks for the 3D viewer's grid modules.

Everything here runs against the real fixtures: SPE1 (10x10x3 cartesian,
FIELD) and Norne (46x112x22 corner-point with faults, 44431 active cells).

The load-bearing check is that cell-centre depth derived from COORD/ZCORN
reproduces the INIT DEPTH array the simulator wrote. If the corner ordering or
the pillar interpolation were wrong, that agreement would collapse; no other
assertion here would necessarily notice.
"""

import json
import struct

import numpy as np
import pytest

from opm_ai.postprocess import grid_mesh as gm
from opm_ai.postprocess.grid3d import (
    EclipseGrid,
    GridError,
    derive_soil,
    find_case,
    statistics,
)
from tests.conftest import FIXTURES_DIR

SPE1_STEM = FIXTURES_DIR / "spe1" / "SPE1CASE1"
NORNE_STEM = (
    FIXTURES_DIR / "norne" / "opm-simulation-reference" / "flow_legacy" / "NORNE_ATW2013"
)

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def spe1():
    return EclipseGrid(SPE1_STEM)


@pytest.fixture(scope="module")
def norne():
    return EclipseGrid(NORNE_STEM)


# ------------------------------------------------------------------- geometry


def test_spe1_dimensions(spe1):
    assert (spe1.nx, spe1.ny, spe1.nz) == (10, 10, 3)
    assert spe1.ncells == 300
    assert spe1.nactive == 300


def test_norne_dimensions(norne):
    assert (norne.nx, norne.ny, norne.nz) == (46, 112, 22)
    assert norne.ncells == 46 * 112 * 22
    assert norne.nactive == 44431


def test_missing_egrid_raises(tmp_path):
    with pytest.raises(GridError, match="No EGRID"):
        EclipseGrid(tmp_path / "NOPE")


def test_find_case(tmp_path):
    assert find_case(tmp_path) is None
    (tmp_path / "M.EGRID").write_bytes(b"\x00")
    assert find_case(tmp_path).name == "M"


def test_spe1_centre_depth_matches_init_exactly(spe1):
    """Cell-centre Z from the corners must reproduce the INIT DEPTH array."""
    depth = spe1.static_properties()["DEPTH"]
    centre_z = spe1.cell_centres()[:, 2]
    assert np.allclose(centre_z, depth, atol=1e-4), (
        f"max |dz| = {np.abs(centre_z - depth).max()}"
    )


@pytest.mark.slow
def test_norne_centre_depth_matches_init(norne):
    """Same check on a faulted corner-point grid; tolerance is float32 DEPTH."""
    depth = norne.static_properties()["DEPTH"]
    centre_z = norne.cell_centres()[:, 2]
    assert np.abs(centre_z - depth).max() < 1e-3


def test_spe1_volumes_match_dx_dy_dz(spe1):
    """On a cartesian grid the tetrahedral decomposition must be exact."""
    props = spe1.static_properties()
    expect = props["DX"].astype(np.float64) * props["DY"] * props["DZ"]
    got = spe1.cell_volumes()
    assert np.allclose(got, expect, rtol=1e-9), (
        f"max rel error {np.abs(got / expect - 1).max()}"
    )


def test_spe1_ijk_of_active_is_grid_order(spe1):
    ijk = spe1.ijk_of_active()
    assert ijk.shape == (300, 3)
    # i varies fastest, then j, then k.
    assert tuple(ijk[0]) == (0, 0, 0)
    assert tuple(ijk[1]) == (1, 0, 0)
    assert tuple(ijk[10]) == (0, 1, 0)
    assert tuple(ijk[100]) == (0, 0, 1)


def test_spe1_has_no_faults(spe1):
    """A cartesian grid is conforming everywhere."""
    assert spe1.fault_faces().sum() == 0


@pytest.mark.slow
def test_norne_fault_and_nnc_counts(norne):
    assert int(norne.fault_faces().sum()) == 17720
    assert norne.nnc_pairs().shape == (15349, 2)


# ------------------------------------------------------------------ surfacing


def test_spe1_surface_is_the_outer_shell(spe1):
    """300 cells with no faults leaves only the box's outside: 320 quads."""
    surface = gm.build_surface(spe1)
    nq = surface["quad_cell"].shape[0]
    # 2*(10*10) top+bottom + 4 sides of 10*3.
    assert nq == 2 * 10 * 10 + 4 * 10 * 3 == 320
    assert surface["positions"].shape == (nq * 4, 3)
    assert surface["indices"].shape == (nq * 2, 3)


@pytest.mark.slow
def test_norne_face_culling_reduces_candidates(norne):
    """44431 active cells offer 266586 faces; only the visible skin survives."""
    assert norne.nactive * 6 == 266586
    assert int(gm.visible_faces(norne).sum()) == 36324
    assert gm.build_surface(norne)["quad_cell"].shape[0] == 36324


def test_surface_z_is_flipped_up(spe1):
    """Viewer Z must increase upward while grid depth increases downward."""
    surface = gm.build_surface(spe1)
    origin = surface["origin"]
    deep = spe1.cell_centres()[:, 2].max()
    shallow = spe1.cell_centres()[:, 2].min()
    assert deep > shallow
    assert gm.to_viewer(np.array([0.0, 0.0, deep]), origin)[2] < \
        gm.to_viewer(np.array([0.0, 0.0, shallow]), origin)[2]


def test_origin_is_independent_of_include_inactive(norne):
    """Toggling inactive cells must not move the model or wells drift off it."""
    a = gm.build_surface(norne, include_inactive=False)["origin"]
    b = gm.build_surface(norne, include_inactive=True)["origin"]
    assert np.array_equal(a, b)
    assert np.array_equal(a, gm.surface_origin(norne))


def test_to_viewer_matches_surface_vertices(spe1):
    """The mesh vertices are exactly to_viewer() of the raw corners."""
    surface = gm.build_surface(spe1)
    origin = surface["origin"]
    expect = gm.to_viewer(spe1.corners()[0, 0, 0, 4, :].copy(), origin)
    # Corner 4 of cell (0,0,0) is on its K+ (deepest) face; find that vertex.
    hits = np.isclose(surface["positions"], expect.astype(np.float32), atol=1e-3).all(axis=1)
    assert hits.any()


def test_edges_outline_every_quad(spe1):
    surface = gm.build_surface(spe1)
    edges = gm.build_edges(surface)
    assert edges.shape == (surface["quad_cell"].shape[0] * 4, 2)


# ------------------------------------------------------------------- packing


def unpack_mesh(blob: bytes) -> dict:
    """Independent reader for the OPMG layout the TypeScript side implements.

    Written from the contract table rather than from pack_mesh, so a change to
    either side that the other does not follow shows up here.
    """
    assert blob[:4] == b"OPMG"
    version, nverts, nindices, nedges = struct.unpack_from("<4I", blob, 4)
    origin = struct.unpack_from("<3d", blob, 20)
    off = 44

    def take(count, dtype, itemsize):
        nonlocal off
        arr = np.frombuffer(blob, dtype=dtype, count=count, offset=off)
        off += count * itemsize
        return arr

    positions = take(nverts * 3, "<f4", 4).reshape(-1, 3)
    normals = take(nverts * 3, "<f4", 4).reshape(-1, 3)
    cell_ids = take(nverts, "<i4", 4)
    face_ids = take(nverts, np.uint8, 1)
    off += (-nverts) % 4  # face ids are padded to a 4-byte boundary
    indices = take(nindices, "<u4", 4)
    edges = take(nedges, "<u4", 4)
    assert off == len(blob), f"{len(blob) - off} trailing bytes"
    return {
        "version": version, "origin": origin, "positions": positions,
        "normals": normals, "cell_ids": cell_ids, "face_ids": face_ids,
        "indices": indices, "edges": edges,
    }


def test_pack_mesh_round_trips(spe1):
    surface = gm.build_surface(spe1)
    edges = gm.build_edges(surface)
    got = unpack_mesh(gm.pack_mesh(surface, edges))

    assert got["version"] == gm.MESH_FORMAT_VERSION
    assert np.allclose(got["origin"], surface["origin"])
    assert np.array_equal(got["positions"], surface["positions"])
    assert np.array_equal(got["normals"], surface["normals"])
    assert np.array_equal(got["cell_ids"], surface["cell_of_vertex"])
    assert np.array_equal(got["face_ids"], surface["face_of_vertex"])
    assert np.array_equal(got["indices"], surface["indices"].reshape(-1))
    assert np.array_equal(got["edges"], edges.reshape(-1))
    assert got["indices"].max() < got["positions"].shape[0]
    assert got["cell_ids"].max() < spe1.nactive
    assert set(np.unique(got["face_ids"])) <= {0, 1, 2, 3, 4, 5}


def test_pack_mesh_padding_holds_for_odd_vertex_counts():
    """n_vertices not a multiple of 4 still leaves the sections aligned."""
    nq = 3  # 12 vertices... use 1 quad to get 4, then trim to force padding.
    surface = {
        "positions": np.zeros((nq * 4 - 1, 3), dtype=np.float32),
        "normals": np.zeros((nq * 4 - 1, 3), dtype=np.float32),
        "cell_of_vertex": np.zeros(nq * 4 - 1, dtype=np.int32),
        "face_of_vertex": np.zeros(nq * 4 - 1, dtype=np.uint8),
        "indices": np.zeros((1, 3), dtype=np.int32),
        "quad_cell": np.zeros(nq, dtype=np.int32),
        "origin": np.zeros(3),
    }
    got = unpack_mesh(gm.pack_mesh(surface, None))
    assert got["positions"].shape == (11, 3)
    assert got["edges"].size == 0


def unpack_cells(blob: bytes) -> dict:
    """Independent reader for the OPMC layout, from the contract table."""
    assert blob[:4] == b"OPMC"
    version, ncells, nnncs = struct.unpack_from("<3I", blob, 4)
    origin = struct.unpack_from("<3d", blob, 16)
    off = 40

    def take(count, dtype, itemsize):
        nonlocal off
        arr = np.frombuffer(blob, dtype=dtype, count=count, offset=off)
        off += count * itemsize
        return arr

    ijk = take(ncells * 3, "<i4", 4).reshape(-1, 3)
    centers = take(ncells * 3, "<f4", 4).reshape(-1, 3)
    faults = take(ncells * 6, np.uint8, 1).reshape(-1, 6)
    off += (-(ncells * 6)) % 4  # fault bytes are padded to a 4-byte boundary
    nnc = take(nnncs * 2, "<i4", 4).reshape(-1, 2)
    assert off == len(blob), f"{len(blob) - off} trailing bytes"
    return {"version": version, "origin": origin, "ijk": ijk,
            "centers": centers, "fault_faces": faults, "nnc": nnc}


def test_pack_cells_round_trips(spe1):
    cells = gm.build_cells(spe1)
    got = unpack_cells(gm.pack_cells(cells))

    assert got["version"] == gm.CELLS_FORMAT_VERSION
    assert np.allclose(got["origin"], gm.surface_origin(spe1))
    assert np.array_equal(got["ijk"], spe1.ijk_of_active())
    assert np.array_equal(got["centers"], cells["centers"])
    assert np.array_equal(got["fault_faces"], spe1.fault_faces().astype(np.uint8))
    assert got["ijk"].shape == (spe1.nactive, 3)
    assert got["nnc"].shape == (0, 2)


def test_pack_cells_centres_share_the_mesh_origin(spe1):
    """Every centre must sit inside its own cell, in the mesh's frame.

    The transform is spelled out by hand here rather than reusing to_viewer, so
    a build_cells that forgot the origin shift or the Z flip fails: either
    mistake throws the centres thousands of units off the grid.
    """
    got = unpack_cells(gm.pack_cells(gm.build_cells(spe1)))
    origin = gm.surface_origin(spe1)

    corners = spe1.active_corners() - origin  # (nactive, 8, 3)
    corners[..., 2] *= -1.0
    lo = corners.min(axis=1)
    hi = corners.max(axis=1)

    assert np.all(got["centers"] >= lo - 1e-3), "a centre is below its own cell"
    assert np.all(got["centers"] <= hi + 1e-3), "a centre is above its own cell"


def test_pack_cells_padding_holds_for_odd_cell_counts():
    """n_cells*6 not a multiple of 4 still leaves the NNC section aligned."""
    cells = {
        "ijk": np.arange(3 * 3, dtype=np.int32).reshape(3, 3),
        "centers": np.zeros((3, 3), dtype=np.float32),
        "fault_faces": np.ones((3, 6), dtype=np.uint8),  # 18 bytes -> pad 2
        "nnc": np.array([[0, 2]], dtype=np.int32),
        "origin": np.zeros(3),
    }
    got = unpack_cells(gm.pack_cells(cells))
    assert np.array_equal(got["ijk"], cells["ijk"])
    assert got["fault_faces"].sum() == 18
    assert np.array_equal(got["nnc"], [[0, 2]])


def test_pack_cells_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="disagree"):
        gm.pack_cells({
            "ijk": np.zeros((3, 3), dtype=np.int32),
            "centers": np.zeros((2, 3), dtype=np.float32),
            "fault_faces": np.zeros((3, 6), dtype=np.uint8),
            "nnc": np.zeros((0, 2), dtype=np.int32),
            "origin": np.zeros(3),
        })


@pytest.mark.slow
def test_pack_cells_norne_faults_and_nncs(norne):
    got = unpack_cells(gm.pack_cells(gm.build_cells(norne)))
    assert got["ijk"].shape == (44431, 3)
    assert got["fault_faces"].sum() == 17720
    assert got["nnc"].shape == (15349, 2)
    # K faces never fault: only lateral faces can be geometrically offset.
    assert got["fault_faces"][:, 4:].sum() == 0
    # Every NNC endpoint must be a real active cell.
    assert got["nnc"].min() >= 0 and got["nnc"].max() < 44431


def test_pack_values_is_little_endian_float32():
    values = np.array([1.5, -2.25, np.inf], dtype=np.float64)
    blob = gm.pack_values(values)
    assert len(blob) == 12
    assert np.array_equal(np.frombuffer(blob, dtype="<f4"), values.astype(np.float32))


# ---------------------------------------------------------------- properties


def test_derive_soil_matches_definition(norne):
    parts = norne.read_dynamic_many({"SWAT", "SGAS", "SSOL"}, 0)
    soil = derive_soil(parts.get("SWAT"), parts.get("SGAS"), parts.get("SSOL"))
    assert soil is not None and soil.size == norne.nactive
    assert np.allclose(soil, 1.0 - parts["SWAT"] - parts["SGAS"], atol=1e-6)
    # A saturation triple must sum to one everywhere.
    assert np.allclose(soil + parts["SWAT"] + parts["SGAS"], 1.0, atol=1e-5)


def test_derive_soil_without_saturations_is_none():
    assert derive_soil(None, None, None) is None


def test_statistics_percentile_convention():
    """p10 is the value exceeded by 10% of cells, i.e. the 90th percentile."""
    stats = statistics(np.arange(101, dtype=np.float32))
    assert stats["min"] == 0.0 and stats["max"] == 100.0
    assert stats["p10"] == pytest.approx(90.0)
    assert stats["p90"] == pytest.approx(10.0)
    assert len(stats["histogram"]) == 50
    assert len(stats["bin_edges"]) == 51


def test_statistics_ignores_non_finite():
    stats = statistics(np.array([1.0, np.nan, 3.0, np.inf], dtype=np.float32))
    assert stats["count"] == 2
    assert (stats["min"], stats["max"]) == (1.0, 3.0)


def test_spe1_time_steps(spe1):
    steps = spe1.time_steps()
    assert len(steps) == 121
    assert steps[0].index == 0 and steps[0].days == 0.0
    assert steps[0].date == "2015-01-01"
    assert steps[-1].days > steps[0].days


@pytest.mark.slow
def test_norne_dynamic_range_agrees_with_per_step_reads(norne):
    ranges, steps = norne.dynamic_range({"PRESSURE"})
    assert steps == 65
    lo, hi = ranges["PRESSURE"]
    first = norne.read_dynamic("PRESSURE", 0)
    assert lo <= first.min() and hi >= first.max()
    assert lo == pytest.approx(67.33113, rel=1e-5)
    assert hi == pytest.approx(612.75916, rel=1e-5)


@pytest.mark.slow
def test_norne_soil_range_stays_within_the_per_step_values(norne):
    span, steps = norne.soil_range()
    assert steps == 65
    parts = norne.read_dynamic_many({"SWAT", "SGAS", "SSOL"}, 0)
    soil0 = derive_soil(parts.get("SWAT"), parts.get("SGAS"), parts.get("SSOL"))
    assert span[0] <= soil0.min() and span[1] >= soil0.max()


# --------------------------------------------------------------------- wells


def test_spe1_wells_appear_and_are_typed(spe1):
    """SPE1 declares its two wells only once the schedule starts."""
    assert spe1.has_wells()
    assert spe1.wells(0) == []
    wells = {w.name: w for w in spe1.wells(120)}
    assert set(wells) == {"PROD", "INJ"}
    assert wells["PROD"].type == "producer"
    assert wells["INJ"].type == "gas_injector"
    # WELSPECS puts PROD at (10,10) and INJ at (1,1), one-based.
    assert (wells["PROD"].i, wells["PROD"].j) == (9, 9)
    assert (wells["INJ"].i, wells["INJ"].j) == (0, 0)
    assert [(c.i, c.j, c.k) for c in wells["PROD"].completions] == [(9, 9, 2)]
    assert [(c.i, c.j, c.k) for c in wells["INJ"].completions] == [(0, 0, 0)]


@pytest.mark.slow
def test_norne_well_layout_validates(norne):
    """36 named wells by the end, all completions in active cells."""
    assert norne.wells(0) != []
    assert len(norne.wells(0)) == 3
    wells = norne.wells(64)
    assert len(wells) == 36
    names = [w.name for w in wells]
    assert names[:3] == ["C-4H", "B-2H", "D-1H"]
    assert all(n and n.replace("-", "").isalnum() for n in names)

    for well in wells:
        assert 0 <= well.i < norne.nx and 0 <= well.j < norne.ny
        assert well.type in {"producer", "oil_injector", "water_injector",
                             "gas_injector", "unknown"}
        assert well.completions, f"{well.name} has no completions"
        for c in well.completions:
            assert 0 <= c.i < norne.nx and 0 <= c.j < norne.ny and 0 <= c.k < norne.nz
            # Every completion must land on a cell the simulator actually solves.
            assert c.cell >= 0, f"{well.name} completes into inactive cell {(c.i, c.j, c.k)}"
            assert c.cell < norne.nactive

    # C-4H is converted to water injection late in the history (WCONINJE
    # 'C-4H' 'WATER' in INCLUDE/BC0407_HIST01122006.SCH) after a spell as a
    # gas injector, which is what makes it a good check that IWEL index 6 is
    # really the type code and not a constant.
    by_name = {w.name: w for w in wells}
    assert by_name["C-4H"].type == "water_injector"
    assert norne.wells(0)[0].type == "producer"
    assert by_name["B-2H"].type == "producer"


@pytest.mark.slow
def test_norne_completion_count_matches_iwel(norne):
    """IWEL index 4 (number of connections) must equal the used ICON slots."""
    import resfo

    seen = -1
    raw = {}
    for kw, arr in resfo.read(str(norne.unrst_path)):
        name = kw.strip()
        if name == "SEQNUM":
            seen += 1
            raw = {}
            continue
        if name in ("INTEHEAD", "IWEL"):
            raw.setdefault(name, np.asarray(arr))
    head, iwel = raw["INTEHEAD"], raw["IWEL"]
    nwells = int(head[16])
    declared = iwel.reshape(nwells, -1)[:, 4]
    parsed = [len(w.completions) for w in norne.wells(seen)]
    assert list(declared) == parsed


def test_wells_out_of_range_step_is_empty(spe1):
    assert spe1.wells(10_000) == []


def test_grid_without_restart_has_no_wells(tmp_path):
    import shutil

    shutil.copy(SPE1_STEM.with_suffix(".EGRID"), tmp_path / "S.EGRID")
    grid = EclipseGrid(tmp_path / "S")
    assert grid.has_wells() is False
    assert grid.wells(0) == []
    assert grid.time_steps() == []
    assert grid.static_properties() == {}
