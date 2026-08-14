import { useMemo } from 'react';
import type { CategorizedVectors, VectorGroup } from '../../types';

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
}

export default function ResultsControlRail({
  categorized,
  selectedWells,
  onWells,
  selectedVectors,
  onVectors,
  logScale,
  onLogScale,
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
      className="w-72 shrink-0 border-r overflow-y-auto p-3 space-y-4 bg-gray-50 dark:bg-gray-900"
      data-testid="results-control-rail"
    >
      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Producers</h4>
        {producerWells.length === 0 ? (
          <p className="text-xs text-gray-400 italic">none</p>
        ) : (
          <div className="space-y-1">
            {producerWells.map((w) => (
              <label key={w} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedWells.has(w)}
                  onChange={() => toggleWell(w)}
                  className="rounded"
                />
                <span>{w}</span>
              </label>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Injectors</h4>
        {injectorWells.length === 0 ? (
          <p className="text-xs text-gray-400 italic">none</p>
        ) : (
          <div className="space-y-1">
            {injectorWells.map((w) => (
              <label key={w} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedWells.has(w)}
                  onChange={() => toggleWell(w)}
                  className="rounded"
                />
                <span>{w}</span>
              </label>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Vector Groups</h4>
        {ALL_GROUPS.map((group) => {
          const vecs = collectGroupVectors(group, categorized);
          if (vecs.length === 0) return null;
          return (
            <details key={group} className="mb-2" open>
              <summary className="text-xs font-medium cursor-pointer">{group.replace('_', ' ')}</summary>
              <div className="ml-2 mt-1 space-y-1">
                {vecs.map((vec) => (
                  <label key={vec} className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={selectedVectors[group]?.has(vec) ?? false}
                      onChange={() => toggleVector(group, vec)}
                      className="rounded"
                    />
                    <span>{vec}</span>
                  </label>
                ))}
              </div>
            </details>
          );
        })}
      </section>

      <section>
        <h4 className="text-xs font-semibold uppercase text-gray-500 mb-2">Display</h4>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={logScale}
            onChange={(e) => onLogScale(e.target.checked)}
            className="rounded"
          />
          <span>Log scale (Y)</span>
        </label>
      </section>
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