/**
 * WebGL rendering engine for the 3D reservoir viewer.
 *
 * A browser reimplementation of ResInsight's 3D view. No React, no fetching:
 * the UI owns all state and pushes it down, the engine only reports picks and
 * hovers back up.
 *
 * Design notes that matter for performance on a field-scale grid (Norne:
 * 145296 vertices / 36324 quads):
 *
 *  - The surface is ONE indexed BufferGeometry with a per-vertex colour
 *    attribute, drawn in one call. Wireframe is a second call over the same
 *    position buffer.
 *  - Cell filtering never touches positions. Vertices are packed four per
 *    quad by `build_surface`, so quad q owns vertices 4q..4q+3, triangles
 *    2q..2q+1 and edge segments 4q..4q+3. Filtering rewrites a prefix of the
 *    preallocated index buffer and moves `drawRange`; only that prefix is
 *    re-uploaded. A full Norne rebuild is a single pass over 36324 quads.
 *  - Rendering is on demand. The rAF loop only issues a draw when something
 *    changed or the orbit damping is still settling.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ParsedMesh } from './meshFormat';
import { FACE_NAMES } from './meshFormat';

export interface CellInfo {
  activeIndex: number;
  /** Zero-based. -1 until `setCellIjk` has been called. */
  i: number;
  j: number;
  k: number;
  center: [number, number, number]; // viewer coords
  depth: number; // positive down, grid units
  faceId: number;
  faceName: string;
  point: [number, number, number]; // exact hit point, viewer coords
}

export interface CellFilter {
  iMin: number;
  iMax: number; // inclusive, zero-based
  jMin: number;
  jMax: number;
  kMin: number;
  kMax: number;
  propertyRange: { min: number; max: number; exclude: boolean } | null;
  hiddenCells: Int32Array | null;
}

export interface DisplayOptions {
  surfaceMode: 'surface' | 'faults_only' | 'none';
  meshMode: 'full' | 'faults_only' | 'none';
  showInactive: boolean;
  zScale: number;
  background: string;
  lighting: boolean;
  opacity: number;
  showAxes: boolean;
  showGridBox: boolean;
  showWells: boolean;
  showWellLabels: boolean;
  showNncs: boolean;
  perspective: boolean;
  edgeColor: string;
}

export type WellType =
  | 'producer'
  | 'oil_injector'
  | 'gas_injector'
  | 'water_injector'
  | 'unknown';

export interface WellCompletion {
  i: number;
  j: number;
  k: number;
  cell: number;
  center: [number, number, number];
  open: boolean;
}

/** Structurally identical to `GridWell` in src/types.ts. */
export interface Well {
  name: string;
  type: WellType;
  head: [number, number, number];
  i: number;
  j: number;
  k: number;
  trajectory: [number, number, number][];
  completions: WellCompletion[];
}

// Okabe-Ito, which stays distinguishable under all three common forms of
// colour blindness. ResInsight's own well colours are not.
const WELL_COLORS: Record<WellType, number> = {
  producer: 0x009e73, // bluish green
  oil_injector: 0xcc79a7, // reddish purple
  gas_injector: 0xd55e00, // vermillion
  water_injector: 0x0072b2, // blue
  unknown: 0x999999,
};

/** What focusWell needs to know about one well after setWells built it. */
interface WellEntry {
  materials: THREE.MeshLambertMaterial[];
  bounds: THREE.Box3;
  radius: number;
}

const DEFAULT_DISPLAY: DisplayOptions = {
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
};

const FOV = 45;
const HOVER_INTERVAL_MS = 50;
const CLICK_SLOP_PX = 4;

/** Guard against a zero-size canvas before layout has settled. */
function safeSize(canvas: HTMLCanvasElement): { w: number; h: number } {
  return {
    w: Math.max(1, canvas.clientWidth || canvas.width || 1),
    h: Math.max(1, canvas.clientHeight || canvas.height || 1),
  };
}

export class Viewer3DEngine {
  private canvas: HTMLCanvasElement;
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private modelRoot = new THREE.Group();

  private perspCamera: THREE.PerspectiveCamera;
  private orthoCamera: THREE.OrthographicCamera;
  private camera: THREE.Camera;
  private controls: OrbitControls;

  private display: DisplayOptions = { ...DEFAULT_DISPLAY };
  private filter: CellFilter | null = null;

  // --- mesh state -----------------------------------------------------
  private mesh: ParsedMesh | null = null;
  private geometry: THREE.BufferGeometry | null = null;
  private surface: THREE.Mesh | null = null;
  private wireframe: THREE.LineSegments | null = null;
  private wireGeometry: THREE.BufferGeometry | null = null;

  private litMaterial: THREE.MeshLambertMaterial;
  private flatMaterial: THREE.MeshBasicMaterial;
  private edgeMaterial: THREE.LineBasicMaterial;

  private quadCount = 0;
  /** Active-cell index per quad. */
  private quadCell: Int32Array = new Int32Array(0);
  /** Per-quad fault flag, from setFaultMask. */
  private quadFault: Uint8Array | null = null;
  /** Centroid of each cell's drawn vertices, 3 per active cell. */
  private cellCenters: Float32Array = new Float32Array(0);
  private cellCount = 0;
  private cellIjk: Int32Array | null = null;
  private values: Float32Array | null = null;
  /** Scratch reused by the filter so slider drags allocate nothing. */
  private hiddenMask: Uint8Array | null = null;
  private surfaceIndex: THREE.BufferAttribute | null = null;
  private edgeIndex: THREE.BufferAttribute | null = null;
  private visibleBounds = new THREE.Box3();
  private modelBounds = new THREE.Box3();

