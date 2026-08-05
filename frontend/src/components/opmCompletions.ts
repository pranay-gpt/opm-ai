/**
 * Monaco completion provider registration for the 'opm' language.
 *
 * Kept in its own module so the test suite can import the pure logic
 * without dragging in React / @monaco-editor/react. The provider is
 * invoked once per editor mount by DeckEditor.tsx after the
 * tokenizer is registered; the catalogue comes from
 * GET /api/keywords (fixture + ERM union).
 *
 * The provider returns one completion item per catalogue entry. Each
 * item has:
 *   - label: keyword name
 *   - kind: CompletionItemKind.Keyword (14)
 *   - detail: section list + parameter count (or "Keyword" fallback)
 *   - documentation: short description from the ERM (when available)
 *
 * Trigger characters are uppercase letters, digits, and underscore —
 * covers all ECLIPSE keyword identifiers.
 */

export interface OpmKeywordEntry {
  name: string;
  sections: string[];
  parameter_count: number;
  description: string;
  deck_count: number;
  parameters?: { name: string; brief: string }[];
}

export interface CompletionSuggestion {
  label: string;
  kind: number;
  insertText: string;
  detail?: string;
  documentation?: string;
  range: {
    startLineNumber: number;
    endLineNumber: number;
    startColumn: number;
    endColumn: number;
  };
}

export interface OpmMonacoLike {
  languages: {
    registerCompletionItemProvider(
      lang: string,
      provider: {
        triggerCharacters: string;
        provideCompletionItems: (
          model: ModelLike,
          position: { lineNumber: number; column: number },
        ) => { suggestions: CompletionSuggestion[] };
      },
    ): { dispose: () => void };
  };
}

export interface ModelLike {
  getWordUntilPosition(position: { lineNumber: number; column: number }): {
    startColumn: number;
    endColumn: number;
    word: string;
  };
}

export const COMPLETION_ITEM_KIND_KEYWORD = 14;

/**
 * Compute the detail label for a catalogue entry.
 *
 * Authoritative sections + parameter count when present:
 *   "SCHEDULE · 18 args"  or  "RUNSPEC · 1 arg" (singular)
 * Otherwise fall back to the fixture observation count:
 *   "601 decks observed"
 * Otherwise just:
 *   "Keyword"
 */
export function sectionLabel(entry: OpmKeywordEntry): string {
  if (entry.sections.length > 0) {
    const plural = entry.parameter_count === 1 ? 'arg' : 'args';
    return `${entry.sections.join('/')} · ${entry.parameter_count} ${plural}`;
  }
  if (entry.deck_count > 0) {
    return `${entry.deck_count} decks observed`;
  }
  return 'Keyword';
}

/**
 * Build the `documentation` field for a completion item.
 *
 * Priority:
 *   1. Per-keyword parameters (name — brief, one per line), truncated
 *      to ~600 chars to keep the hover popover responsive.
 *   2. The ERM `description` text.
 *   3. Empty string (caller omits the field).
 */
export function documentationFor(entry: OpmKeywordEntry): string {
  const params = entry.parameters;
  if (params && params.length > 0) {
    const lines = params.map((p) =>
      p.brief ? `${p.name} — ${p.brief}` : p.name,
    );
    const joined = lines.join('\n');
    return joined.length > 600 ? joined.slice(0, 600) : joined;
  }
  return entry.description ?? '';
}

/**
 * Register a Monaco completion provider for the 'opm' language backed by
 * the supplied catalogue. Returns a disposable that removes the provider.
 */
export function registerOpmCompletions(
  m: OpmMonacoLike,
  catalogue: OpmKeywordEntry[],
): { dispose: () => void } {
  const provider = {
    triggerCharacters: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_',
    provideCompletionItems: (
      model: ModelLike,
      position: { lineNumber: number; column: number },
    ): { suggestions: CompletionSuggestion[] } => {
      const word = model.getWordUntilPosition(position);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: word.startColumn,
        endColumn: word.endColumn,
      };
      const suggestions: CompletionSuggestion[] = catalogue.map((entry) => {
        const suggestion: CompletionSuggestion = {
          label: entry.name,
          kind: COMPLETION_ITEM_KIND_KEYWORD,
          insertText: entry.name,
          detail: sectionLabel(entry),
          range,
        };
        const docs = documentationFor(entry);
        if (docs) {
          suggestion.documentation = docs;
        }
        return suggestion;
      });
      return { suggestions };
    },
  };
  return m.languages.registerCompletionItemProvider('opm', provider);
}