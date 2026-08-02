/**
 * Scalar-to-colour mapping for the 3D viewer.
 *
 * The palettes are the RGB stop lists from ResInsight's
 * `ApplicationLibCode/Application/Tools/RiaColorTables.cpp` (and, for
 * GREEN_RED / BLUE_MAGENTA, `RimEnsembleCurveSetColorManager.cpp`, where
 * those two two-stop ramps actually live). Interpolation between stops is
 * linear in sRGB, which is what caf::ColorTable does, so the banding and the
 * midpoint hues match the desktop app rather than being "nicer".
 *
 * No three.js here: this module produces plain Float32Array RGB in 0..1 and
 * CSS colour strings, so the legend component and the engine share it.
 */

export type PaletteName =
  | 'normal'
  | 'opposite_normal'
  | 'black_white'
  | 'white_black'
  | 'blue_white_red'
  | 'red_white_blue'
  | 'angular'
  | 'rainbow'
  | 'stimplan'
  | 'heat_map'
  | 'green_red'
  | 'blue_magenta'
  | 'category'
  | 'contrast_category';

export type MappingType =
  | 'linear_continuous'
  | 'linear_discrete'
  | 'log_continuous'
  | 'log_discrete'
  | 'category';

export interface ColorMapping {
  palette: PaletteName;
  mapping: MappingType;
  /** Bands for the *_discrete modes. */
  levels: number;
  min: number;
  max: number;
  invert: boolean;
  undefinedColor: [number, number, number];
}

/** Per-component [min, max] used to normalise each saturation. */
export interface TernaryRanges {
  soil: [number, number];
  sgas: [number, number];
  swat: [number, number];
}

type RGB = readonly [number, number, number];

// The 21 Kelly colours, sorted by hue, from RiaColorTables::categoryColors().
// ResInsight's own list stops at medium_blue; black is appended so category
// legends have a 21st slot, as the contrast list does.
const KELLY: readonly RGB[] = [
  [128, 62, 117],
  [212, 28, 132],
  [246, 118, 142],
  [193, 0, 32],
  [127, 24, 13],
  [241, 58, 19],
  [255, 122, 92],
  [129, 112, 102],
  [255, 104, 0],
  [89, 51, 21],
  [255, 142, 0],
  [206, 162, 98],
  [244, 200, 0],
  [147, 170, 0],
  [59, 84, 23],
  [0, 125, 52],
  [54, 125, 123],
  [0, 83, 138],
  [166, 189, 215],
  [46, 76, 224],
  [0, 0, 0],
];

// RiaColorTables::contrastCategoryColors(): the same 21 colours reordered so
// adjacent categories are far apart in hue.
const KELLY_CONTRAST: readonly RGB[] = [
  [244, 200, 0],
  [128, 62, 117],
  [255, 104, 0],
  [166, 189, 215],
  [193, 0, 32],
  [206, 162, 98],
  [129, 112, 102],
  [0, 125, 52],
  [246, 118, 142],
  [0, 83, 138],
  [255, 122, 92],
  [212, 28, 132],
  [255, 142, 0],
  [59, 84, 23],
  [127, 24, 13],
  [54, 125, 123],
  [241, 58, 19],
  [147, 170, 0],
  [46, 76, 224],
  [89, 51, 21],
  [0, 0, 0],
];

export const PALETTES: Record<PaletteName, readonly RGB[]> = {
  // normalPaletteColors(): blue -> cyan -> green -> yellow -> red
  normal: [
    [0, 0, 255],
    [0, 127, 255],
    [0, 255, 255],
    [0, 255, 0],
    [255, 255, 0],
    [255, 127, 0],
    [255, 0, 0],
  ],
  // normalPaletteOppositeOrderingColors()
  opposite_normal: [
    [255, 0, 0],
    [255, 127, 0],
    [255, 255, 0],
    [0, 255, 0],
    [0, 255, 255],
    [0, 127, 255],
    [0, 0, 255],
  ],
  black_white: [
    [0, 0, 0],
    [255, 255, 255],
  ],
  white_black: [
    [255, 255, 255],
    [0, 0, 0],
  ],
  blue_white_red: [
    [0, 0, 255],
    [255, 255, 255],
    [255, 0, 0],
  ],
  red_white_blue: [
    [255, 0, 0],
    [255, 255, 255],
    [0, 0, 255],
  ],
  // angularPaletteColors(): normal with magenta wrapped onto both ends.
  angular: [
    [255, 0, 255],
    [0, 0, 255],
    [0, 127, 255],
    [0, 255, 255],
    [0, 255, 0],
    [255, 255, 0],
    [255, 127, 0],
    [255, 0, 0],
    [255, 0, 255],
  ],
  rainbow: [
    [0, 0, 0],
    [255, 0, 255],
    [0, 0, 255],
    [0, 255, 255],
    [0, 255, 0],
    [255, 0, 0],
    [255, 255, 0],
    [255, 255, 255],
  ],
  stimplan: [
    [220, 220, 220],
    [0, 0, 255],
    [0, 128, 255],
    [80, 240, 60],
    [0, 255, 0],
    [255, 255, 0],
    [255, 192, 0],
    [255, 128, 0],
    [255, 64, 0],
    [255, 0, 255],
  ],
  // heatMapPaletteColors(); DARK_BLUE = (0,0,139), DARK_ORANGE = (255,140,0)
  // per cvfColor3.cpp.
  heat_map: [
    [0, 0, 139],
    [0, 0, 240],
    [0, 102, 204],
    [0, 255, 255],
    [75, 255, 47],
    [255, 140, 0],
    [255, 255, 0],
  ],
  green_red: [
    [0, 255, 0],
    [255, 0, 0],
  ],
  blue_magenta: [
    [0, 0, 255],
    [255, 0, 255],
  ],
  category: KELLY,
  contrast_category: KELLY_CONTRAST,
};

