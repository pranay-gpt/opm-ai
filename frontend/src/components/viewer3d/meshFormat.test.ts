/**
 * Self-check for the binary parsers. No test framework is installed, so this
 * is a plain assert script.
 *
 * Run it with the esbuild that ships with vite (there is no tsx here):
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/components/viewer3d/meshFormat.test.ts --outfile=/tmp/mf.cjs \
 *     && node /tmp/mf.cjs
 *
 * Part 1 builds synthetic OPMG / OPMP buffers matching the contract layout
 * byte for byte and asserts every field round-trips, plus that a bad magic and
 * a bad version both throw. Part 2 parses a blob produced by the real Python
 * packer and checks the counts agree; it is skipped when the file is absent,
 * so the script works with no fixture. Regenerate the blob with:
 *
 *   .venv/bin/python -c "from opm_ai.postprocess.grid3d import EclipseGrid; \
 *     from opm_ai.postprocess.grid_mesh import *; import pathlib; \
 *     g=EclipseGrid(pathlib.Path('tests/fixtures/spe1/SPE1CASE1')); \
 *     s=build_surface(g); \
 *     pathlib.Path('/tmp/spe1_mesh.bin').write_bytes(pack_mesh(s, build_edges(s)))"
 */

import { parseMesh, parseProperty, MESH_FORMAT_VERSION } from './meshFormat';
import type { PropertyStats } from './meshFormat';
import { PALETTES, mapColors, mapTernary, legendStops } from './colormaps';
import type { ColorMapping, PaletteName, TernaryRanges } from './colormaps';

const REAL_MESH = '/tmp/spe1_mesh.bin';

// `@types/node` is deliberately not a dependency of this app (it is a browser
// bundle), so the two Node APIs this script needs are reached through a
// minimal local shim instead. tsc -b type-checks src/ with DOM libs only and
// would otherwise fail on `node:assert` and `Buffer`.
declare const require: (id: string) => unknown;

const nodeAssert = require('node:assert/strict') as {
  equal(a: unknown, b: unknown, m?: string): void;
  deepEqual(a: unknown, b: unknown, m?: string): void;
  ok(v: unknown, m?: string): void;
  match(s: string, re: RegExp, m?: string): void;
  throws(fn: () => unknown, re?: RegExp, m?: string): void;
};
const assert = nodeAssert;

function readFileBytes(path: string): Uint8Array {
  const fs = require('node:fs') as { readFileSync(p: string): Uint8Array };
  return fs.readFileSync(path);
}

function align4(n: number): number {
  return (n + 3) & ~3;
}

// ---------------------------------------------------------------- synthetic

interface Fixture {
  positions: number[];
  normals: number[];
  cellIds: number[];
  faceIds: number[];
  indices: number[];
  edges: number[];
  origin: [number, number, number];
}

/**
 * Two quads, i.e. 8 vertices, an odd-ish vertex count on purpose so the uint8
 * face-id block needs padding (8 is already aligned, so use 6 vertices for the
 * padding case below).
 */
function makeFixture(vertexCount: number): Fixture {
  const positions: number[] = [];
  const normals: number[] = [];
  const cellIds: number[] = [];
  const faceIds: number[] = [];
  for (let v = 0; v < vertexCount; v++) {
    positions.push(v * 1.5, v * -2.25, v * 0.5);
    normals.push(0, 0, 1);
    cellIds.push(v >> 2); // one cell per quad
    faceIds.push(v % 6);
  }
  const quads = vertexCount >> 2;
  const indices: number[] = [];
  const edges: number[] = [];
  for (let q = 0; q < quads; q++) {
    const b = q * 4;
    indices.push(b, b + 1, b + 2, b, b + 2, b + 3);
    edges.push(b, b + 1, b + 1, b + 2, b + 2, b + 3, b + 3, b);
  }
  return { positions, normals, cellIds, faceIds, indices, edges, origin: [453000.5, 7320000.25, -2600.125] };
}

