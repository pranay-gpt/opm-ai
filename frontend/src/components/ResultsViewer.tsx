import { useState, useEffect, useRef, useCallback } from 'react';
import { useSimulationStore, useLastResults, useCurrentJob, useSimulationActions } from '../stores/useAppStore';
import { api } from '../api/client';
import type { KPIsResponse } from '../api/client';
import Plot from 'react-plotly.js';

// Access Plotly directly for newPlot
const Plotly = (window as any).Plotly;

interface KPICard {
  key: string;
  label: string;
  unit: string;
  format: (v: number) => string;
}

const KPI_CARDS: KPICard[] = [
  { key: 'days', label: 'Simulation Days', unit: 'days', format: (v: number) => v.toFixed(1) },
  { key: 'field_oil_recovery', label: 'Oil Recovery', unit: '%', format: (v: number) => (v * 100).toFixed(2) },
  { key: 'max_watercut', label: 'Max Water Cut', unit: '%', format: (v: number) => (v * 100).toFixed(1) },
  { key: 'final_gor', label: 'Final GOR', unit: 'sm³/sm³', format: (v: number) => v.toFixed(1) },
  { key: 'cum_oil', label: 'Cumulative Oil', unit: 'sm³', format: (v: number) => v.toLocaleString() },
  { key: 'cum_water', label: 'Cumulative Water', unit: 'sm³', format: (v: number) => v.toLocaleString() },
  { key: 'cum_gas', label: 'Cumulative Gas', unit: 'sm³', format: (v: number) => v.toLocaleString() },
  { key: 'avg_pressure', label: 'Avg Reservoir Pressure', unit: 'bar', format: (v: number) => v.toFixed(1) },
];

export default function ResultsViewer() {
  const lastResults = useLastResults();
  const currentJob = useCurrentJob();
  const { setLastResults } = useSimulationActions();

  const [results, setResults] = useState<KPIsResponse | null>(lastResults);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'kpis' | 'plots' | '3d'>('kpis');

  // Load results when job completes
  useEffect(() => {
    if (currentJob?.status === 'completed' && currentJob.job_id && !results) {
      loadResults(currentJob.job_id);
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

  // KPI value getter
  const getKpiValue = (kpi: KPICard) => {
    if (!results?.kpis) return '—';
    const value = results.kpis[kpi.key];
    if (value === undefined || value === null) return '—';
    if (typeof value === 'number') return kpi.format(value);
    return String(value);
  };

  if (!results && !isLoading) {
    return (
      <div className="flex flex-col h-full bg-base">
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
    <div className="flex flex-col h-full bg-base">
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
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-border bg-surface">
        {[
          { id: 'kpis', label: 'KPIs', icon: '📊' },
          { id: 'plots', label: 'Plots', icon: '📈' },
          { id: '3d', label: '3D View', icon: '🌐' },
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

        {/* Plots Tab */}
        {activeTab === 'plots' && results?.plots && (
          <div className="p-4 lg:p-6">
            {Object.keys(results.plots).length === 0 ? (
              <div className="flex flex-col items-center justify-center h-96 text-textSecondary">
                <svg className="w-16 h-16 mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <p className="text-lg font-medium text-textPrimary mb-1">No Plots Available</p>
                <p className="text-sm">Run a simulation with plotting enabled to see charts here</p>
              </div>
            ) : (
              <div className="space-y-6">
                {Object.entries(results.plots).map(([plotName, plotJson]) => {
                  const divRef = useRef<HTMLDivElement>(null);
                  useEffect(() => {
                    if (divRef.current) {
                      try {
                        const plotData = JSON.parse(plotJson);
                        Plotly.newPlot(divRef.current!, plotData.data, plotData.layout, { responsive: true, displayModeBar: true });
                      } catch (e) {
                        console.error(`Failed to render ${plotName}:`, e);
                      }
                    }
                  }, [plotJson]);

                  return (
                    <div key={plotName} className="card">
                      <div className="panel-header">
                        <h3 className="panel-title capitalize">{plotName.replace(/_/g, ' ')}</h3>
                      </div>
                      <div className="p-4 h-[500px]">
                        <div ref={divRef} className="plotly-chart" />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* 3D View Tab */}
        {activeTab === '3d' && (
          <div className="h-[calc(100%-50px)] flex items-center justify-center">
            <div className="text-center p-8 text-textSecondary">
              <svg className="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <p className="text-lg font-medium text-textPrimary mb-1">3D Geomodel View</p>
              <p className="text-sm max-w-xs">ResInsight integration coming in Phase 2</p>
              <div className="mt-4 p-4 rounded bg-surface border border-border inline-block">
                <div className="w-96 h-64 flex items-center justify-center bg-base border border-border rounded">
                  <span className="text-textMuted">3D Viewer Placeholder</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}