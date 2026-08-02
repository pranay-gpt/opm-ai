/**
 * Binary mesh / property decoding for the 3D viewer.
 *
 * Pure: no three.js, no DOM beyond TextDecoder. The layouts here mirror
 * `opm_ai/postprocess/grid_mesh.py` (`pack_mesh`) and the property endpoint in
 * `docs/3d-viewer-contract.md` byte for byte. Everything is little-endian.
 *
 * The typed arrays returned by `parseMesh` are *views* onto the incoming
 * ArrayBuffer, not copies: a Norne mesh is ~6 MB and handing it straight to
 * WebGL is the whole point of the binary format. Do not mutate them, and do
 * not keep the mesh alive longer than you need the buffer.
 */

/** Must match `MESH_FORMAT_VERSION` in opm_ai/postprocess/grid_mesh.py. */
export const MESH_FORMAT_VERSION = 1;

/** Version of the `OPMP` property blob described in the contract. */
export const PROPERTY_FORMAT_VERSION = 1;

/** Must match `CELLS_FORMAT_VERSION` in opm_ai/postprocess/grid_mesh.py. */
export const CELLS_FORMAT_VERSION = 1;

/** Face id -> name, matching `FACE_NAMES` in opm_ai/postprocess/grid3d.py. */
export const FACE_NAMES: readonly string[] = ['I-', 'I+', 'J-', 'J+', 'K-', 'K+'];

export interface ParsedMesh {
  version: number;
  origin: [number, number, number];
  positions: Float32Array; // n*3
  normals: Float32Array; // n*3
  cellIds: Int32Array; // n
  faceIds: Uint8Array; // n
  indices: Uint32Array;
  edges: Uint32Array;
  vertexCount: number;
}

const MESH_HEADER_BYTES = 44; // magic(4) + 4*uint32 + 3*float64
const PROPERTY_HEADER_BYTES = 12; // magic(4) + version + json_len

function readMagic(buf: ArrayBuffer, what: string): string {
  if (buf.byteLength < 4) {
    throw new Error(`${what}: truncated, only ${buf.byteLength} bytes`);
  }
  const b = new Uint8Array(buf, 0, 4);
  return String.fromCharCode(b[0], b[1], b[2], b[3]);
}

/** Round up to the next 4-byte boundary, as the packer pads to. */
function align4(n: number): number {
  return (n + 3) & ~3;
}

/**
 * Decode a `pack_mesh()` blob.
 *
 * Layout (little-endian, tightly packed in this order):
 *   0   magic "OPMG"
 *   4   uint32 version
 *   8   uint32 n_vertices
 *   12  uint32 n_indices    (triangle corners)
 *   16  uint32 n_edges      (line endpoints)
 *   20  3 x float64 origin  (NOT 8-byte aligned, so read via DataView)
 *   44  n_vertices*3 float32 positions
 *   ..  n_vertices*3 float32 normals
 *   ..  n_vertices   int32   active cell index per vertex
 *   ..  n_vertices   uint8   face id per vertex, padded to 4 bytes
 *   ..  n_indices    uint32  triangle indices
 *   ..  n_edges      uint32  edge line indices
 */