function packMesh(f: Fixture, opts: { magic?: string; version?: number } = {}): ArrayBuffer {
  const n = f.cellIds.length;
  const magic = opts.magic ?? 'OPMG';
  const version = opts.version ?? MESH_FORMAT_VERSION;

  const total =
    44 + n * 3 * 4 * 2 + n * 4 + align4(n) + f.indices.length * 4 + f.edges.length * 4;
  const buf = new ArrayBuffer(total);
  const dv = new DataView(buf);
  const u8 = new Uint8Array(buf);

  for (let i = 0; i < 4; i++) u8[i] = magic.charCodeAt(i);
  dv.setUint32(4, version, true);
  dv.setUint32(8, n, true);
  dv.setUint32(12, f.indices.length, true);
  dv.setUint32(16, f.edges.length, true);
  dv.setFloat64(20, f.origin[0], true);
  dv.setFloat64(28, f.origin[1], true);
  dv.setFloat64(36, f.origin[2], true);

  let off = 44;
  for (const v of f.positions) {
    dv.setFloat32(off, v, true);
    off += 4;
  }
  for (const v of f.normals) {
    dv.setFloat32(off, v, true);
    off += 4;
  }
  for (const v of f.cellIds) {
    dv.setInt32(off, v, true);
    off += 4;
  }
  for (const v of f.faceIds) u8[off++] = v;
  // Skip the zero padding after the uint8 block: recompute the offset from the
  // section sizes rather than the running counter, since getting this boundary
  // wrong is the exact bug this fixture exists to catch.
  off = 44 + n * 3 * 4 * 2 + n * 4 + align4(n);
  for (const v of f.indices) {
    dv.setUint32(off, v, true);
    off += 4;
  }
  for (const v of f.edges) {
    dv.setUint32(off, v, true);
    off += 4;
  }
  assert.equal(off, total, 'synthetic packer wrote the wrong number of bytes');
  return buf;
}

function checkRoundTrip(vertexCount: number): void {
  const f = makeFixture(vertexCount);
  const parsed = parseMesh(packMesh(f));

  assert.equal(parsed.version, MESH_FORMAT_VERSION);
  assert.equal(parsed.vertexCount, vertexCount);
  // float64 origin must survive exactly; this is the field that would break
  // if the parser used a Float64Array view on the unaligned offset 20.
  assert.deepEqual(parsed.origin, f.origin);

  assert.equal(parsed.positions.length, vertexCount * 3);
  for (let i = 0; i < f.positions.length; i++) {
    assert.equal(parsed.positions[i], Math.fround(f.positions[i]), `positions[${i}]`);
  }
  assert.equal(parsed.normals.length, vertexCount * 3);
  for (let i = 0; i < f.normals.length; i++) {
    assert.equal(parsed.normals[i], f.normals[i], `normals[${i}]`);
  }
  assert.deepEqual(Array.from(parsed.cellIds), f.cellIds);
  assert.deepEqual(Array.from(parsed.faceIds), f.faceIds);
  assert.deepEqual(Array.from(parsed.indices), f.indices);
  assert.deepEqual(Array.from(parsed.edges), f.edges);
  console.log(`  ok  round-trip, ${vertexCount} vertices (face-id pad ${align4(vertexCount) - vertexCount})`);
}

function checkMeshErrors(): void {
  const f = makeFixture(8);

  assert.throws(
    () => parseMesh(packMesh(f, { magic: 'XXXX' })),
    /Bad mesh magic.*OPMG.*XXXX/s,
    'wrong magic must throw'
  );
  console.log('  ok  wrong magic throws');

  assert.throws(
    () => parseMesh(packMesh(f, { version: 99 })),
    /Unsupported mesh format version 99/,
    'wrong version must throw'
  );
  console.log('  ok  wrong version throws');

  const full = packMesh(f);
  assert.throws(() => parseMesh(full.slice(0, full.byteLength - 8)), /Truncated mesh buffer/);
  console.log('  ok  truncated buffer throws');

  assert.throws(() => parseMesh(new ArrayBuffer(2)), /truncated, only 2 bytes/);
  console.log('  ok  two-byte buffer throws');
}

// ---------------------------------------------------------------- property

