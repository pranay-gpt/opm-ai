import { useMemo } from 'react';
import { legendStops } from './colormaps';
import type { ColorMapping } from './colormaps';

interface LegendBarProps {
  mapping: ColorMapping;
  title: string;
  unit: string;
  /** Category legends get one swatch per level instead of a gradient. */
  categorical: boolean;
}

const TICK_COUNT = 6;

function formatTick(v: number): string {
  if (!Number.isFinite(v)) return '-';
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(2);
  if (a >= 100) return v.toFixed(0);
  if (a >= 1) return v.toFixed(2);
  return v.toFixed(4);
}

/**
 * Vertical colour bar with numeric ticks, drawn as an overlay on the canvas.
 * Continuous mappings render a CSS gradient; discrete and category mappings
 * render one solid band per level so the banding is unambiguous.
 */
export default function LegendBar({ mapping, title, unit, categorical }: LegendBarProps) {
  const discrete =
    categorical ||
    mapping.mapping === 'category' ||
    mapping.mapping === 'linear_discrete' ||
    mapping.mapping === 'log_discrete';

  const bands = useMemo(() => {
    const n = discrete ? Math.max(2, Math.min(mapping.levels, 32)) : 24;
    return legendStops(mapping, n);
  }, [mapping, discrete]);

  const ticks = useMemo(() => {
    const out: number[] = [];
    for (let t = 0; t < TICK_COUNT; t++) {
      const f = t / (TICK_COUNT - 1);
      if (mapping.mapping === 'log_continuous' || mapping.mapping === 'log_discrete') {
        const lo = Math.max(mapping.min, 1e-12);
        const hi = Math.max(mapping.max, lo * 10);
        out.push(lo * Math.pow(hi / lo, f));
      } else {
        out.push(mapping.min + (mapping.max - mapping.min) * f);
      }
    }
    return out.reverse(); // top of the bar is the maximum
  }, [mapping]);

  // Gradient runs bottom (min) to top (max), matching the tick order.
  const gradient = `linear-gradient(to top, ${bands
    .map((s, idx) => `${s.color} ${(idx / Math.max(1, bands.length - 1)) * 100}%`)
    .join(', ')})`;

  return (
    <div className="pointer-events-none select-none rounded-sm border border-border bg-surface/85 px-3 py-2 backdrop-blur-sm">
      <div className="mb-1 text-xs font-semibold text-textPrimary">
        {title}
        {unit ? <span className="ml-1 font-normal text-textMuted">[{unit}]</span> : null}
      </div>
      <div className="flex items-stretch gap-2">
        {discrete ? (
          <div className="flex w-5 flex-col-reverse overflow-hidden rounded-sm border border-border">
            {bands.map((s, idx) => (
              <div key={idx} className="flex-1" style={{ background: s.color }} />
            ))}
          </div>
        ) : (
          <div
            className="w-5 rounded-sm border border-border"
            style={{ background: gradient, minHeight: '11rem' }}
          />
        )}
        <div className="flex min-h-[11rem] flex-col justify-between text-[10px] font-mono leading-none text-textSecondary">
          {ticks.map((v, idx) => (
            <span key={idx}>{formatTick(v)}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