export function parseMesh(buf: ArrayBuffer): ParsedMesh {
  const magic = readMagic(buf, 'Bad mesh buffer');
  if (magic !== 'OPMG') {
    throw new Error(`Bad mesh magic: expected "OPMG", got "${magic}"`);
  }

  const dv = new DataView(buf);
  const version = dv.getUint32(4, true);
  if (version !== MESH_FORMAT_VERSION) {
    throw new Error(
      `Unsupported mesh format version ${version} (this build reads ${MESH_FORMAT_VERSION})`
    );
  }

  const vertexCount = dv.getUint32(8, true);
  const indexCount = dv.getUint32(12, true);
  const edgeCount = dv.getUint32(16, true);

  // origin sits at offset 20, which is 4- but not 8-byte aligned, so a
  // Float64Array view would throw. Read the three doubles by hand.
  const origin: [number, number, number] = [
    dv.getFloat64(20, true),
    dv.getFloat64(28, true),
    dv.getFloat64(36, true),
  ];

  const posBytes = vertexCount * 3 * 4;
  const cellBytes = vertexCount * 4;
  const faceBytes = align4(vertexCount);
  const expected =
    MESH_HEADER_BYTES + posBytes * 2 + cellBytes + faceBytes + indexCount * 4 + edgeCount * 4;
  if (buf.byteLength < expected) {
    throw new Error(
      `Truncated mesh buffer: need ${expected} bytes for ${vertexCount} vertices / ` +
        `${indexCount} indices / ${edgeCount} edge endpoints, got ${buf.byteLength}`
    );
  }

  let off = MESH_HEADER_BYTES;
  const positions = new Float32Array(buf, off, vertexCount * 3);
  off += posBytes;
  const normals = new Float32Array(buf, off, vertexCount * 3);
  off += posBytes;
  const cellIds = new Int32Array(buf, off, vertexCount);
  off += cellBytes;
  const faceIds = new Uint8Array(buf, off, vertexCount);
  off += faceBytes;
  const indices = new Uint32Array(buf, off, indexCount);
  off += indexCount * 4;
  const edges = new Uint32Array(buf, off, edgeCount);

  return { version, origin, positions, normals, cellIds, faceIds, indices, edges, vertexCount };
}

export interface ParsedCells {
  version: number;
  origin: [number, number, number];
  /** 3 per active cell, zero-based. */
  ijk: Int32Array;
  /** 3 per active cell, viewer coords, same origin/Z-flip as the mesh. */
  centers: Float32Array;
  /** 6 per active cell, face order I- I+ J- J+ K- K+; 1 = on a fault. */
  faultFaces: Uint8Array;
  /** 2 active-cell indices per non-neighbour connection. */
  nnc: Int32Array;
  cellCount: number;
  nncCount: number;
}

const CELLS_HEADER_BYTES = 40; // magic(4) + 3*uint32 + 3*float64

/**
 * Decode an `OPMC` cell blob (`pack_cells()` in grid_mesh.py).
 *
 * Layout (little-endian, tightly packed in this order):
 *   0   magic "OPMC"
 *   4   uint32 version
 *   8   uint32 n_cells
 *   12  uint32 n_nncs
 *   16  3 x float64 origin  (NOT 8-byte aligned, so read via DataView)
 *   40  n_cells*3 int32   i, j, k
 *   ..  n_cells*3 float32 centres, viewer coords
 *   ..  n_cells*6 uint8   fault faces, padded to 4 bytes
 *   ..  n_nncs*2  int32   active-cell index pairs
 */
export function parseCells(buf: ArrayBuffer): ParsedCells {
  const magic = readMagic(buf, 'Bad cell buffer');
  if (magic !== 'OPMC') {
    throw new Error(`Bad cell magic: expected "OPMC", got "${magic}"`);
  }

  const dv = new DataView(buf);
  const version = dv.getUint32(4, true);
  if (version !== CELLS_FORMAT_VERSION) {
    throw new Error(
      `Unsupported cell format version ${version} (this build reads ${CELLS_FORMAT_VERSION})`
    );
  }

  const cellCount = dv.getUint32(8, true);
  const nncCount = dv.getUint32(12, true);
  const origin: [number, number, number] = [
    dv.getFloat64(16, true),
    dv.getFloat64(24, true),
    dv.getFloat64(32, true),
  ];

  const ijkBytes = cellCount * 3 * 4;
  const centerBytes = cellCount * 3 * 4;
  const faultBytes = align4(cellCount * 6);
  const expected = CELLS_HEADER_BYTES + ijkBytes + centerBytes + faultBytes + nncCount * 8;
  if (buf.byteLength < expected) {
    throw new Error(
      `Truncated cell buffer: need ${expected} bytes for ${cellCount} cells / ` +
        `${nncCount} NNCs, got ${buf.byteLength}`
    );
  }

  let off = CELLS_HEADER_BYTES;
  const ijk = new Int32Array(buf, off, cellCount * 3);
  off += ijkBytes;
  const centers = new Float32Array(buf, off, cellCount * 3);
  off += centerBytes;
  const faultFaces = new Uint8Array(buf, off, cellCount * 6);
  off += faultBytes;
  const nnc = new Int32Array(buf, off, nncCount * 2);

  return { version, origin, ijk, centers, faultFaces, nnc, cellCount, nncCount };
}

