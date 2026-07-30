import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type { DeckListResponse } from '../api/client';

interface DeckPickerProps {
  onSelect: (deckPath: string) => void;
  onClose: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Server-side deck browser.
 *
 * Replaces the old `<input type="file">` Browse. A file input hands over only
 * the bytes of the one file picked, so a deck that INCLUDEs `include/*.grdecl`
 * arrived at the backend orphaned and Flow died on the first missing file.
 * Selecting a path on the server instead leaves the deck among its own
 * siblings, where its relative INCLUDE paths resolve.
 */
export default function DeckPicker({ onSelect, onClose }: DeckPickerProps) {
  const [listing, setListing] = useState<DeckListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (path?: string) => {
    setLoading(true);
    setError(null);
    try {
      setListing(await api.listDecks(path));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to list decks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Escape closes, matching the rest of the app's overlays.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="card flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 className="font-semibold text-textPrimary">Browse Decks</h2>
            <p className="truncate font-mono text-xs text-textMuted" title={listing?.root}>
              {listing?.root ?? '...'}
            </p>
          </div>
          <button onClick={onClose} className="btn-secondary btn-sm" aria-label="Close">
            Close
          </button>
        </div>

        {listing && listing.roots.length > 1 && (
          <div className="flex flex-wrap gap-2 border-b border-border px-4 py-2">
            {listing.roots.map((r) => (
              <button
                key={r}
                onClick={() => load(r)}
                className={`btn-sm rounded font-mono text-xs ${
                  listing.root === r ? 'btn-primary' : 'btn-secondary'
                }`}
                title={r}
              >
                {r.split('/').filter(Boolean).pop() || r}
              </button>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-2">
          {loading && <div className="p-4 text-sm text-textMuted">Loading...</div>}

          {error && !loading && (
            <div className="m-2 rounded border border-error bg-error/20 p-3 text-sm text-error">
              {error}
            </div>
          )}

          {listing && !loading && !error && (
            <div className="space-y-1">
              {listing.parent && (
                <button
                  onClick={() => load(listing.parent!)}
                  className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm hover:bg-surfaceHover"
                >
                  <span className="text-textMuted">^</span>
                  <span className="text-textSecondary">..</span>
                </button>
              )}

              {listing.dirs.map((d) => (
                <button
                  key={d}
                  onClick={() => load(`${listing.root.replace(/\/$/, '')}/${d}`)}
                  className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm hover:bg-surfaceHover"
                >
                  <svg className="h-4 w-4 shrink-0 text-primary/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  <span className="truncate text-textPrimary">{d}</span>
                </button>
              ))}

              {listing.decks.map((deck) => (
                <button
                  key={deck.path}
                  onClick={() => {
                    onSelect(deck.path);
                    onClose();
                  }}
                  className="flex w-full items-center gap-2 rounded px-3 py-2 text-left text-sm hover:bg-surfaceHover"
                >
                  <svg className="h-4 w-4 shrink-0 text-textMuted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="truncate font-mono text-textPrimary">{deck.name}</span>
                  {deck.has_includes && (
                    <span
                      className="badge badge-outline shrink-0 text-xs"
                      title="Uses INCLUDE; runs in place so the included files resolve"
                    >
                      INCLUDE
                    </span>
                  )}
                  <span className="ml-auto shrink-0 text-xs text-textMuted">
                    {formatSize(deck.size)}
                  </span>
                </button>
              ))}

              {listing.dirs.length === 0 && listing.decks.length === 0 && (
                <div className="p-4 text-sm text-textMuted">No decks or folders here.</div>
              )}

              {listing.truncated && (
                <div className="px-3 py-2 text-xs text-warning">
                  Listing truncated; this folder holds more than 500 decks.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
