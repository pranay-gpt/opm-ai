import { useMemo, useState } from 'react';
import type { CategorizedVectors, VectorGroup, GridLayout, UnitSystem } from '../../types';
import type { ReactNode } from 'react';

const ALL_GROUPS: VectorGroup[] = [
  'field_rates',
  'field_cumulative',
  'field_derived',
  'well_rates',
  'well_cumulative',
  'well_injection',
];

interface ResultsControlRailProps {
  categorized: CategorizedVectors;
  selectedWells: Set<string>;
  onWells: (s: Set<string>) => void;
  selectedVectors: Record<VectorGroup, Set<string>>;
  onVectors: (g: VectorGroup, s: Set<string>) => void;
  logScale: boolean;
  onLogScale: (v: boolean) => void;
  gridLayout: GridLayout;
  onGridLayout: (v: GridLayout) => void;
  perProperty: boolean;
  onPerProperty: (v: boolean) => void;
  unitSystem: UnitSystem;
  onUnitSystem: (v: UnitSystem) => void;
}

// ── Small local primitives (matching viewer3d/ControlPanel.tsx pattern) ──

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

export default function ResultsControlRail({
  categorized,
  selectedWells,
  onWells,
  selectedVectors,
  onVectors,
  logScale,
  onLogScale,
  gridLayout,
  onGridLayout,
  perProperty,
  onPerProperty,
  unitSystem,
  onUnitSystem,
}: ResultsControlRailProps) {
  const producerWells = useMemo(
    () =>
      Object.keys(categorized.well_rates)
        .concat(Object.keys(categorized.well_cumulative))
        .filter((v, i, a) => a.indexOf(v) === i)
        .sort(),
    [categorized]
  );
  const injectorWells = useMemo(
    () => Object.keys(categorized.well_injection).sort(),
    [categorized]
  );

  const toggleWell = (well: string) => {
    const next = new Set(selectedWells);
    if (next.has(well)) next.delete(well);
    else next.add(well);
    onWells(next);
  };

  const toggleVector = (group: VectorGroup, vec: string) => {
    const next = new Set(selectedVectors[group]);
    if (next.has(vec)) next.delete(vec);
    else next.add(vec);
    onVectors(group, next);
  };

  return (
    <aside
      className="w-72 shrink-0 border-r overflow-y-auto bg-surface"
      data-testid="results-control-rail"
    >
      <div className="p-3 space-y-4">
        <Section title="Producers" defaultOpen={producerWells.length > 0}>
          {producerWells.length === 0 ? (
            <p className="text-xs text-textMuted italic px-3">none</p>
          ) : (
            producerWells.map((w) => (
              <Check
                key={w}
                label={w}
                checked={selectedWells.has(w)}
                onChange={() => toggleWell(w)}
              />
            ))
          )}
        </Section>

        <Section title="Injectors" defaultOpen={injectorWells.length > 0}>
          {injectorWells.length === 0 ? (
            <p className="text-xs text-textMuted italic px-3">none</p>
          ) : (
            injectorWells.map((w) => (
              <Check
                key={w}
                label={w}
                checked={selectedWells.has(w)}
                onChange={() => toggleWell(w)}
              />
            ))
          )}
        </Section>

        <Section title="Vector Groups" defaultOpen={true}>
          {ALL_GROUPS.map((group) => {
            const vecs = collectGroupVectors(group, categorized);
            if (vecs.length === 0) return null;
            return (
              <div key={group} className="ml-2 mt-1 space-y-1">
                <p className="text-xs font-medium text-textSecondary mb-1">
                  {group.replace('_', ' ')}
                </p>
                {vecs.map((vec) => (
                  <Check
                    key={vec}
                    label={categorized.vector_labels?.[vec] || vec}
                    checked={selectedVectors[group]?.has(vec) ?? false}
                    onChange={() => toggleVector(group, vec)}
                  />
                ))}
              </div>
            );
          })}
        </Section>

        <Section title="Display" defaultOpen={true}>
          <Check
            label="Log scale (Y)"
            checked={logScale}
            onChange={onLogScale}
          />
        </Section>

        <Section title="Layout" defaultOpen={true}>
          <label className="flex items-center justify-between gap-2 text-xs text-textSecondary mb-2">
            <span className="shrink-0">Grid Columns</span>
            <select
              value={gridLayout}
              onChange={(e) => onGridLayout(e.target.value as GridLayout)}
              className="px-2 py-1 text-xs border border-border rounded bg-surface text-textPrimary focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="1col">1 column</option>
              <option value="2col">2 columns</option>
              <option value="4col">4 columns</option>
            </select>
          </label>
          <Check
            label="Per-property (one vector per graph)"
            checked={perProperty}
            onChange={onPerProperty}
          />
        </Section>

        <Section title="Units" defaultOpen={true}>
          <label className="flex items-center justify-between gap-2 text-xs text-textSecondary">
            <span className="shrink-0">Unit System</span>
            <select
              value={unitSystem}
              onChange={(e) => onUnitSystem(e.target.value as UnitSystem)}
              className="px-2 py-1 text-xs border border-border rounded bg-surface text-textPrimary focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="FIELD">Field (STB, MSCF, psia)</option>
              <option value="METRIC">Metric (m³, SM³, bar)</option>
            </select>
          </label>
        </Section>
      </div>
    </aside>
  );
}

function collectGroupVectors(group: VectorGroup, cats: CategorizedVectors): string[] {
  if (group === 'field_rates') return cats.field_rates;
  if (group === 'field_cumulative') return cats.field_cumulative;
  if (group === 'field_derived') return cats.field_derived;
  if (group === 'well_rates') {
    return Array.from(new Set(Object.values(cats.well_rates).flat())).sort();
  }
  if (group === 'well_cumulative') {
    return Array.from(new Set(Object.values(cats.well_cumulative).flat())).sort();
  }
  return Array.from(new Set(Object.values(cats.well_injection).flat())).sort();
}