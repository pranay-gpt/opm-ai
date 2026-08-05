/**
 * Self-check for ChatPanel F8.6 audit fix: the inner `messages`
 * shadow in the WS-connect useEffect was renamed to `initialMessages`
 * to make it obvious that it is the connect-time snapshot, not the
 * live store value. Without the rename, a future maintainer could
 * mistake the inner `messages` for a fresh store read.
 *
 * This is a source-grep regression guard, matching the project's
 * other frontend test files (pure-logic asserts, no React test
 * framework installed).
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/components/ChatPanel.test.ts \
 *     --outfile=node_modules/.cache/cp.cjs \
 *     && node node_modules/.cache/cp.cjs
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

declare const require: (id: string) => unknown;
const assert = require('node:assert/strict') as typeof import('node:assert/strict');

const srcPath = join(process.cwd(), 'src', 'components', 'ChatPanel.tsx');
const source = readFileSync(srcPath, 'utf8');

// The connect-time snapshot must be called `initialMessages` (F8.6
// fix). The old code shadowed `messages` (the live store value from
// useChatMessages() at the top of the component) with a getState()
// read, which made the diff easy to misread.
assert.ok(
  /const\s+initialMessages\s*=\s*useChatStore\.getState\(\)\.messages/.test(source),
  'ChatPanel: F8.6 audit fix requires the connect-time messages snapshot to be named `initialMessages`, not the shadowed `messages`. ' +
    'The rename makes it clear this is the snapshot passed to connectChat, not a live store read.'
);

// The `connectChat(sessionId, ...)` call must use the snapshot, not
// the live `messages` from useChatMessages() (which is the outer
// binding).
assert.ok(
  /connectChat\(\s*\n?\s*sessionId,\s*\n?\s*initialMessages/.test(source),
  'ChatPanel: connectChat must be called with the initialMessages snapshot (F8.6 fix). ' +
    'Passing the live `messages` from useChatMessages() would re-send the entire history on every WS reconnect.'
);

// The shadow pattern `const messages = useChatStore.getState().messages`
// must NOT appear inside the WS-connect effect (it's only used at
// module top-level via the `useChatMessages()` hook).
const shadowPattern = /const\s+messages\s*=\s*useChatStore\.getState\(\)\.messages/;
assert.equal(
  shadowPattern.test(source),
  false,
  'ChatPanel: the inner `const messages = useChatStore.getState().messages` shadow is back. ' +
    'This was renamed to `initialMessages` for clarity (F8.6 audit fix).'
);

console.log('OK: ChatPanel F8.6 source-grep guard verified');
