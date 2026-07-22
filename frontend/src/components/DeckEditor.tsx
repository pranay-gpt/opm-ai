import { useState, useEffect, useCallback, useRef } from 'react';
import { useCurrentDeck, useCurrentDeckPath, useLastBuildResponse, useLastLintResult, useDeckActions, useLintActions, useResolvedTheme } from '../stores/useAppStore';
import { api } from '../api/client';
import type { LintRequest, LintResult, LintIssue } from '../api/client';
import Editor from '@monaco-editor/react';

// Declare monaco for TypeScript
declare const monaco: any;

const OPM_KEYWORDS = [
  'RUNSPEC', 'TITLE', 'DIMENS', 'OIL', 'WATER', 'GAS', 'DISGAS', 'METRIC', 'FIELD', 'EQUIL',
  'GRID', 'SPECGRID', 'DX', 'DY', 'DZ', 'TOPS', 'PORO', 'PERMX', 'PERMY', 'PERMZ', 'COORD',
  'ZCORN', 'ACTNUM', 'NTG', 'MULTX', 'MULTY', 'MULTZ', 'BOX', 'ENDBOX', 'COPY', 'ENDSPEC',
  'PROPS', 'ROCK', 'PVTO', 'PVTW', 'PVTG', 'SWOF', 'SGOF', 'SLGOF', 'KRW', 'KRO', 'KRG',
  'SOLUTION', 'EQUIL', 'OWC', 'GOC', 'WOC', 'PRESSURE', 'RSVD', 'RVVD', 'SGAS', 'SWAT',
  'SCHEDULE', 'RPTRST', 'WELSPECS', 'COMPDAT', 'COMPLUP', 'WCONPROD', 'WCONINJE', 'WCONHIST',
  'WECON', 'WGRUPCON', 'GCONPROD', 'GCONINJE', 'TSTEP', 'DATES', 'RPTSCHED', 'EXCEL', 'END',
  'OPEN', 'SHUT', 'STOP', 'AUTO', 'BHP', 'THP', 'ORAT', 'WRAT', 'GRAT', 'LRAT', 'RESV',
  'GAS', 'WATER', 'OIL', 'LIQ', 'RES', 'SURF', 'STD', 'FIELD', 'METRIC', 'LAB', 'DAY', 'MONTH', 'YEAR',
];