  // --- overlays -------------------------------------------------------
  private gridBox: THREE.Box3Helper | null = null;
  private axisScene = new THREE.Scene();
  private axisCamera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  private wellGroup = new THREE.Group();
  private labelGroup = new THREE.Group();
  /** Per-well materials and extent, for focusWell. Rebuilt by setWells. */
  private wellMeshes = new Map<string, WellEntry>();
  private focusedWell: string | null = null;
  private nncLines: THREE.LineSegments | null = null;
  private highlight: THREE.LineSegments | null = null;
  private highlightFill: THREE.Mesh | null = null;
  /** Objects whose Z must be un-exaggerated so they stay round. */
  private zCompensated: THREE.Object3D[] = [];
  /** Lives as long as the engine: shared materials, axis triad assets. */
  private coreDisposables: Array<{ dispose(): void }> = [];
  /** Rebuilt on every setWells; released first so time-step scrubs are flat. */
  private wellDisposables: Array<{ dispose(): void }> = [];

  // --- interaction ----------------------------------------------------
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private pickCb: ((info: CellInfo | null) => void) | null = null;
  private hoverCb: ((info: CellInfo | null) => void) | null = null;
  private downX = 0;
  private downY = 0;
  private hoverPending = false;
  private lastHoverAt = 0;
  private dirty = true;
  private rafId = 0;
  private disposed = false;

