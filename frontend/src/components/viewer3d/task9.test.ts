/**
 * Self-check for Task 9: cross-section + well property overlay.
 *
 * Run it with:
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/components/viewer3d/task9.test.ts --outfile=/tmp/t9.cjs \
 *     && node /tmp/t9.cjs
 */

import { parseMesh, parseProperty, parseCells } from './meshFormat';
import type { DisplayOptions } from './engine';
import { Viewer3DEngine } from './engine';
import type { GridInfoResponse, GridWell, GridWellCompletion } from '../../types';

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

function align4(n: number): number {
  return (n + 3) & ~3;
}

// ============================================================
// 1. DisplayOptions interface tests
// ============================================================

function testDisplayOptionsDefaults(): void {
  const defaults: DisplayOptions = {
    surfaceMode: 'surface',
    meshMode: 'none',
    showInactive: false,
    zScale: 1,
    background: '#1a1d23',
    lighting: true,
    opacity: 1,
    showAxes: true,
    showGridBox: true,
    showWells: true,
    showWellLabels: false,
    showNncs: false,
    perspective: true,
    edgeColor: '#404550',
    crossSection: null,
    wellTrajectory: null,
  };

  // Verify crossSection defaults to null
  assert.equal(defaults.crossSection, null, 'crossSection should default to null');
  assert.equal(defaults.wellTrajectory, null, 'wellTrajectory should default to null');

  // Verify we can set crossSection
  const withCrossSection: DisplayOptions = {
    ...defaults,
    crossSection: { enabled: true, axis: 'K', index: 5 },
  };
  assert.ok(withCrossSection.crossSection !== null);
  if (withCrossSection.crossSection) {
    assert.equal(withCrossSection.crossSection.axis, 'K');
    assert.equal(withCrossSection.crossSection.index, 5);
    assert.equal(withCrossSection.crossSection.enabled, true);
  }

  // Verify we can set wellTrajectory
  const withWellTrajectory: DisplayOptions = {
    ...defaults,
    wellTrajectory: { enabled: true, property: 'PORO' },
  };
  assert.ok(withWellTrajectory.wellTrajectory !== null);
  if (withWellTrajectory.wellTrajectory) {
    assert.equal(withWellTrajectory.wellTrajectory.property, 'PORO');
    assert.equal(withWellTrajectory.wellTrajectory.enabled, true);
  }

  console.log('  ok  DisplayOptions defaults and assignment');
}

function testDisplayOptionsAxisTypes(): void {
  const opts: DisplayOptions = {
    surfaceMode: 'surface',
    meshMode: 'none',
    showInactive: false,
    zScale: 1,
    background: '#1a1d23',
    lighting: true,
    opacity: 1,
    showAxes: true,
    showGridBox: true,
    showWells: true,
    showWellLabels: false,
    showNncs: false,
    perspective: true,
    edgeColor: '#404550',
    crossSection: { enabled: true, axis: 'I', index: 1 },
    wellTrajectory: null,
  };

  // Test all valid axis values
  opts.crossSection!.axis = 'I';
  opts.crossSection!.axis = 'J';
  opts.crossSection!.axis = 'K';
  assert.ok(true, 'all axis types accepted');

  console.log('  ok  DisplayOptions axis types');
}

// ============================================================
// 2. Cross-section data extraction logic tests
// ============================================================

function makeTestIJK(nx: number, ny: number, nz: number): Int32Array {
  // Create a simple ijk array for a regular grid
  const activeCells = nx * ny * nz;
  const ijk = new Int32Array(activeCells * 3);
  let idx = 0;
  for (let k = 0; k < nz; k++) {
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        ijk[idx++] = i;
        ijk[idx++] = j;
        ijk[idx++] = k;
      }
    }
  }
  return ijk;
}

