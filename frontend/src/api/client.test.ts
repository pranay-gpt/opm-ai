/**
 * Self-check for pollJobStatus: verifies the AbortSignal path cancels the
 * loop between attempts and rejects with an AbortError, instead of
 * silently continuing to fire setTimeout ticks after the component is
 * gone.
 *
 * No test framework is installed, so this is a plain assert script
 * bundled with esbuild the same way the sibling .test.ts files are.
 *
 *   cd frontend
 *   node_modules/.bin/esbuild --bundle --platform=node --format=cjs \
 *     src/api/client.test.ts --outfile=node_modules/.cache/cl.cjs \
 *     && node node_modules/.cache/cl.cjs
 */

import { pollJobStatus } from './client';
import type { JobStatus } from '../types';

declare const require: (id: string) => unknown;

const nodeAssert = require('node:assert/strict') as {
  equal(a: unknown, b: unknown, m?: string): void;
  ok(value: unknown, m?: string): void;
  rejects: (
    fn: () => Promise<unknown>,
    matcher?: unknown,
    m?: string
  ) => Promise<void>;
};

// --- Stubs ----------------------------------------------------------------

const running: JobStatus = { job_id: 'job-1', status: 'running' };

// Track every call so we can prove the poll stopped after abort.
let callCount = 0;
let inFlight: AbortSignal | null = null;

(globalThis as unknown as { fetch: typeof fetch }).fetch = (async (
  _input: RequestInfo | URL,
  init?: RequestInit
) => {
  callCount += 1;
  // Stash the signal used on the first call so the test can assert
  // pollJobStatus forwards it to runStatus.
  if (inFlight === null && init?.signal) inFlight = init.signal;
  // Simulate a slow server: never resolves on its own. The test aborts
  // to drive the loop forward — i.e. we depend on the AbortSignal
  // interrupting the await runStatus, exactly the real-world failure.
  return await new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => {
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}) as unknown as typeof fetch;

// --- Tests ----------------------------------------------------------------

async function testAbortStopsPolling() {
  callCount = 0;
  inFlight = null;

  const controller = new AbortController();
  const updates: JobStatus[] = [];

  // Abort ~25ms in — enough time for the first runStatus call to be
  // outstanding, not enough for the 2s interval to elapse.
  const timer = setTimeout(() => controller.abort(), 25);

  let threw: unknown = null;
  try {
    await pollJobStatus(
      'job-1',
      (s) => updates.push(s),
      2000, // 2s interval
      300,
      controller.signal
    );
  } catch (e) {
    threw = e;
  } finally {
    clearTimeout(timer);
  }

  nodeAssert.ok(threw instanceof Error, 'pollJobStatus should reject when aborted');
  nodeAssert.equal(
    (threw as DOMException).name,
    'AbortError',
    'rejection should be an AbortError'
  );
  // Exactly one network call was made before the abort interrupted it.
  nodeAssert.equal(callCount, 1, 'pollJobStatus should not retry after abort');
  // The signal was forwarded to runStatus (so the in-flight fetch can
  // be cancelled, not just the next setTimeout).
  nodeAssert.ok(
    inFlight !== null,
    'pollJobStatus should pass the signal through to runStatus'
  );
  nodeAssert.equal(inFlight!.aborted, true, 'forwarded signal should be aborted');
}

async function testNoSignalKeepsLegacyBehavior() {
  // Without a signal the loop must still work for callers that have not
  // been updated yet. The fetch stub resolves 'running' twice then
  // 'completed'.
  let n = 0;
  (globalThis as unknown as { fetch: typeof fetch }).fetch = (async () => {
    n += 1;
    const body: JobStatus =
      n < 3 ? running : { job_id: 'job-2', status: 'completed' };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as unknown as typeof fetch;

  const updates: JobStatus[] = [];
  // Tiny interval so the test runs fast.
  const final = await pollJobStatus(
    'job-2',
    (s) => updates.push(s),
    5,
    10
  );
  nodeAssert.equal(final.status, 'completed');
  nodeAssert.equal(updates.length, 3);
  nodeAssert.equal(updates[2].status, 'completed');
}

async function testAbortedBeforeFirstCall() {
  // If the signal is already aborted, the loop must reject immediately
  // without hitting the network.
  let called = 0;
  (globalThis as unknown as { fetch: typeof fetch }).fetch = (async () => {
    called += 1;
    return new Response('{}', { status: 200 });
  }) as unknown as typeof fetch;

  const controller = new AbortController();
  controller.abort();

  let threw: unknown = null;
  try {
    await pollJobStatus('job-3', undefined, 5, 10, controller.signal);
  } catch (e) {
    threw = e;
  }
  nodeAssert.ok(threw instanceof DOMException);
  nodeAssert.equal((threw as DOMException).name, 'AbortError');
  nodeAssert.equal(called, 0, 'no network call when signal is pre-aborted');
}

async function main() {
  await testAbortStopsPolling();
  await testNoSignalKeepsLegacyBehavior();
  await testAbortedBeforeFirstCall();
  // eslint-disable-next-line no-console
  console.log('pollJobStatus AbortSignal tests: OK');
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error(e);
  // Re-throw so node exits non-zero. `process` is not typed in this
  // DOM-only project (no @types/node), so avoid referencing it directly.
  throw e;
});
