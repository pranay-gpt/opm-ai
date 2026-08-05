/** Scans deck text for Eclipse section keywords and returns their 1-based
 *  line numbers. Sections absent from the deck are omitted.
 *
 *  Handles CRLF, trailing -- comments, and banner-style headers such as
 *  "GRID    =================================" (the production Deck parser
 *  in the backend uses word-boundary matching, which the regex below mirrors).
 */

const SECTION_NAMES = [
  'RUNSPEC', 'GRID', 'EDIT', 'PROPS', 'REGIONS', 'SOLUTION', 'SUMMARY', 'SCHEDULE',
] as const;

export type SectionName = (typeof SECTION_NAMES)[number];

export interface SectionEntry {
  section: SectionName;
  lineNumber: number;
}

/**
 * Build the section regex once so we don't reconstruct it on every scan.
 * Looks for a section keyword as a word (case-insensitive) on a line whose
 * first non-whitespace, non-comment content is that word.
 */
const SECTION_RE = new RegExp(
  '^(?:' + SECTION_NAMES.join('|') + ')\\b',
  'im',
);

/** Find each section keyword and its line in deck text. */
export function findSections(text: string): SectionEntry[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const result: SectionEntry[] = [];

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    // Strip inline -- comments before checking for section keyword
    const code = raw.split('--')[0].trim();
    if (!code) continue;

    const m = code.match(SECTION_RE);
    if (m) {
      const section = m[0].toUpperCase() as SectionName;
      // Monaco is 1-based
      result.push({ section, lineNumber: i + 1 });
    }
  }

  return result;
}