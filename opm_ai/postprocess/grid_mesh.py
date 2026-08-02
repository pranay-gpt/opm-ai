"""Surface extraction and binary mesh packing for the 3D viewer.

Builds the drawable skin of a corner-point grid the way ResInsight does
(RigGridCellFaceVisibilityFilter): a cell face is drawn when it faces the
outside world, i.e. when the neighbour across it is missing, inactive, or
offset by a fault. Interior faces between two active, conforming cells are
culled, which is what keeps a 44k-cell field grid down to a few tens of
thousands of quads instead of 266k.

The mesh is delivered as a little-endian binary blob rather than JSON: for
Norne that is ~9 MB of Float32 instead of ~90 MB of decimal text, and the
browser can hand the buffer straight to WebGL without parsing.
"""

from __future__ import annotations

import numpy as np

from opm_ai.postprocess.grid3d import (
    FACE_CORNERS,
    FACE_NEIGHBOUR_OFFSET,
    EclipseGrid,
)

# Bump when the binary layout changes so a stale cached blob is never served.
MESH_FORMAT_VERSION = 1

# Same, for the per-cell companion blob packed by pack_cells().
CELLS_FORMAT_VERSION = 1


def visible_faces(grid: EclipseGrid, include_inactive: bool = False) -> np.ndarray:
    """Boolean mask (ncells_considered, 6) of faces that need drawing.

    With include_inactive=False (the default) only active cells are meshed and
    a face is drawn when the neighbour is off-grid or inactive. With
    include_inactive=True every cell is meshed and only the grid boundary and
    fault faces survive, which is the "show inactive cells" display option.

    Fault faces are always drawn even between two active cells, because the
    two sides do not line up and culling them would leave a visible hole.
    """
    nz, ny, nx = grid.nz, grid.ny, grid.nx
    drawn = grid.actnum if not include_inactive else np.ones_like(grid.actnum)
    ndrawn = int(drawn.sum())
    out = np.zeros((ndrawn, 6), dtype=bool)

    # Index of each drawn cell within the output arrays.
    order = np.full((nz, ny, nx), -1, dtype=np.int64)
    order[drawn] = np.arange(ndrawn)

    for face, (di, dj, dk) in enumerate(FACE_NEIGHBOUR_OFFSET):
        # Neighbour presence: shift the "drawn" mask by the face offset. Cells
        # shifted off the edge of the array have no neighbour, so they are
        # boundary faces and must be drawn.
        neighbour = np.zeros_like(drawn)
        src = [slice(None)] * 3
        dst = [slice(None)] * 3
        for axis, delta in ((0, dk), (1, dj), (2, di)):
            if delta > 0:
                src[axis] = slice(delta, None)
                dst[axis] = slice(None, -delta)
            elif delta < 0:
                src[axis] = slice(None, delta)
                dst[axis] = slice(-delta, None)
        neighbour[tuple(dst)] = drawn[tuple(src)]

        exposed = drawn & ~neighbour
        out[order[exposed], face] = True

    faults = grid.fault_faces()
    if include_inactive:
        # fault_faces() is indexed by active cell; lift it to all-cell order.
        lifted = np.zeros((ndrawn, 6), dtype=bool)
        lifted[order[grid.actnum]] = faults
        faults = lifted
    out |= faults
    return out


def surface_origin(grid: EclipseGrid) -> np.ndarray:
    """Local offset subtracted from every exported coordinate, in grid units.

    float32 loses metre-level precision on UTM-scale coordinates (Norne sits
    near 4.5e5, 7.3e6, where a float32 step is ~0.5 m), so everything the
    viewer receives is expressed relative to this point.

    Deliberately computed from the ACTIVE cells only, never from the drawn
    set: it must not move when "show inactive cells" is toggled, or the model
    would jump and the well trajectories (which use this same origin) would
    detach from the grid.
    """
    flat = grid.active_corners().reshape(-1, 3)
    return np.array([flat[:, 0].mean(), flat[:, 1].mean(), flat[:, 2].mean()], dtype=np.float64)


