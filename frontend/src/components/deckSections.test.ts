/**
 * Self-check for the deck section scanner. No test framework is installed, so
 * this is a plain assert script, following the same convention as
 * viewer3d/meshFormat.test.ts.
 *
 * Run it via the existing `npm test` script - it bundles both test files into a
 * single esbuild invocation and executes them in sequence.
 */

import { findSections } from './deckSections';

// Match the meshFormat.test.ts convention: use a top-level require for
// node:assert/strict, since some esbuild invocations mishandle top-level
// `node:assert` imports on Windows line endings.
declare const require: (id: string) => unknown;
const assert = require('node:assert/strict') as {
  equal(a: unknown, b: unknown, m?: string): void;
  ok(v: unknown, m?: string): void;
};

// Minimal deck fixture for the "all sections" case: one keyword per line,
// with comments and blank lines mixed in.
const FULL = [
  '-- Comment-only line',
  'RUNSPEC',
  'TITLE',
  '  -- trailing comment',
  '',
  'GRID',
  'INIT',
  '',
  'EDIT',
  '',
  'PROPS',
  'SWOF',
  '',
  'REGIONS',
  '',
  'SOLUTION',
  'EQUIL',
  '',
  'SUMMARY',
  '',
  'SCHEDULE',
  'WELSPECS',
  'END',
].join('\n');

// Optional sections (EDIT, REGIONS) deliberately omitted.
const PARTIAL = [
  'RUNSPEC',
  'DIMENS',
  '',
  'GRID',
  'INIT',
  '',
  'PROPS',
  'PVTW',
  '',
  'SOLUTION',
  'EQUIL',
  '',
  'SCHEDULE',
  'WELSPECS',
].join('\n');

// Banner-style header: keyword followed by a run of '='s on the same line.
// Real OPM decks do this and the regex must treat it as a section marker.
const BANNER = [
  'RUNSPEC',
  'DIMENS',
  '',
  'GRID    ===============================',  // banner header
  'INIT',
  'TOPS',
  '',
  'PROPS',
  '',
  'SCHEDULE',
  'END',
].join('\n');

// Section names appearing inside comments should NOT register as hits.
const COMMENT_NAMED = [
  '-- RUNSPEC is the first section',
  '-- The GRID keyword follows',
  'RUNSPEC',
  'DIMENS',
  'GRID',
  'INIT',
].join('\n');

// CRLF line endings must be handled.
const CRLF_FIXTURE = 'RUNSPEC\r\nDIMENS\r\nGRID\r\nINIT\r\nPROPS\r\nPVTW\r\nSCHEDULE\r\nEND';

console.log('deckSections self-check');

// All sections present -> all 8 entries, line numbers correct, 1-based.
{
  const got = findSections(FULL);
  const expected = [
    ['RUNSPEC', 2],  // line after the comment
    ['GRID', 6],
    ['EDIT', 9],
    ['PROPS', 11],
    ['REGIONS', 14],
    ['SOLUTION', 16],
    ['SUMMARY', 19],
    ['SCHEDULE', 21],
  ];
  assert.equal(got.length, expected.length, 'all eight sections found');
  for (let i = 0; i < expected.length; i++) {
    assert.equal(got[i].section, expected[i][0], `section ${i} name`);
    assert.equal(got[i].lineNumber, expected[i][1], `section ${i} line`);
  }
  console.log('  ok  full deck with comments and blank lines');
}

// Optional sections absent -> omitted from results, not zeroed.
{
  const got = findSections(PARTIAL);
  const names = new Set(got.map((s) => s.section));
  assert.equal(got.length, 5, 'five sections found');
  assert.ok(names.has('RUNSPEC'), 'RUNSPEC present');
  assert.ok(names.has('SCHEDULE'), 'SCHEDULE present');
  assert.ok(!names.has('EDIT'), 'EDIT omitted');
  assert.ok(!names.has('REGIONS'), 'REGIONS omitted');
  console.log('  ok  partial deck: absent sections omitted, not zeroed');
}

// Banner-style header is recognised as a section marker.
{
  const got = findSections(BANNER);
  const grid = got.find((s) => s.section === 'GRID');
  assert.ok(grid, 'GRID detected despite banner');
  assert.equal(grid!.lineNumber, 4, 'banner header is on its own line');
  console.log('  ok  banner-style header (GRID ============)');
}

// Section name inside a comment must NOT register.
{
  const got = findSections(COMMENT_NAMED);
  // Commented mentions of RUNSPEC/GRID line up with the real ones, so the
  // result must show ONE RUNSPEC and ONE GRID, not two of either.
  const runspecs = got.filter((s) => s.section === 'RUNSPEC');
  const grids = got.filter((s) => s.section === 'GRID');
  assert.equal(runspecs.length, 1, 'commented RUNSPEC ignored');
  assert.equal(grids.length, 1, 'commented GRID ignored');
  assert.equal(runspecs[0].lineNumber, 3, 'real RUNSPEC at line 3');
  assert.equal(grids[0].lineNumber, 5, 'real GRID at line 5');
  console.log('  ok  section names in comments do not register');
}

// CRLF line endings handled identically to LF.
{
  // Re-flow FULL into CRLF and compare to the LF result - same names, same
  // line numbers. The fixture constant CRLF_FIXTURE covers a smaller deck
  // for completeness.
  const lfResult = findSections(FULL);
  const crlfResult = findSections(FULL.replace(/\n/g, '\r\n'));
  assert.equal(crlfResult.length, lfResult.length, 'CRLF yields the same count as LF');
  for (let i = 0; i < crlfResult.length; i++) {
    assert.equal(crlfResult[i].section, lfResult[i].section, `CRLF section ${i} matches LF`);
    assert.equal(crlfResult[i].lineNumber, lfResult[i].lineNumber, `CRLF line ${i} matches LF`);
  }
  const direct = findSections(CRLF_FIXTURE);
  assert.equal(direct.length, 4, 'CRLF fixture yields four sections');
  console.log('  ok  CRLF line endings normalised');
}

console.log('  all deckSections checks passed');