function packProperty(
  stats: PropertyStats,
  values: number[],
  opts: { magic?: string; version?: number; json?: string } = {}
): ArrayBuffer {
  const json = opts.json ?? JSON.stringify(stats);
  const jsonBytes = new TextEncoder().encode(json);
  const total = 12 + align4(jsonBytes.length) + values.length * 4;
  const buf = new ArrayBuffer(total);
  const dv = new DataView(buf);
  const u8 = new Uint8Array(buf);
  const magic = opts.magic ?? 'OPMP';
  for (let i = 0; i < 4; i++) u8[i] = magic.charCodeAt(i);
  dv.setUint32(4, opts.version ?? 1, true);
  dv.setUint32(8, jsonBytes.length, true);
  u8.set(jsonBytes, 12);
  let off = 12 + align4(jsonBytes.length);
  for (const v of values) {
    dv.setFloat32(off, v, true);
    off += 4;
  }
  return buf;
}

function checkProperty(): void {
  const values = [0.1, 0.25, NaN, -3.5, 1e6];
  const stats: PropertyStats = {
    // A non-ASCII name makes the JSON byte length differ from its character
    // length, which is exactly what the 4-byte padding must be computed from.
    name: 'PRESSUREµ',
    step: 3,
    count: values.length,
    kind: 'dynamic',
    categorical: false,
    unit: 'barsa',
    min: -3.5,
    max: 1e6,
    mean: 0.2,
    p10: 0.9,
    p90: 0.05,
    sum: 12.5,
    count_finite: 4,
    histogram: [1, 2, 3],
    bin_edges: [0, 1, 2, 3],
  };

  const parsed = parseProperty(packProperty(stats, values));
  assert.deepEqual(parsed.stats, stats, 'property metadata must round-trip');
  assert.equal(parsed.values.length, values.length);
  for (let i = 0; i < values.length; i++) {
    if (Number.isNaN(values[i])) {
      assert.ok(Number.isNaN(parsed.values[i]), `values[${i}] should be NaN`);
    } else {
      assert.equal(parsed.values[i], Math.fround(values[i]), `values[${i}]`);
    }
  }
  console.log(`  ok  property round-trip, ${values.length} values, non-ASCII name`);

  assert.throws(
    () => parseProperty(packProperty(stats, values, { magic: 'OPMG' })),
    /Bad property magic.*OPMP.*OPMG/s
  );
  console.log('  ok  wrong property magic throws');

  assert.throws(
    () => parseProperty(packProperty(stats, values, { version: 7 })),
    /Unsupported property format version 7/
  );
  console.log('  ok  wrong property version throws');

  assert.throws(
    () => parseProperty(packProperty(stats, values, { json: '{not json' })),
    /not valid JSON/
  );
  console.log('  ok  bad JSON metadata throws');

  // count in the metadata disagreeing with the payload is a real corruption
  // mode (a truncated response), so it must not silently short-read.
  assert.throws(
    () => parseProperty(packProperty({ ...stats, count: 99 }, values)),
    /claims 99 values but the blob holds 5/
  );
  console.log('  ok  count mismatch throws');
}

// ---------------------------------------------------------------- real blob

