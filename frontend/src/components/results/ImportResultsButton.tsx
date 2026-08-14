import { useRef, useState } from 'react';
import { api } from '../../api/client';
import type { ImportedResultResponse } from '../../types';

interface ImportResultsButtonProps {
  onImported?: (response: ImportedResultResponse) => void;
}

const ALLOWED_EXTENSIONS = [
  '.SMSPEC', '.UNSMRY', '.ESMRY',
  '.EGRID', '.FEGRID', '.GRID', '.FGRID',
  '.UNRST', '.INIT', '.RFT', '.PRT',
];

export default function ImportResultsButton({ onImported }: ImportResultsButtonProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const open = () => {
    setFiles([]);
    setError(null);
    dialogRef.current?.showModal();
  };

  const close = () => dialogRef.current?.close();

  const submit = async () => {
    if (files.length === 0) return;
    setSubmitting(true);
    setError(null);
    const form = new FormData();
    for (const f of files) form.append('files', f, f.name);
    try {
      const response = await api.importResults(form);
      onImported?.(response);
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        onClick={open}
        className="px-3 py-1 text-sm border rounded hover:bg-gray-100 dark:hover:bg-gray-700"
        data-testid="import-results-button"
      >
        Import Results
      </button>
      <dialog ref={dialogRef} className="rounded-lg p-6 w-[480px] backdrop:bg-black/40">
        <h2 className="text-lg font-semibold mb-3">Import Simulation Results</h2>

        <div className="mb-3 text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-800 p-2 rounded">
          Required: one *.SMSPEC + one *.UNSMRY (or one *.ESMRY).
          Optional: .EGRID, .GRID, .UNRST, .INIT, .RFT, .PRT.
        </div>

        <label className="block text-sm font-medium mb-1" htmlFor="import-file-select">Select files</label>
        <input
          id="import-file-select"
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="block w-full text-sm mb-3"
        />

        {files.length > 0 && (
          <ul className="text-xs mb-3 max-h-32 overflow-y-auto border rounded p-2">
            {files.map((f) => (
              <li key={f.name} className="flex justify-between">
                <span>{f.name}</span>
                <button
                  onClick={() => setFiles(files.filter((x) => x !== f))}
                  className="text-red-500"
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && (
          <div className="text-xs text-red-600 mb-3" data-testid="import-error">{error}</div>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={close}
            className="px-3 py-1 text-sm border rounded"
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={files.length === 0 || submitting}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded disabled:opacity-50"
            data-testid="import-submit"
          >
            {submitting ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </dialog>
    </>
  );
}