export default function DeckEditor() {
  const currentDeck = useCurrentDeck();
  const currentDeckPath = useCurrentDeckPath();
  const lastBuildResponse = useLastBuildResponse();
  const lastLintResult = useLastLintResult();
  const { setCurrentDeck, setLastBuildResponse, setLastDeckPath } = useDeckActions();
  const { setLastLintResult } = useLintActions();

  const resolvedTheme = useResolvedTheme();
  const [deck, setDeck] = useState(currentDeck || '');
  const [isDirty, setIsDirty] = useState(false);
  const [isLinting, setIsLinting] = useState(false);
  const [lintErrors, setLintErrors] = useState<{ line: number; message: string }[]>([]);
  const [activeSection, setActiveSection] = useState<string>('RUNSPEC');

  // Sync with store
  useEffect(() => {
    if (currentDeck && currentDeck !== deck) {
      setDeck(currentDeck);
      setIsDirty(false);
    }
  }, [currentDeck]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (value !== undefined) {
      setDeck(value);
      setIsDirty(true);
    }
  }, []);

  const handleLint = useCallback(async () => {
    if (!deck.trim()) return;

    setIsLinting(true);
    try {
      // Save deck to backend temp file first
      const saveResponse = await api.saveDeck({ content: deck, filename: 'DECK.DATA' });
      const deckPath = saveResponse.deck_path;

      // Lint the saved deck
      const result: LintResult = await api.lint({ deck_path: deckPath });

      setLintErrors(
        result.issues
          .filter((i) => i.line !== null)
          .map((i) => ({ line: i.line!, message: i.message }))
      );
      setLastLintResult(result);
    } catch (err) {
      console.error('Lint error:', err);
    } finally {
      setIsLinting(false);
    }
  }, [deck, setLastLintResult]);

  const handleSave = useCallback(() => {
    setCurrentDeck(deck);
    setLastBuildResponse({
      deck,
      lint: lastLintResult || {
        deck_path: 'memory://deck.DATA',
        issues: [],
        lint_summary: 'All checks passed',
        errors: [],
        passed: true,
      },
    });
    setIsDirty(false);
  }, [deck, lastLintResult, setCurrentDeck, setLastBuildResponse]);

  const handleNewDeck = useCallback(() => {
    const template = `-- OPM Flow Deck
RUNSPEC
  TITLE
    New Deck
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
    setDeck(template);
    setCurrentDeck(template);
    setIsDirty(true);
  }, [setCurrentDeck]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(deck);
  }, [deck]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([deck], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deck_${Date.now()}.DATA`;
    a.click();
    URL.revokeObjectURL(url);
  }, [deck]);

  const scrollToSection = useCallback((section: string) => {
    const m = (window as any).monaco;
    if (m && m.editor) {
      // We need access to the editor instance
      // This is a limitation - we can't easily scroll without the editor ref
      // For now, just store the active section
      setActiveSection(section);
    }
  }, []);

  // Register OPM language on mount
  useEffect(() => {
    const m = (window as any).monaco;
    if (m) {
      m.languages.register({ id: 'opm' });
      m.languages.setMonarchTokensProvider('opm', {
        keywords: OPM_KEYWORDS,
        operators: ['/', '*', '+', '-', '=', '<', '>', '<=', '>=', '==', '!=', 'AND', 'OR', 'NOT'],
        tokenizer: {
          root: [
            [/^(\s*)(RUNSPEC|GRID|EDIT|PROPS|REGIONS|SOLUTION|SUMMARY|SCHEDULE)(\s*)$/, ['', 'keyword.section', '']],
            [/^(\s*--)([\s\S]*)$/, 'comment'],
            [/^\s*\/\s*$/, 'keyword.terminator'],
            [/\b(RUNSPEC|GRID|EDIT|PROPS|REGIONS|SOLUTION|SUMMARY|SCHEDULE)\b/, 'keyword.section'],
            [/\b(OIL|WATER|GAS|DISGAS|METRIC|FIELD|EQUIL|DIMENS|SPECGRID|DX|DY|DZ|TOPS|PORO|PERMX|PERMY|PERMZ|COORD|ZCORN|ACTNUM|NTG|MULTX|MULTY|MULTZ|BOX|ENDBOX|COPY|ENDSPEC|ROCK|PVTO|PVTW|PVTG|SWOF|SGOF|SLGOF|KRW|KRO|KRG|EQUIL|OWC|GOC|WOC|PRESSURE|RSVD|RVVD|SGAS|SWAT|RPTRST|WELSPECS|COMPDAT|COMPLUP|WCONPROD|WCONINJE|WCONHIST|WECON|WGRUPCON|GCONPROD|GCONINJE|TSTEP|DATES|RPTSCHED|EXCEL|END|OPEN|SHUT|STOP|AUTO|BHP|THP|ORAT|WRAT|GRAT|LRAT|RESV|GAS|WATER|OIL|LIQ|RES|SURF|STD|FIELD|METRIC|LAB|DAY|MONTH|YEAR)\b/, 'keyword'],
            [/\d+\.?\d*(?:[eE][+-]?\d+)?/, 'number'],
            [/'([^'\\]|\\.)*'/, 'string'],
            [/"/, 'string', '@string'],
            [/[;,]/, 'delimiter'],
            [/\//, 'keyword.terminator'],
          ],
          string: [
            [/[^\\"]+/, 'string'],
            [/\\./, 'string.escape'],
            [/"/, 'string', '@pop'],
          ],
        },
      });

      m.languages.setLanguageConfiguration('opm', {
        comments: { lineComment: '--', blockComment: ['/*', '*/'] },
        brackets: [
          ['{', '}'],
          ['[', ']'],
          ['(', ')'],
        ],
        autoClosingPairs: [
          { open: '{', close: '}' },
          { open: '[', close: ']' },
          { open: '(', close: ')' },
          { open: '"', close: '"' },
          { open: "'", close: "'" },
        ],
        folding: {
          markers: {
            start: /^\s*--\s*#region\b/,
            end: /^\s*--\s*#endregion\b/,
          },
        },
      });

      m.editor.defineTheme('opm-dark', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          { token: 'keyword.section', foreground: '00D9FF', fontStyle: 'bold' },
          { token: 'keyword', foreground: '00D9FF' },
          { token: 'number', foreground: 'DCDCAA' },
          { token: 'string', foreground: 'CE9178' },
          { token: 'comment', foreground: '6A9955' },
          { token: 'delimiter', foreground: 'D4D4D4' },
          { token: 'keyword.terminator', foreground: 'FFB020' },
        ],
        colors: {
          'editor.background': '#081028',
          'editor.foreground': '#F0F6FF',
          'editor.lineHighlightBackground': '#0D1E3C',
          'editorLineNumber.foreground': '#5A6E8C',
          'editorIndentGuide.background': '#1A3A64',
          'editorIndentGuide.activeBackground': '#00D2FF40',
        },
      });

      m.editor.defineTheme('opm-light', {
        base: 'vs',
        inherit: true,
        rules: [
          { token: 'keyword.section', foreground: '0066CC', fontStyle: 'bold' },
          { token: 'keyword', foreground: '0066CC' },
          { token: 'number', foreground: '795E26' },
          { token: 'string', foreground: 'A31515' },
          { token: 'comment', foreground: '008000' },
          { token: 'delimiter', foreground: '333333' },
          { token: 'keyword.terminator', foreground: 'C88200' },
        ],
        colors: {
          'editor.background': '#FFFFFF',
          'editor.foreground': '#0A1432',
          'editor.lineHighlightBackground': '#EAF0FA',
          'editorLineNumber.foreground': '#8296B4',
          'editorIndentGuide.background': '#D2DCEE',
          'editorIndentGuide.activeBackground': '#0066CC40',
        },
      });
    }
  }, []);

  const sections = [
    'RUNSPEC', 'GRID', 'EDIT', 'PROPS', 'REGIONS', 'SOLUTION', 'SUMMARY', 'SCHEDULE',
  ];

  return (
    <div className="flex flex-col h-full bg-page">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface">
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-semibold text-textPrimary">Deck Editor</h1>
          {isDirty && <span className="badge badge-warning text-xs">Unsaved</span>}
          {currentDeckPath && (
            <span className="text-xs text-textMuted font-mono">{currentDeckPath}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleNewDeck} className="btn-secondary btn-sm" title="New Deck (Ctrl+N)">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New
          </button>
          <button onClick={handleSave} disabled={!isDirty} className="btn-primary btn-sm" title="Save (Ctrl+S)">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
            Save
          </button>
          <button onClick={handleCopy} className="btn-secondary btn-sm" title="Copy">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2" />
            </svg>
            Copy
          </button>
          <button onClick={handleDownload} className="btn-secondary btn-sm" title="Download">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
          <button onClick={handleLint} disabled={isLinting} className="btn-secondary btn-sm" title="Lint">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            {isLinting ? 'Linting...' : 'Lint'}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Section Tree Sidebar */}
        <aside className="w-56 border-r border-border bg-surface flex-shrink-0 hidden lg:block">
          <div className="p-3 border-b border-border">
            <h3 className="text-xs font-semibold text-textSecondary uppercase tracking-wider">Sections</h3>
          </div>
          <nav className="flex-1 overflow-y-auto p-2 space-y-1">
            {sections.map((section) => (
              <button
                key={section}
                onClick={() => scrollToSection(section)}
                className={`w-full text-left px-3 py-2 rounded text-sm font-mono transition-colors ${
                  activeSection === section
                    ? 'bg-primary/15 text-primary border-l-2 border-primary'
                    : 'text-textSecondary hover:text-textPrimary hover:bg-surfaceHover'
                }`}
              >
                {section}
              </button>
            ))}
          </nav>
        </aside>

        {/* Editor */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Tabs */}
          <div className="flex items-center px-3 py-1 border-b border-border bg-surface">
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-t-md text-sm font-mono bg-primary/15 text-primary border-b-2 border-primary">
              <span className="w-5 h-5 flex items-center justify-center">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              </span>
              deck.DATA
              {isDirty && <span className="w-1.5 h-1.5 rounded-full bg-warning" />}
            </button>
          </div>

          {/* Editor */}
          <div className="flex-1 overflow-hidden relative">
            <Editor
              height="100%"
              language="opm"
              value={deck}
              theme={resolvedTheme === 'light' ? 'opm-light' : 'opm-dark'}
              options={{
                minimap: { enabled: true },
                lineNumbers: 'on',
                fontSize: 13,
                fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                tabSize: 2,
                wordWrap: 'on',
                automaticLayout: true,
                bracketPairColorization: { enabled: true },
                guides: { bracketPairs: true },
                renderLineHighlight: 'all',
                folding: true,
                showFoldingControls: 'always',
                cursorBlinking: 'smooth',
                cursorSmoothCaretAnimation: 'on',
              }}
              onChange={handleEditorChange}
              onMount={(editor, m) => {
                (window as any).monaco = m;
              }}
            />
          </div>

          {/* Status Bar */}
          <div className="flex items-center justify-between px-3 py-1.5 border-t border-border bg-surface text-xs text-textSecondary">
            <div className="flex items-center gap-4">
              <span>Ln 1, Col 1</span>
              <span>UTF-8</span>
              <span>LF</span>
              <span>OPM</span>
            </div>
            <div className="flex items-center gap-3">
              {lintErrors.length > 0 && (
                <span className="flex items-center gap-1 text-error">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                  {lintErrors.length} error{lintErrors.length !== 1 ? 's' : ''}
                </span>
              )}
              <span className="text-textMuted">{deck.split('\n').length} lines</span>
            </div>
          </div>
        </div>

        {/* Lint Errors Panel */}
        {lintErrors.length > 0 && (
          <aside className="w-80 border-l border-border bg-surface flex-shrink-0 overflow-y-auto">
            <div className="p-3 border-b border-border flex items-center justify-between">
              <h3 className="text-sm font-semibold text-textPrimary">Validation Issues</h3>
              <span className="badge badge-error text-xs">{lintErrors.length}</span>
            </div>
            <div className="p-3 space-y-2 max-h-64 overflow-y-auto">
              {lintErrors.map((error, i) => (
                <div
                  key={i}
                  className="p-2 rounded bg-page border border-border text-xs"
                  onClick={() => scrollToSection(activeSection)}
                >
                  <div className="flex items-center gap-1 text-error mb-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    Line {error.line}
                  </div>
                  <div className="text-textSecondary ml-5">{error.message}</div>
                </div>
              ))}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}