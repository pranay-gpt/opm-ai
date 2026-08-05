import { useState, useCallback, useEffect, useRef } from 'react';
import { useSimulationStore, useDeckStore } from '../stores/useAppStore';
import { api, pollJobStatus } from '../api/client';
import type { RunRequest, JobStatus } from '../api/client';
import type { UploadResponse } from '../types';
import DeckPicker from './DeckPicker';
import DeckUploader from './DeckUploader';

export default function SimulationRunner() {
  const { currentJob, jobHistory, setCurrentJob, addToHistory } = useSimulationStore();
  const { lastDeckPath, lastBuildResponse, currentDeck } = useDeckStore();

  const [deckPath, setDeckPath] = useState(lastDeckPath || '');
  const [timeout, setTimeout] = useState(120);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [picking, setPicking] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Holds the controller for the currently-running poll so cleanup can
  // cancel it on unmount. A bare Promise from pollJobStatus would keep
  // the setTimeout chain alive past the component's lifetime.
  const pollControllerRef = useRef<AbortController | null>(null);

  // inFlightRef guards handleRun against double-firing before React
  // commits disabled={isRunning || polling} on the button (F8.8 audit
  // fix). A ref is used instead of reading isRunning from the
  // useCallback closure so we don't have to add isRunning/polling to
  // the deps array (which would re-create handleRun every render and
  // thrash children that depend on it).
  const inFlightRef = useRef(false);

  // Abort any in-flight poll when the component unmounts (e.g. user
  // navigates away mid-run). The job itself keeps running on the server
  // — only the client-side polling and the onUpdate callbacks stop.
  useEffect(() => {
    return () => {
      pollControllerRef.current?.abort();
    };
  }, []);

  // Reconcile persisted job state with the backend on mount: the job store
  // is in-memory server-side, so a restart orphans "running" jobs.
  useEffect(() => {
    if (currentJob && (currentJob.status === 'running' || currentJob.status === 'pending')) {
      api.runStatus(currentJob.job_id)
        .then((status) => setCurrentJob(status))
        .catch(() => {
          setCurrentJob({ ...currentJob, status: 'failed', error: 'Job no longer exists (server restarted)' });
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRun = useCallback(async () => {
    if (!deckPath.trim()) {
      setError('Please enter a deck path or build a deck first');
      return;
    }

    setIsRunning(true);
    inFlightRef.current = true;
    setError(null);

    try {
      const request: RunRequest = { deck_path: deckPath, timeout };
      const job = await api.run(request);

      setCurrentJob(job);
      addToHistory(job);
      setPolling(true);

      // Poll for completion. The AbortController is owned by the
      // component (ref + unmount cleanup) so the loop and onUpdate
      // stop when the user navigates away.
      const controller = new AbortController();
      pollControllerRef.current = controller;
      const finalJob = await pollJobStatus(
        job.job_id,
        (status) => setCurrentJob(status),
        2000,
        300,
        controller.signal
      );
      pollControllerRef.current = null;

      setPolling(false);
      if (finalJob.status === 'failed') {
        setError(finalJob.error || 'Simulation failed');
      }
    } catch (err) {
      setPolling(false);
      // Polling aborted on unmount is not a user-facing error — the job
      // is still running on the server, the client just stopped watching.
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      const message = err instanceof Error ? err.message : 'Failed to start simulation';
      setError(message);
      console.error('Run error:', err);
    } finally {
      setIsRunning(false);
      inFlightRef.current = false;
    }
  }, [deckPath, timeout, setCurrentJob, addToHistory]);

  // Wraps handleRun with the in-flight guard so it stays referentially
  // stable across renders but always reads the latest ref value (F8.8).
  // The button's onClick uses handleRunGuarded; the disabled check still
  // reads isRunning/polling for visual feedback.
  const handleRunGuarded = useCallback(() => {
    if (inFlightRef.current) return;
    return handleRun();
  }, [handleRun]);

  const handleUseLastDeck = useCallback(async () => {
    // Use the deck from last build response or current deck editor content
    const deckText = lastBuildResponse?.deck || currentDeck;
    if (deckText) {
      try {
        // Save to backend and get a real path
        const saveResponse = await api.saveDeck({ content: deckText, filename: 'DECK.DATA' });
        setDeckPath(saveResponse.deck_path);
      } catch (err) {
        console.error('Save deck error:', err);
        setError('Failed to save deck for simulation');
      }
    }
  }, [lastBuildResponse, currentDeck]);

  // Browse picks a path on the server rather than uploading file bytes. A
  // browser file input can only hand over the one file selected, so a deck
  // with INCLUDE arrived without its include/ tree and Flow aborted on the
  // first missing .grdecl. Selecting in place keeps those siblings reachable.
  const handlePicked = useCallback((path: string) => {
    setDeckPath(path);
    setError(null);
  }, []);

  // Upload is the laptop-local-files counterpart to Browse. The
  // user picks the .DATA and an optional include/ folder; the
  // backend writes them to a fresh mkdtemp and returns the .DATA's
  // server-side path so the existing run flow works unchanged.
  const handleUploaded = useCallback((result: UploadResponse) => {
    setDeckPath(result.deck_path);
    setError(null);
    setUploading(false);
  }, []);

  const handleRefresh = useCallback(async () => {
    if (currentJob) {
      try {
        const status = await api.runStatus(currentJob.job_id);
        setCurrentJob(status);
      } catch (err) {
        console.error('Refresh error:', err);
      }
    }
  }, [currentJob, setCurrentJob]);

  return (
    <div className="flex flex-col h-full bg-page">
      {picking && (
        <DeckPicker onSelect={handlePicked} onClose={() => setPicking(false)} />
      )}
      {uploading && (
        <DeckUploader onUpload={handleUploaded} onClose={() => setUploading(false)} />
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-semibold text-textPrimary">Simulator</h1>
          <p className="text-sm text-textSecondary">Run OPM Flow simulations</p>
        </div>
        <div className="flex items-center gap-2">
          {currentJob && (
            <span className={`badge ${getStatusBadgeClass(currentJob.status)} text-xs`}>
              {currentJob.status.toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Configuration */}
        <div className="w-full lg:w-1/2 border-r border-border p-4 lg:p-6 overflow-y-auto">
          <div className="space-y-6 max-w-xl mx-auto">
            {/* Deck Input */}
            <div className="card p-4">
              <label className="block text-sm font-medium text-textPrimary mb-2">Deck Path</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={deckPath}
                  onChange={(e) => setDeckPath(e.target.value)}
                  placeholder="/path/to/deck.DATA"
                  className="input flex-1 font-mono text-sm"
                />
                <button
                  onClick={() => setPicking(true)}
                  className="btn-secondary btn-sm whitespace-nowrap"
                  title="Browse .DATA decks on the server"
                >
                  Browse
                </button>
                <button
                  onClick={() => setUploading(true)}
                  className="btn-secondary btn-sm whitespace-nowrap"
                  title="Upload a .DATA file and its include/ folder from your laptop"
                >
                  Upload
                </button>
                {lastBuildResponse && (
                  <button
                    onClick={handleUseLastDeck}
                    className="btn-secondary btn-sm whitespace-nowrap"
                  >
                    Use Last Built Deck
                  </button>
                )}
              </div>
              <p className="text-xs text-textMuted mt-2">
                Browse decks on the server, Upload from your laptop, enter a path, or
                build one in the Deck Builder. Decks run in their own folder, so
                INCLUDE files resolve.
              </p>
            </div>

            {/* Options */}
            <div className="card p-4">
              <h3 className="font-medium text-textPrimary mb-4">Simulation Options</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-textPrimary mb-1">Timeout (seconds)</label>
                  <input
                    type="number"
                    value={timeout}
                    onChange={(e) => setTimeout(Number(e.target.value))}
                    min={10}
                    max={3600}
                    className="input w-32 font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Run Button */}
            <div className="flex gap-3">
              <button
                onClick={handleRunGuarded}
                disabled={isRunning || polling || !deckPath.trim()}
                className="btn-primary flex-1 py-3 text-base"
              >
                {isRunning ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Starting...
                  </span>
                ) : polling ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Running...
                  </span>
                ) : (
                  'Run Simulation'
                )}
              </button>
              {currentJob && (
                <button onClick={handleRefresh} className="btn-secondary px-4" disabled={polling}>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Refresh
                </button>
              )}
            </div>

            {error && (
              <div className="p-3 rounded bg-error/20 border border-error text-error text-sm">
                {error}
              </div>
            )}

            {/* Current Job Status */}
            {currentJob && (
              <div className="card p-4">
                <h3 className="font-medium text-textPrimary mb-3">Job Status</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-textSecondary">Job ID</span>
                    <code className="text-xs font-mono text-textPrimary">{currentJob.job_id.slice(0, 12)}...</code>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-textSecondary">Status</span>
                    <span className={`font-medium ${getStatusColor(currentJob.status)}`}>
                      {getStatusLabel(currentJob.status)}
                    </span>
                  </div>
                  {currentJob.result && (
                    <>
                      <div className="flex items-center justify-between">
                        <span className="text-textSecondary">Success</span>
                        <span className={currentJob.result.success ? 'text-success' : 'text-error'}>
                          {currentJob.result.success ? 'Yes' : 'No'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-textSecondary">Return Code</span>
                        <code className="text-xs font-mono">{currentJob.result.return_code}</code>
                      </div>
                    </>
                  )}
                  {currentJob.error && (
                    <div className="text-error text-sm">Error: {currentJob.error}</div>
                  )}

                  {/* Progress Bar for running jobs */}
                  {currentJob.status === 'running' && (
                    <div className="progress-bar mt-2">
                      <div className="progress-fill animate-pulse" style={{ width: '50%' }} />
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Job History */}
            {jobHistory.length > 0 && (
              <div className="card p-4">
                <h3 className="font-medium text-textPrimary mb-3">Recent Jobs</h3>
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {jobHistory.slice(0, 10).map((job) => (
                    <button
                      key={job.job_id}
                      onClick={() => setCurrentJob(job)}
                      className={`w-full text-left p-3 rounded border transition-colors ${
                        currentJob?.job_id === job.job_id
                          ? 'border-primary bg-primary/10'
                          : 'border-border hover:border-primary/50 hover:bg-surfaceHover'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <code className="text-xs font-mono text-textPrimary">{job.job_id.slice(0, 12)}...</code>
                        <span className={`badge text-xs ${getStatusBadgeClass(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                      <div className="text-xs text-textSecondary mt-1">
                        {job.result?.success ? '[OK] Completed' : job.error ? '[FAIL] Failed' : '[RUN] Running...'}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - Live Output */}
        <div className="w-full lg:w-1/2 flex flex-col bg-surface border-l border-border">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <h2 className="font-semibold text-textPrimary">Live Output</h2>
            <div className="flex items-center gap-2">
              {polling && (
                <span className="flex items-center gap-1 text-xs text-primary">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  Streaming...
                </span>
              )}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-4 font-mono text-sm">
            {currentJob?.result?.stdout ? (
              <pre className="whitespace-pre-wrap text-textSecondary">{currentJob.result.stdout}</pre>
            ) : polling ? (
              <div className="flex flex-col items-center justify-center h-full text-textMuted">
                <svg className="w-12 h-12 mb-4 opacity-30 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p>Waiting for simulation output...</p>
                <p className="text-xs mt-1">Output will appear here as the simulation runs</p>
              </div>
            ) : currentJob?.error ? (
              <pre className="whitespace-pre-wrap text-error">{currentJob.error}</pre>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-textMuted">
                <svg className="w-12 h-12 mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p>No simulation running</p>
                <p className="text-xs mt-1">Start a simulation to see live output here</p>
              </div>
            )}

            {currentJob?.result?.stderr && (
              <div className="border-t border-border mt-4 pt-4">
                <div className="text-xs font-semibold text-textSecondary mb-2">STDERR</div>
                <pre className="whitespace-pre-wrap text-warning">{currentJob.result.stderr}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function getStatusColor(status: JobStatus['status']): string {
  switch (status) {
    case 'completed': return 'text-success';
    case 'failed': return 'text-error';
    case 'running': return 'text-primary';
    default: return 'text-warning';
  }
}

function getStatusLabel(status: JobStatus['status']): string {
  switch (status) {
    case 'completed': return 'Completed';
    case 'failed': return 'Failed';
    case 'running': return 'Running';
    default: return 'Pending';
  }
}

function getStatusBadgeClass(status: JobStatus['status']): string {
  switch (status) {
    case 'completed': return 'badge-success';
    case 'failed': return 'badge-error';
    case 'running': return 'badge-primary';
    default: return 'badge-warning';
  }
}