/** Smallest positive value we will take a log of, so log modes never NaN. */
const LOG_FLOOR = 1e-12;

/** Sample a palette at t in 0..1, linear between stops. Returns 0..1 RGB. */
export function samplePalette(palette: PaletteName, t: number): [number, number, number] {
  const stops = PALETTES[palette];
  if (!Number.isFinite(t)) t = 0;
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  const x = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  const a = stops[i];
  const b = stops[i + 1] ?? a;
  return [
    (a[0] + (b[0] - a[0]) * f) / 255,
    (a[1] + (b[1] - a[1]) * f) / 255,
    (a[2] + (b[2] - a[2]) * f) / 255,
  ];
}

function isLog(m: MappingType): boolean {
  return m === 'log_continuous' || m === 'log_discrete';
}

function isDiscrete(m: MappingType): boolean {
  return m === 'linear_discrete' || m === 'log_discrete';
}

/**
 * Position of `value` in 0..1 for the mapping, or NaN when it cannot be
 * placed (non-finite, or outside [min, max]). Discrete modes quantise to the
 * centre of one of `levels` bands so a band renders as one flat colour.
 */
function normalize(value: number, m: ColorMapping): number {
  if (!Number.isFinite(value)) return NaN;

  let t: number;
  if (isLog(m.mapping)) {
    // Guard non-positive bounds and values: clamp everything to the smallest
    // positive number we are willing to log, so a zero-filled SGAS array
    // renders as the low end of the ramp instead of a NaN hole.
    const lo = Math.max(m.min, LOG_FLOOR);
    const hi = Math.max(m.max, lo * (1 + 1e-9));
    if (value < m.min || value > m.max) return NaN;
    const v = Math.max(value, LOG_FLOOR);
    t = (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo));
  } else {
    if (value < m.min || value > m.max) return NaN;
    const span = m.max - m.min;
    t = span > 0 ? (value - m.min) / span : 0;
  }

  if (!Number.isFinite(t)) return NaN;
  t = t < 0 ? 0 : t > 1 ? 1 : t;

  if (isDiscrete(m.mapping)) {
    const n = Math.max(1, Math.floor(m.levels));
    const band = Math.min(n - 1, Math.floor(t * n));
    t = n > 1 ? band / (n - 1) : 0;
  }

  return m.invert ? 1 - t : t;
}

/** Category mode: integer value picks a palette entry by value modulo length. */
function categoryColor(value: number, m: ColorMapping): [number, number, number] | null {
  if (!Number.isFinite(value)) return null;
  const stops = PALETTES[m.palette];
  const n = stops.length;
  // Round, not truncate: the values arrive as float32 so SATNUM 3 can be
  // 2.9999998, and truncating would shift it a whole category.
  let idx = Math.round(value) % n;
  if (idx < 0) idx += n;
  const c = stops[m.invert ? n - 1 - idx : idx];
  return [c[0] / 255, c[1] / 255, c[2] / 255];
}

/** Colour for a single scalar, 0..1 RGB. Exposed for the picking readout. */
export function colorForValue(value: number, m: ColorMapping): [number, number, number] {
  if (m.mapping === 'category') {
    return categoryColor(value, m) ?? m.undefinedColor;
  }
  const t = normalize(value, m);
  if (Number.isNaN(t)) return m.undefinedColor;
  return samplePalette(m.palette, t);
}

/**
 * Fill an RGB Float32Array (n*3, 0..1) from per-cell values.
 *
 * `cellIds` is the per-vertex active-cell index straight out of the mesh, so
 * `out` ends up per-vertex and can be uploaded as a colour attribute with no
 * further indirection. Values are looked up per vertex; for Norne that is
 * 145k lookups, ~1 ms, which is fine to redo on every time step.
 */