function checkRealMesh(): void {
  let bytes: Uint8Array;
  try {
    bytes = readFileBytes(REAL_MESH);
  } catch {
    console.log(`  skip real Python blob (${REAL_MESH} not present)`);
    return;
  }

  // Node hands back a Buffer that is a view into a shared pool, so slice out
  // exactly this file's bytes before handing the ArrayBuffer to the parser.
  const buf = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer;
  const m = parseMesh(buf);

  // Counts reported by build_surface / build_edges on tests/fixtures/spe1.
  assert.equal(bytes.byteLength, 55084, 'blob size');
  assert.equal(m.vertexCount, 1280, 'n_vertices');
  assert.equal(m.indices.length, 1920, 'n_indices');
  assert.equal(m.edges.length, 2560, 'n_edges');
  assert.deepEqual(m.origin, [5000.0, 5000.0, 8365.0], 'origin');

  // SPE1 is 10x10x3 = 300 active cells, all of them exposed, and vertices are
  // packed four per quad, so quads = vertices / 4 and every index is in range.
  assert.equal(m.vertexCount % 4, 0, 'vertices must pack four per quad');
  assert.equal(m.indices.length, (m.vertexCount / 4) * 6, 'six tri indices per quad');
  assert.equal(m.edges.length, (m.vertexCount / 4) * 8, 'eight edge indices per quad');

  let maxCell = -1;
  for (let i = 0; i < m.cellIds.length; i++) if (m.cellIds[i] > maxCell) maxCell = m.cellIds[i];
  assert.equal(maxCell, 299, 'highest active cell index');
  assert.equal(m.cellIds[m.cellIds.length - 1], 299, 'last vertex cell');
  assert.equal(m.faceIds[m.faceIds.length - 1], 5, 'last vertex face (K+)');
  assert.equal(m.indices[m.indices.length - 1], 1279, 'last triangle index');
  assert.equal(m.edges[m.edges.length - 1], 1276, 'last edge index');

  // The first vertex of the SPE1 grid, origin already subtracted and Z flipped.
  assert.equal(m.positions[0], -5000);
  assert.equal(m.positions[1], -5000);
  assert.equal(m.positions[2], 40);

  for (let i = 0; i < m.indices.length; i++) {
    assert.ok(m.indices[i] < m.vertexCount, `index ${i} out of range`);
  }
  for (let i = 0; i < m.edges.length; i++) {
    assert.ok(m.edges[i] < m.vertexCount, `edge ${i} out of range`);
  }
  // Every cell id must resolve to a real active cell, and every face to 0..5.
  for (let i = 0; i < m.vertexCount; i++) {
    assert.ok(m.cellIds[i] >= 0 && m.cellIds[i] <= 299, `cellIds[${i}]`);
    assert.ok(m.faceIds[i] <= 5, `faceIds[${i}]`);
  }
  // Vertices within a quad must share cell and face, which is the invariant
  // the engine's per-quad arrays rely on.
  for (let q = 0; q < m.vertexCount / 4; q++) {
    for (let c = 1; c < 4; c++) {
      assert.equal(m.cellIds[q * 4 + c], m.cellIds[q * 4], `quad ${q} cell`);
      assert.equal(m.faceIds[q * 4 + c], m.faceIds[q * 4], `quad ${q} face`);
    }
  }
  console.log(
    `  ok  real SPE1 blob: ${m.vertexCount} verts / ${m.vertexCount / 4} quads / ` +
      `${m.indices.length} indices / ${m.edges.length} edge endpoints`
  );
}

// ---------------------------------------------------------------- colormaps

function baseMapping(over: Partial<ColorMapping> = {}): ColorMapping {
  return {
    palette: 'normal',
    mapping: 'linear_continuous',
    levels: 4,
    min: 0,
    max: 100,
    invert: false,
    undefinedColor: [0.5, 0.5, 0.5],
    ...over,
  };
}

/** All three channels of vertex v. */
function rgbAt(out: Float32Array, v: number): [number, number, number] {
  return [out[v * 3], out[v * 3 + 1], out[v * 3 + 2]];
}

function close(a: number, b: number, tol = 2 / 255): boolean {
  return Math.abs(a - b) <= tol;
}

