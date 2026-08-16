import { useState } from 'react';
import type { ReactNode } from 'react';
import type { PaletteName, MappingType } from './colormaps';
import type { DisplayOptions } from './engine';
import type { GridInfoResponse, GridWell, GridWellType } from '../../types';
import type { PropertyStats } from './meshFormat';
import HistogramBar from './HistogramBar';

function axisMax(axis: 'I' | 'J' | 'K', info: GridInfoResponse): number {
  if (axis === 'I') return info.nx;
  if (axis === 'J') return info.ny;
  return info.nz;
}

// ── State shapes owned by Grid3DViewer, edited here ────────────────────

/** 'ternary' is a display mode, not a property name (see the contract). */
export const TERNARY = '__ternary__';

export type AutoRangeMode = 'step' | 'global' | 'manual';

export interface LegendState {
  palette: PaletteName;
  mapping: MappingType;
  levels: number;
  invert: boolean;
  autoRange: AutoRangeMode;
  /** Only authoritative when autoRange === 'manual'; otherwise it mirrors. */
  min: number;
  max: number;
}

export interface FilterState {
  iMin: number;
  iMax: number;
  jMin: number;
  jMax: number;
  kMin: number;
  kMax: number;
  propertyFilterOn: boolean;
  propMin: number;
  propMax: number;
  propExclude: boolean;
}

interface ControlPanelProps {
  info: GridInfoResponse;
  // Property
  property: string;
  onProperty: (name: string) => void;
  ternaryAvailable: boolean;
  stats: PropertyStats | null;
  // Legend
  legend: LegendState;
  onLegend: (patch: Partial<LegendState>) => void;
  effectiveMin: number;
  effectiveMax: number;
  globalRangeLoading: boolean;
  globalRangeError: string | null;
  // Filters
  filter: FilterState;
  onFilter: (patch: Partial<FilterState>) => void;
  /** Active cells passing the property filter; null when not computable. */
  passingCells: number | null;
  // Display
  display: DisplayOptions;
  onDisplay: (patch: Partial<DisplayOptions>) => void;
  // Views
  onViewAlong: (axis: '+x' | '-x' | '+y' | '-y' | '+z' | '-z') => void;
  onZoomAll: () => void;
  onScreenshot: () => void;
  // Wells
  wells: GridWell[];
  wellsError: string | null;
  selectedWell: string | null;
  onSelectWell: (name: string | null) => void;
}

const PALETTES: PaletteName[] = [
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

const MAPPINGS: Array<{ value: MappingType; label: string }> = [
  { value: 'linear_continuous', label: 'Linear · continuous' },
  { value: 'linear_discrete', label: 'Linear · discrete' },
  { value: 'log_continuous', label: 'Log · continuous' },
  { value: 'log_discrete', label: 'Log · discrete' },
  { value: 'category', label: 'Category' },
];

const WELL_BADGE: Record<GridWellType, { cls: string; short: string }> = {
  producer: { cls: 'badge-success', short: 'PROD' },
  oil_injector: { cls: 'badge-warning', short: 'OIL INJ' },
  gas_injector: { cls: 'badge-error', short: 'GAS INJ' },
  water_injector: { cls: 'badge-primary', short: 'WAT INJ' },
  unknown: { cls: 'badge-outline', short: '?' },
};

// ── Small local primitives (no new deps, no exported abstractions) ─────

function Section({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wide text-textSecondary hover:bg-surfaceHover"
      >
        {title}
        <span className="text-textMuted">{open ? '−' : '+'}</span>
      </button>
      {open && <div className="space-y-2 px-3 pb-3">{children}</div>}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs text-textSecondary">
      <span className="shrink-0">{label}</span>
      {children}
    </label>
  );
}

function Check({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-textSecondary">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 accent-[rgb(var(--c-primary))]"
      />
      {label}
    </label>
  );
}

function Num({
  value,
  onChange,
  step = 'any',
  min,
  max,
  className = 'w-24',
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number | 'any';
  min?: number;
  max?: number;
  className?: string;
}) {
  return (
    <input
      type="number"
      value={Number.isFinite(value) ? value : ''}
      step={step}
      min={min}
      max={max}
      onChange={(e) => {
        const v = parseFloat(e.target.value);
        if (Number.isFinite(v)) onChange(v);
      }}
      className={`input input-sm ${className} font-mono`}
    />
  );
}

function Sel<T extends string>({
  value,
  onChange,
  options,
  className = 'w-36',
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ value: T; label: string }>;
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className={`input input-sm ${className}`}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

/** Two number inputs standing in for a dual-handle range, plus a live slider. */
function IjkRange({
  label,
  n,
  lo,
  hi,
  onChange,
}: {
  label: string;
  n: number;
  lo: number;
  hi: number;
  onChange: (lo: number, hi: number) => void;
}) {
  // Displayed one-based to match ResInsight; stored zero-based.
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-textSecondary">
        <span>
          {label} <span className="text-textMuted">(1..{n})</span>
        </span>
        <span className="font-mono text-[11px] text-textPrimary">
          {lo + 1} – {hi + 1}
        </span>
      </div>
      <div className="mt-1 flex items-center gap-1">
        <input
          type="range"
          min={0}
          max={n - 1}
          value={lo}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            onChange(Math.min(v, hi), hi);
          }}
          className="w-full accent-[rgb(var(--c-primary))]"
        />
        <input
          type="range"
          min={0}
          max={n - 1}
          value={hi}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            onChange(lo, Math.max(v, lo));
          }}
          className="w-full accent-[rgb(var(--c-primary))]"
        />
      </div>
    </div>
  );
}

