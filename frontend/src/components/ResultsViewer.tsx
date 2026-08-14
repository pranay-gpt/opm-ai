import { useState, useEffect, useRef, useCallback } from 'react';
import { useLastResults, useCurrentJob, useSimulationActions, useResolvedTheme, useCategoriesForJob } from '../stores/useAppStore';
import { api } from '../api/client';
import type { KPIsResponse, ExplainRequest, ExplainResponse, ExplanationLevel, Citation, CategorizedVectors, VectorGroup, JobStatus } from '../types';
import Grid3DViewer from './viewer3d/Grid3DViewer';
import PlotCard from './results/PlotCard';
import ResultsControlRail from './results/ResultsControlRail';
import ImportResultsButton from './results/ImportResultsButton';
// @ts-expect-error plotly.js-dist ships no types; @types/plotly.js covers the API
import Plotly from 'plotly.js-dist-min';

interface KPICard {
  key: string;
  label: string;
  unit: string;
  format: (v: number) => string;
}

const KPI_CARDS: KPICard[] = [
  { key: 'days', label: 'Simulation Days', unit: 'days', format: (v: number) => v.toFixed(0) },
  { key: 'field_oil_recovery', label: 'Cumulative Oil', unit: 'STB', format: (v: number) => v.toLocaleString() },
  { key: 'field_water_recovery', label: 'Cumulative Water', unit: 'STB', format: (v: number) => v.toLocaleString() },
  { key: 'field_gas_recovery', label: 'Cumulative Gas', unit: 'MSCF', format: (v: number) => v.toLocaleString() },
  { key: 'max_watercut', label: 'Max Water Cut', unit: '%', format: (v: number) => (v * 100).toFixed(1) },
  { key: 'final_gor', label: 'Final GOR', unit: 'MSCF/STB', format: (v: number) => v.toFixed(2) },
  { key: 'producer_count', label: 'Producers', unit: '', format: (v: number) => v.toFixed(0) },
  { key: 'plateau_duration_days', label: 'Plateau Duration', unit: 'days', format: (v: number) => v.toFixed(0) },
];