function checkColormaps(): void {
  // Every declared palette must exist and be non-empty, or a UI dropdown entry
  // would render as undefined at runtime.
  const names: PaletteName[] = [
    'normal',
    'opposite_normal',
    'black_white',
    'white_black',
    'blue_white_red',
    'red_white_blue',
    'angular',
    'rainbow',
    'stimplan',
    'heat_map',
    'green_red',
    'blue_magenta',
    'category',
    'contrast_category',
  ];
  for (const n of names) {
    assert.ok(PALETTES[n] && PALETTES[n].length >= 2, `palette ${n} missing or too short`);
    for (const stop of PALETTES[n]) {
      for (const c of stop) assert.ok(c >= 0 && c <= 255, `palette ${n} stop out of 0..255`);
    }
  }
  assert.equal(PALETTES.category.length, 21, 'category = 21 Kelly colours');
  assert.equal(PALETTES.contrast_category.length, 21);
  assert.deepEqual(PALETTES.normal[0], [0, 0, 255], 'normal starts blue');
  assert.deepEqual(PALETTES.normal[PALETTES.normal.length - 1], [255, 0, 0], 'normal ends red');
  assert.deepEqual(PALETTES.angular[0], PALETTES.angular[PALETTES.angular.length - 1]);
  console.log(`  ok  ${names.length} palettes present, category = 21 colours`);

  // Endpoints and the undefined colour.
  const m = baseMapping();
  const cellIds = new Int32Array([0, 1, 2, 3, 4]);
  const values = new Float32Array([0, 100, NaN, -1, 101]);
  const out = new Float32Array(cellIds.length * 3);
  mapColors(values, cellIds, m, out);
  assert.deepEqual(rgbAt(out, 0), [0, 0, 1], 'min -> blue');
  assert.deepEqual(rgbAt(out, 1), [1, 0, 0], 'max -> red');
  assert.deepEqual(rgbAt(out, 2), [0.5, 0.5, 0.5], 'NaN -> undefinedColor');
  assert.deepEqual(rgbAt(out, 3), [0.5, 0.5, 0.5], 'below min -> undefinedColor');
  assert.deepEqual(rgbAt(out, 4), [0.5, 0.5, 0.5], 'above max -> undefinedColor');
  console.log('  ok  linear endpoints and out-of-range -> undefinedColor');

  // Invert must swap the endpoints.
  const inv = new Float32Array(6);
  mapColors(new Float32Array([0, 100]), new Int32Array([0, 1]), baseMapping({ invert: true }), inv);
  assert.deepEqual(rgbAt(inv, 0), [1, 0, 0], 'inverted min -> red');
  assert.deepEqual(rgbAt(inv, 1), [0, 0, 1], 'inverted max -> blue');
  console.log('  ok  invert swaps the ramp');

  // Discrete: `levels` bands, each one flat colour, and no more distinct
  // colours than there are levels.
  const dm = baseMapping({ mapping: 'linear_discrete', levels: 4 });
  const n = 40;
  const dv = new Float32Array(n);
  const dc = new Int32Array(n);
  for (let i = 0; i < n; i++) {
    dv[i] = (i / (n - 1)) * 100;
    dc[i] = i;
  }
  const dout = new Float32Array(n * 3);
  mapColors(dv, dc, dm, dout);
  const distinct = new Set<string>();
  for (let i = 0; i < n; i++) distinct.add(rgbAt(dout, i).join(','));
  assert.equal(distinct.size, 4, `linear_discrete levels=4 gave ${distinct.size} colours`);
  console.log('  ok  linear_discrete quantises to exactly `levels` colours');

  // Log modes must never produce NaN, including with a zero or negative floor.
  for (const mapping of ['log_continuous', 'log_discrete'] as const) {
    const lm = baseMapping({ mapping, min: 0, max: 1000, levels: 5 });
    const lv = new Float32Array([0, 1e-30, 1, 1000, -0]);
    const lo = new Float32Array(5 * 3);
    mapColors(lv, new Int32Array([0, 1, 2, 3, 4]), lm, lo);
    for (let i = 0; i < lo.length; i++) {
      assert.ok(Number.isFinite(lo[i]), `${mapping} produced non-finite channel at ${i}`);
      assert.ok(lo[i] >= 0 && lo[i] <= 1, `${mapping} channel ${i} out of 0..1`);
    }
    // Zero must land at the low end of the ramp, not become a grey hole.
    assert.deepEqual(rgbAt(lo, 0), [0, 0, 1], `${mapping}: zero -> low end`);
  }
  console.log('  ok  log modes clamp non-positive values, never NaN');

  // Category: integer value modulo palette length, and non-integers round.
  const cm = baseMapping({ mapping: 'category', palette: 'category' });
  const len = PALETTES.category.length;
  const cv = new Float32Array([0, 1, len, len + 1, 2.9999998, NaN]);
  const co = new Float32Array(6 * 3);
  mapColors(cv, new Int32Array([0, 1, 2, 3, 4, 5]), cm, co);
  // `out` is a Float32Array, so compare against float32-rounded expectations.
  const f32 = (c: readonly [number, number, number]): [number, number, number] => [
    Math.fround(c[0] / 255),
    Math.fround(c[1] / 255),
    Math.fround(c[2] / 255),
  ];
  assert.deepEqual(rgbAt(co, 0), f32(PALETTES.category[0]), 'category 0');
  assert.deepEqual(rgbAt(co, 2), rgbAt(co, 0), `category ${len} wraps to 0`);
  assert.deepEqual(rgbAt(co, 3), rgbAt(co, 1), `category ${len + 1} wraps to 1`);
  assert.deepEqual(
    rgbAt(co, 4),
    f32(PALETTES.category[3]),
    'float32 2.9999998 must round to category 3, not truncate to 2'
  );
  assert.deepEqual(rgbAt(co, 5), [0.5, 0.5, 0.5], 'NaN category -> undefinedColor');
  console.log('  ok  category wraps modulo palette length and rounds float32');

  // Ternary: pure phases go to the pure channels.
  const tr: TernaryRanges = { soil: [0, 1], sgas: [0, 1], swat: [0, 1] };
  const tOut = new Float32Array(3 * 3);
  mapTernary(
    new Float32Array([1, 0, 0]), // SOIL
    new Float32Array([0, 1, 0]), // SGAS
    new Float32Array([0, 0, 1]), // SWAT
    new Int32Array([0, 1, 2]),
    tr,
    tOut
  );
  assert.deepEqual(rgbAt(tOut, 0), [0, 1, 0], 'pure oil -> green');
  assert.deepEqual(rgbAt(tOut, 1), [1, 0, 0], 'pure gas -> red');
  assert.deepEqual(rgbAt(tOut, 2), [0, 0, 1], 'pure water -> blue');
  // A blend must stay in gamut and sum to about one, as the ternary triangle
  // requires; that is the invariant that breaks if the clamping is wrong.
  const blend = new Float32Array(3);
  mapTernary(
    new Float32Array([0.5]),
    new Float32Array([0.3]),
    new Float32Array([0.2]),
    new Int32Array([0]),
    tr,
    blend
  );
  assert.ok(close(blend[0] + blend[1] + blend[2], 1, 1e-5), 'ternary blend must sum to 1');
  assert.ok(close(blend[1], 0.5) && close(blend[0], 0.3), 'ternary blend channels');
  console.log('  ok  mapTernary: pure phases and an in-gamut blend');

  // legendStops: monotone values, parseable colours, category one per entry.
  const stops = legendStops(baseMapping(), 12);
  assert.equal(stops.length, 12);
  assert.equal(stops[0].value, 0);
  assert.equal(stops[11].value, 100);
  for (let i = 1; i < stops.length; i++) {
    assert.ok(stops[i].value > stops[i - 1].value, 'legend values must increase');
    assert.match(stops[i].color, /^rgb\(\d{1,3}, \d{1,3}, \d{1,3}\)$/, 'legend colour must be CSS');
  }
  const logStops = legendStops(baseMapping({ mapping: 'log_continuous', min: 1, max: 1000 }), 4);
  assert.ok(close(logStops[1].value, 10, 1e-6), 'log legend must be geometric');
  assert.ok(close(logStops[2].value, 100, 1e-6));
  const catStops = legendStops(baseMapping({ mapping: 'category', palette: 'category' }), 50);
  assert.equal(catStops.length, 21, 'category legend caps at the palette length');
  console.log('  ok  legendStops: linear, geometric log, capped category');
}

// ---------------------------------------------------------------- main

console.log('meshFormat self-check');
checkRoundTrip(8); // 4-aligned, no face-id padding
checkRoundTrip(6); // pad 2: exercises the uint8 -> uint32 section boundary
checkRoundTrip(5); // pad 3
checkMeshErrors();
checkProperty();
checkRealMesh();
checkColormaps();
console.log('all viewer3d checks passed');
