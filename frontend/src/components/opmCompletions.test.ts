/**
 * Self-check for the Monaco completion provider (`opmCompletions.ts`).
 * No test framework is installed, so this is a plain assert script
 * following the same convention as
 * viewer3d/meshFormat.test.ts and deckSections.test.ts.
 *
 * Run via `npm test` (the script bundles both test files via esbuild
 * and executes them in sequence).
 */

import {
  registerOpmCompletions,
  sectionLabel,
  documentationFor,
  COMPLETION_ITEM_KIND_KEYWORD,
  type OpmKeywordEntry,
} from './opmCompletions';

declare const require: (id: string) => unknown;
const assert = require('node:assert/strict') as {
  equal(a: unknown, b: unknown, m?: string): void;
  ok(v: unknown, m?: string): void;
  throws(fn: () => unknown, m?: string): void;
};

// ---------------------------------------------------------------------------
// Mock monaco + model
// ---------------------------------------------------------------------------

function makeMockMonaco() {
  let provider: unknown = null;
  const m = {
    languages: {
      registerCompletionItemProvider: (_lang: string, p: unknown) => {
        if (_lang === 'opm') provider = p;
        return { dispose: () => { provider = null; } };
      },
    },
    get provider() { return provider; },
  };
  return m;
}

function fakeModel(line: string, column: number) {
  return {
    getWordUntilPosition: () => ({ startColumn: 1, endColumn: column, word: line }),
  };
}

const SAMPLE: OpmKeywordEntry[] = [
  {
    name: 'WELSPECS',
    sections: ['SCHEDULE'],
    parameter_count: 18,
    description: 'The keyword introduces a new well, defining its name.',
    deck_count: 601,
  },
  {
    name: 'DUALPORO',
    sections: ['RUNSPEC'],
    parameter_count: 0,
    description: 'This requests that the dual porosity option is used in the run.',
    deck_count: 0,
  },
  {
    name: 'NOECHO',
    sections: ['RUNSPEC', 'GRID', 'EDIT', 'PROPS', 'REGIONS', 'SOLUTION', 'SUMMARY', 'SCHEDULE'],
    parameter_count: 0,
    description: 'The keyword causes the echo of the data input that is produced.',
    deck_count: 522,
  },
];

// ---------------------------------------------------------------------------
// sectionLabel
// ---------------------------------------------------------------------------

assert.equal(sectionLabel(SAMPLE[0]), 'SCHEDULE · 18 args', 'SCHEDULE · 18 args');
assert.equal(sectionLabel({
  name: 'DIMENS', sections: ['RUNSPEC'], parameter_count: 1, description: '', deck_count: 0,
}), 'RUNSPEC · 1 arg', 'singular arg form');
assert.equal(sectionLabel(SAMPLE[1]), 'RUNSPEC · 0 args', 'zero args');
assert.equal(sectionLabel({
  name: 'OBS_ONLY', sections: [], parameter_count: 0, description: '', deck_count: 7,
}), '7 decks observed', 'deck_count fallback');
assert.equal(sectionLabel({
  name: 'EMPTY', sections: [], parameter_count: 0, description: '', deck_count: 0,
}), 'Keyword', 'final fallback');

// ---------------------------------------------------------------------------
// registerOpmCompletions
// ---------------------------------------------------------------------------

function test_register_provider_for_opm_language(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  assert.ok(m.provider, 'completion provider not registered for opm');
}

function test_provideCompletionItems_returns_one_per_keyword(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  const result = (m.provider as any).provideCompletionItems(
    fakeModel('WEL', 5),
    { lineNumber: 1, column: 5 },
  );
  assert.equal(result.suggestions.length, 3, 'one suggestion per catalogue entry');
  const labels = result.suggestions.map((s: { label: string }) => s.label);
  for (const expected of ['WELSPECS', 'DUALPORO', 'NOECHO']) {
    assert.ok(labels.includes(expected), `missing keyword ${expected}`);
  }
}

function test_suggestion_label_uses_section_label_with_param_count(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  const result = (m.provider as any).provideCompletionItems(fakeModel('', 1), { lineNumber: 1, column: 1 });
  const welspecs = result.suggestions.find((s: { label: string }) => s.label === 'WELSPECS');
  assert.ok(welspecs, 'WELSPECS suggestion missing');
  assert.equal(welspecs.detail, 'SCHEDULE · 18 args');
}

function test_kind_is_keyword_constant(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  const result = (m.provider as any).provideCompletionItems(fakeModel('', 1), { lineNumber: 1, column: 1 });
  assert.equal(result.suggestions[0].kind, COMPLETION_ITEM_KIND_KEYWORD);
}

function test_documentation_carries_description(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  const result = (m.provider as any).provideCompletionItems(fakeModel('', 1), { lineNumber: 1, column: 1 });
  const welspecs = result.suggestions.find((s: { label: string }) => s.label === 'WELSPECS');
  assert.ok(welspecs, 'WELSPECS suggestion missing');
  assert.ok(
    (welspecs.documentation ?? '').includes('introduces a new well'),
    `expected description in documentation, got: ${welspecs.documentation}`,
  );
}

