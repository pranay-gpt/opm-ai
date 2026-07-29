import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../../api/client';
import type { GridInfoResponse, GridWell } from '../../types';
import { useResolvedTheme } from '../../stores/useAppStore';
import { expandFaultMask, parseCells, parseMesh, parseProperty } from './meshFormat';
import type { ParsedCells, ParsedMesh, PropertyStats } from './meshFormat';
import { mapColors, mapTernary } from './colormaps';
import type { ColorMapping } from './colormaps';
import { Viewer3DEngine } from './engine';
import type { CellInfo, DisplayOptions } from './engine';
import ControlPanel, { TERNARY } from './ControlPanel';
import type { FilterState, LegendState } from './ControlPanel';
import LegendBar from './LegendBar';
import ResultInfoBox from './ResultInfoBox';

interface Grid3DViewerProps {
  jobId: string;
}

/** Fetch debounce, ms. Below the fastest playback interval so play never stalls. */
const FETCH_DEBOUNCE_MS = 80;

const SPEEDS = [
  { value: 2000, label: '0.5x' },
  { value: 1000, label: '1x' },
  { value: 500, label: '2x' },
  { value: 250, label: '4x' },
  { value: 125, label: '8x' },
];

const TERNARY_KEYS = ['SOIL', 'SGAS', 'SWAT'] as const;

function defaultDisplay(dark: boolean): DisplayOptions {
  return {
    surfaceMode: 'surface',
    meshMode: 'full',
    showInactive: false,
    zScale: 1,
    background: dark ? '#0d1e3c' : '#f4f7fc',
    lighting: true,
    opacity: 1,
    showAxes: true,
    showGridBox: true,
    showWells: true,
    showWellLabels: false,
    showNncs: false,
    perspective: true,
    edgeColor: dark ? '#1a3a64' : '#c8d4e8',
  };
}

function errText(e: unknown, fallback: string): string {
  if (e instanceof Error) return e.message;
  return fallback;
}

/** Pick the property ResInsight would open on: SOIL, else PRESSURE, else first. */
function initialProperty(info: GridInfoResponse): string {
  const all = [...info.dynamic_properties, ...info.static_properties];
  return all.find((p) => p === 'SOIL') ?? all.find((p) => p === 'PRESSURE') ?? all[0] ?? '';
}