export default function ResultsViewer() {
  const lastResults = useLastResults();
  const currentJob = useCurrentJob();
  const { setLastResults, setCurrentJob } = useSimulationActions();

  const [results, setResults] = useState<KPIsResponse | null>(lastResults);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'kpis' | 'plots' | '3d'>('kpis');

  // ResInsight launch state. The route is localhost-gated (403 from a remote
  // client); the button is disabled when viewer_available is false so we never
  // claim a launch we cannot deliver.
  const [resinsightLaunching, setResinsightLaunching] = useState(false);
  const [resinsightPid, setResinsightPid] = useState<number | null>(null);
  const [resinsightError, setResinsightError] = useState<string | null>(null);

  // Explain results state
  const [explainResponse, setExplainResponse] = useState<ExplainResponse | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [explainLevel, setExplainLevel] = useState<ExplanationLevel>('intermediate');

  // Plots tab state
  const [categorized, setCategorizedState] = useState<CategorizedVectors | null>(null);
  const [selectedWells, setSelectedWells] = useState<Set<string>>(new Set());
  const [selectedVectors, setSelectedVectors] = useState<Record<VectorGroup, Set<string>>>({
    field_rates: new Set(), field_cumulative: new Set(), field_derived: new Set(),
    well_rates: new Set(), well_cumulative: new Set(), well_injection: new Set(),
  });
  const [logScale, setLogScale] = useState(false);
  const { setCategories } = useSimulationActions();
  const cachedCategories = useCategoriesForJob(currentJob?.job_id);

  // Wrapper to match ResultsControlRail's expected signature
  const handleSetVectors = useCallback((group: VectorGroup, vecs: Set<string>) => {
    setSelectedVectors((prev) => ({ ...prev, [group]: vecs }));
  }, []);

  // Load categories when results become available
  useEffect(() => {
    if (!currentJob?.job_id || !results) return;
    if (cachedCategories) {
      setCategorizedState(cachedCategories);
      return;
    }
    api.categories(currentJob.job_id).then((cats) => {
      setCategorizedState(cats);
      setCategories(currentJob.job_id, cats);
    }).catch((err) => {
      console.error('categories fetch failed', err);
    });
  }, [currentJob?.job_id, results, cachedCategories, setCategories]);

  // Load results when job completes. The `!results` guard is the
  // load-once invariant (F8.3 audit: previously flagged as a
  // re-trigger risk, but the only writer of `results` is loadResults
  // itself which always sets a non-null payload; the `!results` check
  // is therefore sufficient and `loadedJobIdRef` is unnecessary).
  useEffect(() => {
    if (currentJob?.status === 'completed' && currentJob.job_id && !results) {
      loadResults(currentJob.job_id);
    }
    if (currentJob?.status === 'failed') {
      setError(currentJob.error || 'Simulation failed');
    }
  }, [currentJob, results]);

  const loadResults = useCallback(async (jobId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.results(jobId);
      setResults(data);
      setLastResults(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load results';
      setError(message);
      console.error('Results error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [setLastResults]);

  const handleLaunchResinsight = useCallback(async () => {
    if (!currentJob?.job_id) return;
    setResinsightLaunching(true);
    setResinsightError(null);
    try {
      const res = await api.launchResinsight(currentJob.job_id);
      setResinsightPid(res.pid);
      if (!res.launched && res.reason === 'already running') {
        // Not an error - just no-op with the existing PID. UI shows it.
      } else if (res.error) {
        setResinsightError(res.error);
      }
    } catch (err) {
      // 403 from non-loopback and 503 from unavailable come through here.
      const message = err instanceof Error ? err.message : 'Failed to launch ResInsight';
      setResinsightError(message);
      console.error('ResInsight launch error:', err);
    } finally {
      setResinsightLaunching(false);
    }
  }, [currentJob?.job_id]);

  // Handle explain results
  const handleExplainResults = useCallback(async () => {
    if (!results?.kpis) {
      setExplainError('No KPIs available to explain');
      return;
    }

    setExplainLoading(true);
    setExplainError(null);
    setExplainResponse(null);

    try {
      const request: ExplainRequest = {
        topic: null,
        kpis: results.kpis,
        level: explainLevel,
        context: null,
      };
      const response = await api.explainConcept(request);
      setExplainResponse(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to explain results';
      setExplainError(message);
      console.error('Explain error:', err);
    } finally {
      setExplainLoading(false);
    }
  }, [results?.kpis, explainLevel]);

  // KPI value getter
  const getKpiValue = (kpi: KPICard) => {
    if (!results?.kpis) return '-';
    const value = results.kpis[kpi.key];
    if (value === undefined || value === null) return '-';
    if (typeof value === 'number') return kpi.format(value);
    return String(value);
  };

  if (!results && !isLoading) {
    return (
      <div className="flex flex-col h-full bg-page">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
          <h1 className="text-xl font-semibold text-textPrimary">Results Viewer</h1>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center p-8 text-textSecondary">
            <svg className="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <p className="text-lg font-medium text-textPrimary mb-1">No Results Available</p>
            <p className="text-sm max-w-xs">Run a simulation to see KPIs and production plots here</p>
            {currentJob?.job_id && (
              <button
                onClick={() => loadResults(currentJob.job_id)}
                className="btn-primary mt-4"
                disabled={isLoading}
              >
                {isLoading ? 'Loading...' : 'Load Results'}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-page">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-semibold text-textPrimary">Results Viewer</h1>
          <p className="text-sm text-textSecondary">
            {currentJob ? `Job: ${currentJob.job_id.slice(0, 12)}...` : 'Latest results'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && (
            <span className="flex items-center gap-1 text-xs text-primary">
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Loading...
            </span>
          )}
          {error && (
            <span className="badge badge-error text-xs">{error}</span>
          )}
          <ImportResultsButton
            onImported={(resp) => {
              // Trigger a results reload for the new job
              const newJob: JobStatus = { job_id: resp.job_id, status: 'completed', result: null, error: null };
              setCurrentJob(newJob as any);
              loadResults(resp.job_id);
            }}
          />
          {currentJob?.status === 'completed' && currentJob.job_id && (
            <button
              onClick={handleLaunchResinsight}
              disabled={!results?.viewer_available || resinsightLaunching}
              className="btn-secondary btn-sm"
              title={
                !results?.viewer_available
                  ? 'ResInsight is not available on the server (no binary or no DISPLAY)'
                  : resinsightPid
                    ? `ResInsight is running on the server (pid ${resinsightPid})`
                    : 'Open this case in ResInsight on the server\'s display'
              }
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              {resinsightLaunching
                ? 'Launching...'
                : resinsightPid
                  ? 'ResInsight open'
                  : 'Open in ResInsight'}
            </button>
          )}
          {resinsightError && (
            <span className="badge badge-error text-xs">{resinsightError}</span>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border bg-surface">
        {[
          { id: 'kpis', label: 'KPIs', icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg> },
          { id: 'plots', label: 'Plots', icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg> },
          { id: '3d', label: '3D View', icon: <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={`tab ${activeTab === tab.id ? 'tab-active' : ''}`}
          >
            <span className="flex items-center gap-1.5">
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {/* KPIs Tab */}
        {activeTab === 'kpis' && (
          <div className="p-4 lg:p-6">
            {error && (
              <div className="mb-4 p-3 rounded bg-error/20 border border-error text-error text-sm">
                {error}
              </div>
            )}

            {/* KPI Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {KPI_CARDS.map((kpi) => (
                <div key={kpi.key} className="kpi-card">
                  <div className="kpi-value">{getKpiValue(kpi)}</div>
                  <div className="kpi-label">{kpi.label}</div>
                  <div className="text-xs text-textMuted">{kpi.unit}</div>
                </div>
              ))}

              {/* Raw KPIs from backend */}
              {results?.kpis && (
                <>
                  {Object.entries(results.kpis)
                    .filter(([key]) => !KPI_CARDS.some((k) => k.key === key))
                    .slice(0, 8)
                    .map(([key, value]) => (
                      <div key={key} className="kpi-card">
                        <div className="kpi-value">
                          {typeof value === 'number' ? value.toLocaleString() : String(value)}
                        </div>
                        <div className="kpi-label">{key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</div>
                      </div>
                    ))}
                </>
              )}
            </div>

            {/* Explain Results Button */}
            <div className="card p-4 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                <div className="flex items-center gap-3">
                  <label className="text-sm font-medium text-textPrimary">Explanation Level:</label>
                  <div className="flex gap-2">
                    {['beginner', 'intermediate', 'advanced'].map((level) => (
                      <button
                        key={level}
                        onClick={() => setExplainLevel(level as ExplanationLevel)}
                        className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                          explainLevel === level
                            ? 'bg-primary text-page'
                            : 'bg-surface border border-border text-textSecondary hover:text-textPrimary hover:border-primary/50'
                        }`}
                        disabled={explainLoading}
                      >
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={handleExplainResults}
                  disabled={explainLoading || !results?.kpis || Object.keys(results.kpis).length === 0}
                  title={!results?.kpis || Object.keys(results.kpis).length === 0 ? 'No KPIs to explain' : ''}
                  className="btn-primary flex-1 sm:flex-none py-2.5"
                >
                  {explainLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Explaining...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Explain These Results
                    </span>
                  )}
                </button>
              </div>

              {explainError && (
                <div className="mt-3 p-3 rounded bg-error/20 border border-error text-error text-sm">
                  {explainError}
                </div>
              )}

              {/* Explanation Panel */}
              {explainResponse && (
                <div className="mt-4 pt-4 border-t border-border">
                  <h3 className="font-semibold text-textPrimary mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Explanation ({explainResponse.level})
                  </h3>
                  <div className="prose prose-invert max-w-none whitespace-pre-wrap text-sm leading-relaxed">
                    {explainResponse.text}
                  </div>

                  {/* Citations */}
                  {explainResponse.citations.length > 0 && (
                    <details className="mt-4">
                      <summary className="cursor-pointer font-medium text-textPrimary flex items-center gap-2 text-sm">
                        <span>Citations ({explainResponse.citations.length})</span>
                        <svg className="w-4 h-4 text-textSecondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </summary>
                      <ul className="mt-2 space-y-2 text-xs">
                        {explainResponse.citations.map((citation, idx) => (
                          <li key={idx} className="text-textSecondary">
                            <div className="font-mono text-textMuted">{citation.source_id}</div>
                            <div className="font-medium text-textPrimary">{citation.title}</div>
                            {citation.url_or_path && (
                              <a href={citation.url_or_path} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primaryHover underline">
                                {citation.url_or_path}
                              </a>
                            )}
                            <div className="line-clamp-2">{citation.snippet}</div>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}

                  {/* Follow-up Questions */}
                  {explainResponse.follow_up_questions.length > 0 && (
                    <div className="mt-4">
                      <h4 className="font-medium text-textPrimary mb-2 text-sm">Follow-up Questions</h4>
                      <div className="flex flex-wrap gap-2">
                        {explainResponse.follow_up_questions.map((q, idx) => (
                          <button
                            key={idx}
                            onClick={() => {
                              // Could trigger a re-explain with the follow-up as topic
                              setExplainLevel(explainLevel);
                            }}
                            className="px-3 py-1.5 text-xs rounded border border-border text-textSecondary hover:text-textPrimary hover:border-primary/50 hover:bg-surfaceHover transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Full KPI JSON */}
            {results?.kpis && (
              <details className="card">
                <summary className="p-4 cursor-pointer font-medium text-textPrimary flex items-center justify-between">
                  <span>All KPIs (JSON)</span>
                  <svg className="w-4 h-4 text-textSecondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="p-4 border-t border-border">
                  <pre className="text-xs font-mono text-textSecondary overflow-auto max-h-96">
                    {JSON.stringify(results.kpis, null, 2)}
                  </pre>
                </div>
              </details>
            )}
          </div>
        )}

        {/* Plots Tab. The plots field is `dict[str, str]` in the contract but
            a malformed payload (null/missing/object) would otherwise throw
            inside Object.keys. The `plots &&` guard and the `Object.keys`
            check below both treat missing/empty as the same "no plots" state
            so the user gets a clear empty-state instead of a silent blank
            tab (F1.6 audit fix - the previous `results?.plots &&` short-
            circuit hid the whole tab with no fallback). */}
        {activeTab === 'plots' && results && (
          <div className="flex h-full">
            {categorized && (
              <ResultsControlRail
                categorized={categorized}
                selectedWells={selectedWells}
                onWells={setSelectedWells}
                selectedVectors={selectedVectors}
                onVectors={handleSetVectors}
                logScale={logScale}
                onLogScale={setLogScale}
              />
            )}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {results.plots && Object.keys(results.plots).length > 0 ? (
                <>
                  <PlotCard jobId={currentJob?.job_id ?? ''} plotName="Field Rates" plotJson={results.plots['field_rates'] ?? ''} />
                  <PlotCard jobId={currentJob?.job_id ?? ''} plotName="Field Cumulative" plotJson={results.plots['field_cumulative'] ?? ''} />
                  <PlotCard jobId={currentJob?.job_id ?? ''} plotName="Field Derived" plotJson={results.plots['field_derived'] ?? ''} />
                  {selectedWells.size > 0 && (
                    <>
                      <PlotCard jobId={currentJob?.job_id ?? ''} plotName="Well Rates" plotJson={results.plots['well_rates'] ?? ''} />
                      <PlotCard jobId={currentJob?.job_id ?? ''} plotName="Well Cumulative" plotJson={results.plots['well_cumulative'] ?? ''} />
                      <PlotCard jobId={currentJob?.job_id ?? ''} plotName="Well Injection" plotJson={results.plots['well_injection'] ?? ''} />
                    </>
                  )}
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-96 text-textSecondary">
                  <svg className="w-16 h-16 mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <p className="text-lg font-medium text-textPrimary mb-1">No Plots Available</p>
                  <p className="text-sm">Run a simulation with plotting enabled to see charts here</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 3D View Tab. Mounted only while active so the WebGL context and
            its fetches go away when the user switches tabs. */}
        {activeTab === '3d' && (
          <div className="h-[calc(100%-50px)] min-h-[32rem]">
            {currentJob?.status === 'completed' && currentJob.job_id ? (
              <Grid3DViewer jobId={currentJob.job_id} />
            ) : (
              <div className="flex h-full items-center justify-center">
                <div className="p-8 text-center text-textSecondary">
                  <svg className="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                  </svg>
                  <p className="mb-1 text-lg font-medium text-textPrimary">3D Geomodel View</p>
                  <p className="max-w-sm text-sm">
                    {currentJob?.status === 'failed'
                      ? 'The last simulation failed, so there is no grid to display.'
                      : currentJob
                        ? 'Waiting for the simulation to finish. The grid appears once the run completes.'
                        : 'Run a simulation to explore its grid in 3D.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}