/**
 * Self-check for the reservoir interview panel's restart path.
 *
 * Pins the bug found in browser testing on 2026-10-03: Restart cleared
 * the local state and the store's answers, but the mount effect that
 * fetches the first question depends only on [isOpen, description,
 * fetchNext]. None of those change when Restart is clicked, so the panel
 * sat blank - no question, progress stuck at the pre-restart count -
 * until something else forced a re-render. handleRestart now awaits
 * fetchNext() itself.
 *
 * This is a source-grep regression guard, matching the project's other
 * frontend test files (no React test framework is installed).
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/components/InterviewPanel.test.ts \
 *     --outfile=node_modules/.cache/ip.cjs \
 *     && node node_modules/.cache/ip.cjs
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

declare const require: (id: string) => unknown;
const assert = require('node:assert/strict') as typeof import('node:assert/strict');

const PANEL = readFileSync(
  join(process.cwd(), 'src', 'components', 'InterviewPanel.tsx'),
  'utf8',
);

// Isolate handleRestart from the rest of the file: the first occurrence of
// its name is the destructure in the props type's function signature area
// on some builds, so slice from the declaration onward.
const start = PANEL.indexOf('const handleRestart');
assert.ok(start > 0, 'handleRestart is declared');
const body = PANEL.slice(start, PANEL.indexOf('const handleIngest') > start
  ? PANEL.indexOf('const handleIngest')
  : start + 2000);

assert.ok(
  body.includes('fetchNext()'),
  'handleRestart must call fetchNext() - clearing local state and the store '
  + 'does not change the mount effect deps, so nothing else re-asks the server',
);

assert.ok(
  body.includes('onReset()'),
  'handleRestart must still clear the stored answers',
);

assert.ok(
  body.includes('answersRef.current = {}'),
  'handleRestart must clear the answers ref synchronously; the prop will not '
  + 'have updated yet when the next fetch reads it',
);

// The answers ref is the statelessness contract: the panel owns the dict and
// round-trips it on every call, so a stale ref would replay old answers.
assert.ok(
  PANEL.includes('answersRef.current = { ...answersRef.current, [question.id]: value }'),
  'answer path still writes through the ref',
);
assert.ok(
  PANEL.includes('answersRef.current = { ...answersRef.current, [question.id]: null }'),
  'skip path still records the declared default through the ref',
);

console.log('InterviewPanel.test.ts: restart + stateless-ref checks passed');
