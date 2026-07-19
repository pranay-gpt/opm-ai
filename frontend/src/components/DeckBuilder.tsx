import { useState, useCallback } from 'react';
import { useCurrentDeck, useCurrentDeckPath, useLastBuildResponse, useLastLintResult, useDeckActions, useLintActions } from '../stores/useAppStore';
import { api } from '../api/client';
import type { BuildRequest, BuildResponse } from '../api/client';
import Editor from '@monaco-editor/react';

export default function DeckBuilder() {
  const currentDeck = useCurrentDeck();
  const currentDeckPath = useCurrentDeckPath();
  const lastBuildResponse = useLastBuildResponse();
  const lastLintResult = useLastLintResult();
  const { setCurrentDeck, setLastBuildResponse, setLastDeckPath } = useDeckActions();
  const { setLastLintResult } = useLintActions();

  const [description, setDescription] = useState('10x10x3 grid with one producer at 5,5, depletion drive, 3000m depth, 200 bar initial pressure');
  const [isBuilding, setIsBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEditor, setShowEditor] = useState(false);

  const handleBuild = useCallback(async () => {
    if (!description.trim()) {
      setError('Please enter a description');
      return;
    }

    setIsBuilding(true);
    setError(null);

    try {
      const request: BuildRequest = { description };
      const response: BuildResponse = await api.build(request);

      setCurrentDeck(response.deck);
      setLastBuildResponse(response);
      setLastLintResult(response.lint);

      if (!response.lint.passed) {
        setError(`Build succeeded but lint found issues: ${response.lint.errors.join('; ')}`);
      } else {
        setShowEditor(true);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Build failed';
      setError(message);
      console.error('Build error:', err);
    } finally {
      setIsBuilding(false);
    }
  }, [description, setCurrentDeck, setLastBuildResponse, setLastLintResult]);

  const handleUseDeck = useCallback(() => {
    if (lastBuildResponse?.deck) {
      setCurrentDeck(lastBuildResponse.deck);
      setShowEditor(true);
    }
  }, [lastBuildResponse, setCurrentDeck]);

  const handleCopyDeck = useCallback(() => {
    if (currentDeck) {
      navigator.clipboard.writeText(currentDeck);
    }
  }, [currentDeck]);

  const handleSaveDeck = useCallback(async () => {
    if (!currentDeck) return;
    const blob = new Blob([currentDeck], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deck_${Date.now()}.DATA`;
    a.click();
    URL.revokeObjectURL(url);
  }, [currentDeck]);

  return (
    <div className="flex flex-col h-full bg-base">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-semibold text-textPrimary">Deck Builder</h1>
          <p className="text-sm text-textSecondary">
            Describe your reservoir model in plain English
          </p>
        </div>
        <div className="flex items-center gap-2">
          {showEditor && currentDeck && (
            <>
              <button onClick={handleCopyDeck} className="btn-secondary btn-sm" title="Copy deck to clipboard">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2" />
                </svg>
                Copy
              </button>
              <button onClick={handleSaveDeck} className="btn-secondary btn-sm" title="Save deck as file">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Save
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Description & Build */}
        <div className="w-full lg:w-1/2 border-r border-border p-4 lg:p-6 overflow-y-auto">
          <div className="space-y-4 max-w-xl mx-auto">
            <div className="card p-4">
              <label className="block text-sm font-medium text-textPrimary mb-2">
                Model Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={8}
                placeholder="e.g., 10x10x3 grid with one producer at 5,5, depletion drive, 3000m depth, 200 bar initial pressure..."
                className="input w-full font-mono text-sm resize-none"
              />
              <p className="text-xs text-textMuted mt-2">
                Try: "20x20x5 waterflood with 4 injectors and 1 producer" or "depletion deck with 3 layers and gas cap"
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleBuild}
                disabled={isBuilding || !description.trim()}
                className="btn-primary flex-1 py-3 text-base"
              >
                {isBuilding ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Building...
                  </span>
                ) : (
                  'Build Deck'
                )}
              </button>
              {lastBuildResponse && !showEditor && (
                <button onClick={handleUseDeck} className="btn-secondary px-6">
                  Use Last Deck
                </button>
              )}
            </div>

            {error && (
              <div className="p-3 rounded bg-error/20 border border-error text-error text-sm">
                {error}
              </div>
            )}

            {lastBuildResponse?.lint && (
              <div className={`p-3 rounded border ${
                lastBuildResponse.lint.passed
                  ? 'bg-success/20 border-success'
                  : 'bg-error/20 border-error'
              }`}>
                <div className="flex items-center gap-2 text-sm">
                  <span className={lastBuildResponse.lint.passed ? 'text-success' : 'text-error'}>
                    {lastBuildResponse.lint.passed ? '✓' : '✗'}
                  </span>
                  <span className="font-medium">
                    {lastBuildResponse.lint.passed ? 'Lint Passed' : 'Lint Issues Found'}
                  </span>
                </div>
                {!lastBuildResponse.lint.passed && lastBuildResponse.lint.errors.length > 0 && (
                  <ul className="mt-2 ml-4 space-y-1 text-xs text-textSecondary">
                    {lastBuildResponse.lint.errors.slice(0, 5).map((err, i) => (
                      <li key={i}>• {err}</li>
                    ))}
                    {lastBuildResponse.lint.errors.length > 5 && (
                      <li>• ... and {lastBuildResponse.lint.errors.length - 5} more</li>
                    )}
                  </ul>
                )}
              </div>
            )}

            {/* Template Quick-start */}
            <div className="card p-4">
              <h3 className="font-medium text-textPrimary mb-3">Quick Templates</h3>
              <div className="flex flex-wrap gap-2">
                {[
                  { label: 'Depletion', desc: '10x10x3, 1 producer' },
                  { label: 'Waterflood', desc: '20x20x5, 4 inj + 1 prod' },
                  { label: 'Gas Cap', desc: '15x15x4, gas cap drive' },
                  { label: 'Multi-layer', desc: '10x10x10, 3 rock types' },
                ].map((tmpl) => (
                  <button
                    key={tmpl.label}
                    onClick={() => setDescription(`${tmpl.desc}, standard PVT and relperm`)}
                    className="px-3 py-1.5 text-xs rounded border border-border text-textSecondary hover:text-textPrimary hover:border-primary/50 hover:bg-surfaceHover transition-colors"
                  >
                    {tmpl.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Panel - Generated Deck Preview */}
        {showEditor && currentDeck && (
          <div className="w-full lg:w-1/2 flex flex-col border-l border-border bg-surface">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="font-semibold text-textPrimary">Generated Deck</h2>
              <div className="flex items-center gap-2">
                <span className="badge badge-primary text-xs">Read-only</span>
                <button
                  onClick={() => setShowEditor(false)}
                  className="p-1.5 rounded hover:bg-surfaceHover text-textSecondary hover:text-textPrimary"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-hidden p-2">
              <Editor
                height="100%"
                language="opm"
                value={currentDeck}
                theme="vs-dark"
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  lineNumbers: 'on',
                  fontSize: 12,
                  fontFamily: '"JetBrains Mono", monospace',
                  tabSize: 2,
                  wordWrap: 'on',
                }}
              />
            </div>
          </div>
        )}

        {/* Empty state when no deck built */}
        {!showEditor && (
          <div className="w-full lg:w-1/2 flex items-center justify-center bg-surface border-l border-border">
            <div className="text-center p-8 text-textSecondary">
              <svg className="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              <p className="text-lg font-medium text-textPrimary mb-1">No Deck Generated</p>
              <p className="text-sm max-w-xs">
                Enter a description and click "Build Deck" to generate an OPM Flow input file.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}