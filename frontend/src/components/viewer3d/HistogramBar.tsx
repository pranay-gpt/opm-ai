import { useMemo } from 'react';
import type { PropertyStats } from './meshFormat';

interface HistogramBarProps {
  stats: PropertyStats;
  /** Current legend window, shaded over the bars so clipping is visible. */
  rangeMin: number;
  rangeMax: number;
}

function fmt(v: number): string {
  if (!Number.isFinite(v)) return '-';
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(2);
  if (a >= 100) return v.toFixed(1);
  if (a >= 1) return v.toFixed(3);
  return v.toFixed(4);
}

const READOUT: Array<{ key: keyof PropertyStats; label: string }> = [
  { key: 'min', label: 'Min' },
  { key: 'p10', label: 'P10' },
  { key: 'mean', label: 'Mean' },
  { key: 'p90', label: 'P90' },
  { key: 'max', label: 'Max' },
];

/**
 * Histogram of the current property. Bins and statistics both come straight
 * from the property endpoint - nothing is recomputed on the client.
 */
export default function HistogramBar({ stats, rangeMin, rangeMax }: HistogramBarProps) {
  // Memoised off the raw fields: `?? []` allocates a fresh array every render,
  // which would make the peak recompute each time even though the data is the same.
  const bars = useMemo(() => stats.histogram ?? [], [stats.histogram]);
  const edges = stats.bin_edges ?? [];
  const peak = useMemo(() => bars.reduce((m, v) => (v > m ? v : m), 0), [bars]);

  // Legend window as a percentage span across the histogram's own domain.
  const lo = edges.length ? edges[0] : stats.min;
  const hi = edges.length ? edges[edges.length - 1] : stats.max;
  const span = hi - lo;
  const pct = (v: number) => (span > 0 ? Math.min(100, Math.max(0, ((v - lo) / span) * 100)) : 0);
  const left = pct(rangeMin);
  const right = pct(rangeMax);

  return (
    <div>
      <div className="relative flex h-20 items-end gap-px overflow-hidden rounded-sm border border-border bg-page px-1 pt-1">
        {peak > 0 &&
          bars.map((count, idx) => (
            <div
              key={idx}
              className="flex-1 bg-primary/60"
              style={{ height: `${(count / peak) * 100}%`, minHeight: count > 0 ? '1px' : '0' }}
              title={
                edges.length > idx + 1
                  ? `${fmt(edges[idx])} .. ${fmt(edges[idx + 1])}: ${count}`
                  : `${count}`
              }
            />
          ))}
        {peak === 0 && (
          <div className="flex h-full w-full items-center justify-center text-xs text-textMuted">
            No finite values
          </div>
        )}
        {span > 0 && (
          <>
            <div
              className="pointer-events-none absolute inset-y-0 left-0 bg-page/70"
              style={{ width: `${left}%` }}
            />
            <div
              className="pointer-events-none absolute inset-y-0 right-0 bg-page/70"
              style={{ width: `${100 - right}%` }}
            />
          </>
        )}
      </div>
      <div className="mt-2 grid grid-cols-5 gap-1 text-center">
        {READOUT.map(({ key, label }) => (
          <div key={label}>
            <div className="text-[10px] uppercase tracking-wide text-textMuted">{label}</div>
            <div className="font-mono text-[11px] text-textPrimary">{fmt(stats[key] as number)}</div>
          </div>
        ))}
      </div>
      <div className="mt-1 text-[10px] text-textMuted">
        {stats.count_finite.toLocaleString()} of {stats.count.toLocaleString()} cells finite
        {stats.unit ? ` · unit ${stats.unit}` : ''}
      </div>
    </div>
  );
}