def to_viewer(points: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """Grid coordinates -> viewer coordinates: shift to origin, flip Z up.

    The single place this transform is spelled out. Mesh vertices and well
    trajectories both go through it, which is what keeps them registered.
    """
    out = np.asarray(points, dtype=np.float64) - origin
    out[..., 2] *= -1.0
    return out


def build_surface(grid: EclipseGrid, include_inactive: bool = False) -> dict:
    """Triangulate the visible skin of the grid.

    Returns a dict of NumPy arrays:
        positions   (nverts, 3) float32  vertex coordinates, Z up
        normals     (nverts, 3) float32  per-vertex (flat, per-quad) normals
        indices     (ntris, 3)  int32    triangle vertex indices
        cell_of_vertex (nverts,) int32   active cell index per vertex
        face_of_vertex (nverts,) uint8   which of the 6 faces the vertex is on
        quad_cell   (nquads,)   int32    active cell index per quad
        origin      (3,)        float64  subtracted offset, for label display

    Vertices are not shared between quads: each quad carries its own four,
    so a cell's colour and a face's flat normal stay crisp at the seams. That
    is also how ResInsight builds its grid parts.
    """
    mask = visible_faces(grid, include_inactive=include_inactive)
    corners = grid.corners()
    drawn_corners = corners[grid.actnum] if not include_inactive else corners.reshape(-1, 8, 3)

    if not include_inactive:
        cell_ids = np.arange(grid.nactive, dtype=np.int32)
    else:
        cell_ids = grid.active_index.reshape(-1).astype(np.int32)

    origin = surface_origin(grid)

    quad_cells: list[np.ndarray] = []
    quad_face: list[np.ndarray] = []
    quad_pts: list[np.ndarray] = []

    for face, face_corner_idx in enumerate(FACE_CORNERS):
        sel = np.nonzero(mask[:, face])[0]
        if sel.size == 0:
            continue
        pts = drawn_corners[sel][:, face_corner_idx, :]  # (n, 4, 3)
        quad_pts.append(pts)
        quad_cells.append(cell_ids[sel])
        quad_face.append(np.full(sel.size, face, dtype=np.uint8))

    if not quad_pts:
        empty_f = np.zeros((0, 3), dtype=np.float32)
        return {
            "positions": empty_f,
            "normals": empty_f,
            "indices": np.zeros((0, 3), dtype=np.int32),
            "cell_of_vertex": np.zeros(0, dtype=np.int32),
            "face_of_vertex": np.zeros(0, dtype=np.uint8),
            "quad_cell": np.zeros(0, dtype=np.int32),
            "origin": origin,
        }

    pts = np.concatenate(quad_pts, axis=0)          # (nq, 4, 3)
    quad_cell = np.concatenate(quad_cells).astype(np.int32)
    faces_of_quad = np.concatenate(quad_face)
    nq = pts.shape[0]

    local = to_viewer(pts, origin)

    # Flat normal per quad from the diagonals, which is stable on the warped
    # non-planar faces corner-point grids produce (RigCell::faceNormal).
    d1 = local[:, 2, :] - local[:, 0, :]
    d2 = local[:, 3, :] - local[:, 1, :]
    normal = np.cross(d1, d2)
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    normal = np.divide(normal, length, out=np.zeros_like(normal), where=length > 1e-30)

    positions = local.reshape(nq * 4, 3).astype(np.float32)
    normals = np.repeat(normal, 4, axis=0).astype(np.float32)
    cell_of_vertex = np.repeat(quad_cell, 4)
    face_of_vertex = np.repeat(faces_of_quad, 4)

    base = np.arange(nq, dtype=np.int32) * 4
    indices = np.empty((nq * 2, 3), dtype=np.int32)
    indices[0::2, 0] = base
    indices[0::2, 1] = base + 1
    indices[0::2, 2] = base + 2
    indices[1::2, 0] = base
    indices[1::2, 1] = base + 2
    indices[1::2, 2] = base + 3

    return {
        "positions": positions,
        "normals": normals,
        "indices": indices,
        "cell_of_vertex": cell_of_vertex.astype(np.int32),
        "face_of_vertex": face_of_vertex.astype(np.uint8),
        "quad_cell": quad_cell,
        "origin": origin,
    }


def build_edges(surface: dict) -> np.ndarray:
    """Line-segment indices outlining every quad, for the mesh/grid-line mode."""
    nq = surface["quad_cell"].shape[0]
    if nq == 0:
        return np.zeros((0, 2), dtype=np.int32)
    base = np.arange(nq, dtype=np.int32) * 4
    edges = np.empty((nq * 4, 2), dtype=np.int32)
    for n, (a, b) in enumerate(((0, 1), (1, 2), (2, 3), (3, 0))):
        edges[n::4, 0] = base + a
        edges[n::4, 1] = base + b
    return edges


def pack_mesh(surface: dict, edges: np.ndarray | None = None) -> bytes:
    """Serialise a surface into the viewer's binary mesh format.

    Layout, all little-endian, sections in this order and tightly packed:

        magic      4 bytes   b"OPMG"
        version    uint32
        n_vertices uint32
        n_indices  uint32    (triangle corner count = ntris * 3)
        n_edges    uint32    (line endpoint count  = nsegs * 2)
        origin     3 x float64
        positions  n_vertices * 3 float32
        normals    n_vertices * 3 float32
        cell_ids   n_vertices int32
        face_ids   n_vertices uint8   (padded to a 4-byte boundary)
        indices    n_indices  uint32
        edges      n_edges    uint32
    """
    positions = np.ascontiguousarray(surface["positions"], dtype="<f4")
    normals = np.ascontiguousarray(surface["normals"], dtype="<f4")
    cell_ids = np.ascontiguousarray(surface["cell_of_vertex"], dtype="<i4")
    face_ids = np.ascontiguousarray(surface["face_of_vertex"], dtype=np.uint8)
    indices = np.ascontiguousarray(surface["indices"].reshape(-1), dtype="<u4")
    edge_arr = (
        np.ascontiguousarray(edges.reshape(-1), dtype="<u4")
        if edges is not None and edges.size
        else np.zeros(0, dtype="<u4")
    )

    nverts = positions.shape[0]
    header = np.array(
        [MESH_FORMAT_VERSION, nverts, indices.size, edge_arr.size], dtype="<u4"
    )
    origin = np.ascontiguousarray(surface["origin"], dtype="<f8")

    pad = (-face_ids.size) % 4
    parts = [
        b"OPMG",
        header.tobytes(),
        origin.tobytes(),
        positions.tobytes(),
        normals.tobytes(),
        cell_ids.tobytes(),
        face_ids.tobytes(),
        b"\x00" * pad,
        indices.tobytes(),
        edge_arr.tobytes(),
    ]
    return b"".join(parts)


def build_cells(grid: EclipseGrid) -> dict:
    """Per-active-cell companion data for the mesh: i/j/k, centres, faults, NNCs.

    Everything here is keyed by *active* cell index, exactly the index the mesh
    carries in `cell_of_vertex`, so the client can join the two without knowing
    anything about the grid.

    Centres go through `to_viewer(..., surface_origin(grid))` -- the same two
    helpers `build_surface` uses -- rather than a locally recomputed shift, so
    they land inside the meshed cells instead of floating off by the origin.
    """
    origin = surface_origin(grid)
    return {
        "ijk": np.ascontiguousarray(grid.ijk_of_active(), dtype=np.int32),
        "centers": to_viewer(grid.cell_centres(), origin).astype(np.float32),
        "fault_faces": np.ascontiguousarray(grid.fault_faces(), dtype=np.uint8),
        "nnc": np.ascontiguousarray(grid.nnc_pairs(), dtype=np.int32),
        "origin": origin,
    }


def pack_cells(cells: dict) -> bytes:
    """Serialise `build_cells()` output into the viewer's binary cell format.

    Layout, all little-endian, sections in this order and tightly packed:

        magic       4 bytes   b"OPMC"
        version     uint32
        n_cells     uint32    active cell count
        n_nncs      uint32    non-neighbour connection count
        origin      3 x float64   same value the mesh blob carries
        ijk         n_cells * 3 int32     zero-based i, j, k per active cell
        centers     n_cells * 3 float32   cell centroid, viewer coords
        fault_faces n_cells * 6 uint8     1 = face sits on a fault, face order
                                          I- I+ J- J+ K- K+ (padded to 4 bytes)
        nnc         n_nncs * 2 int32      active-cell index pairs

    The fault mask stays per *cell* rather than per drawn quad: the quad set
    depends on include_inactive, so a per-quad mask would silently mismatch the
    other mesh variant. The client expands it with the mesh's own cell/face
    arrays, which is ordering-independent.
    """
    ijk = np.ascontiguousarray(cells["ijk"], dtype="<i4").reshape(-1, 3)
    centers = np.ascontiguousarray(cells["centers"], dtype="<f4").reshape(-1, 3)
    faults = np.ascontiguousarray(cells["fault_faces"], dtype=np.uint8).reshape(-1, 6)
    nnc = np.ascontiguousarray(cells["nnc"], dtype="<i4").reshape(-1, 2)

    n_cells = ijk.shape[0]
    if centers.shape[0] != n_cells or faults.shape[0] != n_cells:
        raise ValueError(
            f"cell arrays disagree: ijk {ijk.shape}, centers {centers.shape}, "
            f"fault_faces {faults.shape}"
        )

    header = np.array([CELLS_FORMAT_VERSION, n_cells, nnc.shape[0]], dtype="<u4")
    origin = np.ascontiguousarray(cells["origin"], dtype="<f8")
    pad = (-faults.size) % 4
    return b"".join([
        b"OPMC",
        header.tobytes(),
        origin.tobytes(),
        ijk.tobytes(),
        centers.tobytes(),
        faults.tobytes(),
        b"\x00" * pad,
        nnc.tobytes(),
    ])


def pack_values(values: np.ndarray) -> bytes:
    """Serialise a per-cell float array as a little-endian float32 blob."""
    return np.ascontiguousarray(values, dtype="<f4").tobytes()
