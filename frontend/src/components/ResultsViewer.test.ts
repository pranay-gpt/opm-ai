/**
 * Self-check for the F1.6 audit fix: the Plots tab in ResultsViewer
 * must render the "No Plots Available" placeholder whenever the
 * plots field is missing or empty, instead of silently hiding the
 * whole tab (which left users staring at a blank panel).
 *
 * This is a source-grep regression guard rather than a full render
 * test because the project has no React test framework installed
 * (the sibling .test.ts files in this repo are pure-logic asserts,
 * not DOM-level component tests). The pattern it locks in is:
 *
 *   - The Plots tab is shown iff `results` is set, NOT iff
 *     `results.plots` is set.
 *   - The empty-state placeholder renders for both `plots=undefined`
 *     and `plots={}`.
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/components/ResultsViewer.test.ts \
 *     --outfile=node_modules/.cache/rv.cjs \
 *     && node node_modules/.cache/rv.cjs
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

declare const require: (id: string) => unknown;
const assert = require('node:assert/strict') as typeof import('node:assert/strict');

// Resolve ResultsViewer.tsx relative to the project root. The CJS
// bundle's __dirname is the cache dir, so walk up from process.cwd()
// (the project root when invoked as `node node_modules/.cache/rv.cjs`).
const srcPath = join(process.cwd(), 'src', 'components', 'ResultsViewer.tsx');
const source = readFileSync(srcPath, 'utf8');

// The F1.6 fix renames the guard from `results?.plots &&` (which
// short-circuits the whole tab with no fallback) to a positive
// `results &&` followed by an inner empty-state branch.

// 1. The Plots tab must NOT be gated on `results?.plots &&` (the old
//    pattern that hid the tab silently).
const oldGuard = /activeTab === ['"]plots['"] && results\?\.plots\s*&&/;
assert.equal(
  oldGuard.test(source),
  false,
  'ResultsViewer still has the old `activeTab === "plots" && results?.plots &&` guard. ' +
    'This guard hides the whole tab with no empty-state fallback (F1.6). ' +
    'Replace with `activeTab === "plots" && results &&` so the inner branch can show the placeholder.'
);

// 2. The Plots tab must be gated on `results &&` so the inner branch
//    is reachable when plots is missing or empty.
const newGuard = /activeTab === ['"]plots['"] && results\b/;
assert.ok(
  newGuard.test(source),
  'ResultsViewer Plots tab is not gated on `activeTab === "plots" && results` ' +
    '— the F1.6 fix requires this so the empty-state placeholder is reachable.'
);

// 3. The inner branch must contain the empty-state markup.
assert.ok(
  /No Plots Available/.test(source),
  'ResultsViewer is missing the "No Plots Available" placeholder markup. ' +
    'The F1.6 fix requires it inside the Plots tab body so missing/empty plots render an empty state, not a blank tab.'
);

// 4. The inner branch must check for plots (via plotFigures or results.plots)
//    so that empty state renders when no plots available.
const innerCheck = /plotFigures|results\.plots/;
assert.ok(
  innerCheck.test(source),
  'ResultsViewer Plots tab inner branch must check for plots (plotFigures or results.plots) before rendering cards.'
);

// --- F8.3 regression guard ----------------------------------------------
// The ResultsViewer "load on completion" effect uses a `!results`
// guard to ensure loadResults fires once per job. The only writer of
// `results` is loadResults (always non-null), so the guard is
// sufficient. This test fails if someone later adds a `setResults(null)`
// call without also adding a "loaded for this job" ref, which would
// re-introduce the multi-fetch risk the deferred item was worried about.
const resultsWriters = source.match(/setResults\s*\(/g) || [];
// Count of `setResults(` calls — must be exactly 1 (inside loadResults).
// Plus the `useState<KPIsResponse | null>(lastResults)` initialiser
// does NOT count (it doesn't call setResults). Any new callsite of
// `setResults(null)` would push this above 1.
assert.equal(
  resultsWriters.length,
  1,
  `ResultsViewer has ${resultsWriters.length} setResults() callsites. ` +
    'The load-once invariant (F8.3) assumes setResults is only called from loadResults ' +
    'with a non-null payload. If you add a setResults(null) call, add a loadedJobIdRef ' +
    'to the loadResults effect first to keep the load-once guarantee.'
);

// --- F8.9 regression guard ----------------------------------------------
// PlotCard must guard Plotly.purge behind a chartMountedRef so the
// early-return path (empty plotJson) doesn't issue a spurious purge.
const plotCardSrcPath = join(process.cwd(), 'src', 'components', 'results', 'PlotCard.tsx');
const plotCardSource = readFileSync(plotCardSrcPath, 'utf8');
assert.ok(
  /chartMountedRef/.test(plotCardSource),
  'PlotCard is missing the chartMountedRef guard (F8.9). ' +
    'The cleanup function must only call Plotly.purge if a chart was actually mounted ' +
    'on this effect run, otherwise the early-return path (empty plotJson) issues a ' +
    'spurious purge that can race a fresh mount.'
);

// --- Task 11 regression guards ------------------------------------------
// 5. Grid layout selector must be present in ResultsControlRail
const railSrcPath = join(process.cwd(), 'src', 'components', 'results', 'ResultsControlRail.tsx');
const railSource = readFileSync(railSrcPath, 'utf8');
assert.ok(
  /gridLayout|Grid Columns/.test(railSource),
  'ResultsControlRail is missing the grid layout selector (Task 11).'
);

// 6. Per-property toggle must be present
assert.ok(
  /perProperty|Per-property/.test(railSource),
  'ResultsControlRail is missing the per-property toggle (Task 11).'
);

// 7. Unit system selector must be present
assert.ok(
  /unitSystem|Unit System/.test(railSource),
  'ResultsControlRail is missing the unit system selector (Task 11).'
);

// 8. ResultsViewer must use plotGroup API for fetching plots
assert.ok(
  /plotGroup|fetchPlots/.test(source),
  'ResultsViewer must use the plotGroup API / fetchPlots function (Task 11).'
);

// 9. ResultsViewer must have dynamic grid layout
assert.ok(
  /gridLayout|grid-cols/.test(source),
  'ResultsViewer must have dynamic grid layout CSS (Task 11).'
);

console.log('OK: ResultsViewer F1.6 + F8.3 + F8.9 + Task 11 source-grep guards verified');