function test_empty_catalogue_registers_but_yields_nothing(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, []);
  const result = (m.provider as any).provideCompletionItems(fakeModel('', 1), { lineNumber: 1, column: 1 });
  assert.equal(result.suggestions.length, 0, 'expected 0 suggestions for empty catalogue');
}

function test_suggestion_range_covers_word_under_cursor(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  const result = (m.provider as any).provideCompletionItems(
    fakeModel('WEL', 5),
    { lineNumber: 7, column: 5 },
  );
  const welspecs = result.suggestions.find((s: { label: string }) => s.label === 'WELSPECS');
  assert.ok(welspecs, 'WELSPECS suggestion missing');
  assert.equal(welspecs.range.startLineNumber, 7);
  assert.equal(welspecs.range.startColumn, 1);
}

function test_dispose_clears_provider(): void {
  const m = makeMockMonaco();
  const disposable = registerOpmCompletions(m, SAMPLE);
  disposable.dispose();
  assert.equal(m.provider, null, 'provider should be cleared after dispose');
}

function test_trigger_characters_cover_keywords(): void {
  const m = makeMockMonaco();
  registerOpmCompletions(m, SAMPLE);
  const p = m.provider as { triggerCharacters: string };
  // Every uppercase letter A-Z must be a trigger so completion fires
  // mid-word on partial keyword entry.
  for (let ch = 65; ch <= 90; ch++) {
    assert.ok(p.triggerCharacters.includes(String.fromCharCode(ch)), `missing trigger ${String.fromCharCode(ch)}`);
  }
  assert.ok(p.triggerCharacters.includes('_'), 'underscore trigger');
  assert.ok(p.triggerCharacters.includes('0'), 'digit trigger');
}

function test_documentation_includes_parameter_names_when_present(): void {
  // A fake catalogue with parameters; documentationFor should list
  // each parameter name (with brief when non-empty, plain name when
  // the brief is blank).
  const catalogue: OpmKeywordEntry[] = [
    {
      name: 'WELSPECS',
      sections: ['SCHEDULE'],
      parameter_count: 2,
      description: 'should not appear, parameters take priority',
      deck_count: 0,
      parameters: [
        { name: 'Foo', brief: 'A foo' },
        { name: 'Bar', brief: '' },
      ],
    },
  ];
  const m = makeMockMonaco();
  registerOpmCompletions(m, catalogue);
  const result = (m.provider as any).provideCompletionItems(fakeModel('', 1), { lineNumber: 1, column: 1 });
  const welspecs = result.suggestions.find((s: { label: string }) => s.label === 'WELSPECS');
  assert.ok(welspecs, 'WELSPECS suggestion missing');
  const docs = welspecs.documentation ?? '';
  assert.ok(docs.includes('Foo'), `documentation should contain parameter name 'Foo', got: ${docs}`);
  assert.ok(docs.includes('Bar'), `documentation should contain parameter name 'Bar', got: ${docs}`);
  // Sanity-check the formatting helper directly as well.
  const fromHelper = documentationFor(catalogue[0]);
  assert.equal(fromHelper, 'Foo — A foo\nBar', 'parameter lines formatted as "name — brief"');
}

function test_documentation_falls_back_to_description_when_no_parameters(): void {
  // No parameters array at all -> fall back to description exactly.
  const catalogue: OpmKeywordEntry[] = [
    {
      name: 'WELSPECS',
      sections: ['SCHEDULE'],
      parameter_count: 0,
      description: 'fallback description',
      deck_count: 0,
      parameters: [],
    },
  ];
  const m = makeMockMonaco();
  registerOpmCompletions(m, catalogue);
  const result = (m.provider as any).provideCompletionItems(fakeModel('', 1), { lineNumber: 1, column: 1 });
  const welspecs = result.suggestions.find((s: { label: string }) => s.label === 'WELSPECS');
  assert.ok(welspecs, 'WELSPECS suggestion missing');
  assert.equal(welspecs.documentation, 'fallback description', 'documentation must equal description when parameters is empty');
}

// Run all
test_register_provider_for_opm_language();
test_provideCompletionItems_returns_one_per_keyword();
test_suggestion_label_uses_section_label_with_param_count();
test_kind_is_keyword_constant();
test_documentation_carries_description();
test_empty_catalogue_registers_but_yields_nothing();
test_suggestion_range_covers_word_under_cursor();
test_dispose_clears_provider();
test_trigger_characters_cover_keywords();
test_documentation_includes_parameter_names_when_present();
test_documentation_falls_back_to_description_when_no_parameters();

console.log('  ok  registerOpmCompletions dispatched all 11 checks');
console.log('  all opmCompletions checks passed');