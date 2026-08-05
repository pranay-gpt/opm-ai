import { useState, useCallback } from 'react';
import { useCurrentDeck, useCurrentDeckPath, useLastBuildResponse, useLastLintResult, useDeckActions, useLintActions, useResolvedTheme, useBuilderDescription, useBuilderShowEditor, useBuilderUseLlmExtraction, useBuilderFluidProps, useBuilderUseCustomFluid, useBuilderShowFluidSection, useBuilderActions, useRockBasicsOverrides, useResolvedRockBasics, useRockBasicsProvenance, useShowRockBasicsSection, type ResolvedRockBasics } from '../stores/useAppStore';
import { api } from '../api/client';
import type { BuildRequest, BuildResponse, FluidDescriptorRequest } from '../api/client';
import RockBasicsSection from './RockBasicsSection';
import Editor from '@monaco-editor/react';

export default function DeckBuilder() {
  const currentDeck = useCurrentDeck();
  const currentDeckPath = useCurrentDeckPath();
  const lastBuildResponse = useLastBuildResponse();
  const lastLintResult = useLastLintResult();
  const { setCurrentDeck, setLastBuildResponse, setLastDeckPath } = useDeckActions();
  const { setLastLintResult } = useLintActions();
  const resolvedTheme = useResolvedTheme();

  // Persisted builder form state - survives route navigation and reload.
  const description = useBuilderDescription();
  const showEditor = useBuilderShowEditor();
  const useLlmExtraction = useBuilderUseLlmExtraction();
  const fluidProps = useBuilderFluidProps();
  const useCustomFluid = useBuilderUseCustomFluid();
  const showFluidSection = useBuilderShowFluidSection();
  const rockBasicsOverrides = useRockBasicsOverrides();
  const resolvedRockBasics = useResolvedRockBasics();
  const rockBasicsProvenance = useRockBasicsProvenance();
  const showRockBasicsSection = useShowRockBasicsSection();
  const {
    setDescription,
    setShowEditor,
    setUseLlmExtraction,
    setUseCustomFluid,
    setFluidProps,
    setShowFluidSection,
    setRockBasicsOverride,
    resetRockBasicsOverrides,
    setResolvedRockBasics,
    setShowRockBasicsSection,
  } = useBuilderActions();

  // Transient: lives only in this component, never persisted.
  const [isBuilding, setIsBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBuild = useCallback(async () => {
    if (!description.trim()) {
      setError('Please enter a description');
      return;
    }

    setIsBuilding(true);
    setError(null);

    try {
      // Stage 3.2: forward any user overrides on the rock-basics fields to
      // the backend. The backend tags the deck's provenance accordingly;
      // we then hydrate the store with the resolved values so the section
      // can show what was actually generated.
      const request: BuildRequest = {
        description,
        fluid: useCustomFluid ? fluidProps : null,
        use_llm: useLlmExtraction,
        porosity: rockBasicsOverrides.porosity,
        top_depth: rockBasicsOverrides.top_depth,
        initial_pressure: rockBasicsOverrides.initial_pressure,
        dz: rockBasicsOverrides.dz,
        permx: rockBasicsOverrides.permx,
        permy: rockBasicsOverrides.permy,
        permz: rockBasicsOverrides.permz,
      };
      const response: BuildResponse = await api.build(request);

      setCurrentDeck(response.deck);
      setLastBuildResponse(response);
      setLastLintResult(response.lint);

      // Hydrate the rock-basics store with whatever the backend resolved.
      // Type guard: the resolver dict from the backend matches the
      // ResolvedRockBasics shape by construction; cast is safe here.
      if (response.resolved && response.provenance) {
        setResolvedRockBasics(
          response.resolved as unknown as ResolvedRockBasics,
          response.provenance,
        );
      }

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
  }, [
    description, useCustomFluid, fluidProps, useLlmExtraction,
    rockBasicsOverrides, setCurrentDeck, setLastBuildResponse,
    setLastLintResult, setResolvedRockBasics, setShowEditor,
  ]);

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

  // Helper to safely parse numeric strings - returns fallback if NaN or non-finite
  // Uses Number.isFinite to correctly handle valid 0 values
  const num = (v: string, fallback: number) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : fallback;
  };

  const handleFluidChange = useCallback((field: keyof FluidDescriptorRequest, value: string | number | [number, number]) => {
    setFluidProps((prev: FluidDescriptorRequest) => {
      if (field === 'pressure_range_psi' && Array.isArray(value)) {
        return { ...prev, [field]: value };
      }
      // correlation is a string-enum field; pass through untouched so
      // the user picks one of the three valid options rather than letting
      // the numeric coercion path turn it into NaN.
      if (field === 'correlation') {
        return { ...prev, correlation: value as FluidDescriptorRequest['correlation'] };
      }
      return { ...prev, [field]: typeof value === 'string' ? num(value, 0) : value };
    });
  }, []);

  return (
    <div className="flex flex-col h-full bg-page">
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

            {/* LLM Extraction Checkbox */}
            <div className="card p-4">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useLlmExtraction}
                  onChange={(e) => setUseLlmExtraction(e.target.checked)}
                  className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                />
                <span className="text-sm font-medium text-textPrimary">Use LLM extraction</span>
              </label>
              <p className="text-xs text-textMuted mt-1 ml-7">
                When enabled, uses the LLM to extract structured parameters from the description (requires configured API key).
              </p>
            </div>

            {/* Fluid Properties Section (Collapsible) */}
            <div className="card">
              <button
                onClick={() => setShowFluidSection(!showFluidSection)}
                className="w-full flex items-center justify-between p-4 text-left"
              >
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-textSecondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="font-medium text-textPrimary">Fluid properties (optional)</span>
                </div>
                <svg className={`w-4 h-4 text-textSecondary transition-transform ${showFluidSection ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showFluidSection && (
                <div className="px-4 pb-4 space-y-4 border-t border-border">
                  <label className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={useCustomFluid}
                      onChange={(e) => setUseCustomFluid(e.target.checked)}
                      className="w-4 h-4 rounded border-border text-primary focus:ring-primary"
                    />
                    <span className="text-sm font-medium text-textPrimary">Use custom fluid</span>
                  </label>

                  {useCustomFluid && (
                    <>
                      <p className="text-xs text-textMuted italic ml-7">
                        Tables generated via {fluidProps.correlation ?? 'Standing'} correlation family
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 ml-7">
                        <div>
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            API Gravity
                          </label>
                          <input
                            type="number"
                            step="0.1"
                            value={fluidProps.api_gravity}
                            onChange={(e) => handleFluidChange('api_gravity', e.target.value)}
                            className="input w-full text-sm"
                            min="1"
                            max="100"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            Gas Specific Gravity
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            value={fluidProps.gas_specific_gravity}
                            onChange={(e) => handleFluidChange('gas_specific_gravity', e.target.value)}
                            className="input w-full text-sm"
                            min="0.1"
                            max="2.0"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            GOR (scf/stb)
                          </label>
                          <input
                            type="number"
                            step="1"
                            value={fluidProps.gor}
                            onChange={(e) => handleFluidChange('gor', e.target.value)}
                            className="input w-full text-sm"
                            min="0"
                            max="10000"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            Reservoir Temp (°F)
                          </label>
                          <input
                            type="number"
                            step="1"
                            value={fluidProps.reservoir_temp_f}
                            onChange={(e) => handleFluidChange('reservoir_temp_f', e.target.value)}
                            className="input w-full text-sm"
                            min="-100"
                            max="500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            Salinity (ppm)
                          </label>
                          <input
                            type="number"
                            step="1"
                            value={fluidProps.salinity_ppm}
                            onChange={(e) => handleFluidChange('salinity_ppm', e.target.value)}
                            className="input w-full text-sm"
                            min="0"
                            max="500000"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            Correlation
                          </label>
                          <select
                            value={fluidProps.correlation ?? 'Standing'}
                            onChange={(e) => handleFluidChange('correlation', e.target.value)}
                            className="input w-full text-sm"
                          >
                            <option value="Standing">Standing (default)</option>
                            <option value="VasquezBeggs">Vasquez-Beggs</option>
                            <option value="AlMarhoun">Al-Marhoun</option>
                          </select>
                        </div>
                        <div className="sm:col-span-2">
                          <label className="block text-xs font-medium text-textSecondary mb-1">
                            Pressure Range (psia)
                          </label>
                          <div className="flex gap-3">
                            <input
                              type="number"
                              step="0.1"
                              value={fluidProps.pressure_range_psi[0]}
                              onChange={(e) => handleFluidChange('pressure_range_psi', [num(e.target.value, 14.7), fluidProps.pressure_range_psi[1]])}
                              className="input w-full text-sm"
                              min="0"
                              placeholder="Min"
                            />
                            <input
                              type="number"
                              step="0.1"
                              value={fluidProps.pressure_range_psi[1]}
                              onChange={(e) => handleFluidChange('pressure_range_psi', [fluidProps.pressure_range_psi[0], num(e.target.value, 5000)])}
                              className="input w-full text-sm"
                              min="0"
                              placeholder="Max"
                            />
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Rock Basics Section (Stage 3.2). Collapsed by default; the
                user can expand it to confirm/edit porosity, top depth,
                initial pressure, and per-layer permeability before the
                build runs. Provenance badges on each field show whether
                the value was extracted from the description, defaulted
                by the parser, or replaced by the user. */}
            <RockBasicsSection
              overrides={rockBasicsOverrides}
              resolved={resolvedRockBasics}
              provenance={rockBasicsProvenance}
              isOpen={showRockBasicsSection}
              onToggle={() => setShowRockBasicsSection(!showRockBasicsSection)}
              onChange={setRockBasicsOverride}
              onReset={resetRockBasicsOverrides}
            />

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
                    {lastBuildResponse.lint.passed ? '[OK]' : '[FAIL]'}
                  </span>
                  <span className="font-medium">
                    {lastBuildResponse.lint.passed ? 'Lint Passed' : 'Lint Issues Found'}
                  </span>
                </div>
                {lastBuildResponse.lint.lint_summary && (
                  <div className="mt-2 pt-2 border-t border-border/40 text-xs text-textSecondary whitespace-pre-wrap">
                    {lastBuildResponse.lint.lint_summary}
                  </div>
                )}
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
                theme={resolvedTheme === 'light' ? 'light' : 'vs-dark'}
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
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
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