export function mapColors(
  values: Float32Array,
  cellIds: Int32Array,
  m: ColorMapping,
  out: Float32Array
): void {
  const n = Math.min(cellIds.length, out.length / 3);
  const undef = m.undefinedColor;

  if (m.mapping === 'category') {
    for (let v = 0; v < n; v++) {
      const cell = cellIds[v];
      const c =
        cell >= 0 && cell < values.length ? categoryColor(values[cell], m) ?? undef : undef;
      out[v * 3] = c[0];
      out[v * 3 + 1] = c[1];
      out[v * 3 + 2] = c[2];
    }
    return;
  }

  // Continuous and discrete modes hit the same handful of t values over and
  // over (discrete has exactly `levels` of them), so cache the ramp in a LUT
  // and index it instead of interpolating per vertex.
  const lutSize = 1024;
  const lut = new Float32Array(lutSize * 3);
  for (let i = 0; i < lutSize; i++) {
    const c = samplePalette(m.palette, i / (lutSize - 1));
    lut[i * 3] = c[0];
    lut[i * 3 + 1] = c[1];
    lut[i * 3 + 2] = c[2];
  }

  for (let v = 0; v < n; v++) {
    const cell = cellIds[v];
    const t = cell >= 0 && cell < values.length ? normalize(values[cell], m) : NaN;
    if (Number.isNaN(t)) {
      out[v * 3] = undef[0];
      out[v * 3 + 1] = undef[1];
      out[v * 3 + 2] = undef[2];
    } else {
      const li = Math.min(lutSize - 1, Math.max(0, Math.round(t * (lutSize - 1)))) * 3;
      out[v * 3] = lut[li];
      out[v * 3 + 1] = lut[li + 1];
      out[v * 3 + 2] = lut[li + 2];
    }
  }
}

function ternaryComponent(value: number, lo: number, hi: number): number {
  const span = hi - lo;
  if (!Number.isFinite(value) || !(span > 0)) return 0;
  const t = (value - lo) / span;
  return t < 0 ? 0 : t > 1 ? 1 : t;
}

/**
 * Ternary saturation blend: R = SGAS, G = SOIL, B = SWAT, each normalised by
 * its own range and clamped, as RivTernaryScalarMapper does. ResInsight
 * derives blue as `1 - red - green` inside the texture; doing the same here
 * keeps the classic ternary triangle (pure water is blue, not dark blue plus
 * whatever SWAT happens to hold) while still honouring the SWAT range for the
 * degenerate case where the caller supplies one.
 */
export function mapTernary(
  soil: Float32Array,
  sgas: Float32Array,
  swat: Float32Array,
  cellIds: Int32Array,
  ranges: TernaryRanges,
  out: Float32Array
): void {
  const n = Math.min(cellIds.length, out.length / 3);
  for (let v = 0; v < n; v++) {
    const cell = cellIds[v];
    if (cell < 0) {
      out[v * 3] = 0;
      out[v * 3 + 1] = 0;
      out[v * 3 + 2] = 0;
      continue;
    }
    const g = cell < soil.length ? ternaryComponent(soil[cell], ranges.soil[0], ranges.soil[1]) : 0;
    let r = cell < sgas.length ? ternaryComponent(sgas[cell], ranges.sgas[0], ranges.sgas[1]) : 0;
    // Gas cannot claim more than what oil left over, matching the mapper's
    // clamp of sgasNormalized to 1 - soilNormalized.
    if (r > 1 - g) r = 1 - g;
    let b = 1 - r - g;
    if (b < 0) b = 0;
    // Honour an explicit SWAT range when the caller narrowed it.
    if (ranges.swat[0] !== 0 || ranges.swat[1] !== 1) {
      const w =
        cell < swat.length ? ternaryComponent(swat[cell], ranges.swat[0], ranges.swat[1]) : b;
      b = Math.min(b, w);
    }
    out[v * 3] = r;
    out[v * 3 + 1] = g;
    out[v * 3 + 2] = b;
  }
}

function toCss(c: [number, number, number]): string {
  const b = (x: number) => Math.max(0, Math.min(255, Math.round(x * 255)));
  return `rgb(${b(c[0])}, ${b(c[1])}, ${b(c[2])})`;
}

/**
 * Evenly spaced legend swatches, index 0 at the minimum. Category mappings
 * return one swatch per palette entry (values 0, 1, 2, ...); everything else
 * walks the value range linearly, or logarithmically for the log modes.
 */
export function legendStops(
  m: ColorMapping,
  n: number
): Array<{ value: number; color: string }> {
  const count = Math.max(1, Math.floor(n));
  const out: Array<{ value: number; color: string }> = [];

  if (m.mapping === 'category') {
    const len = Math.min(count, PALETTES[m.palette].length);
    for (let i = 0; i < len; i++) {
      out.push({ value: i, color: toCss(colorForValue(i, m)) });
    }
    return out;
  }

  const log = isLog(m.mapping);
  const lo = log ? Math.max(m.min, LOG_FLOOR) : m.min;
  const hi = log ? Math.max(m.max, lo * 10) : m.max;

  for (let i = 0; i < count; i++) {
    const f = count > 1 ? i / (count - 1) : 0;
    const value = log ? lo * Math.pow(hi / lo, f) : lo + (hi - lo) * f;
    out.push({ value, color: toCss(colorForValue(value, m)) });
  }
  return out;
}