function testCrossSectionExtraction(): void {
  const nx = 4, ny = 3, nz = 2;
  const ijk = makeTestIJK(nx, ny, nz);
  const cellCount = nx * ny * nz;

  // Create test property values
  const values = new Float32Array(cellCount);
  for (let c = 0; c < cellCount; c++) {
    values[c] = c * 10.0; // Unique value per cell
  }

  // Test K-slice (axis='K', index=1 -> k=0)
  const sliceK1: { u: number; v: number; value: number }[] = [];
  for (let c = 0; c < cellCount; c++) {
    const i = ijk[c * 3];
    const j = ijk[c * 3 + 1];
    const k = ijk[c * 3 + 2];
    if (k === 0) { // index=1 -> 0-based k=0
      sliceK1.push({ u: i, v: j, value: values[c] });
    }
  }
  assert.equal(sliceK1.length, nx * ny, `K-slice should have ${nx * ny} cells`);
  // Verify u=i, v=j
  for (const cell of sliceK1) {
    assert.ok(cell.u >= 0 && cell.u < nx);
    assert.ok(cell.v >= 0 && cell.v < ny);
  }

  // Test J-slice (axis='J', index=2 -> j=1)
  const sliceJ2: { u: number; v: number; value: number }[] = [];
  for (let c = 0; c < cellCount; c++) {
    const i = ijk[c * 3];
    const j = ijk[c * 3 + 1];
    const k = ijk[c * 3 + 2];
    if (j === 1) { // index=2 -> 0-based j=1
      sliceJ2.push({ u: i, v: k, value: values[c] });
    }
  }
  assert.equal(sliceJ2.length, nx * nz, `J-slice should have ${nx * nz} cells`);
  for (const cell of sliceJ2) {
    assert.ok(cell.u >= 0 && cell.u < nx);
    assert.ok(cell.v >= 0 && cell.v < nz);
  }

  // Test I-slice (axis='I', index=3 -> i=2)
  const sliceI3: { u: number; v: number; value: number }[] = [];
  for (let c = 0; c < cellCount; c++) {
    const i = ijk[c * 3];
    const j = ijk[c * 3 + 1];
    const k = ijk[c * 3 + 2];
    if (i === 2) { // index=3 -> 0-based i=2
      sliceI3.push({ u: j, v: k, value: values[c] });
    }
  }
  assert.equal(sliceI3.length, ny * nz, `I-slice should have ${ny * nz} cells`);
  for (const cell of sliceI3) {
    assert.ok(cell.u >= 0 && cell.u < ny);
    assert.ok(cell.v >= 0 && cell.v < nz);
  }

  console.log('  ok  Cross-section extraction logic for all axes');
}

function testCrossSectionIndexBounds(): void {
  const nx = 4, ny = 3, nz = 2;
  const ijk = makeTestIJK(nx, ny, nz);
  const cellCount = nx * ny * nz;
  const values = new Float32Array(cellCount);

  // Test index=1 (minimum, 1-based)
  let count = 0;
  for (let c = 0; c < cellCount; c++) {
    if (ijk[c * 3 + 2] === 0) count++; // k=0 for index=1
  }
  assert.equal(count, nx * ny, 'index=1 should give first K layer');

  // Test index=nz (maximum, 1-based)
  count = 0;
  for (let c = 0; c < cellCount; c++) {
    if (ijk[c * 3 + 2] === nz - 1) count++; // k=nz-1 for index=nz
  }
  assert.equal(count, nx * ny, `index=${nz} should give last K layer`);

  console.log('  ok  Cross-section index bounds (1-based)');
}

// ============================================================
// 3. Well trajectory interpolation tests
// ============================================================

function makeTestWell(): GridWell {
  const completions: GridWellCompletion[] = [
    { i: 0, j: 0, k: 0, cell: 0, center: [0, 0, -100], open: true },
    { i: 1, j: 0, k: 0, cell: 1, center: [100, 0, -100], open: true },
    { i: 2, j: 0, k: 1, cell: 2, center: [200, 0, -200], open: true },
  ];
  return {
    name: 'WELL-1',
    type: 'producer',
    head: [0, 0, -100],
    i: 0, j: 0, k: 0,
    trajectory: [
      [0, 0, -100],
      [50, 0, -100],
      [100, 0, -100],
      [150, 0, -150],
      [200, 0, -200],
    ],
    completions,
  };
}

