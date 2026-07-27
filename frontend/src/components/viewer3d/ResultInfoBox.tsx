import type { CellInfo } from './engine';

interface ResultInfoBoxProps {
  picked: CellInfo | null;
  hovered: CellInfo | null;
  /** Label of what is currently coloured, e.g. "SOIL" or "Ternary". */
  propertyName: string;
  propertyUnit: string;
  /** Value of the active property at the picked cell, or null if unavailable. */
  pickedValue: number | null;
  hoveredValue: number | null;
  lengthUnit: string;
  onClear: () => void;
}

function fmt(v: number, digits = 2): string {
  if (!Number.isFinite(v)) return '-';
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(3);
  return v.toFixed(digits);
}

/**
 * i/j/k are shown ONE-BASED. ResInsight and every reservoir engineer count
 * from 1; the engine reports zero-based, so we add one here and say so.
 */
function ijkLabel(info: CellInfo): string {
  if (info.i < 0 || info.j < 0 || info.k < 0) {
    return `cell #${info.activeIndex} (i,j,k unavailable)`;
  }
  return `${info.i + 1}, ${info.j + 1}, ${info.k + 1}`;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-textMuted">{label}</span>
      <span className="font-mono text-textPrimary">{value}</span>
    </div>
  );
}

export default function ResultInfoBox({
  picked,
  hovered,
  propertyName,
  propertyUnit,
  pickedValue,
  hoveredValue,
  lengthUnit,
  onClear,
}: ResultInfoBoxProps) {
  if (!picked) {
    return (
      <div className="rounded-sm border border-border bg-surface/85 px-3 py-2 text-xs backdrop-blur-sm">
        {hovered ? (
          <span className="font-mono text-textSecondary">
            [{ijkLabel(hovered)}]
            {hoveredValue !== null ? ` · ${propertyName} ${fmt(hoveredValue, 4)}` : ''}
          </span>
        ) : (
          <span className="text-textMuted">Click a cell for result info</span>
        )}
      </div>
    );
  }

  const u = lengthUnit || '';
  return (
    <div className="w-64 rounded-sm border border-border bg-surface/90 backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-xs font-semibold text-textPrimary">Result Info</span>
        <button
          onClick={onClear}
          className="text-xs text-textMuted hover:text-textPrimary"
          title="Clear selection"
        >
          ✕
        </button>
      </div>
      <div className="space-y-1 px-3 py-2 text-[11px]">
        <Row label="Cell i,j,k (1-based)" value={ijkLabel(picked)} />
        <Row label="Active index" value={String(picked.activeIndex)} />
        <Row label={`X (${u})`} value={fmt(picked.center[0])} />
        <Row label={`Y (${u})`} value={fmt(picked.center[1])} />
        <Row label={`Z (${u})`} value={fmt(picked.center[2])} />
        <Row label={`Depth (${u})`} value={fmt(picked.depth)} />
        <Row label="Face" value={`${picked.faceName} (${picked.faceId})`} />
        <div className="my-1 border-t border-border" />
        <Row
          label={propertyUnit ? `${propertyName} [${propertyUnit}]` : propertyName}
          value={pickedValue !== null ? fmt(pickedValue, 5) : 'n/a'}
        />
        <div className="pt-1 text-[10px] text-textMuted">
          Hit point {fmt(picked.point[0], 1)}, {fmt(picked.point[1], 1)}, {fmt(picked.point[2], 1)}
        </div>
      </div>
    </div>
  );
}