/**
 * Per-cell x per-face fault flags -> the per-quad mask `setFaultMask` wants.
 *
 * Done on the client rather than server-side because the quad set depends on
 * `include_inactive`, while `(cell, face)` does not: vertex `4q` of quad `q`
 * carries both, so this join never has to assume anything about the order
 * `build_surface` emitted the quads in.
 */
export function expandFaultMask(mesh: ParsedMesh, faultFaces: Uint8Array): Uint8Array {
  const quads = mesh.vertexCount >> 2;
  const out = new Uint8Array(quads);
  for (let q = 0; q < quads; q++) {
    const v = q * 4;
    const cell = mesh.cellIds[v];
    if (cell < 0) continue; // an inactive cell, drawn but never faulted
    const o = cell * 6 + mesh.faceIds[v];
    if (o < faultFaces.length && faultFaces[o] !== 0) out[q] = 1;
  }
  return out;
}

export interface PropertyStats {
  name: string;
  step: number;
  count: number;
  kind: 'static' | 'dynamic' | 'derived';
  categorical: boolean;
  unit: string;
  min: number;
  max: number;
  mean: number;
  p10: number;
  p90: number;
  sum: number;
  count_finite: number;
  histogram: number[];
  bin_edges: number[];
}

export interface ParsedProperty {
  stats: PropertyStats;
  values: Float32Array;
}

/**
 * Decode an `OPMP` property blob.
 *
 * Layout: magic "OPMP", uint32 version, uint32 json_len, json_len UTF-8 bytes
 * padded to a 4-byte boundary, then one float32 per active cell in grid order.
 */
export function parseProperty(buf: ArrayBuffer): ParsedProperty {
  const magic = readMagic(buf, 'Bad property buffer');
  if (magic !== 'OPMP') {
    throw new Error(`Bad property magic: expected "OPMP", got "${magic}"`);
  }

  const dv = new DataView(buf);
  const version = dv.getUint32(4, true);
  if (version !== PROPERTY_FORMAT_VERSION) {
    throw new Error(
      `Unsupported property format version ${version} ` +
        `(this build reads ${PROPERTY_FORMAT_VERSION})`
    );
  }

  const jsonLen = dv.getUint32(8, true);
  const dataOffset = PROPERTY_HEADER_BYTES + align4(jsonLen);
  if (buf.byteLength < dataOffset) {
    throw new Error(`Truncated property buffer: metadata claims ${jsonLen} JSON bytes`);
  }

  const json = new TextDecoder().decode(new Uint8Array(buf, PROPERTY_HEADER_BYTES, jsonLen));
  let stats: PropertyStats;
  try {
    stats = JSON.parse(json) as PropertyStats;
  } catch (e) {
    throw new Error(`Property metadata is not valid JSON: ${(e as Error).message}`);
  }

  const valueCount = (buf.byteLength - dataOffset) >> 2;
  if (typeof stats.count === 'number' && stats.count !== valueCount) {
    throw new Error(
      `Property "${stats.name}" claims ${stats.count} values but the blob holds ${valueCount}`
    );
  }

  return { stats, values: new Float32Array(buf, dataOffset, valueCount) };
}
