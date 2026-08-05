# frontend/src/components/ - React components

## Purpose
Top-level UI components for the OPM-AI SPA. Three "feature areas":

1. **Deck authoring**: `DeckBuilder`, `DeckEditor`, `LinterPanel`,
   `RockBasicsSection`, `DeckPicker`
2. **Run + results**: `SimulationRunner`, `ResultsViewer`
3. **Discovery + chat**: `Home`, `Learn`, `ChatPanel`, `SettingsPanel`,
   `Header`, `Sidebar`, `ErrorBoundary`

## OPM language support (Monaco)
- `deckSections.ts` — section classification (RUNSPEC/GRID/.../SCHEDULE)
- `opmCompletions.ts` (Stage 3.4, 2026-08-04) — extracted Monaco
  completion provider; pure module, registered against `monaco.languages.registerCompletionItemProvider('opm', ...)`. Fetches
  `/api/keywords` on registration; falls back to bundled list if backend
  unreachable.
- `opmCompletions.test.ts` (Stage 3.4) — 11 self-check tests via
  esbuild/node pattern (was 9; +2 in Stage 3.5 for parameter
  documentation rendering)

## Lint summary rendering (2026-08-04)
- `LinterPanel.tsx`: summary card renders `lint_summary` below the
  [OK]/[FAIL] indicator when truthy (top border separator).
- `DeckBuilder.tsx`: same inside the build-result card, above the
  error list.
- `DeckEditor.tsx`: removed the fabricated "All checks passed"
  string from the synthetic LintResult fallback at handleSave;
  replaced with `lint_summary: null` and pass-through of
  `lastLintResult` verbatim when present.

## Tests
- `npm test` runs both `deckSections.test.ts` and `opmCompletions.test.ts`
  via esbuild + node (no vitest on this host). Append to the `test`
  script in `package.json` to add a new check.

## Conventions
- Components are plain functional components with hooks
- API calls go through `src/api/client.ts` (typed wrapper)
- State is Zustand (`src/stores/useAppStore.ts`) for shared cross-page
  state; local state for ephemeral UI

## Future / Plan
- Monaco inline lint squiggles (currently lint is post-save)
- Mobile polish (currently desktop-first; the 3D viewer assumes desktop GPU)
- Stage 3.5 DONE (2026-08-04): parameter-extraction-driven hover docs
  live in `opmCompletions.ts` (parameters → documentation as
  `"name — brief"` lines, truncated to 600 chars; falls back to
  description when parameters is empty).
- Correlation dropdown DONE (2026-08-04): fluid card now has a
  Standing / Vasquez-Beggs / Al-Marhoun select. Default Standing.
  Threaded through `FluidDescriptorRequest.correlation` ->
  `FluidDescriptor.correlation` -> `build_pvt_blocks` selection.
