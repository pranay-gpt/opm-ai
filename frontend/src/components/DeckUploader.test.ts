/**
 * Self-check for the deck upload feature.
 *
 * Pins three invariants that are easy to break later:
 *
 *   1. SimulationRunner exposes BOTH a Browse button and an Upload
 *      button. Removing the Upload button would silently regress
 *      the laptop-local-files workflow.
 *
 *   2. DeckUploader renders the two file inputs with the right
 *      attributes. <input type="file" webkitdirectory directory
 *      multiple> is what gives Chromium the directory-picker
 *      behaviour. Removing `webkitdirectory` would silently turn
 *      it into a plain multi-file picker that doesn't preserve
 *      the include/ layout.
 *
 *   3. The api.uploadDeck helper does NOT set Content-Type. The
 *      browser sets it with the correct `boundary=` parameter for
 *      multipart bodies; setting it manually would either lose
 *      the boundary (parser rejects the body) or send a wrong
 *      one (server-side parser refuses).
 *
 * This is a source-grep regression guard, matching the project's
 * other frontend test files (pure-logic asserts, no React test
 * framework installed).
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/components/DeckUploader.test.ts \
 *     --outfile=node_modules/.cache/du.cjs \
 *     && node node_modules/.cache/du.cjs
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

declare const require: (id: string) => unknown;
const assert = require('node:assert/strict') as typeof import('node:assert/strict');

const SR_PATH = join(process.cwd(), 'src', 'components', 'SimulationRunner.tsx');
const DU_PATH = join(process.cwd(), 'src', 'components', 'DeckUploader.tsx');
const AC_PATH = join(process.cwd(), 'src', 'api', 'client.ts');

const sr = readFileSync(SR_PATH, 'utf8');
const du = readFileSync(DU_PATH, 'utf8');
const ac = readFileSync(AC_PATH, 'utf8');

// --- 1. Browse + Upload buttons coexist ----------------------------

assert.ok(
  /onClick=\{[^}]*setPicking\(true\)[^}]*\}[\s\S]{0,200}Browse/.test(sr),
  'SimulationRunner is missing the Browse button.'
);

assert.ok(
  /onClick=\{[^}]*setUploading\(true\)[^}]*\}[\s\S]{0,200}Upload/.test(sr),
  'SimulationRunner is missing the Upload button next to Browse. ' +
    'The deck upload workflow (laptop-local .DATA + include/ folder) ' +
    'lives entirely on this button.'
);

// The DeckUploader modal must be rendered when uploading is set.
assert.ok(
  /uploading\s*&&[\s\S]{0,80}<DeckUploader/.test(sr),
  'SimulationRunner is not rendering the DeckUploader modal.'
);

// --- 2. DeckUploader has both file inputs with the right attrs ----

assert.ok(
  /<input\s+[^>]*type="file"[^>]*accept="\.DATA"/.test(du),
  'DeckUploader is missing the .DATA-only file input for the deck.'
);

assert.ok(
  /<input\s+[\s\S]{0,400}webkitdirectory[\s\S]{0,200}directory[\s\S]{0,200}multiple/.test(du),
  'DeckUploader include input is missing webkitdirectory / directory / multiple. ' +
    'These three attributes together give Chromium the directory-picker behaviour; ' +
    'removing any one silently breaks the include/ folder upload.'
);

// --- 3. api.uploadDeck does NOT set Content-Type ------------------

assert.ok(
  /uploadDeck:\s*\([^)]*FormData[^)]*\)[^=]*=>[\s\S]{0,200}fetchMultipart/.test(ac),
  'api.uploadDeck must call fetchMultipart (which is the helper that ' +
    'omits the Content-Type header).'
);

// fetchMultipart must not set Content-Type.
const fetchMultipartMatch = ac.match(/async function fetchMultipart[^{]*\{([\s\S]*?)\n\}/);
assert.ok(fetchMultipartMatch, 'fetchMultipart helper not found in client.ts');
const fetchMultipartBody = fetchMultipartMatch[1];
assert.ok(
  !/['"]Content-Type['"]/.test(fetchMultipartBody) && !/headers:/.test(fetchMultipartBody),
  'fetchMultipart is setting Content-Type or a headers object. ' +
    'For multipart bodies the browser must set Content-Type itself ' +
    '(with the correct boundary= parameter). Setting it manually ' +
    'either loses the boundary (parser rejects the body) or sends ' +
    'a wrong one (server-side parser refuses).'
);

console.log('OK: deck upload source-grep guards verified');