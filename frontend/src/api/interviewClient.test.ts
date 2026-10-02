/**
 * Self-check for the interview client wrappers.
 *
 * The interview server is stateless: the client owns the answers dict and
 * round-trips it on every call. This proves the wrappers hit the right
 * paths, send the answers verbatim, and surface the backend's terminal
 * response (deck + lint) without reshaping it.
 *
 * No test framework is installed, so this is a plain assert script
 * bundled with esbuild the same way the sibling .test.ts files are.
 */

import { api } from './client';

declare const require: (id: string) => unknown;

const assert = require('node:assert/strict') as {
  equal(a: unknown, b: unknown, m?: string): void;
  ok(value: unknown, m?: string): void;
};

interface Captured {
  path: string;
  method: string;
  // JSON-parsed for JSON bodies; left raw for FormData (multipart).
  body: unknown;
}

// Record every request so we can assert on the wire contract.
const captured: Captured[] = [];
let nextResponse: unknown = {};

(globalThis as unknown as { fetch: typeof fetch }).fetch = (async (
  input: RequestInfo | URL,
  init?: RequestInit,
) => {
  const body = init?.body;
  captured.push({
    path: String(input),
    method: init?.method ?? 'GET',
    body: body instanceof FormData ? body : body ? JSON.parse(String(body)) : null,
  });
  return new Response(JSON.stringify(nextResponse), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}) as typeof fetch;

// --- interviewNext ---------------------------------------------------------

async function testInterviewNextSendsAnswers() {
  captured.length = 0;
  nextResponse = {
    question: {
      id: 'grid.nx',
      section: 'grid',
      prompt: 'How many grid blocks in X?',
      kind: 'number',
      default: 10,
      units: 'blocks',
      options: null,
      blocking: true,
    },
    progress: { answered: 0, total: 12 },
    findings: [],
    resolved: { porosity: 0.22 },
  };

  const res = await api.interviewNext({
    description: '10x10x3 depletion',
    answers: { 'intent.scenario': 'depletion' },
    use_llm: false,
  });

  const call = captured[0];
  assert.ok(call.path.endsWith('/interview/next'), 'hits /interview/next');
  assert.equal(call.method, 'POST');
  // The answers dict is round-tripped verbatim - the server holds none.
  assert.deepEqual(
    (call.body as { answers: Record<string, unknown> }).answers,
    { 'intent.scenario': 'depletion' },
  );
  assert.equal(res.question?.id, 'grid.nx');
  assert.equal(res.progress.total, 12);
  assert.equal(res.resolved?.porosity, 0.22);
}

// --- interviewFinish -------------------------------------------------------

async function testInterviewFinishReturnsDeck() {
  captured.length = 0;
  const lint = { deck_path: '', issues: [], lint_summary: null, errors: [], passed: true };
  nextResponse = {
    deck: 'RUNSPEC\nDIMENS\n 10 10 3 /\n',
    lint,
    provenance: { porosity: 'user_override' },
    resolved: { porosity: 0.25 },
    findings: ['Water-oil contact depth lies outside the grid span.'],
  };

  const res = await api.interviewFinish({
    description: '10x10x3 depletion',
    answers: { 'grid.nx': 10, 'rock.porosity': 0.25 },
  });

  assert.ok(captured[0].path.endsWith('/interview/finish'), 'hits /interview/finish');
  assert.equal(res.lint.passed, true);
  assert.ok(res.deck.includes('DIMENS'));
  assert.equal(res.findings.length, 1);
}

// --- ingest ---------------------------------------------------------------

async function testIngestParse() {
  captured.length = 0;
  nextResponse = {
    detected: 'grdecl',
    patch: { porosity: 0.25 },
    findings: [],
  };

  const res = await api.ingestParse('PORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n');

  assert.ok(captured[0].path.endsWith('/ingest/parse'), 'hits /ingest/parse');
  assert.equal(
    (captured[0].body as { text: string }).text,
    'PORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n',
  );
  assert.equal(res.detected, 'grdecl');
  assert.equal(res.patch.porosity, 0.25);
}

async function testIngestUpload() {
  captured.length = 0;
  nextResponse = { detected: 'grdecl', patch: { porosity: 0.25 }, findings: [] };

  const res = await api.ingestUpload(new File(['PORO\n 300*0.25 /\n'], 'model.GRDECL'));

  assert.ok(captured[0].path.endsWith('/ingest/upload'), 'hits /ingest/upload');
  // multipart: the body is FormData, not a JSON string.
  const sent = captured[0].body as FormData;
  assert.ok(sent instanceof FormData, 'upload sends multipart FormData');
  assert.ok(sent.get('file') instanceof File, 'the file rides in a "file" part');
  assert.equal(res.patch.porosity, 0.25);
}

async function main() {
  await testInterviewNextSendsAnswers();
  await testInterviewFinishReturnsDeck();
  await testIngestParse();
  await testIngestUpload();
  console.log('client.test.ts: all interview/ingest client checks passed');
}

void main();