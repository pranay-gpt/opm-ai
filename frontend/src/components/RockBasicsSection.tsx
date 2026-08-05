import { useCallback } from 'react';
import type {
  RockBasicsOverrides,
  ResolvedRockBasics,
} from '../stores/useAppStore';

export type RockBasicsField = keyof RockBasicsOverrides;

interface Props {
  overrides: RockBasicsOverrides;
  resolved: ResolvedRockBasics | null;
  provenance: Record<string, string>;
  isOpen: boolean;
  onToggle: () => void;
  onChange: <K extends RockBasicsField>(
    field: K,
    value: RockBasicsOverrides[K],
  ) => void;
  onReset: () => void;
}

// What the UI displays per field. Order matters - this is the order the
// rows appear in the card. Scalar fields come first (one input each);
// per-layer array fields come last (a CSV input with a length hint).
const SCALAR_FIELDS: Array<{
  field: RockBasicsField;
  label: string;
  units: string;
  hint: string;
  step: number;
}> = [
  { field: 'porosity',       label: 'Porosity',           units: '(fraction)', hint: '0.05 – 0.40 typical', step: 0.01 },
  { field: 'top_depth',      label: 'Top depth',          units: '(ft)',       hint: '500 – 20000 typical', step: 50 },
  { field: 'initial_pressure', label: 'Initial pressure', units: '(psia)',     hint: 'must be ≥ reservoir hydrostatic', step: 50 },
];

const ARRAY_FIELDS: Array<{
  field: RockBasicsField;
  label: string;
  units: string;
  hint: string;
}> = [
  { field: 'dz',    label: 'Layer thickness (dz)',  units: '(ft)', hint: 'one entry per layer' },
  { field: 'permx', label: 'Permeability X (kx)',   units: '(mD)', hint: 'one entry per layer' },
  { field: 'permy', label: 'Permeability Y (ky)',   units: '(mD)', hint: 'one entry per layer' },
  { field: 'permz', label: 'Permeability Z (kz)',   units: '(mD)', hint: 'one entry per layer' },
];

type Provenance = 'extracted' | 'defaulted' | 'user_override' | 'required_missing' | string;

const PROVENANCE_LABEL: Record<Provenance, string> = {
  extracted: 'extracted',
  defaulted: 'defaulted',
  user_override: 'user override',
  required_missing: 'missing',
};
const PROVENANCE_CLASS: Record<Provenance, string> = {
  extracted: 'bg-success/10 text-success',
  defaulted: 'bg-warning/10 text-warning',
  user_override: 'bg-info/10 text-info',
  required_missing: 'bg-error/10 text-error',
};

function parseCsv(raw: string): number[] {
  return raw
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map(Number)
    .filter((n) => Number.isFinite(n));
}

function formatList(values: number[] | null | undefined): string {
  if (!values || values.length === 0) return '';
  return values.join(', ');
}

export default function RockBasicsSection({
  overrides,
  resolved,
  provenance,
  isOpen,
  onToggle,
  onChange,
  onReset,
}: Props) {
  // The value displayed in the input. If the user has an override, show
  // it; otherwise hydrate from the resolved value (or empty before any
  // build has run). The user types a new value -> onChange -> store -> we
  // re-render with the override displayed.
  const scalarValue = useCallback(
    (field: RockBasicsField): string => {
      const o = overrides[field];
      if (typeof o === 'number') return String(o);
      if (o !== null && Array.isArray(o)) return String(o[0] ?? '');
      // No override; show resolved (or empty).
      if (resolved && typeof resolved[field] === 'number') {
        return String(resolved[field]);
      }
      return '';
    },
    [overrides, resolved],
  );

  const arrayValue = useCallback(
    (field: RockBasicsField): string => {
      const o = overrides[field];
      if (Array.isArray(o)) return formatList(o);
      if (resolved && Array.isArray(resolved[field])) return formatList(resolved[field]);
      return '';
    },
    [overrides, resolved],
  );

  const tag = useCallback(
    (field: RockBasicsField): Provenance => {
      // If the user has overridden this field, it is always "user_override"
      // regardless of what the last backend resolved to.
      if (overrides[field] !== null) return 'user_override';
      return provenance[field] ?? 'defaulted';
    },
    [overrides, provenance],
  );

  const arrayLength = (field: RockBasicsField): number | null => {
    if (resolved && Array.isArray(resolved[field])) return resolved[field].length;
    return null;
  };

  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-textSecondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7l4-4h10l4 4-9 9-9-9zm0 0v10a2 2 0 002 2h14a2 2 0 002-2V7" />
          </svg>
          <span className="font-medium text-textPrimary">Rock basics (porosity, depth, perm)</span>
          {!isOpen && resolved && (
            <span className="ml-2 text-xs text-textMuted">
              porosity {resolved.porosity.toFixed(2)} ·
              {' '}depth {Math.round(resolved.top_depth)} ft ·
              {' '}p {Math.round(resolved.initial_pressure)} psia
            </span>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-textSecondary transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-4 border-t border-border">
          <p className="text-xs text-textMuted pt-2">
            Confirm or replace values the offline extractor inferred. Unchanged
            fields use whatever the parser resolved on the last build.
          </p>

          {/* Scalar fields */}
          {SCALAR_FIELDS.map(({ field, label, units, hint, step }) => (
            <div key={field} className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3 items-end">
              <div>
                <label className="block text-xs font-medium text-textSecondary mb-1">
                  {label} <span className="text-textMuted">{units}</span>
                </label>
                <input
                  type="number"
                  step={step}
                  value={scalarValue(field)}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === '') {
                      // Clearing the input clears the override.
                      onChange(field, null);
                      return;
                    }
                    const n = Number(raw);
                    if (Number.isFinite(n)) {
                      onChange(field, n);
                    }
                  }}
                  className="input w-full text-sm"
                />
                <p className="text-xs text-textMuted mt-1">{hint}</p>
              </div>
              <span
                className={`text-xs px-2 py-1 rounded h-fit whitespace-nowrap ${PROVENANCE_CLASS[tag(field)]}`}
                title={`Where this value comes from`}
              >
                {PROVENANCE_LABEL[tag(field)]}
              </span>
            </div>
          ))}

          {/* Array fields (one CSV input per field) */}
          {ARRAY_FIELDS.map(({ field, label, units, hint }) => {
            const n = arrayLength(field);
            return (
              <div key={field} className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3 items-end">
                <div>
                  <label className="block text-xs font-medium text-textSecondary mb-1">
                    {label} <span className="text-textMuted">{units}</span>
                  </label>
                  <input
                    type="text"
                    placeholder={n ? `e.g. ${Array.from({ length: n }, (_, i) => (i === 0 ? 100 : 50)).join(', ')}` : 'e.g. 100, 50'}
                    value={arrayValue(field)}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      if (raw === '') {
                        onChange(field, null);
                        return;
                      }
                      const parsed = parseCsv(raw);
                      onChange(field, parsed.length === 0 ? null : parsed);
                    }}
                    className="input w-full text-sm font-mono"
                  />
                  <p className="text-xs text-textMuted mt-1">
                    {n ? `${hint} (${n} layers)` : hint}
                  </p>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded h-fit whitespace-nowrap ${PROVENANCE_CLASS[tag(field)]}`}
                >
                  {PROVENANCE_LABEL[tag(field)]}
                </span>
              </div>
            );
          })}

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={onReset}
              className="text-xs text-textSecondary hover:text-textPrimary underline"
              title="Clear all user overrides; deck will use whatever the parser resolved on the next build."
            >
              Reset overrides
            </button>
          </div>
        </div>
      )}
    </div>
  );
}