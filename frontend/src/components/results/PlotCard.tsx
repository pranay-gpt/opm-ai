import { useState, useEffect, useRef } from 'react';
import { useResolvedTheme } from '../../stores/useAppStore';
// @ts-expect-error plotly.js-dist ships no types; @types/plotly.js covers the API
import Plotly from 'plotly.js-dist-min';

interface PlotCardProps {
  jobId: string;
  plotName: string;
  plotJson: string;
}

export default function PlotCard({ jobId, plotName, plotJson }: PlotCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const resolvedTheme = useResolvedTheme();
  const [renderError, setRenderError] = useState<string | null>(null);
  const chartMountedRef = useRef(false);

  useEffect(() => {
    setRenderError(null);
    chartMountedRef.current = false;
    if (!divRef.current || !plotJson) return;
    try {
      const plotData = JSON.parse(plotJson);
      const dark = resolvedTheme === 'dark';
      const layout = {
        ...plotData.layout,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: dark ? '#1f2937' : '#ffffff',
        font: { color: dark ? '#e5e7eb' : '#111827' },
      };
      Plotly.newPlot(divRef.current, plotData.data, layout, { responsive: true });
      chartMountedRef.current = true;
    } catch (e) {
      setRenderError(e instanceof Error ? e.message : String(e));
    }
    return () => {
      if (chartMountedRef.current && divRef.current) {
        Plotly.purge(divRef.current);
        chartMountedRef.current = false;
      }
    };
  }, [plotJson, resolvedTheme]);

  return (
    <div className="border rounded-lg p-3 bg-white dark:bg-gray-800" data-testid={`plot-card-${plotName}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{plotName}</h3>
        <details className="text-xs">
          <summary className="cursor-pointer text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">
            Export
          </summary>
          <div className="absolute z-10 mt-1 bg-white dark:bg-gray-800 border rounded shadow-lg p-2 right-0">
            <div className="text-xs text-gray-500">Wiring lands in Task 10</div>
          </div>
        </details>
      </div>
      {!plotJson ? (
        <div className="text-xs text-gray-500 italic p-4 text-center">No data available</div>
      ) : (
        <>
          <div ref={divRef} className="w-full" style={{ minHeight: '400px' }} />
          {renderError && (
            <div className="text-xs text-red-500 mt-2">Render error: {renderError}</div>
          )}
        </>
      )}
    </div>
  );
}