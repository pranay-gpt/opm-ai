import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';
import type { UploadResponse } from '../types';

interface DeckUploaderProps {
  onUpload: (result: UploadResponse) => void;
  onClose: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Upload modal: pick a .DATA file and an optional include/ folder,
 * POST them to /api/upload_deck, hand the returned server path
 * back to the caller.
 *
 * Sits alongside DeckPicker (the server-side path browser). The
 * Browse button is unchanged: that workflow still works for users
 * who have the deck on the server. This is the workflow for users
 * with the deck on their laptop.
 *
 * Two file inputs:
 *   - Deck: <input type="file" accept=".DATA">. Required.
 *   - Include: <input type="file" webkitdirectory directory multiple>.
 *     Optional. The browser hands over each File with
 *     webkitRelativePath set to "include/<rel>" (the picked folder
 *     becomes the "include" folder).
 *
 * The include input's webkitdirectory attribute is non-standard
 * (Chromium-only). Firefox/Safari users will see the include
 * picker do nothing useful; the deck upload alone still works.
 * A future enhancement could add a polyfill, but for the dev
 * workflow that's the target audience, Chromium is the norm.
 */
export default function DeckUploader({ onUpload, onClose }: DeckUploaderProps) {
  const [deckFile, setDeckFile] = useState<File | null>(null);
  const [includeFiles, setIncludeFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // inFlightRef guards handleSubmit against double-firing (matches
  // the inFlightRef pattern in SimulationRunner.handleRun).
  const inFlightRef = useRef(false);

  // Escape closes, matching the rest of the app's overlays.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleDeckChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setDeckFile(file);
    setError(null);
  }, []);

  const handleIncludeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setIncludeFiles(files);
    setError(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (inFlightRef.current) return;
    if (!deckFile) {
      setError('Pick a .DATA file first.');
      return;
    }
    inFlightRef.current = true;
    setSubmitting(true);
    setError(null);

    const form = new FormData();
    form.append('deck', deckFile, deckFile.name);
    for (const f of includeFiles) {
      // The third arg is the part filename, which the backend
      // uses as the relative path. webkitRelativePath looks like
      // "include/foo.GRDECL" which the backend strips of the
      // leading "include/" before writing.
      form.append('include', f, f.webkitRelativePath || f.name);
    }

    try {
      const result = await api.uploadDeck(form);
      onUpload(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setSubmitting(false);
      inFlightRef.current = false;
    }
  }, [deckFile, includeFiles, onUpload]);

  const totalSize = (deckFile?.size ?? 0) + includeFiles.reduce((s, f) => s + f.size, 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-surface rounded-lg border border-border shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="font-semibold text-textPrimary">Upload Deck</h2>
          <button
            onClick={onClose}
            className="text-textMuted hover:text-textPrimary text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Deck picker */}
          <div>
            <label className="block text-sm font-medium text-textPrimary mb-1">
              Deck file <span className="text-textMuted">(required, .DATA)</span>
            </label>
            <input
              type="file"
              accept=".DATA"
              onChange={handleDeckChange}
              className="block w-full text-sm text-textPrimary file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-accent file:text-white file:cursor-pointer"
            />
            {deckFile && (
              <p className="text-xs text-textMuted mt-1 font-mono">
                {deckFile.name} &middot; {formatSize(deckFile.size)}
              </p>
            )}
          </div>

          {/* Include folder picker */}
          <div>
            <label className="block text-sm font-medium text-textPrimary mb-1">
              Include folder <span className="text-textMuted">(optional)</span>
            </label>
            <input
              type="file"
              // @ts-expect-error webkitdirectory is non-standard but
              // works in Chromium; Firefox/Safari users get a
              // normal file picker which is the best fallback
              // without a polyfill.
              webkitdirectory=""
              directory=""
              multiple
              onChange={handleIncludeChange}
              className="block w-full text-sm text-textPrimary file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-accent file:text-white file:cursor-pointer"
            />
            <p className="text-xs text-textMuted mt-1">
              Pick the sibling <code className="font-mono">include/</code> folder
              (the one your deck INCLUDEs from). Layout is preserved.
            </p>
            {includeFiles.length > 0 && (
              <p className="text-xs text-textMuted mt-1 font-mono">
                {includeFiles.length} file{includeFiles.length === 1 ? '' : 's'} &middot;{' '}
                {formatSize(includeFiles.reduce((s, f) => s + f.size, 0))}
              </p>
            )}
          </div>

          {error && (
            <div className="text-sm text-red-400 bg-red-900/20 border border-red-800 rounded p-2">
              {error}
            </div>
          )}

          {totalSize > 0 && !error && (
            <p className="text-xs text-textMuted font-mono">
              Total: {formatSize(totalSize)}
            </p>
          )}
        </div>

        <div className="px-4 py-3 border-t border-border flex justify-end gap-2">
          <button
            onClick={onClose}
            className="btn-secondary btn-sm"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="btn-primary btn-sm"
            disabled={submitting || !deckFile}
          >
            {submitting ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>
    </div>
  );
}