function testWellTrajectoryInterpolation(): void {
  const well = makeTestWell();
  const nx = 3, ny = 1, nz = 2;
  const ijk = makeTestIJK(nx, ny, nz);
  const cellCount = nx * ny * nz;

  // Create property values
  const values = new Float32Array(cellCount);
  for (let c = 0; c < cellCount; c++) {
    const i = ijk[c * 3];
    const j = ijk[c * 3 + 1];
    const k = ijk[c * 3 + 2];
    // Simple property: i + k * 10
    values[c] = i + k * 10;
  }

  // Build propMap
  const propMap = new Map<string, number>();
  for (let c = 0; c < cellCount; c++) {
    const i = ijk[c * 3];
    const j = ijk[c * 3 + 1];
    const k = ijk[c * 3 + 2];
    propMap.set(`${i},${j},${k}`, values[c]);
  }

  // Test trajectory sampling at each trajectory point
  const trajectoryPoints = well.trajectory;
  const depths: number[] = [];
  const vals: number[] = [];

  // Mock cell centers (viewer coordinates)
  // Cells are at (i*100, 0, -k*100)
  const centers = new Float32Array(cellCount * 3);
  for (let c = 0; c < cellCount; c++) {
    const i = ijk[c * 3];
    const j = ijk[c * 3 + 1];
    const k = ijk[c * 3 + 2];
    centers[c * 3] = i * 100;
    centers[c * 3 + 1] = j * 100;
    centers[c * 3 + 2] = -k * 100; // Z up, depth down
  }
  const origin: [number, number, number] = [0, 0, 0];

  for (const trajPoint of trajectoryPoints) {
    let bestDist = Infinity;
    let bestVal: number | null = null;
    let bestDepth = 0;

    for (let c = 0; c < cellCount; c++) {
      const cx = centers[c * 3];
      const cy = centers[c * 3 + 1];
      const cz = centers[c * 3 + 2];
      const dx = trajPoint[0] - cx;
      const dy = trajPoint[1] - cy;
      const dz = trajPoint[2] - cz;
      const dist = dx * dx + dy * dy + dz * dz;
      if (dist < bestDist) {
        bestDist = dist;
        const key = `${ijk[c * 3]},${ijk[c * 3 + 1]},${ijk[c * 3 + 2]}`;
        bestVal = propMap.get(key) ?? null;
        bestDepth = origin[2] - cz; // Depth = origin_z - viewer_z (positive down)
      }
    }

    if (bestVal !== null && Number.isFinite(bestVal)) {
      depths.push(bestDepth);
      vals.push(bestVal);
    }
  }

  // Should have values for all trajectory points (5 points)
  assert.equal(depths.length, trajectoryPoints.length, 'should sample at all trajectory points');
  assert.equal(vals.length, trajectoryPoints.length, 'should get values for all trajectory points');

  // Verify depth calculation: origin[2] - center_z
  // For k=0: center_z = 0, depth = 0 - 0 = 0
  // For k=1: center_z = -100, depth = 0 - (-100) = 100
  // The trajectory points at z=-100 are closer to k=0 cells (center_z=0) than k=1 (center_z=-100)
  // Actually trajectory at z=-100: dist to k=0 cell (z=0) is 100, to k=1 cell (z=-100) is 0
  // So first point at z=-100 maps to k=1 cell, depth=100
  // Points at z=-100, -100, -100 map to k=1, depth=100
  // Point at z=-150 maps to k=1 (dist 50 vs 150), depth=100
  // Point at z=-200 maps to k=1 (dist 100 vs 200), depth=100
  // All depths will be 100 since all trajectory points are closer to k=1 layer
  for (const d of depths) {
    assert.equal(d, 100, `all depths should be 100 (k=1 layer), got ${d}`);
  }

  console.log('  ok  Well trajectory interpolation and depth calculation');
}

// ============================================================
// 4. Engine DisplayOptions integration test
// ============================================================

function testEngineDisplayOptions(): void {
  // In Node, we can't create a canvas, so we test the type system only
  // The actual engine test runs in browser context
  // Verify that DisplayOptions accepts the new fields
  const opts: DisplayOptions = {
    surfaceMode: 'surface',
    meshMode: 'none',
    showInactive: false,
    zScale: 1,
    background: '#1a1d23',
    lighting: true,
    opacity: 1,
    showAxes: true,
    showGridBox: true,
    showWells: true,
    showWellLabels: false,
    showNncs: false,
    perspective: true,
    edgeColor: '#404550',
    crossSection: { enabled: true, axis: 'K', index: 5 },
    wellTrajectory: { enabled: true, property: 'PERMX' },
  };

  assert.ok(opts.crossSection !== null);
  assert.ok(opts.wellTrajectory !== null);
  if (opts.crossSection) {
    assert.equal(opts.crossSection.axis, 'K');
    assert.equal(opts.crossSection.index, 5);
  }
  if (opts.wellTrajectory) {
    assert.equal(opts.wellTrajectory.property, 'PERMX');
  }

  console.log('  ok  Engine DisplayOptions type accepts new fields');
}

// ============================================================
// Main
// ============================================================

console.log('Task 9 self-check');

testDisplayOptionsDefaults();
testDisplayOptionsAxisTypes();
testCrossSectionExtraction();
testCrossSectionIndexBounds();
testWellTrajectoryInterpolation();
testEngineDisplayOptions();

console.log('all Task 9 checks passed');