  private onPointerDown: (e: PointerEvent) => void;
  private onPointerUp: (e: PointerEvent) => void;
  private onPointerMove: (e: PointerEvent) => void;
  private onPointerLeave: () => void;
  private onControlsChange: () => void;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const { w, h } = safeSize(canvas);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      // Screenshots re-render synchronously before reading the buffer, so we
      // do not pay the preserveDrawingBuffer cost on every frame.
      preserveDrawingBuffer: false,
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h, false);
    this.renderer.sortObjects = true;

    this.scene.background = new THREE.Color(this.display.background);
    this.scene.add(this.modelRoot);
    this.modelRoot.add(this.wellGroup);
    this.wellGroup.add(this.labelGroup);

    this.perspCamera = new THREE.PerspectiveCamera(FOV, w / h, 0.1, 1e7);
    this.perspCamera.up.set(0, 0, 1);
    this.perspCamera.position.set(1, -1, 1);
    this.orthoCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, -1e7, 1e7);
    this.orthoCamera.up.set(0, 0, 1);
    this.orthoCamera.position.set(1, -1, 1);
    this.camera = this.perspCamera;

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.12;
    this.controls.screenSpacePanning = true;

    // Two head lights on the camera plus a fill, so rotating never leaves the
    // model in shadow. Attaching to the camera keeps shading stable.
    const key = new THREE.DirectionalLight(0xffffff, 2.0);
    key.position.set(0.4, 0.6, 1);
    const rim = new THREE.DirectionalLight(0xffffff, 0.6);
    rim.position.set(-0.6, -0.4, -0.5);
    this.perspCamera.add(key, rim);
    this.orthoCamera.add(key.clone(), rim.clone());
    this.scene.add(this.perspCamera, this.orthoCamera);
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.1));

    this.litMaterial = new THREE.MeshLambertMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
      // Push the surface back a hair so the wireframe drawn over it does not
      // z-fight; this is exactly what ResInsight does for its mesh lines.
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });
    this.flatMaterial = new THREE.MeshBasicMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });
    this.edgeMaterial = new THREE.LineBasicMaterial({ color: this.display.edgeColor });
    this.coreDisposables.push(this.litMaterial, this.flatMaterial, this.edgeMaterial);

    this.buildAxisTriad();

    this.onPointerDown = (e) => {
      this.downX = e.clientX;
      this.downY = e.clientY;
    };
    this.onPointerUp = (e) => {
      if (!this.pickCb) return;
      if (
        Math.abs(e.clientX - this.downX) > CLICK_SLOP_PX ||
        Math.abs(e.clientY - this.downY) > CLICK_SLOP_PX
      ) {
        return; // an orbit/pan drag, not a click
      }
      this.updatePointer(e);
      const info = this.pickAtPointer();
      this.setHighlight(info ? info.activeIndex : -1);
      this.pickCb(info);
    };
    this.onPointerMove = (e) => {
      if (!this.hoverCb) return;
      this.updatePointer(e);
      this.hoverPending = true;
    };
    this.onPointerLeave = () => {
      this.hoverPending = false;
      if (this.hoverCb) this.hoverCb(null);
    };
    this.onControlsChange = () => {
      this.dirty = true;
    };

    canvas.addEventListener('pointerdown', this.onPointerDown);
    canvas.addEventListener('pointerup', this.onPointerUp);
    canvas.addEventListener('pointermove', this.onPointerMove);
    canvas.addEventListener('pointerleave', this.onPointerLeave);
    this.controls.addEventListener('change', this.onControlsChange);

    this.tick = this.tick.bind(this);
    this.rafId = requestAnimationFrame(this.tick);
  }

  // ==================================================================
  // Mesh
  // ==================================================================

  setMesh(mesh: ParsedMesh): void {
    this.clearMesh();
    this.mesh = mesh;

    const nVerts = mesh.vertexCount;
    const nQuads = nVerts >> 2;
    this.quadCount = nQuads;

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(mesh.positions, 3));
    geo.setAttribute('normal', new THREE.BufferAttribute(mesh.normals, 3));
    // Start white so a mesh with no property loaded still renders.
    const colors = new Float32Array(nVerts * 3).fill(0.78);
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Preallocate the full index buffers once; filtering only ever rewrites a
    // prefix of them and moves drawRange.
    this.surfaceIndex = new THREE.BufferAttribute(new Uint32Array(nQuads * 6), 1);
    this.surfaceIndex.setUsage(THREE.DynamicDrawUsage);
    geo.setIndex(this.surfaceIndex);
    this.geometry = geo;

    const wireGeo = new THREE.BufferGeometry();
    wireGeo.setAttribute('position', new THREE.BufferAttribute(mesh.positions, 3));
    this.edgeIndex = new THREE.BufferAttribute(new Uint32Array(nQuads * 8), 1);
    this.edgeIndex.setUsage(THREE.DynamicDrawUsage);
    wireGeo.setIndex(this.edgeIndex);
    this.wireGeometry = wireGeo;

    // Per-quad cell/face, and the model bounds, in one pass.
    this.quadCell = new Int32Array(nQuads);
    let maxCell = -1;
    for (let q = 0; q < nQuads; q++) {
      const c = mesh.cellIds[q * 4];
      this.quadCell[q] = c;
      if (c > maxCell) maxCell = c;
    }
    this.cellCount = maxCell + 1;

    // Cell "centre" = centroid of the cell's drawn vertices. The mesh only
    // carries the visible skin, so for a fully exposed cell this is the true
    // centre and for a partly buried one it is the centre of what you can
    // see, which is what a pick readout wants anyway.
    this.cellCenters = new Float32Array(Math.max(0, this.cellCount) * 3);
    const counts = new Int32Array(Math.max(0, this.cellCount));
    for (let v = 0; v < nVerts; v++) {
      const c = mesh.cellIds[v];
      if (c < 0) continue;
      this.cellCenters[c * 3] += mesh.positions[v * 3];
      this.cellCenters[c * 3 + 1] += mesh.positions[v * 3 + 1];
      this.cellCenters[c * 3 + 2] += mesh.positions[v * 3 + 2];
      counts[c]++;
    }
    for (let c = 0; c < this.cellCount; c++) {
      const n = counts[c];
      if (n > 0) {
        this.cellCenters[c * 3] /= n;
        this.cellCenters[c * 3 + 1] /= n;
        this.cellCenters[c * 3 + 2] /= n;
      }
    }

    this.modelBounds.makeEmpty();
    const p = new THREE.Vector3();
    for (let v = 0; v < nVerts; v++) {
      this.modelBounds.expandByPoint(
        p.set(mesh.positions[v * 3], mesh.positions[v * 3 + 1], mesh.positions[v * 3 + 2])
      );
    }
    geo.boundingBox = this.modelBounds.clone();
    geo.boundingSphere = this.modelBounds.getBoundingSphere(new THREE.Sphere());
    wireGeo.boundingBox = geo.boundingBox.clone();
    wireGeo.boundingSphere = geo.boundingSphere.clone();

    this.surface = new THREE.Mesh(geo, this.display.lighting ? this.litMaterial : this.flatMaterial);
    this.surface.frustumCulled = false;
    this.wireframe = new THREE.LineSegments(wireGeo, this.edgeMaterial);
    this.wireframe.frustumCulled = false;
    this.modelRoot.add(this.surface, this.wireframe);

    this.gridBox = new THREE.Box3Helper(this.modelBounds.clone(), new THREE.Color(0x6a7280));
    this.gridBox.visible = this.display.showGridBox;
    this.modelRoot.add(this.gridBox);

    this.rebuildIndices();
    this.applyDisplay();
    this.zoomAll();
    this.dirty = true;
  }

  setColors(rgb: Float32Array): void {
    if (!this.geometry) return;
    const attr = this.geometry.getAttribute('color') as THREE.BufferAttribute;
    const dst = attr.array as Float32Array;
    dst.set(rgb.length > dst.length ? rgb.subarray(0, dst.length) : rgb);
    attr.needsUpdate = true;
    this.dirty = true;
  }

  /** Per-active-cell values used by the property-range filter. */
  setValues(values: Float32Array | null): void {
    this.values = values;
    if (this.filter?.propertyRange) this.rebuildIndices();
    this.dirty = true;
  }

  /**
   * Fault flag per quad (length = quadCount). A per-vertex mask
   * (length = quadCount * 4, as the backend's face arrays are shaped) is also
   * accepted and sampled every fourth entry.
   */
  setFaultMask(isFault: Uint8Array | null): void {
    if (!isFault) {
      this.quadFault = null;
    } else if (isFault.length >= this.quadCount * 4) {
      const q = new Uint8Array(this.quadCount);
      for (let i = 0; i < this.quadCount; i++) q[i] = isFault[i * 4];
      this.quadFault = q;
    } else {
      this.quadFault = isFault;
    }
    this.rebuildIndices();
    this.dirty = true;
  }

  /**
   * CONTRACT ADDITION. i,j,k per active cell, 3 entries each, so the engine
   * can fill CellInfo and honour the I/J/K range filter. The mesh only
   * carries a flat active-cell index; without this the engine cannot know
   * where a cell sits in the grid. Call it once after `setMesh`.
   */
  setCellIjk(ijk: Int32Array): void {
    this.cellIjk = ijk;
    this.rebuildIndices();
    this.dirty = true;
  }

  /**
   * CONTRACT ADDITION. Non-neighbour connections drawn as line segments.
   * `pairs` holds two active-cell indices per NNC; `centers` holds three
   * floats per active cell (viewer coords). Pass an empty `centers` to fall
   * back to the centroids the engine derives from the mesh.
   */
  setNncs(pairs: Int32Array, centers: Float32Array): void {
    this.disposeNncs();
    const src = centers.length >= this.cellCount * 3 ? centers : this.cellCenters;
    const n = pairs.length >> 1;
    if (n === 0 || src.length === 0) {
      this.dirty = true;
      return;
    }

    const pts = new Float32Array(n * 6);
    let out = 0;
    for (let i = 0; i < n; i++) {
      const a = pairs[i * 2];
      const b = pairs[i * 2 + 1];
      if (a < 0 || b < 0 || a * 3 + 2 >= src.length || b * 3 + 2 >= src.length) continue;
      pts[out++] = src[a * 3];
      pts[out++] = src[a * 3 + 1];
      pts[out++] = src[a * 3 + 2];
      pts[out++] = src[b * 3];
      pts[out++] = src[b * 3 + 1];
      pts[out++] = src[b * 3 + 2];
    }
    if (out === 0) {
      this.dirty = true;
      return;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pts.subarray(0, out), 3));
    const mat = new THREE.LineBasicMaterial({ color: 0xffb000, transparent: true, opacity: 0.9 });
    this.nncLines = new THREE.LineSegments(geo, mat);
    this.nncLines.visible = this.display.showNncs;
    this.nncLines.frustumCulled = false;
    this.modelRoot.add(this.nncLines);
    this.dirty = true;
  }

  // ==================================================================
  // Filtering
  // ==================================================================

  setFilter(filter: CellFilter): void {
    this.filter = filter;
    this.rebuildIndices();
    this.dirty = true;
  }

  /**
   * Rewrite the surface and wireframe index prefixes from the visible quads.
   * One pass over `quadCount`; nothing is reallocated and positions are never
   * re-uploaded, which is what keeps a filter-slider drag interactive.
   */
  private rebuildIndices(): void {
    if (!this.geometry || !this.surfaceIndex || !this.edgeIndex || !this.mesh) return;

    const nq = this.quadCount;
    const f = this.filter;
    const ijk = this.cellIjk;
    const values = this.values;
    const range = f?.propertyRange ?? null;
    const fault = this.quadFault;
    const surfaceMode = this.display.surfaceMode;
    const meshMode = this.display.meshMode;

    // Explicit hide list -> byte mask, reusing the same buffer across calls.
    let hidden: Uint8Array | null = null;
    if (f?.hiddenCells && f.hiddenCells.length > 0 && this.cellCount > 0) {
      if (!this.hiddenMask || this.hiddenMask.length !== this.cellCount) {
        this.hiddenMask = new Uint8Array(this.cellCount);
      } else {
        this.hiddenMask.fill(0);
      }
      for (let i = 0; i < f.hiddenCells.length; i++) {
        const c = f.hiddenCells[i];
        if (c >= 0 && c < this.cellCount) this.hiddenMask[c] = 1;
      }
      hidden = this.hiddenMask;
    }

    // I/J/K filtering needs the lookup the UI supplies via setCellIjk; without
    // it the engine has only a flat active-cell index and cannot range-filter.
    const useIjk = !!f && !!ijk;

    const tri = this.surfaceIndex.array as Uint32Array;
    const seg = this.edgeIndex.array as Uint32Array;
    const positions = this.mesh.positions;

    let ti = 0;
    let si = 0;
    let minX = Infinity;
    let minY = Infinity;
    let minZ = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    let maxZ = -Infinity;

    for (let q = 0; q < nq; q++) {
      const cell = this.quadCell[q];

      if (hidden && cell >= 0 && hidden[cell]) continue;

      if (useIjk && ijk && cell >= 0) {
        const o = cell * 3;
        const i = ijk[o];
        const j = ijk[o + 1];
        const k = ijk[o + 2];
        if (i < f!.iMin || i > f!.iMax) continue;
        if (j < f!.jMin || j > f!.jMax) continue;
        if (k < f!.kMin || k > f!.kMax) continue;
      }

      if (range && values && cell >= 0 && cell < values.length) {
        const v = values[cell];
        const inside = Number.isFinite(v) && v >= range.min && v <= range.max;
        if (range.exclude ? inside : !inside) continue;
      }

      const isFault = fault ? fault[q] !== 0 : false;
      const drawSurface =
        surfaceMode === 'surface' || (surfaceMode === 'faults_only' && isFault);
      const drawEdges = meshMode === 'full' || (meshMode === 'faults_only' && isFault);

      const b = q * 4;

      if (drawSurface) {
        tri[ti] = b;
        tri[ti + 1] = b + 1;
        tri[ti + 2] = b + 2;
        tri[ti + 3] = b;
        tri[ti + 4] = b + 2;
        tri[ti + 5] = b + 3;
        ti += 6;
      }
      if (drawEdges) {
        seg[si] = b;
        seg[si + 1] = b + 1;
        seg[si + 2] = b + 1;
        seg[si + 3] = b + 2;
        seg[si + 4] = b + 2;
        seg[si + 5] = b + 3;
        seg[si + 6] = b + 3;
        seg[si + 7] = b;
        si += 8;
      }
      if (!drawSurface && !drawEdges) continue;

      // Bounds of what is actually on screen, so zoomAll frames the filter.
      for (let c = 0; c < 4; c++) {
        const o = (b + c) * 3;
        const x = positions[o];
        const y = positions[o + 1];
        const z = positions[o + 2];
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (z < minZ) minZ = z;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
        if (z > maxZ) maxZ = z;
      }
    }

    if (minX === Infinity) {
      this.visibleBounds.copy(this.modelBounds);
    } else {
      this.visibleBounds.min.set(minX, minY, minZ);
      this.visibleBounds.max.set(maxX, maxY, maxZ);
    }

    this.surfaceIndex.clearUpdateRanges();
    this.surfaceIndex.addUpdateRange(0, ti);
    this.surfaceIndex.needsUpdate = true;
    this.geometry.setDrawRange(0, ti);

    this.edgeIndex.clearUpdateRanges();
    this.edgeIndex.addUpdateRange(0, si);
    this.edgeIndex.needsUpdate = true;
    this.wireGeometry?.setDrawRange(0, si);

    if (this.surface) this.surface.visible = ti > 0;
    if (this.wireframe) this.wireframe.visible = si > 0;
  }

  // ==================================================================
  // Display options
  // ==================================================================

  setDisplay(opts: Partial<DisplayOptions>): void {
    const prev = this.display;
    this.display = { ...prev, ...opts };
    const d = this.display;

    if (d.surfaceMode !== prev.surfaceMode || d.meshMode !== prev.meshMode) {
      this.rebuildIndices();
    }
    if (d.perspective !== prev.perspective) this.switchCamera(d.perspective);
    this.applyDisplay();
    this.dirty = true;
  }

  private applyDisplay(): void {
    const d = this.display;

    (this.scene.background as THREE.Color).set(d.background);

    // Non-uniform Z scale. three.js builds a proper normal matrix
    // (transpose(inverse(modelView))) per object and normalises in the
    // shader, so lighting stays correct without touching the normals.
    const z = d.zScale > 0 ? d.zScale : 1;
    this.modelRoot.scale.set(1, 1, z);
    this.modelRoot.updateMatrixWorld(true);
    for (const o of this.zCompensated) o.scale.setZ(1 / z);

    if (this.surface) {
      const mat = d.lighting ? this.litMaterial : this.flatMaterial;
      this.surface.material = mat;
      const opaque = d.opacity >= 1;
      for (const m of [this.litMaterial, this.flatMaterial]) {
        m.opacity = d.opacity;
        m.transparent = !opaque;
        // Transparent grids read as mush when every face writes depth; drop
        // depth writes and let the sorter handle back-to-front, which is
        // what ResInsight's transparent surfaces do.
        m.depthWrite = opaque;
        m.needsUpdate = true;
      }
      this.surface.renderOrder = opaque ? 0 : 1;
    }

    this.edgeMaterial.color.set(d.edgeColor);
    if (this.gridBox) this.gridBox.visible = d.showGridBox;
    this.wellGroup.visible = d.showWells;
    this.labelGroup.visible = d.showWells && d.showWellLabels;
    if (this.nncLines) this.nncLines.visible = d.showNncs;
  }

  // ==================================================================
  // Camera
  // ==================================================================

  private switchCamera(perspective: boolean): void {
    const target = this.controls.target.clone();
    const from = this.camera as THREE.PerspectiveCamera | THREE.OrthographicCamera;
    const dist = from.position.distanceTo(target);
    const { w, h } = safeSize(this.canvas);
    const aspect = w / h;

    if (perspective) {
      // Recover the distance that reproduces the orthographic frustum height.
      const o = this.orthoCamera;
      const viewH = (o.top - o.bottom) / o.zoom;
      const d = viewH / 2 / Math.tan((FOV * Math.PI) / 360);
      this.perspCamera.position
        .copy(target)
        .add(o.position.clone().sub(target).normalize().multiplyScalar(d));
      this.perspCamera.up.copy(o.up);
      this.perspCamera.aspect = aspect;
      this.perspCamera.updateProjectionMatrix();
      this.camera = this.perspCamera;
    } else {
      const viewH = 2 * dist * Math.tan((FOV * Math.PI) / 360);
      const viewW = viewH * aspect;
      const o = this.orthoCamera;
      o.left = -viewW / 2;
      o.right = viewW / 2;
      o.top = viewH / 2;
      o.bottom = -viewH / 2;
      o.zoom = 1;
      o.position.copy(from.position);
      o.up.copy(from.up);
      o.updateProjectionMatrix();
      this.camera = o;
    }

    this.camera.lookAt(target);
    // OrbitControls binds one camera at construction; retarget in place
    // rather than rebuilding (which would drop our 'change' listener).
    this.controls.object = this.camera as THREE.PerspectiveCamera;
    this.controls.target.copy(target);
    this.controls.update();
  }

  viewAlong(axis: '+x' | '-x' | '+y' | '-y' | '+z' | '-z'): void {
    const box = this.visibleBounds.isEmpty() ? this.modelBounds : this.visibleBounds;
    if (box.isEmpty()) return;

    const center = this.worldCenter(box);
    const radius = this.worldRadius(box);
    const dist = this.distanceFor(radius);

    const dir = new THREE.Vector3();
    switch (axis) {
      case '+x':
        dir.set(1, 0, 0);
        break;
      case '-x':
        dir.set(-1, 0, 0);
        break;
      case '+y':
        dir.set(0, 1, 0);
        break;
      case '-y':
        dir.set(0, -1, 0);
        break;
      case '+z':
        dir.set(0, 0, 1);
        break;
      case '-z':
        dir.set(0, 0, -1);
        break;
    }
    // Looking straight down Z needs a different up or the view degenerates.
    const up = axis === '+z' || axis === '-z' ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, 1);

    this.camera.up.copy(up);
    this.camera.position.copy(center).addScaledVector(dir, dist);
    this.controls.target.copy(center);
    this.fitFrustum(radius);
    this.camera.lookAt(center);
    this.controls.update();
    this.dirty = true;
  }

  zoomAll(): void {
    const box = this.visibleBounds.isEmpty() ? this.modelBounds : this.visibleBounds;
    if (box.isEmpty()) return;

    const center = this.worldCenter(box);
    const radius = this.worldRadius(box);
    const dist = this.distanceFor(radius);

    const dir = this.camera.position.clone().sub(this.controls.target);
    if (dir.lengthSq() < 1e-12) dir.set(1, -1, 0.6);
    dir.normalize();

    this.camera.position.copy(center).addScaledVector(dir, dist);
    this.controls.target.copy(center);
    this.fitFrustum(radius);
    this.camera.lookAt(center);
    this.controls.update();
    this.dirty = true;
  }

  /** Box is in model space; the camera lives in world space (Z exaggerated). */
  private worldCenter(box: THREE.Box3): THREE.Vector3 {
    const c = box.getCenter(new THREE.Vector3());
    c.z *= this.modelRoot.scale.z;
    return c;
  }

  private worldRadius(box: THREE.Box3): number {
    const s = box.getSize(new THREE.Vector3());
    s.z *= this.modelRoot.scale.z;
    return Math.max(1e-3, s.length() / 2);
  }

  private distanceFor(radius: number): number {
    return (radius / Math.sin((FOV * Math.PI) / 360)) * 1.05;
  }

  private fitFrustum(radius: number): void {
    const { w, h } = safeSize(this.canvas);
    const aspect = w / h;
    if (this.camera === this.orthoCamera) {
      const o = this.orthoCamera;
      const half = radius * 1.05;
      o.left = -half * aspect;
      o.right = half * aspect;
      o.top = half;
      o.bottom = -half;
      o.zoom = 1;
      o.near = -radius * 100;
      o.far = radius * 100;
      o.updateProjectionMatrix();
    } else {
      const p = this.perspCamera;
      p.aspect = aspect;
      p.near = Math.max(radius * 1e-4, 1e-3);
      p.far = radius * 200;
      p.updateProjectionMatrix();
    }
  }

  // ==================================================================
  // Picking
  // ==================================================================

  onPick(cb: (info: CellInfo | null) => void): void {
    this.pickCb = cb;
  }

  onHover(cb: (info: CellInfo | null) => void): void {
    this.hoverCb = cb;
  }

  private updatePointer(e: PointerEvent): void {
    const r = this.canvas.getBoundingClientRect();
    this.pointer.x = ((e.clientX - r.left) / Math.max(1, r.width)) * 2 - 1;
    this.pointer.y = -((e.clientY - r.top) / Math.max(1, r.height)) * 2 + 1;
  }

  /**
   * ponytail: brute-force raycast over the visible draw range. Norne is 72k
   * triangles, roughly 10 ms, which is why hover is throttled rather than run
   * per pointermove. Add a BVH (three-mesh-bvh or a hand-rolled grid over the
   * quad list) if picking ever needs to be per-frame.
   */
  private pickAtPointer(): CellInfo | null {
    if (!this.surface || !this.mesh || !this.surface.visible) return null;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObject(this.surface, false);
    if (hits.length === 0) return null;

    const hit = hits[0];
    const face = hit.face;
    if (!face) return null;

    const vertex = face.a;
    const cell = this.mesh.cellIds[vertex];
    const faceId = this.mesh.faceIds[vertex];

    // The hit point comes back in world space, where Z is exaggerated.
    const local = this.modelRoot.worldToLocal(hit.point.clone());

    const center: [number, number, number] =
      cell >= 0 && cell * 3 + 2 < this.cellCenters.length
        ? [
            this.cellCenters[cell * 3],
            this.cellCenters[cell * 3 + 1],
            this.cellCenters[cell * 3 + 2],
          ]
        : [local.x, local.y, local.z];

    let i = -1;
    let j = -1;
    let k = -1;
    if (this.cellIjk && cell >= 0 && cell * 3 + 2 < this.cellIjk.length) {
      i = this.cellIjk[cell * 3];
      j = this.cellIjk[cell * 3 + 1];
      k = this.cellIjk[cell * 3 + 2];
    }

    // build_surface subtracts the origin and flips Z, so raw depth (positive
    // downward, as ECLIPSE stores it) is originZ - zViewer.
    const depth = this.mesh.origin[2] - center[2];

    return {
      activeIndex: cell,
      i,
      j,
      k,
      center,
      depth,
      faceId,
      faceName: FACE_NAMES[faceId] ?? '?',
      point: [local.x, local.y, local.z],
    };
  }

  /** Outline + translucent fill over every drawn face of the picked cell. */
  private setHighlight(cell: number): void {
    this.disposeHighlight();
    if (cell < 0 || !this.mesh) {
      this.dirty = true;
      return;
    }

    const quads: number[] = [];
    for (let q = 0; q < this.quadCount; q++) {
      if (this.quadCell[q] === cell) quads.push(q);
    }
    if (quads.length === 0) {
      this.dirty = true;
      return;
    }

    // Copy the handful of vertices rather than sharing the main attribute:
    // disposing a geometry releases its attributes' GPU buffers, and these
    // come and go on every click.
    const pos = new Float32Array(quads.length * 4 * 3);
    const src = this.mesh.positions;
    for (let n = 0; n < quads.length; n++) {
      const b = quads[n] * 4;
      for (let c = 0; c < 4; c++) {
        const o = (b + c) * 3;
        const d = (n * 4 + c) * 3;
        pos[d] = src[o];
        pos[d + 1] = src[o + 1];
        pos[d + 2] = src[o + 2];
      }
    }

    const lineIdx = new Uint32Array(quads.length * 8);
    const triIdx = new Uint32Array(quads.length * 6);
    for (let n = 0; n < quads.length; n++) {
      const b = n * 4;
      const l = n * 8;
      lineIdx[l] = b;
      lineIdx[l + 1] = b + 1;
      lineIdx[l + 2] = b + 1;
      lineIdx[l + 3] = b + 2;
      lineIdx[l + 4] = b + 2;
      lineIdx[l + 5] = b + 3;
      lineIdx[l + 6] = b + 3;
      lineIdx[l + 7] = b;
      const t = n * 6;
      triIdx[t] = b;
      triIdx[t + 1] = b + 1;
      triIdx[t + 2] = b + 2;
      triIdx[t + 3] = b;
      triIdx[t + 4] = b + 2;
      triIdx[t + 5] = b + 3;
    }

    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    lineGeo.setIndex(new THREE.BufferAttribute(lineIdx, 1));
    const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false });
    this.highlight = new THREE.LineSegments(lineGeo, lineMat);
    this.highlight.renderOrder = 10;
    this.highlight.frustumCulled = false;

    const fillGeo = new THREE.BufferGeometry();
    fillGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    fillGeo.setIndex(new THREE.BufferAttribute(triIdx, 1));
    const fillMat = new THREE.MeshBasicMaterial({
      color: 0xffd54a,
      transparent: true,
      opacity: 0.35,
      depthTest: false,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    this.highlightFill = new THREE.Mesh(fillGeo, fillMat);
    this.highlightFill.renderOrder = 9;
    this.highlightFill.frustumCulled = false;

    this.modelRoot.add(this.highlight, this.highlightFill);
    this.dirty = true;
  }

  // ==================================================================
  // Wells
  // ==================================================================

  setWells(wells: Well[]): void {
    // A time-step scrub rebuilds every well; keep the emphasis on whichever
    // well the UI has selected instead of silently dropping it.
    const wasFocused = this.focusedWell;
    this.disposeWells();

    const size = this.modelBounds.isEmpty()
      ? 1000
      : this.modelBounds.getSize(new THREE.Vector3()).length();
    const radius = Math.max(size * 0.0015, 1e-3);
    const markerR = radius * 2.2;

    for (const well of wells) {
      const color = WELL_COLORS[well.type] ?? WELL_COLORS.unknown;
      const mat = new THREE.MeshLambertMaterial({ color, emissive: color, emissiveIntensity: 0.25 });
      this.wellDisposables.push(mat);

      // Per-well rather than shared, so focusWell can dim one well's closed
      // completions without touching another's.
      let closedMat: THREE.MeshLambertMaterial | null = null;
      const closed = (): THREE.MeshLambertMaterial => {
        if (!closedMat) {
          closedMat = new THREE.MeshLambertMaterial({ color: 0x666666 });
          this.wellDisposables.push(closedMat);
        }
        return closedMat;
      };

      const bounds = new THREE.Box3();
      const entry: WellEntry = { materials: [mat], bounds, radius };
      this.wellMeshes.set(well.name, entry);

      const pts = well.trajectory
        .filter((p) => p.every((v) => Number.isFinite(v)))
        .map((p) => new THREE.Vector3(p[0], p[1], p[2]));
      for (const p of pts) bounds.expandByPoint(p);

      if (pts.length >= 2) {
        const curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.2);
        const tube = new THREE.TubeGeometry(
          curve,
          Math.min(400, Math.max(8, pts.length * 3)),
          radius,
          6,
          false
        );
        const mesh = new THREE.Mesh(tube, mat);
        mesh.frustumCulled = false;
        this.wellGroup.add(mesh);
        this.wellDisposables.push(tube);
      }

      const head = pts[0] ?? new THREE.Vector3(...well.head);
      const headGeo = new THREE.SphereGeometry(markerR, 12, 8);
      const headMesh = new THREE.Mesh(headGeo, mat);
      headMesh.position.copy(head);
      headMesh.frustumCulled = false;
      this.wellGroup.add(headMesh);
      this.wellDisposables.push(headGeo);
      this.zCompensated.push(headMesh);

      bounds.expandByPoint(head);

      for (const comp of well.completions) {
        if (!comp.center.every((v) => Number.isFinite(v))) continue;
        const geo = new THREE.SphereGeometry(markerR * 0.7, 8, 6);
        const cm = comp.open ? mat : closed();
        if (!entry.materials.includes(cm)) entry.materials.push(cm);
        const m = new THREE.Mesh(geo, cm);
        m.position.set(comp.center[0], comp.center[1], comp.center[2]);
        m.frustumCulled = false;
        this.wellGroup.add(m);
        this.wellDisposables.push(geo);
        this.zCompensated.push(m);
        bounds.expandByPoint(m.position);
      }

      const label = this.makeLabel(well.name);
      // Lift the label clear of the head marker.
      label.position.set(head.x, head.y, head.z + markerR * 3);
      label.scale.multiplyScalar(size * 0.02);
      this.labelGroup.add(label);
    }

    this.focusedWell = wasFocused && this.wellMeshes.has(wasFocused) ? wasFocused : null;
    this.applyWellEmphasis();
    this.applyDisplay();
    this.dirty = true;
  }

  /**
   * CONTRACT ADDITION. Frame one well's trajectory and make it stand out:
   * every other well is dimmed to a fraction of its opacity. Pass null (or an
   * unknown name) to clear the emphasis without moving the camera.
   */
  focusWell(name: string | null): void {
    this.focusedWell = name && this.wellMeshes.has(name) ? name : null;
    this.applyWellEmphasis();

    const entry = this.focusedWell ? this.wellMeshes.get(this.focusedWell) : null;
    if (!entry || entry.bounds.isEmpty()) {
      this.dirty = true;
      return;
    }

    // A single-completion well is a point box; pad it by the tube radius so the
    // camera does not end up inside the well.
    const box = entry.bounds.clone().expandByScalar(Math.max(entry.radius * 12, 1e-3));
    const center = this.worldCenter(box);
    const radius = this.worldRadius(box);

    const dir = this.camera.position.clone().sub(this.controls.target);
    if (dir.lengthSq() < 1e-12) dir.set(1, -1, 0.6);
    dir.normalize();

    this.camera.position.copy(center).addScaledVector(dir, this.distanceFor(radius));
    this.controls.target.copy(center);
    this.fitFrustum(radius);
    this.camera.lookAt(center);
    this.controls.update();
    this.dirty = true;
  }

  /** Dim every well but the focused one. No-op when nothing is focused. */
  private applyWellEmphasis(): void {
    for (const [name, entry] of this.wellMeshes) {
      const dim = this.focusedWell !== null && name !== this.focusedWell;
      for (const m of entry.materials) {
        m.opacity = dim ? 0.2 : 1;
        m.transparent = dim;
        m.depthWrite = !dim;
        m.emissiveIntensity = dim ? 0 : 0.25;
        m.needsUpdate = true;
      }
    }
    this.dirty = true;
  }

  /** Text sprite drawn into a CanvasTexture, so no font dependency. */
  private makeLabel(text: string): THREE.Sprite {
    const pad = 8;
    const font = '600 44px system-ui, sans-serif';
    const measure = document.createElement('canvas').getContext('2d');
    let width = 200;
    if (measure) {
      measure.font = font;
      width = Math.ceil(measure.measureText(text).width) + pad * 2;
    }
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(16, width);
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.font = font;
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(15,18,24,0.75)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#f2f4f8';
      ctx.fillText(text, pad, canvas.height / 2);
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
    const sprite = new THREE.Sprite(mat);
    sprite.renderOrder = 20;
    // Keep the aspect ratio; setWells applies the world-size multiplier.
    sprite.scale.set(canvas.width / canvas.height, 1, 1);
    this.wellDisposables.push(tex, mat);
    return sprite;
  }

  // ==================================================================
  // Axis triad
  // ==================================================================

  private buildAxisTriad(): void {
    const axes = new THREE.AxesHelper(1);
    this.axisScene.add(axes);
    this.coreDisposables.push(axes);
    const labels: Array<[string, THREE.Vector3, string]> = [
      ['X', new THREE.Vector3(1.25, 0, 0), '#ff5a5a'],
      ['Y', new THREE.Vector3(0, 1.25, 0), '#5aff7a'],
      ['Z', new THREE.Vector3(0, 0, 1.25), '#6aa8ff'],
    ];
    for (const [text, pos, color] of labels) {
      const canvas = document.createElement('canvas');
      canvas.width = 64;
      canvas.height = 64;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.font = '700 48px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = color;
        ctx.fillText(text, 32, 34);
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.colorSpace = THREE.SRGBColorSpace;
      const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
      const sprite = new THREE.Sprite(mat);
      sprite.position.copy(pos);
      sprite.scale.setScalar(0.5);
      this.axisScene.add(sprite);
      this.coreDisposables.push(tex, mat);
    }
    this.axisCamera.up.set(0, 0, 1);
  }

  // ==================================================================
  // Frame loop
  // ==================================================================

  private tick(): void {
    if (this.disposed) return;
    this.rafId = requestAnimationFrame(this.tick);

    // OrbitControls returns true while damping is still moving the camera.
    if (this.controls.update()) this.dirty = true;

    if (this.hoverPending && this.hoverCb) {
      const now = performance.now();
      if (now - this.lastHoverAt >= HOVER_INTERVAL_MS) {
        this.lastHoverAt = now;
        this.hoverPending = false;
        this.hoverCb(this.pickAtPointer());
      }
    }

    if (this.dirty) {
      this.dirty = false;
      this.renderFrame();
    }
  }

  private renderFrame(): void {
    const { w, h } = safeSize(this.canvas);
    this.renderer.autoClear = true;
    this.renderer.setViewport(0, 0, w, h);
    this.renderer.setScissorTest(false);
    this.renderer.render(this.scene, this.camera);

    if (this.display.showAxes) {
      // Corner triad: same orientation as the main camera, own tiny viewport.
      const s = Math.round(Math.min(110, Math.min(w, h) * 0.22));
      const dir = this.camera.position.clone().sub(this.controls.target);
      if (dir.lengthSq() < 1e-12) dir.set(1, -1, 0.6);
      this.axisCamera.position.copy(dir.normalize().multiplyScalar(4));
      this.axisCamera.up.copy(this.camera.up);
      this.axisCamera.lookAt(0, 0, 0);

      this.renderer.autoClear = false;
      this.renderer.clearDepth();
      this.renderer.setViewport(8, 8, s, s);
      this.renderer.setScissor(8, 8, s, s);
      this.renderer.setScissorTest(true);
      this.renderer.render(this.axisScene, this.axisCamera);
      this.renderer.setScissorTest(false);
      this.renderer.setViewport(0, 0, w, h);
      this.renderer.autoClear = true;
    }
  }

  // ==================================================================
  // Misc
  // ==================================================================

  screenshot(): string {
    // No preserveDrawingBuffer, so the back buffer is only guaranteed valid
    // between the draw and the next composite: render synchronously here.
    this.renderFrame();
    return this.renderer.domElement.toDataURL('image/png');
  }

  resize(): void {
    const { w, h } = safeSize(this.canvas);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h, false);
    const aspect = w / h;
    this.perspCamera.aspect = aspect;
    this.perspCamera.updateProjectionMatrix();
    const halfH = (this.orthoCamera.top - this.orthoCamera.bottom) / 2;
    this.orthoCamera.left = -halfH * aspect;
    this.orthoCamera.right = halfH * aspect;
    this.orthoCamera.updateProjectionMatrix();
    this.dirty = true;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.rafId);

    this.canvas.removeEventListener('pointerdown', this.onPointerDown);
    this.canvas.removeEventListener('pointerup', this.onPointerUp);
    this.canvas.removeEventListener('pointermove', this.onPointerMove);
    this.canvas.removeEventListener('pointerleave', this.onPointerLeave);
    this.controls.removeEventListener('change', this.onControlsChange);
    this.controls.dispose();

    this.pickCb = null;
    this.hoverCb = null;

    this.disposeHighlight();
    this.disposeWells();
    this.disposeNncs();
    this.clearMesh();

    for (const d of this.coreDisposables) d.dispose();
    this.coreDisposables = [];

    this.axisScene.clear();
    this.scene.clear();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }

  private clearMesh(): void {
    if (this.surface) {
      this.modelRoot.remove(this.surface);
      this.surface = null;
    }
    if (this.wireframe) {
      this.modelRoot.remove(this.wireframe);
      this.wireframe = null;
    }
    if (this.gridBox) {
      this.modelRoot.remove(this.gridBox);
      this.gridBox.dispose();
      (this.gridBox.material as THREE.Material).dispose();
      this.gridBox = null;
    }
    this.geometry?.dispose();
    this.wireGeometry?.dispose();
    this.geometry = null;
    this.wireGeometry = null;
    this.surfaceIndex = null;
    this.edgeIndex = null;
    this.mesh = null;
    this.quadCount = 0;
    this.quadCell = new Int32Array(0);
    this.cellCenters = new Float32Array(0);
    this.cellCount = 0;
    this.hiddenMask = null;
  }

  private disposeWells(): void {
    for (const child of [...this.wellGroup.children]) {
      if (child === this.labelGroup) continue;
      this.wellGroup.remove(child);
    }
    for (const child of [...this.labelGroup.children]) this.labelGroup.remove(child);
    // Every geometry, material and texture made by setWells went onto
    // wellDisposables, so a time-step scrub releases exactly what it made and
    // nothing shared.
    for (const d of this.wellDisposables) d.dispose();
    this.wellDisposables = [];
    this.zCompensated = [];
    this.wellMeshes.clear();
    this.focusedWell = null;
    this.dirty = true;
  }

  private disposeNncs(): void {
    if (!this.nncLines) return;
    this.modelRoot.remove(this.nncLines);
    this.nncLines.geometry.dispose();
    (this.nncLines.material as THREE.Material).dispose();
    this.nncLines = null;
  }

  private disposeHighlight(): void {
    if (this.highlight) {
      this.modelRoot.remove(this.highlight);
      this.highlight.geometry.dispose();
      (this.highlight.material as THREE.Material).dispose();
      this.highlight = null;
    }
    if (this.highlightFill) {
      this.modelRoot.remove(this.highlightFill);
      this.highlightFill.geometry.dispose();
      (this.highlightFill.material as THREE.Material).dispose();
      this.highlightFill = null;
    }
  }
}