export default function Grid3DViewer({ jobId }: Grid3DViewerProps) {
  const theme = useResolvedTheme();
  const dark = theme === 'dark';

  const containerRef = useRef<HTMLDivElement | null>(null);
  const engineRef = useRef<Viewer3DEngine | null>(null);
  const meshRef = useRef<ParsedMesh | null>(null);
  const cellsRef = useRef<ParsedCells | null>(null);
  const rgbRef = useRef<Float32Array | null>(null);

  // ── Data state ──────────────────────────────────────────────────────
  const [info, setInfo] = useState<GridInfoResponse | null>(null);
  const [infoError, setInfoError] = useState<string | null>(null);
  const [meshError, setMeshError] = useState<string | null>(null);
  const [meshLoading, setMeshLoading] = useState(false);
  const [meshReady, setMeshReady] = useState(false);

  /** Bumped whenever a fresh engine is live, so the push effects below re-send
   *  their state to it. Without this, any display/filter change made before the
   *  engine existed would be silently dropped: the engine starts from its own
   *  defaults and those effects would not re-run on their own. */
  const [engineGen, setEngineGen] = useState(0);

  const [property, setProperty] = useState('');
  const [step, setStep] = useState(0);
  const [stats, setStats] = useState<PropertyStats | null>(null);
  const [values, setValues] = useState<Float32Array | null>(null);
  const [ternary, setTernary] = useState<Record<string, Float32Array> | null>(null);
  const [propError, setPropError] = useState<string | null>(null);
  const [propLoading, setPropLoading] = useState(false);

  const [wells, setWells] = useState<GridWell[]>([]);
  const [wellsError, setWellsError] = useState<string | null>(null);
  const [selectedWell, setSelectedWell] = useState<string | null>(null);

  const [globalRange, setGlobalRange] = useState<{ min: number; max: number } | null>(null);
  const [globalRangeLoading, setGlobalRangeLoading] = useState(false);
  const [globalRangeError, setGlobalRangeError] = useState<string | null>(null);

  // ── UI state ────────────────────────────────────────────────────────
  const [legend, setLegend] = useState<LegendState>({
    palette: 'normal',
    mapping: 'linear_continuous',
    levels: 8,
    invert: false,
    autoRange: 'step',
    min: 0,
    max: 1,
  });
  const [filter, setFilter] = useState<FilterState>({
    iMin: 0,
    iMax: 0,
    jMin: 0,
    jMax: 0,
    kMin: 0,
    kMax: 0,
    propertyFilterOn: false,
    propMin: 0,
    propMax: 1,
    propExclude: false,
  });
  const [display, setDisplay] = useState<DisplayOptions>(() => defaultDisplay(dark));
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(500);
  const [picked, setPicked] = useState<CellInfo | null>(null);
  const [hovered, setHovered] = useState<CellInfo | null>(null);

  const nSteps = info?.time_steps.length ?? 0;
  const isTernary = property === TERNARY;
  const ternaryAvailable = useMemo(
    () => !!info && TERNARY_KEYS.every((k) => info.dynamic_properties.includes(k)),
    [info]
  );
  const isDynamic = isTernary || !!info?.dynamic_properties.includes(property);

  // ── Engine lifecycle: created once the viewport exists ──────────────
  // Keyed on `info`, not [], because the loading and error states render their
  // own tree: the container div only exists once info has arrived, so on the
  // first mount containerRef is null. An []-effect would bail there and never
  // re-run, leaving the canvas uncreated and every engine call silently
  // no-opping through its optional chain.
  //
  // This effect is declared ahead of the mesh effect deliberately. Both fire in
  // the commit that delivers `info`, and effects run in declaration order, so
  // the engine exists by the time setMesh reaches for it.
  //
  // The canvas is created imperatively so a StrictMode double-mount cannot
  // leave a second canvas (or a second WebGL context) behind.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const canvas = document.createElement('canvas');
    canvas.className = 'block h-full w-full outline-none';
    container.appendChild(canvas);

    let engine: Viewer3DEngine;
    try {
      engine = new Viewer3DEngine(canvas);
    } catch (e) {
      canvas.remove();
      setMeshError(errText(e, 'Failed to initialise WebGL'));
      return;
    }
    engineRef.current = engine;
    engine.onPick(setPicked);
    engine.onHover(setHovered);

    const ro = new ResizeObserver(() => engine.resize());
    ro.observe(container);
    engine.resize();
    setEngineGen((n) => n + 1);

    return () => {
      ro.disconnect();
      engineRef.current = null;
      engine.dispose();
      canvas.remove();
      meshRef.current = null;
      cellsRef.current = null;
      rgbRef.current = null;
    };
    // `info` gates whether the container exists; its contents are not read here.
  }, [info]);

  // ── Grid info ───────────────────────────────────────────────────────
  useEffect(() => {
    const ac = new AbortController();
    setInfo(null);
    setInfoError(null);
    setMeshReady(false);
    // The component is reused across jobs (no `key` at the call site), so a
    // readout keyed to the old grid would otherwise survive into the new one
    // and describe a cell that is now a different cell.
    setPicked(null);
    setHovered(null);
    setSelectedWell(null);
    api
      .gridInfo(jobId, ac.signal)
      .then((d) => {
        setInfo(d);
        setProperty(initialProperty(d));
        setStep(0);
        setFilter((f) => ({
          ...f,
          iMin: 0,
          iMax: d.nx - 1,
          jMin: 0,
          jMax: d.ny - 1,
          kMin: 0,
          kMax: d.nz - 1,
        }));
      })
      .catch((e) => {
        if (ac.signal.aborted) return;
        setInfoError(errText(e, 'Failed to load grid info'));
      });
    return () => ac.abort();
  }, [jobId]);

  // ── Mesh ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!info) return;
    const ac = new AbortController();
    setMeshLoading(true);
    setMeshError(null);
    // Both blobs are needed before the engine is usable: the mesh alone has no
    // i/j/k, so the I/J/K filter and the pick readout would be dead. /grid/cells
    // does not depend on include_inactive and is ETag-cached, so refetching it
    // when that toggle flips costs a 304.
    Promise.all([
      api.gridMesh(jobId, display.showInactive, ac.signal),
      api.gridCells(jobId, ac.signal),
    ])
      .then(([meshBuf, cellsBuf]) => {
        if (ac.signal.aborted) return;
        const mesh = parseMesh(meshBuf);
        const cells = parseCells(cellsBuf);
        meshRef.current = mesh;
        cellsRef.current = cells;
        rgbRef.current = new Float32Array(mesh.vertexCount * 3);

        const engine = engineRef.current;
        engine?.setMesh(mesh);
        // Order matters: setNncs sizes itself against the mesh's cell count.
        engine?.setCellIjk(cells.ijk);
        engine?.setFaultMask(expandFaultMask(mesh, cells.faultFaces));
        engine?.setNncs(cells.nnc, cells.centers);
        engine?.zoomAll();
        setMeshReady(true);
      })
      .catch((e) => {
        if (ac.signal.aborted) return;
        cellsRef.current = null;
        setMeshReady(false);
        setMeshError(errText(e, 'Failed to load grid mesh'));
      })
      .finally(() => {
        if (!ac.signal.aborted) setMeshLoading(false);
      });
    return () => ac.abort();
  }, [jobId, info, display.showInactive, engineGen]);

  // ── Property (debounced + aborted so scrubbing stays responsive) ─────
  useEffect(() => {
    if (!info || !property) return;
    const ac = new AbortController();
    const effectiveStep = isDynamic ? step : 0;

    const timer = setTimeout(() => {
      setPropLoading(true);
      setPropError(null);

      const load = isTernary
        ? Promise.all(
            TERNARY_KEYS.map((k) => api.gridProperty(jobId, k, effectiveStep, ac.signal))
          ).then((bufs) => {
            const parsed = bufs.map(parseProperty);
            setTernary({
              SOIL: parsed[0].values,
              SGAS: parsed[1].values,
              SWAT: parsed[2].values,
            });
            setValues(parsed[0].values); // SOIL drives picking / filtering
            setStats(parsed[0].stats);
          })
        : api.gridProperty(jobId, property, effectiveStep, ac.signal).then((buf) => {
            const parsed = parseProperty(buf);
            setTernary(null);
            setValues(parsed.values);
            setStats(parsed.stats);
          });

      load
        .catch((e) => {
          if (ac.signal.aborted) return;
          setValues(null);
          setStats(null);
          setTernary(null);
          setPropError(errText(e, `Failed to load ${isTernary ? 'saturations' : property}`));
        })
        .finally(() => {
          if (!ac.signal.aborted) setPropLoading(false);
        });
    }, FETCH_DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      ac.abort();
    };
  }, [jobId, info, property, step, isDynamic, isTernary]);

  // ── Global (all time steps) range for the legend ────────────────────
  useEffect(() => {
    setGlobalRange(null);
    setGlobalRangeError(null);
    if (legend.autoRange !== 'global' || !property || isTernary) return;
    const ac = new AbortController();
    setGlobalRangeLoading(true);
    api
      .gridPropertyRange(jobId, property, ac.signal)
      .then((r) => setGlobalRange({ min: r.min, max: r.max }))
      .catch((e) => {
        if (ac.signal.aborted) return;
        setGlobalRangeError(errText(e, 'Failed to scan all time steps'));
      })
      .finally(() => {
        if (!ac.signal.aborted) setGlobalRangeLoading(false);
      });
    return () => ac.abort();
  }, [jobId, property, legend.autoRange, isTernary]);

  // ── Wells ───────────────────────────────────────────────────────────
  useEffect(() => {
    if (!info?.has_wells) {
      setWells([]);
      return;
    }
    const ac = new AbortController();
    setWellsError(null);
    api
      .gridWells(jobId, step, ac.signal)
      .then((r) => {
        setWells(r.wells);
        engineRef.current?.setWells(r.wells);
      })
      .catch((e) => {
        if (ac.signal.aborted) return;
        setWells([]);
        setWellsError(errText(e, 'Failed to load wells'));
      });
    return () => ac.abort();
  }, [jobId, info, step, engineGen]);

  // ── Effective legend range ──────────────────────────────────────────
  const [effectiveMin, effectiveMax] = useMemo<[number, number]>(() => {
    if (legend.autoRange === 'manual') return [legend.min, legend.max];
    if (legend.autoRange === 'global' && globalRange) return [globalRange.min, globalRange.max];
    if (stats) return [stats.min, stats.max];
    return [legend.min, legend.max];
  }, [legend.autoRange, legend.min, legend.max, globalRange, stats]);

  const mapping = useMemo<ColorMapping>(
    () => ({
      palette: legend.palette,
      mapping: legend.mapping,
      levels: legend.levels,
      min: effectiveMin,
      max: effectiveMax,
      invert: legend.invert,
      undefinedColor: dark ? [0.35, 0.35, 0.38] : [0.75, 0.75, 0.78],
    }),
    [legend.palette, legend.mapping, legend.levels, legend.invert, effectiveMin, effectiveMax, dark]
  );

  // ── Colours: one pass into a buffer reused across recolours ─────────
  useEffect(() => {
    const engine = engineRef.current;
    const mesh = meshRef.current;
    const rgb = rgbRef.current;
    if (!engine || !mesh || !rgb || !meshReady) return;

    if (isTernary && ternary) {
      mapTernary(
        ternary.SOIL,
        ternary.SGAS,
        ternary.SWAT,
        mesh.cellIds,
        { soil: [0, 1], sgas: [0, 1], swat: [0, 1] },
        rgb
      );
    } else if (values) {
      mapColors(values, mesh.cellIds, mapping, rgb);
    } else {
      return;
    }
    engine.setColors(rgb);
  }, [values, ternary, isTernary, mapping, meshReady, engineGen]);

  // Values also drive the engine-side property filter.
  useEffect(() => {
    engineRef.current?.setValues(values);
  }, [values, meshReady, engineGen]);

  // ── Push display + filter down ──────────────────────────────────────
  useEffect(() => {
    engineRef.current?.setDisplay(display);
  }, [display, engineGen]);

  useEffect(() => {
    engineRef.current?.setFilter({
      iMin: filter.iMin,
      iMax: filter.iMax,
      jMin: filter.jMin,
      jMax: filter.jMax,
      kMin: filter.kMin,
      kMax: filter.kMax,
      propertyRange: filter.propertyFilterOn
        ? { min: filter.propMin, max: filter.propMax, exclude: filter.propExclude }
        : null,
      hiddenCells: null,
    });
  }, [filter, meshReady, engineGen]);

  // Follow the theme when the user has not chosen their own colours.
  useEffect(() => {
    setDisplay((d) => {
      const other = defaultDisplay(!dark);
      const now = defaultDisplay(dark);
      return {
        ...d,
        background: d.background === other.background ? now.background : d.background,
        edgeColor: d.edgeColor === other.edgeColor ? now.edgeColor : d.edgeColor,
      };
    });
  }, [dark]);

  // ── Animation ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!playing || nSteps < 2) return;
    const id = setInterval(() => setStep((s) => (s + 1) % nSteps), speed);
    return () => clearInterval(id);
  }, [playing, speed, nSteps]);

  useEffect(() => {
    if (nSteps < 2) setPlaying(false);
  }, [nSteps]);

  // ── Derived readouts ────────────────────────────────────────────────
  const passingCells = useMemo(() => {
    if (!values) return null;
    if (!filter.propertyFilterOn) return values.length;
    let n = 0;
    for (let c = 0; c < values.length; c++) {
      const v = values[c];
      if (!Number.isFinite(v)) continue;
      const inside = v >= filter.propMin && v <= filter.propMax;
      if (inside !== filter.propExclude) n++;
    }
    return n;
  }, [values, filter.propertyFilterOn, filter.propMin, filter.propMax, filter.propExclude]);

  const valueAt = useCallback(
    (info2: CellInfo | null): number | null => {
      if (!info2 || !values) return null;
      const idx = info2.activeIndex;
      if (idx < 0 || idx >= values.length) return null;
      const v = values[idx];
      return Number.isFinite(v) ? v : null;
    },
    [values]
  );

  const onLegendPatch = useCallback(
    (patch: Partial<LegendState>) => {
      setLegend((l) => {
        // Editing a bound switches to manual; carry the other bound over from
        // whatever is currently displayed so the range never jumps.
        const next = { ...l, ...patch };
        if (patch.autoRange === 'manual') {
          if (patch.min === undefined) next.min = effectiveMin;
          if (patch.max === undefined) next.max = effectiveMax;
        }
        return next;
      });
    },
    [effectiveMin, effectiveMax]
  );

  // Selecting a well in the list frames and brightens it; deselecting clears
  // the emphasis and leaves the camera where the user put it.
  const onSelectWell = useCallback((name: string | null) => {
    setSelectedWell(name);
    engineRef.current?.focusWell(name);
  }, []);

  const onScreenshot = useCallback(() => {
    const url = engineRef.current?.screenshot();
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = `grid3d-${jobId}-${property || 'view'}-step${step}.png`;
    a.click();
  }, [jobId, property, step]);

  const currentStep = info?.time_steps[step];

  // ── Failure / empty states ──────────────────────────────────────────
  if (infoError) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-md rounded-sm border border-error/40 bg-error/10 p-4 text-center">
          <p className="mb-1 font-medium text-error">3D grid unavailable</p>
          <p className="text-sm text-textSecondary">{infoError}</p>
        </div>
      </div>
    );
  }

  if (!info) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-textSecondary">
        <span className="animate-pulse">Loading grid…</span>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Viewport */}
      <div className="relative flex min-w-0 flex-1 flex-col">
        <div ref={containerRef} className="relative min-h-0 flex-1 bg-page">
          {/* Legend overlay */}
          {stats && !isTernary && (
            <div className="pointer-events-none absolute left-3 top-3 z-10">
              <LegendBar
                mapping={mapping}
                title={stats.name}
                unit={stats.unit}
                categorical={stats.categorical}
              />
            </div>
          )}
          {isTernary && (
            <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-sm border border-border bg-surface/85 px-3 py-2 text-xs backdrop-blur-sm">
              <div className="mb-1 font-semibold text-textPrimary">Ternary saturation</div>
              <div className="space-y-0.5 text-[10px] text-textSecondary">
                <div>
                  <span className="mr-1 inline-block h-2 w-2 bg-[#ff0000]" /> SGAS
                </div>
                <div>
                  <span className="mr-1 inline-block h-2 w-2 bg-[#00ff00]" /> SOIL
                </div>
                <div>
                  <span className="mr-1 inline-block h-2 w-2 bg-[#0000ff]" /> SWAT
                </div>
              </div>
            </div>
          )}

          {/* Result info overlay */}
          <div className="absolute right-3 top-3 z-10">
            <ResultInfoBox
              picked={picked}
              hovered={hovered}
              propertyName={isTernary ? 'SOIL' : property}
              propertyUnit={stats?.unit ?? ''}
              pickedValue={valueAt(picked)}
              hoveredValue={valueAt(hovered)}
              lengthUnit={info.length_unit}
              onClear={() => setPicked(null)}
            />
          </div>

          {/* Status overlays */}
          {(meshLoading || propLoading) && (
            <div className="pointer-events-none absolute bottom-3 left-3 z-10 rounded-sm border border-border bg-surface/85 px-2 py-1 text-[11px] text-textSecondary backdrop-blur-sm">
              {meshLoading ? 'Loading mesh…' : 'Loading property…'}
            </div>
          )}
          {meshError && (
            <div className="absolute inset-x-8 top-1/2 z-20 -translate-y-1/2 rounded-sm border border-error/40 bg-error/10 p-4 text-center">
              <p className="font-medium text-error">Could not draw the grid</p>
              <p className="mt-1 text-sm text-textSecondary">{meshError}</p>
            </div>
          )}
          {propError && !meshError && (
            <div className="absolute bottom-3 right-3 z-20 max-w-sm rounded-sm border border-error/40 bg-error/10 px-3 py-2 text-xs text-error">
              {propError}
            </div>
          )}
        </div>

        {/* Time step animation bar */}
        <div className="flex items-center gap-3 border-t border-border bg-surface px-3 py-2">
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={!isDynamic || step === 0}
            title="Previous time step"
          >
            ◀
          </button>
          <button
            className="btn btn-primary btn-sm w-16"
            onClick={() => setPlaying((p) => !p)}
            disabled={!isDynamic || nSteps < 2}
          >
            {playing ? 'Pause' : 'Play'}
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setStep((s) => Math.min(nSteps - 1, s + 1))}
            disabled={!isDynamic || step >= nSteps - 1}
            title="Next time step"
          >
            ▶
          </button>
          <input
            type="range"
            min={0}
            max={Math.max(0, nSteps - 1)}
            value={step}
            disabled={!isDynamic || nSteps < 2}
            onChange={(e) => setStep(parseInt(e.target.value, 10))}
            className="min-w-0 flex-1 accent-[rgb(var(--c-primary))]"
          />
          <div className="w-52 shrink-0 text-right font-mono text-xs text-textPrimary">
            {currentStep ? (
              <>
                {currentStep.date}
                <span className="ml-2 text-textMuted">
                  {currentStep.days.toFixed(0)} d · {step + 1}/{nSteps}
                </span>
              </>
            ) : (
              <span className="text-textMuted">no time steps</span>
            )}
          </div>
          <select
            value={speed}
            onChange={(e) => setSpeed(parseInt(e.target.value, 10))}
            className="input input-sm w-20 shrink-0"
            title="Playback speed"
          >
            {SPEEDS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <ControlPanel
        info={info}
        property={property}
        onProperty={setProperty}
        ternaryAvailable={ternaryAvailable}
        stats={stats}
        legend={legend}
        onLegend={onLegendPatch}
        effectiveMin={effectiveMin}
        effectiveMax={effectiveMax}
        globalRangeLoading={globalRangeLoading}
        globalRangeError={globalRangeError}
        filter={filter}
        onFilter={(patch) => setFilter((f) => ({ ...f, ...patch }))}
        passingCells={passingCells}
        display={display}
        onDisplay={(patch) => setDisplay((d) => ({ ...d, ...patch }))}
        onViewAlong={(axis) => engineRef.current?.viewAlong(axis)}
        onZoomAll={() => engineRef.current?.zoomAll()}
        onScreenshot={onScreenshot}
        wells={wells}
        wellsError={wellsError}
        selectedWell={selectedWell}
        onSelectWell={onSelectWell}
      />
    </div>
  );
}
