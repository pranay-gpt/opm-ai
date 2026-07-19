import { useState, useCallback } from 'react';
import { useLintActions, useLastLintResult } from '../stores/useAppStore';
import { api } from '../api/client';
import type { LintResult, LintIssue } from '../api/client';
import Editor from '@monaco-editor/react';

export default function LinterPanel() {
  const { setLastLintResult } = useLintActions();
  const lastLintResult = useLastLintResult();

  const [deckText, setDeckText] = useState('');
  const [isLinting, setIsLinting] = useState(false);
  const [lintResult, setLintResult] = useState<LintResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleLint = useCallback(async () => {
    if (!deckText.trim()) {
      setError('Please enter a deck to lint');
      return;
    }

    setIsLinting(true);
    setError(null);

    try {
      // Write to temp file and call backend lint endpoint
      // For now, do client-side linting as fallback
      const requiredSections = ['RUNSPEC', 'GRID', 'PROPS', 'SOLUTION', 'SCHEDULE'];
      const errors: string[] = [];

      requiredSections.forEach((section) => {
        if (!new RegExp(`^\\s*${section}\\b`, 'm').test(deckText)) {
          errors.push(`Missing required section: ${section}`);
        }
      });

      if (!/DIMENS\s+.*\/\s*$/m.test(deckText)) {
        errors.push('DIMENS keyword not found or malformed in RUNSPEC');
      }

      // Check for common issues
      if (/PERMX.*\/\s*$/m.test(deckText) && !/PORO.*\/\s*$/m.test(deckText)) {
        errors.push('PERMX defined but PORO missing');
      }

      const issues: LintIssue[] = errors.map((err, i) => ({
        severity: 'ERROR' as const,
        section: null,
        keyword: null,
        line: null,
        message: err,
        rule_id: `client-lint-${i}`,
      }));

      const result: LintResult = {
        deck_path: 'memory://deck.DATA',
        issues,
        lint_summary: errors.length === 0 ? 'All checks passed' : `${errors.length} issue(s) found`,
        errors,
        passed: errors.length === 0,
      };

      setLintResult(result);
      setLastLintResult(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Lint failed';
      setError(message);
      console.error('Lint error:', err);
    } finally {
      setIsLinting(false);
    }
  }, [deckText, setLastLintResult]);

  const handlePaste = useCallback(() => {
    navigator.clipboard.readText().then((text) => {
      setDeckText(text);
    }).catch(() => {
      setError('Failed to read clipboard');
    });
  }, []);

  const handleClear = useCallback(() => {
    setDeckText('');
    setLintResult(null);
    setError(null);
  }, []);

  const handleLoadExample = useCallback(() => {
    const example = `-- OPM Flow Example Deck
RUNSPEC
  TITLE
    Example Deck for Linting
  /
  DIMENS
    10 10 3 /
  OIL
  WATER
  METRIC
  EQUIL
/

GRID
  SPECGRID
  DX
    300*100 /
  DY
    300*100 /
  DZ
    10*10 10*15 10*20 /
  TOPS
    300*3000 /
  PORO
    300*0.2 /
  PERMX
    300*100 /
  PERMY
    300*100 /
  PERMZ
    300*10 /
/

PROPS
  ROCK
    3000  1.0e-5 /
  PVTO
    100  1.0  1.0  0.5  0.001 /
    200  1.1  1.2  0.4  0.0008 /
    300  1.2  1.5  0.3  0.0006 /
  PVTW
    100  1.0  0.0003  1.0 /
  PVTG
    100  0.001  0.0001  1.5 /
    200  0.002  0.0002  1.2 /
  SWOF
    0.2  0.0  1.0  0.0 /
    0.3  0.1  0.8  0.2 /
    0.5  0.5  0.3  0.5 /
    0.8  1.0  0.0  1.0 /
  SGOF
    0.0  0.0  1.0 /
    0.2  0.3  0.5 /
    0.5  1.0  0.0 /
/

SOLUTION
  EQUIL
  OWC
    3100 /
  PRESSURE
    3100  300 /
  RSVD
    100 /
  RVVD
    0 /
/

SCHEDULE
  RPTRST
    BASIC=5 FREQ=1 /
  WELSPECS
    'PROD1'  'PROD'  5  5  3000  0.1  1*  1*  1*  'GAS' /
  COMPDAT
    'PROD1'  1  3  1  3  'OPEN'  1*  1*  1*  1*  1*  1* /
  WCONPROD
    'PROD1'  'OPEN'  'BHP'  150  1*  1*  1* /
  TSTEP
    10*10  20*30  10*100  10*365 /
/
`;
    setDeckText(example);
  }, []);

  // Use lintResult after null check
  const hasResult = lintResult !== null;
  const isPassed = lintResult?.passed ?? false;
  const errorCount = lintResult?.issues.length ?? 0;
  const issueList = lintResult?.issues ?? [];

  return (
    <div className="flex flex-col h-full bg-base">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface">
        <div>
          <h1 className="text-xl font-semibold text-textPrimary">Data Linter</h1>
          <p className="text-sm text-textSecondary">Validate OPM Flow decks for syntax and consistency</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handlePaste} className="btn-secondary btn-sm" disabled={isLinting}>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2" />
            </svg>
            Paste
          </button>
          <button onClick={handleLoadExample} className="btn-secondary btn-sm" disabled={isLinting}>
            Load Example
          </button>
          <button onClick={handleClear} className="btn-secondary btn-sm" disabled={isLinting}>
            Clear
          </button>
          <button onClick={handleLint} disabled={isLinting || !deckText.trim()} className="btn-primary btn-sm">
            {isLinting ? 'Linting...' : 'Lint Deck'}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor Panel */}
        <div className="w-full lg:w-1/2 border-r border-border flex flex-col">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
            <span className="text-sm font-medium text-textPrimary">Deck Editor</span>
            <span className="text-xs text-textSecondary">{deckText.split('\n').length} lines</span>
          </div>
          <div className="flex-1 overflow-hidden p-2">
            <Editor
              height="100%"
              language="opm"
              value={deckText}
              onChange={(value) => value !== undefined && setDeckText(value)}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                lineNumbers: 'on',
                fontSize: 12,
                fontFamily: '"JetBrains Mono", monospace',
                tabSize: 2,
                wordWrap: 'on',
                automaticLayout: true,
              }}
            />
          </div>
        </div>

        {/* Results Panel */}
        <div className="w-full lg:w-1/2 flex flex-col bg-surface">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border">
            <span className="text-sm font-medium text-textPrimary">Lint Results</span>
            {hasResult && (
              <span className={`badge ${isPassed ? 'badge-success' : 'badge-error'}`}>
                {isPassed ? 'Passed' : `${errorCount} Error(s)`}
              </span>
            )}
          </div>

          {error && (
            <div className="m-4 p-3 rounded bg-error/20 border border-error text-error text-sm">
              {error}
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-4">
            {!hasResult && !isLinting ? (
              <div className="flex flex-col items-center justify-center h-full text-textSecondary">
                <svg className="w-16 h-16 mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                <p className="text-lg font-medium text-textPrimary mb-1">No Lint Results</p>
                <p className="text-sm max-w-xs text-center">Enter a deck and click "Lint Deck" to validate</p>
              </div>
            ) : isLinting ? (
              <div className="flex flex-col items-center justify-center h-full text-primary">
                <svg className="animate-spin w-12 h-12 mb-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <p>Analyzing deck...</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Summary */}
                <div className={`p-4 rounded border ${isPassed ? 'bg-success/20 border-success' : 'bg-error/20 border-error'}`}>
                  <div className="flex items-center gap-3">
                    <span className={`text-2xl ${isPassed ? 'text-success' : 'text-error'}`}>
                      {isPassed ? '[OK]' : '[FAIL]'}
                    </span>
                    <div>
                      <div className="font-semibold text-textPrimary">
                        {isPassed ? 'Lint Passed' : 'Lint Failed'}
                      </div>
                      <div className="text-sm text-textSecondary">
                        {errorCount} error(s) found in deck
                      </div>
                    </div>
                  </div>
                </div>

                {/* Errors List */}
                {!isPassed && errorCount > 0 && (
                  <div>
                    <h3 className="font-medium text-textPrimary mb-3">Errors</h3>
                    <div className="space-y-2">
                      {issueList.map((issue, i) => (
                        <div key={i} className="p-3 rounded bg-base border border-border">
                          <div className="flex items-start gap-2">
                            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-error/20 text-error flex items-center justify-center text-xs">
                              {i + 1}
                            </span>
                            <div className="flex-1">
                              <p className="text-textPrimary">{issue.message}</p>
                              <p className="text-xs text-textMuted mt-1">
                                Review the highlighted section in the editor
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Quick Fixes */}
                {!isPassed && (
                  <div className="pt-4 border-t border-border">
                    <h3 className="font-medium text-textPrimary mb-3">Quick Fixes</h3>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={handleLoadExample}
                        className="btn-secondary btn-sm"
                      >
                        Load Valid Template
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}