// ── Panel ──────────────────────────────────────────────────────────────

export default function ControlPanel(props: ControlPanelProps) {
  const {
    info,
    property,
    onProperty,
    ternaryAvailable,
    stats,
    legend,
    onLegend,
    effectiveMin,
    effectiveMax,
    globalRangeLoading,
    globalRangeError,
    filter,
    onFilter,
    passingCells,
    display,
    onDisplay,
    onViewAlong,
    onZoomAll,
    onScreenshot,
    wells,
    wellsError,
    selectedWell,
    onSelectWell,
  } = props;

  const discrete =
    legend.mapping === 'linear_discrete' ||
    legend.mapping === 'log_discrete' ||
    legend.mapping === 'category';

  const ijkBoxCells =
    (filter.iMax - filter.iMin + 1) *
    (filter.jMax - filter.jMin + 1) *
    (filter.kMax - filter.kMin + 1);

  return (
    <div className="flex h-full w-72 shrink-0 flex-col overflow-y-auto border-l border-border bg-surface scrollbar-thin">
      {/* Property */}
      <Section title="Property">
        <select
          value={property}
          onChange={(e) => onProperty(e.target.value)}
          className="input input-sm w-full"
        >
          {ternaryAvailable && (
            <optgroup label="Display mode">
              <option value={TERNARY}>Ternary saturation (SGAS/SOIL/SWAT)</option>
            </optgroup>
          )}
          {info.static_properties.length > 0 && (
            <optgroup label="Static">
              {info.static_properties.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </optgroup>
          )}
          {info.dynamic_properties.length > 0 && (
            <optgroup label="Dynamic">
              {info.dynamic_properties.map((p) => (
                <option key={p} value={p}>
                  {p}
                  {info.derived_properties.includes(p) ? ' (derived)' : ''}
                </option>
              ))}
            </optgroup>
          )}
        </select>
        <div className="text-[10px] text-textMuted">
          {info.nx}×{info.ny}×{info.nz} · {info.active_cells.toLocaleString()} active of{' '}
          {info.total_cells.toLocaleString()}
          {info.unit_system ? ` · ${info.unit_system}` : ''}
        </div>
      </Section>

      {/* Legend */}
      {property !== TERNARY && (
        <Section title="Legend">
          <Field label="Auto range">
            <Sel<AutoRangeMode>
              value={legend.autoRange}
              onChange={(v) => onLegend({ autoRange: v })}
              options={[
                { value: 'step', label: 'Current time step' },
                { value: 'global', label: 'All time steps' },
                { value: 'manual', label: 'Manual' },
              ]}
            />
          </Field>
          {globalRangeLoading && (
            <div className="text-[10px] text-textMuted">Scanning all time steps…</div>
          )}
          {globalRangeError && (
            <div className="text-[10px] text-error">{globalRangeError}</div>
          )}
          <Field label="Min">
            <Num
              value={effectiveMin}
              onChange={(v) => onLegend({ min: v, autoRange: 'manual' })}
            />
          </Field>
          <Field label="Max">
            <Num
              value={effectiveMax}
              onChange={(v) => onLegend({ max: v, autoRange: 'manual' })}
            />
          </Field>
          <Field label="Palette">
            <Sel<PaletteName>
              value={legend.palette}
              onChange={(v) => onLegend({ palette: v })}
              options={PALETTES.map((p) => ({ value: p, label: p.replace(/_/g, ' ') }))}
            />
          </Field>
          <Field label="Mapping">
            <Sel<MappingType>
              value={legend.mapping}
              onChange={(v) => onLegend({ mapping: v })}
              options={MAPPINGS}
            />
          </Field>
          {discrete && (
            <Field label="Levels">
              <Num
                value={legend.levels}
                onChange={(v) => onLegend({ levels: Math.max(2, Math.min(64, Math.round(v))) })}
                step={1}
                min={2}
                max={64}
                className="w-20"
              />
            </Field>
          )}
          <Check
            label="Invert colours"
            checked={legend.invert}
            onChange={(v) => onLegend({ invert: v })}
          />
          {stats?.categorical && (
            <div className="text-[10px] text-textMuted">
              Categorical property — the category mapping is recommended.
            </div>
          )}
        </Section>
      )}

      {/* Histogram */}
      {stats && property !== TERNARY && (
        <Section title="Histogram">
          <HistogramBar stats={stats} rangeMin={effectiveMin} rangeMax={effectiveMax} />
        </Section>
      )}

      {/* Cell filters */}
      <Section title="Cell filters" defaultOpen={false}>
        <IjkRange
          label="I"
          n={info.nx}
          lo={filter.iMin}
          hi={filter.iMax}
          onChange={(lo, hi) => onFilter({ iMin: lo, iMax: hi })}
        />
        <IjkRange
          label="J"
          n={info.ny}
          lo={filter.jMin}
          hi={filter.jMax}
          onChange={(lo, hi) => onFilter({ jMin: lo, jMax: hi })}
        />
        <IjkRange
          label="K"
          n={info.nz}
          lo={filter.kMin}
          hi={filter.kMax}
          onChange={(lo, hi) => onFilter({ kMin: lo, kMax: hi })}
        />
        <button
          className="btn btn-secondary btn-sm w-full"
          onClick={() =>
            onFilter({
              iMin: 0,
              iMax: info.nx - 1,
              jMin: 0,
              jMax: info.ny - 1,
              kMin: 0,
              kMax: info.nz - 1,
            })
          }
        >
          Reset I/J/K
        </button>

        <div className="pt-1">
          <Check
            label="Property range filter"
            checked={filter.propertyFilterOn}
            onChange={(v) => onFilter({ propertyFilterOn: v })}
          />
          {filter.propertyFilterOn && (
            <div className="mt-2 space-y-2">
              <Field label="From">
                <Num value={filter.propMin} onChange={(v) => onFilter({ propMin: v })} />
              </Field>
              <Field label="To">
                <Num value={filter.propMax} onChange={(v) => onFilter({ propMax: v })} />
              </Field>
              <Field label="Mode">
                <Sel<'include' | 'exclude'>
                  value={filter.propExclude ? 'exclude' : 'include'}
                  onChange={(v) => onFilter({ propExclude: v === 'exclude' })}
                  options={[
                    { value: 'include', label: 'Include range' },
                    { value: 'exclude', label: 'Exclude range' },
                  ]}
                />
              </Field>
              {stats && (
                <button
                  className="btn btn-ghost btn-sm w-full"
                  onClick={() => onFilter({ propMin: stats.min, propMax: stats.max })}
                >
                  Fit to property range
                </button>
              )}
            </div>
          )}
        </div>

        <div className="rounded-sm bg-page px-2 py-1.5 text-[10px] text-textSecondary">
          <div>
            I/J/K box: <span className="font-mono">{ijkBoxCells.toLocaleString()}</span> of{' '}
            {info.total_cells.toLocaleString()} cells
          </div>
          <div>
            Passing property filter:{' '}
            <span className="font-mono">
              {passingCells === null ? 'n/a' : passingCells.toLocaleString()}
            </span>{' '}
            of {info.active_cells.toLocaleString()} active
          </div>
        </div>
      </Section>

      {/* Display options */}
      <Section title="Display" defaultOpen={false}>
        <Field label="Surface">
          <Sel<DisplayOptions['surfaceMode']>
            value={display.surfaceMode}
            onChange={(v) => onDisplay({ surfaceMode: v })}
            options={[
              { value: 'surface', label: 'Surface' },
              { value: 'faults_only', label: 'Faults only' },
              { value: 'none', label: 'None' },
            ]}
          />
        </Field>
        <Field label="Mesh">
          <Sel<DisplayOptions['meshMode']>
            value={display.meshMode}
            onChange={(v) => onDisplay({ meshMode: v })}
            options={[
              { value: 'full', label: 'Full' },
              { value: 'faults_only', label: 'Faults only' },
              { value: 'none', label: 'None' },
            ]}
          />
        </Field>
        <Field label={`Z scale ×${display.zScale.toFixed(1)}`}>
          <input
            type="range"
            min={1}
            max={50}
            step={0.5}
            value={display.zScale}
            onChange={(e) => onDisplay({ zScale: parseFloat(e.target.value) })}
            className="w-28 accent-[rgb(var(--c-primary))]"
          />
        </Field>
        <Field label={`Opacity ${(display.opacity * 100).toFixed(0)}%`}>
          <input
            type="range"
            min={0.1}
            max={1}
            step={0.05}
            value={display.opacity}
            onChange={(e) => onDisplay({ opacity: parseFloat(e.target.value) })}
            className="w-28 accent-[rgb(var(--c-primary))]"
          />
        </Field>
        <Field label="Background">
          <input
            type="color"
            value={display.background}
            onChange={(e) => onDisplay({ background: e.target.value })}
            className="h-7 w-14 cursor-pointer rounded-sm border border-border bg-page"
          />
        </Field>
        <Field label="Edge colour">
          <input
            type="color"
            value={display.edgeColor}
            onChange={(e) => onDisplay({ edgeColor: e.target.value })}
            className="h-7 w-14 cursor-pointer rounded-sm border border-border bg-page"
          />
        </Field>
        <Field label="Projection">
          <Sel<'persp' | 'ortho'>
            value={display.perspective ? 'persp' : 'ortho'}
            onChange={(v) => onDisplay({ perspective: v === 'persp' })}
            options={[
              { value: 'persp', label: 'Perspective' },
              { value: 'ortho', label: 'Orthographic' },
            ]}
          />
        </Field>
        <div className="grid grid-cols-2 gap-x-2 gap-y-1 pt-1">
          <Check
            label="Inactive cells"
            checked={display.showInactive}
            onChange={(v) => onDisplay({ showInactive: v })}
          />
          <Check
            label="Lighting"
            checked={display.lighting}
            onChange={(v) => onDisplay({ lighting: v })}
          />
          <Check
            label="Axes"
            checked={display.showAxes}
            onChange={(v) => onDisplay({ showAxes: v })}
          />
          <Check
            label="Grid box"
            checked={display.showGridBox}
            onChange={(v) => onDisplay({ showGridBox: v })}
          />
          <Check
            label="Wells"
            checked={display.showWells}
            onChange={(v) => onDisplay({ showWells: v })}
          />
          <Check
            label="Well labels"
            checked={display.showWellLabels}
            onChange={(v) => onDisplay({ showWellLabels: v })}
          />
          <Check
            label="NNCs"
            checked={display.showNncs}
            onChange={(v) => onDisplay({ showNncs: v })}
          />
        </div>
        <div className="text-[10px] text-textMuted">
          {info.fault_face_count.toLocaleString()} fault faces · {info.nnc_count.toLocaleString()}{' '}
          NNCs
        </div>
      </Section>

      {/* Cross-section */}
      <Section title="Cross-section">
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={!!display.crossSection}
            onChange={(e) => onDisplay({
              crossSection: e.target.checked
                ? { enabled: true, axis: 'K', index: Math.floor(info.nz / 2) }
                : null,
            })}
            className="rounded"
          />
          <span>Show cross-section</span>
        </label>
        {display.crossSection && (
          (() => {
            const cs = display.crossSection;
            return (
              <>
                <label className="flex items-center gap-2 text-xs">
                  <span>Axis:</span>
                  <select
                    value={cs.axis}
                    onChange={(e) => onDisplay({
                      crossSection: { enabled: true, axis: e.target.value as 'I' | 'J' | 'K', index: cs.index },
                    })}
                    className="border rounded px-1 py-0.5"
                  >
                    <option value="I">I</option>
                    <option value="J">J</option>
                    <option value="K">K</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-xs">
                  <span>Index:</span>
                  <input
                    type="range"
                    min={1}
                    max={axisMax(cs.axis, info)}
                    value={cs.index}
                    onChange={(e) => onDisplay({
                      crossSection: { enabled: true, axis: cs.axis, index: parseInt(e.target.value) },
                    })}
                    className="flex-1"
                  />
                  <span className="font-mono">{cs.index}</span>
                </label>
              </>
            );
          })()
        )}
      </Section>

      {/* Well property overlay */}
      <Section title="Well Property Overlay">
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={!!display.wellTrajectory}
            onChange={(e) => onDisplay({
              wellTrajectory: e.target.checked ? { enabled: true, property: 'PORO' } : null,
            })}
            className="rounded"
          />
          <span>Show property along wells</span>
        </label>
        {display.wellTrajectory && (
          <label className="flex items-center gap-2 text-xs">
            <span>Property:</span>
            <select
              value={display.wellTrajectory.property}
              onChange={(e) => onDisplay({
                wellTrajectory: { enabled: true, property: e.target.value },
              })}
              className="border rounded px-1 py-0.5"
            >
              {info.static_properties.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
        )}
      </Section>

      {/* Views */}
      <Section title="View">
        <div className="grid grid-cols-3 gap-1">
          {(['+x', '-x', '+y', '-y', '+z', '-z'] as const).map((axis) => (
            <button
              key={axis}
              onClick={() => onViewAlong(axis)}
              className="btn btn-secondary btn-sm px-0"
              title={`Look along ${axis}`}
            >
              {axis.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          <button onClick={onZoomAll} className="btn btn-secondary btn-sm flex-1">
            Zoom all
          </button>
          <button onClick={onScreenshot} className="btn btn-primary btn-sm flex-1">
            Snapshot
          </button>
        </div>
      </Section>

      {/* Wells */}
      {(wells.length > 0 || wellsError) && (
        <Section title={`Wells (${wells.length})`} defaultOpen={false}>
          {wellsError && <div className="text-[10px] text-error">{wellsError}</div>}
          <div className="max-h-56 space-y-1 overflow-y-auto scrollbar-thin">
            {wells.map((w) => {
              const b = WELL_BADGE[w.type] ?? WELL_BADGE.unknown;
              const active = selectedWell === w.name;
              return (
                <button
                  key={w.name}
                  onClick={() => onSelectWell(active ? null : w.name)}
                  className={`flex w-full items-center justify-between gap-2 rounded-sm border px-2 py-1 text-left text-xs ${
                    active
                      ? 'border-primary/50 bg-primary/10 text-textPrimary'
                      : 'border-border bg-page text-textSecondary hover:bg-surfaceHover'
                  }`}
                >
                  <span className="truncate font-mono">{w.name}</span>
                  <span className={`${b.cls} shrink-0 text-[9px]`}>{b.short}</span>
                </button>
              );
            })}
          </div>
          {selectedWell && (
            <div className="text-[10px] text-textMuted">
              {(() => {
                const w = wells.find((x) => x.name === selectedWell);
                if (!w) return null;
                // ECLIPSE often leaves the head K unset in IWEL (Norne does),
                // which reaches us as -1. Showing "0" would look like a real
                // 1-based index, so name the layer only when the file gave one.
                const head =
                  w.k >= 0
                    ? `${w.i + 1}, ${w.j + 1}, ${w.k + 1}`
                    : `${w.i + 1}, ${w.j + 1}, K n/a`;
                return `Head cell ${head} (1-based) · ${w.completions.length} completions`;
              })()}
            </div>
          )}
        </Section>
      )}
    </div>
  );
}
