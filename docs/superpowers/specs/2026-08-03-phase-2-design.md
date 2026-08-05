# Phase 2: refinement and features

Date: 2026-08-03
Status: design approved, not yet implemented

Nine areas, grouped into three stages. Stage 1 fixes what is broken, Stage 2 is
presentational, Stage 3 adds capability. Each stage lands as its own commit with
the suite green, and each is independently shippable.

## What the investigation found

Four read-only subagents mapped the affected components. Every load-bearing
claim was re-verified by hand before landing in this document, and two were
wrong:

| Claim | Verdict |
|---|---|
| `useChatStore()` without a selector causes infinite re-render (React #185) | **False.** Read zustand 5.0.14's source: `useStore(api, selector = identity)` returns `api.getState()`, a stable reference. It over-subscribes to re-renders; it cannot loop. `useShallow` is only needed for selectors that build a fresh object. |
| Interactive ResInsight launch is theoretical / needs streaming | **False as stated.** Launched it: `ResInsight --case SPE1CASE1.EGRID` under `DISPLAY=:0 QT_QPA_PLATFORM=xcb` produced window `ResInsight (64bit) - [3D View: SOIL]` at 1214x688, case loaded, empty stderr. `xwininfo` confirms the window. The server-display constraint is real; the "cannot work" framing was not. |
| opm-common is a licence-clean source for keyword data | **False, and it was my error.** opm-common is GPL-3.0, as is opm-flow-editor-support. Only opm-reference-manual is MIT-compatible (CC-BY 4.0). Corrected before any code was written. |

Verified true: the chat dict-render crash, the absent markdown renderer, the
no-op deck editor navigation, and the builder's unmount-on-navigate state loss.

## Stage 1: the four defects

### 1.1 Chat crash and the missing error boundary

**Root cause.** `chat.py:420` sends `{"type": "tool_result", "result": tool_result}`
where `tool_result` is a `dict` (`execute_tool` returns `dict`, chat.py:263).
`client.ts:349` passes it through untouched, `ChatPanel.tsx:65` stores it as
`content`, and `ChatPanel.tsx:240` renders `{message.content}`. React cannot
render an object as a child and throws "Objects are not valid as a React child".

**Why the whole page vanishes.** There is no error boundary anywhere in
`frontend/src/` (grepped: no `componentDidCatch`, no `getDerivedStateFromError`).
An uncaught throw during render unmounts the entire tree, so a chat bug blanks
the whole app.

**Why it recurs after reload.** `useAppStore.ts` persists chat `messages` to
localStorage. The malformed message survives a refresh and crashes again on
mount. A fix that does not sanitise existing storage leaves current sessions
broken.

Three changes:

- Serialise at the boundary: `ChatPanel`'s `onToolResult` stores
  `JSON.stringify(result, null, 2)` rather than the raw object. Tool results are
  JSON and belong in the existing `<pre>`, not in prose.
- Retype `WSServerMessage.tool_result.result` in `types.ts:235` from `string` to
  `Record<string, unknown>`. The type currently lies about the wire shape, which
  is what allowed this to compile.
- Add one `ErrorBoundary` around the router `<Outlet>` in `App.tsx`, rendering
  the error message and a reset button. This is worth more than the specific bug:
  today *any* render error in *any* route blanks the app with no diagnostic.
- On chat-store rehydration, coerce any non-string `content` to a string. Bounded
  and mechanical; without it, already-poisoned localStorage keeps crashing.

Tests: a unit check that a dict tool result renders as text rather than throwing,
and one that the boundary catches a child throw instead of propagating.

### 1.2 Markdown rendering in Learn and Chat

**Root cause.** No markdown renderer is installed. `frontend/package.json`
dependencies are `@monaco-editor/react`, `@types/three`, `plotly.js-dist-min`,
`react`, `react-dom`, `react-router-dom`, `three`, `zustand` — nothing else.
Backend explainer text is markdown, so asterisks and hashes reach the DOM
literally.

**Second, quieter defect.** `Learn.tsx:243` and `ChatPanel.tsx:210` both apply
`prose prose-invert`, but `tailwind.config.js:32` is `plugins: []`. Without
`@tailwindcss/typography` those classes generate nothing — confirmed by grepping
the built CSS for `prose`: zero hits. The styling has never applied.

Changes:

- Add `react-markdown`, `remark-gfm`, and `@tailwindcss/typography`; register the
  plugin in `tailwind.config.js`.
- One shared `<Markdown>` component under `components/ui/`, used by Learn's
  explanation pane, Learn's learning-report pane, and Chat's assistant messages.
- Drop `whitespace-pre-wrap` where markdown now handles spacing, and remove the
  `<pre>` wrapper from assistant messages. **Tool results stay in `<pre>`** —
  they are JSON, and running them through a markdown renderer would mangle them.
- Theme: the typography plugin needs the palette's CSS vars, not its own greys.
  `prose-invert` is dark-only, so the dark/light/auto toggle must be respected
  via the existing `useResolvedTheme()`.

This adds three dependencies to a project that just dropped three. Justified:
the alternative is hand-rolling a markdown parser, and the current state is
visibly broken output on two pages.

### 1.3 Deck Editor section navigation

**Root cause, two independent defects.**

`scrollToSection` (`DeckEditor.tsx:193-201`) only calls `setActiveSection`. The
code says so itself: *"This is a limitation - we can't easily scroll without the
editor ref."* No Monaco navigation API is called.

`onMount` (`DeckEditor.tsx:411-413`) does `(window as any).monaco = m` — it keeps
the *namespace* and discards the *editor instance*, which is the object that owns
`revealLineInCenter` and `setPosition`.

Third issue: the section list (`DeckEditor.tsx:300`) is eight hardcoded ECLIPSE
names. It is not parsed from the deck, so it lists sections the deck may not have
and cannot list what it does have.

Changes:

- Keep the editor instance in a ref on mount, **in addition to** the existing
  `window.monaco` assignment. Do not replace it: `frontend/context.md` documents
  the Playwright convention of setting deck content via
  `window.monaco.editor.getModels()[0].setValue(...)`, so removing the global
  would break the browser-test approach.
- Scan the deck text for section keywords at line start, producing
  `{section, lineNumber}`. Memoised on deck content.
- Click calls `revealLineInCenter(line)` then `setPosition({lineNumber: line, column: 1})`,
  and still sets `activeSection` for the highlight.
- Sections absent from the deck render disabled rather than silently doing
  nothing. The current UI's real failure is that it looks functional.

Test: the scanner is a pure function over deck text — unit-test it against a
fixture deck for correct line numbers, including a deck missing optional sections.

### 1.4 Builder form state lost on navigation

**Root cause.** Standard SPA behaviour, not a bug in isolation: `App.tsx` renders
each route as a separate component, so navigating away unmounts `DeckBuilder` and
destroys all eight `useState` values (`description`, `fluidProps`,
`useLlmExtraction`, `useCustomFluid`, `showFluidSection`, `showEditor`, plus
transient `isBuilding`/`error`). No builder form state is in any store; the deck
slice persists only the *generated* deck.

Change: a `useBuilderStore` slice holding `description`, `fluidProps`,
`useLlmExtraction`, `useCustomFluid`, `showFluidSection`, persisted via the same
middleware as the deck and simulation slices. Transient state
(`isBuilding`, `error`) stays local — persisting a spinner across a reload would
strand the UI mid-flight.

Selector discipline: any selector returning a fresh object must use
`useShallow`. That rule is real (it is why `frontend/context.md` calls it out);
what is *not* true is that a plain `state => state.field` selector needs it.

## Stage 2: presentation

### 2.1 Home reorder and heading

Current vertical order (`Home.tsx`): hero+3D (31-75), workflow stats (78-93),
capabilities (96-138), recent jobs (141-199), quick actions (202-230). The
sections are a plain vertical stack (`space-y-4`, block children) with no grid
constraints, so reordering is moving JSX blocks.

New order: workflow stats, capabilities, recent jobs, then the 3D viewer, then
quick actions.

**The 3D container keeps `h-[34rem]`.** `frontend/context.md` records why: the
viewer sizes from its parent and `zoomAll` frames the model's bounding *sphere*
against the vertical FOV, so a wide flat grid like Norne reads small in a short
letterbox. Moving the block must not shrink it.

Heading (`Home.tsx:34`): `End-to-End Geo Workflow` -> `AI Integrated Reservoir
Simulation Tool`. The heading currently sits inside the hero; since the hero
moves down, the page title moves to the top of the new first section.

### 2.2 Collapsible sidebar

`Sidebar.tsx:33` fixes width at `w-56`. Icon and label are already separate
spans (`{item.icon}` and `<span className="truncate">{item.label}</span>`), so
collapsing means hiding the label span and narrowing the rail. Main content is
`flex-1` with no fixed margin, so it reflows automatically.

- `sidebarCollapsed` in `useUIStore`, persisted alongside `theme`. Distinct from
  the existing `sidebarOpen`, which is the mobile drawer and is deliberately not
  persisted.
- Collapsed rail shows icons only, with the label as a `title` tooltip.
- **Duration 200ms**, matching the app's existing `duration-200 ease-out`
  (sidebar transform) and `duration-150` (nav items). The request specified ~2s;
  that is roughly 10x every other transition here and reads as a hang rather than
  an animation, so 200ms was agreed instead.
- The `navItems` array is duplicated in `Sidebar.tsx:4-14` and `Header.tsx:4-14`.
  Extract it to one module while touching both files — this is the change that
  makes the duplication actively dangerous, since a collapsed rail needs icon
  metadata to stay in sync.

### 2.3 Rename Linter to "Simulation Deck Checker (.DATA)"

User-facing only. Nav labels in `Sidebar.tsx:12` and `Header.tsx:12`; the
`LinterPanel.tsx` heading (`Data Linter`, :154) and subtitle; button text
(`Lint Deck`/`Linting...`, :170); empty state (`No Lint Results`, :227);
placeholder (:228); status text (`Lint Passed`/`Lint Failed`, :247-248); the
`DeckEditor.tsx` toolbar button (:339-343); and the Home capability card
(:106-108).

Explicitly unchanged, because renaming them breaks things:

| Identifier | Why it stays |
|---|---|
| `/linter` URL path | Deep links and bookmarks; also referenced in App.tsx, Header, Sidebar, Home |
| `POST /api/lint` | Backend contract, chat tool, api client |
| `opm-ai-lint` storage key | Renaming silently discards users' persisted lint results |
| `opm_ai/linter/` module | Internal; 458-line negative test suite imports it |
| `LintRequest`/`LintResult`/`LintIssue` | Internal types, backend schema mirror |

Shortening the label: "Simulation Deck Checker (.DATA)" is too long for a 224px
sidebar rail. Nav shows **Deck Checker**; the page heading carries the full
"Simulation Deck Checker (.DATA)".

## Stage 3: features

### 3.1 ResInsight launch button (localhost-gated)

**Verified working.** `/usr/bin/ResInsight --case <path>.EGRID` with
`DISPLAY=:0 QT_QPA_PLATFORM=xcb` opens a real window with the case loaded
(`ResInsight (64bit) - [3D View: SOIL]`, 1214x688, confirmed via `xwininfo`,
empty stderr).

**This is not the snapshot path.** Batch export (`--savesnapshots views`) reports
success while writing a 329x127 crop of the window with no grid in it, and cannot
run headless at all. Interactive launch is a different mechanism and its working
says nothing about snapshots, nor vice versa. The premise "since 3D snapshot was
working this would too" is false in its first half and true in its conclusion.

**The constraint that shapes the design.** The backend runs on the server. A
launched GUI appears on the *server's* display. For a user on a laptop or phone —
the deployment the README advertises — clicking the button would open a window on
an unattended machine while the UI reported success.

So: `POST /api/results/{job_id}/resinsight` spawns the process detached
(`start_new_session=True`) and returns immediately without waiting. The route
returns 403 unless the request client is loopback. The button renders disabled
with an explanatory tooltip when `GET /api/results/{job_id}` reports the viewer
unavailable, so the UI never claims a launch it cannot deliver.

Guards: 404 unknown job, 400 job not completed, 404 no `.EGRID`, 503 when
`is_resinsight_available()` is false (no binary or no `DISPLAY`). One process per
job at a time — track the PID and no-op if it is alive, so double-clicking does
not spawn a second 91MB GUI.

Not doing: VNC/noVNC streaming for remote users. Recorded as future work.

### 3.2 Builder: rock basics and guided prompts

Currently settable: `porosity` (single value, default 0.3), `permx/permy/permz`
(per-layer, default `[500, 50, 200]`), `dx/dy/dz`, `top_depth`, and an optional
`FluidDescriptor`. Hardcoded and unreachable: initial pressure (4800 psia,
`builder.py:161`), rock compressibility (`3E-6`, `base.j2:104`), water PVT
(`base.j2:100`), densities (`base.j2:142`), SWOF/SGOF tables (`base.j2:106-139`),
and contact depths (WOC 8450, OWC 8300).

Expose in the form and in `ModelSpec`: porosity, per-layer permeability, top
depth, layer thickness, initial pressure. Relperm, PVT and density tables stay in
the template — every one of those is a way to produce a deck that will not
converge, and the linter cannot catch a physically silly relperm curve.

Teach `extract_parameters_offline` the vocabulary. It currently recognises grid
dimensions, scenario words, rates and well counts, and nothing physical. Add
porosity (percent and fraction), permeability (mD, including per-layer lists),
depth, and initial pressure.

**Guided prompts.** After extraction, the builder returns which fields were
*extracted from the description*, which were *defaulted*, and which are
*required but missing*. The UI shows the defaulted ones for confirmation before
generating, so the deck is never silently built on assumptions. This is a
provenance field on the response, not a conversational agent — the builder stays
a single request/response.

### 3.3 Per-scenario templates via Jinja2 inheritance (revised 2026-08-04)

#### Honest current state

The previous version of this section was built on a false premise. It claimed
`base.j2` "handles all 9 scenarios through inline conditionals" and that the
refactor would split one file with `{% if scenario == ... %}` blocks into a
`base.j2` plus per-scenario children. That is not what the code does.

Verified 2026-08-04: `grep -n "{% if scenario" opm_ai/builder/templates/base.j2`
returns zero matches. The template is scenario-agnostic. All scenario logic lives
in `opm_ai/builder/extract.py` (function `extract_parameters_offline_with_provenance`,
lines 61-547): well selection, per-layer permeability, PVDG, EQUIL, schedule
events. `base.j2` renders whichever `wells`, `permx`, `pvdg_rows`, `equil_*`,
`timesteps`, and `schedule_events` it is handed. The cleanest refactor
therefore does not need to enumerate scenarios in the template layer at all —
only in the few places where the layout itself (not just the data) differs.

Two data-driven switches remain in `base.j2`:
- `{% if pvdg_rows %}` (lines 145-160) — switches PVDG table between the
  SPE1 default and the CO2-like injector-gas table.
- `{% if pvt_blocks %}` (lines 91-98) — switches between auto-generated and
  inline PVT/relperm/density.

Neither references `spec.scenario`. The 8 scenarios reach the template through
`ModelSpec` fields the extractor mutates.

#### Refactor: Option A (block markers + dispatch scaffolding)

Add `{% block %}` markers to `base.j2` only at the points where a scenario
legitimately overrides layout. The other six scenarios never need a per-scenario
child — they continue to use `base.j2` unchanged, because the differences they
need are already in `ModelSpec` by the time the template renders.

Three options were considered:

- **Option A (recommended): block markers + forward scaffolding.** Add
  `{% block %}` markers to `base.j2` at the PVDG block, the EQUIL block,
  and the schedule tail. Write zero scenario children for v1. The template
  loader tries `scenarios/<scenario>.j2` first, falls back to `base.j2` for
  all eight. `extract.py` stays the source of truth for well selection,
  perm arrays, schedule events, EQUIL pressures, and every other piece of
  scenario logic. The change to the deck output is zero — golden files
  prove it. The block markers are forward-looking scaffolding: they make
  future per-scenario layout changes possible without a second refactor.
- **Option B (rejected): move well selection into templates.** Move the
  `wells = [...]` builder calls out of `extract.py` into per-scenario
  templates. Re-implementing 5-spot corner geometry, WAG injector/producer
  pair, gas-cap oil-zone-only completion (`extract.py:401-410`), and the
  SPE1-style injector/producer pair in Jinja2 — including unit-system-aware
  depth math from `_compute_field_context` / `_compute_metric_context`
  (`builder.py:165-303`). The byte-identical contract becomes much harder
  to hold.
- **Option C (rejected): move all scenario logic out of `extract.py`.**
  Same reasoning as B but bigger — also moves the perm contrast (multilayer),
  the timestep lists (buildup, default monthly-then-quarterly), and the
  schedule event construction. `extract.py` and the templates would now
  describe the same scenarios twice, with no single source of truth.

The byte-identical gate in the design (`before and after the split, the deck
generated for each existing scenario must be identical`) makes Options B and C
unjustifiable. Option A keeps placement in the only module with an existing
test suite (`tests/unit/test_scenario_templates.py` and
`tests/integration/test_dataset_validation.py`).

#### Concrete plan for Option A

**Step 1 — Golden fixtures, written first.** For each of the 8 scenarios in
`ScenarioType`, render the current `base.j2` once and save the output as a
golden file under `tests/fixtures/golden/<scenario>.DATA`. Use the same
descriptions the integration test already enumerates
(`tests/integration/test_dataset_validation.py:25-41`). The golden-file test is
a new test in `tests/unit/` (e.g. `test_golden_decks.py`) that calls
`build_deck(desc)` for each scenario, compares the output bytes against the
fixture, and fails on any drift. The contract: 8 scenarios × 1 golden file
each, byte-equality, written **before** any template change. The git commit
for the golden fixtures must precede the commit that adds block markers.

**Step 2 — Add `{% block %}` markers to `base.j2`.** Three named blocks, each
at a single point:

- `{% block pvdg %}` at line 145, wrapping the existing
  `{% if pvdg_rows %}...{% else %}...{% endif %}` PVDG table block. Default
  content stays as the methane-like fallback (lines 150-159) so `base.j2`
  rendered in isolation still produces the SPE1 default.
- `{% block equil %}` at line 179, wrapping the single `EQUIL` line (line 180).
  Default content is the existing EQUIL emission.
- `{% block schedule_tail %}` at line 283, wrapping the initial `TSTEP` block
  plus the `{% for event in schedule_events %}` loop (lines 283-306). Default
  content is the existing schedule emission including the END.

No other markers. The PVTW/ROCK/SWOF/SGOF/DENSITY/PVTO block (lines 91-175)
stays as a single unblocked region — none of the 8 scenarios change relperm
or PVTO, only PVDG. The WELSPECS/COMPDAT/WCONPROD/WCONINJE region (lines
261-281) stays as a single unblocked region — well layout is data-driven from
`spec.wells`. The SUMMARY block (lines 186-248) stays unblocked — it iterates
the well list, which is already scenario-correct.

**Step 3 (skipped for v1) — write zero scenario overrides.** No child template
files are written. The block markers' default content is byte-identical to
the current text, so v1 ships with the dispatch scaffolding in place and no
behavior change. Re-evaluate only if a future per-scenario layout change
breaks the byte-identical contract and the data-driven switches reach their
limit.

**Step 4 — Template loader change in `builder.py`.** Replace the two hard-coded
`env.get_template("base.j2")` calls (lines 348 and 386) with a helper:

```
def _load_scenario_template(env, scenario: str):
    name = f"scenarios/{scenario}.j2"
    try:
        return env.get_template(name)
    except jinja2.TemplateNotFound:
        return env.get_template("base.j2")
```

The `scenarios/` subdirectory is created as an empty directory (with a
`.gitkeep`) so Jinja2's `FileSystemLoader` resolves the lookup predictably. No
new dependency. No loader reconfiguration — `FileSystemLoader` already searches
the configured template directory recursively for the `scenarios/` subpath.
Re-run the golden-file test from Step 1; it must pass with zero changes.

**Step 5 — Order of changes, locked in.** Git history must read in this order:

1. Add `tests/unit/test_golden_decks.py` and the 8 fixtures under
   `tests/fixtures/golden/`. Run it; record the 8 byte-exact outputs as the
   committed fixtures. This commit is the contract.
2. Add the three `{% block %}` markers to `base.j2` with their default content
   equal to the current text. The golden test must still pass without fixture
   changes — this is the proof that the markers are no-ops.
3. Add the `_load_scenario_template` helper in `builder.py` and rewire the two
   call sites. The golden test must still pass — this is the proof that the
   fallback path is equivalent.
4. (Optional, future) Add `scenarios/<name>.j2` only when a real layout
   change is needed.

#### What this does NOT do

- **Does not split `base.j2` into 8 (or 9) standalone files.** That would
  duplicate the shared ~80% (grid init, PROPS, SUMMARY, WELSPECS, COMPDAT,
  WCONPROD, WCONINJE, schedule, END) and give eight places to miss a PVT fix.
  The whole point of block markers is to share the common body.
- **Does not move well selection logic out of `extract.py`.** The 5-spot
  corner geometry (`extract.py:328`), WAG injector/producer pair (lines
  366-386), gas-cap oil-zone-only completion (lines 401-410), SPE1-style
  injector/producer pair (lines 285-308), buildup single-bottom-layer
  producer (lines 452-462), and multilayer all-layers producer (lines
  475-483) all stay in `extract.py`. They are tested as Python in
  `tests/unit/test_scenario_templates.py`.
- **Does not move per-layer permeability logic out of `extract.py`.** The
  MULTILAYER contrast (lines 469-472) and BUILDUP low-perm override (lines
  447-449) stay in the extractor. The template iterates whatever
  `reservoir.permx` it is given.
- **Does not move schedule event construction out of `extract.py`.** The WAG
  quarter-cycle generator (lines 510-528) and the buildup stop-and-restep
  event (lines 532-537) stay in the extractor. The template's
  `{% for event in schedule_events %}` loop (lines 288-306) is already
  data-driven.
- **Does not move PVDG / EQUIL / pvt_blocks defaults out of `base.j2`.** The
  inline defaults at lines 100-159 (PVTW, ROCK, SWOF, SGOF, DENSITY, PVDG,
  PVTO) and line 180 (EQUIL) stay in `base.j2`. Per-scenario children
  override the blocks; they do not own the defaults.
- **Does not change the `ScenarioType` enum or the public `ModelSpec` API.**
  The 8 enum values stay; the new code only reads `spec.scenario.value` to
  build the child-template filename.
- **Does not pursue Options B or C.** Both are explicitly ruled out for the
  reasons in the option analysis above.

#### Risks

1. **Block-marker whitespace drift.** Adding `{% block %}` and `{% endblock %}`
   tags around the existing PVDG, EQUIL, and schedule tail regions will add or
   remove blank lines unless `trim_blocks=True` and `lstrip_blocks=True`
   (already set in `_get_template_env` at `builder.py:22-23`) handle them
   perfectly. The golden-file test from Step 1 is the only way to catch this.
   Mitigation: every block marker must be placed on a line by itself, with the
   surrounding blank lines preserved exactly. If whitespace drift appears in
   Step 2, the fix is to re-record the fixtures, not to disable the trim flags.
2. **`scenarios/` directory not committed.** Step 4 creates
   `opm_ai/builder/templates/scenarios/` as a new directory. If the directory
   is empty and the commit does not include a `.gitkeep` or other tracked
   file, the directory will not exist in a fresh checkout, and
   `_load_scenario_template` will still resolve `base.j2` correctly (Jinja2's
   `TemplateNotFound` is what we catch), so this is a non-issue for behavior.
   But it is a trap for the next contributor: they will add
   `scenarios/foo.j2`, commit it, and expect the loader to find it. The
   directory needs a `.gitkeep` so the existence is obvious. Mitigation:
   commit the `.gitkeep` in the Step 4 commit, with a one-line README
   explaining the dispatch contract.
3. **Golden fixtures become a maintenance hazard.** Once the 8 byte-exact
   fixtures are committed, any future change to `base.j2` (even a single-space
   tweak) will fail the test. That is the point of the test, but it also means
   a well-intentioned whitespace cleanup will produce 8 red test failures and
   require re-recording all 8 fixtures. The test should be marked
   `@pytest.mark.slow` (matching the existing integration test at
   `test_dataset_validation.py:61`) so it does not run on every save, and
   re-recording should be a single command documented in the test module's
   docstring. The integration test in `test_dataset_validation.py:25-41`
   already enumerates the 14 scenario descriptions, so the golden test should
   source its descriptions from the same list to avoid drift.

### 3.4 Keyword catalogue from the fixture decks

**Licence finding that determined the source.** The requested repo
(OPM/opm-flow-editor-support) ships an excellent catalogue — 3161 keywords with
sections, parameters, expected column counts and examples — but it is
**GPL-3.0**, and so is opm-common, its upstream. OPM-AI is MIT. Only
opm-reference-manual is MIT-compatible (CC-BY 4.0), and it is a large
LibreOffice-XML corpus needing a substantial parser. The GPL clone made during
investigation was deleted; no GPL text entered the tree.

Source instead: the 722 opm-tests deck files already in `tests/fixtures/`
(measured 2026-08-04; the original 1090 figure was from an earlier tree
snapshot). A scan found **1079 distinct keywords** appearing as section-style
tokens. These are facts about data already in the repository.

A build-time script emits `opm_ai/linter/keywords.json`: keyword name, sections
observed in, and observed argument shape. Consumers:

- Monaco autocomplete and hover in DeckEditor.
- A new `unknown_keyword` linter rule with `difflib.get_close_matches` for "did
  you mean WELSPECS?".

**The generator MUST reuse `opm_ai.linter.deck.Deck`, not a fresh regex.**
Learned the hard way while scoping this: an ad-hoc scanner using
`^([A-Z][A-Z0-9_]{1,7})$` to find section headers mis-attributed keywords in 722
fixture decks, because real decks write banner headers like
`GRID    ================================`. The strict anchor missed those, so
every keyword after one was credited to the *previous* section — producing false
readings such as `INIT` appearing in RUNSPEC (3 times) and `TOPS` in RUNSPEC.
`Deck` handles this correctly via case-insensitive word-boundary matching:
on `co2store/CO2STORE_GASWAT.DATA` it finds all 7 sections where the naive regex
found the wrong ones.

**Record frequency, not just presence.** Even with correct parsing, a keyword
legitimately appears in several sections (`NOECHO` and `ECHO` appear in six
each). A rule shaped "keyword X must be in section Y" would fire on valid decks.
The catalogue stores per-section counts so a rule can distinguish "never seen
here" from "seen once in 700 decks".

**The rule ships as a WARNING, never an ERROR.** The linter is calibrated to zero
false positives across 133 fixtures, and an ERROR blocks the builder
(`opm-ai-linter-strictness`). A catalogue derived from observed decks is by
construction incomplete — a valid keyword no fixture happens to use would be
flagged. Warning severity makes that a hint instead of a blocked deck.

Honest limitation to state in the docs: this covers what your decks use, not the
full documented keyword set. A keyword absent from opm-tests is absent here.

## Risks

- **Markdown rendering** is the widest blast radius in Stage 1: it changes how
  every explanation and every assistant message displays, and adds a Tailwind
  plugin that alters generated CSS. Check both themes in a browser.
- **Template split (3.3)** touches deck generation, which feeds the linter and
  the simulator. Mitigated by golden-file byte-equality tests written first. If
  any scenario's output shifts, the split is wrong.
- **Unknown-keyword rule (3.4)** could produce false positives on valid decks.
  Mitigated by WARNING severity and by running the full 133-fixture calibration
  set before commit.
- **ResInsight (3.1)** spawns a detached 91MB GUI. Mitigated by the loopback
  gate, the one-process-per-job guard, and never blocking the request on it.
- Stage 2 is presentational; the only real risk is shrinking the 3D container,
  which the design explicitly forbids.

## Verification at every stage

`pytest` (332 passed / 2 skipped today), `npm test` (19 checks), `npm run build`,
`tsc -b`, and for UI stages a browser check on both ports. `tsc -b` and eslint
both passed while the 3D viewer drew nothing, so browser confirmation is not
optional for visual changes; `frontend/src/components/viewer3d/probe/` exists for
exactly that reason.

Stage 1 additionally needs a manual chat check with a tool-calling message, since
that is the reported symptom and no automated test currently drives a live WS
tool call.

---

## Update: Stage 3.4 — ERM catalogue added (2026-08-04)

The licence analysis above correctly rejected the GPL `opm-flow-editor-support`
catalogue. The reasoning that also rejected `opm-reference-manual` ("a large
LibreOffice-XML corpus needing a substantial parser") does not apply to the
HTML version of the manual shipped at `tests/eclipse/ecl_rm/`: well-formed
DITA HTML with a flat `<table class="flagtable">` for section placement and
`<ol><li>` for parameter items. The parser (`scripts/build_keyword_rm_catalogue.py`)
is ~240 lines of stdlib regex. It produces 1,916 keywords, far more than the
1,079 the fixture scan finds, with the following additional fields per keyword:

- `sections_authoritative` — from the flagtable (the ECLIPSE 100 column).
- `parameter_count_authoritative` — `<li>` items in the parameter list.
- `description` — first `<p>` after the flagtable, truncated to 400 chars.

The L016 rule's `_get_catalogue()` now unions both files. Calibration invariant
preserved: zero L016 hits across the 730-deck calibration set, same as the
fixture-only baseline. The union can only add recognition, never remove it.

Monaco autocomplete (`GET /api/keywords`, `frontend/src/components/opmCompletions.ts`)
uses the union, so suggestions are available for keywords the fixtures don't
happen to use (advanced compositional, thermal, polymer, etc.).

Honest limitation: the ERM documents Schlumberger ECLIPSE; OPM Flow 2026.04
implements a subset. A keyword in the ERM but rejected by Flow will be
autocompleted but flagged by the linter only if Flow's error surfaces in the
deck text. To detect Flow-specific rejections, a future stage could run the
binary against a synthesised deck for each unknown keyword and capture the
diagnostic — but that requires `flow` in CI.

Scripts:
- `scripts/build_keyword_rm_catalogue.py` — regenerate `keywords_rm.json`.
- `scripts/build_keyword_catalogue.py` — regenerate `keywords.json`.

Commit history for this update: `f3b955e` (catalogue + union),
`fad8cd0` (autocomplete + endpoint).

---

## Update: Stage 3.5 — per-keyword parameter extraction (planned 2026-08-04)

Stage 3.4 added `parameter_count_authoritative` (count of `<li>` in first
`<ol>`) but not the per-parameter names. The natural follow-on is to
extract each `<li>` as `{name, brief}`:

- `name` — the text before the first nested block element (`<p>`, `<table>`,
  `<div>`, `<ul>`, `<ol>`, `<pre>`).
- `brief` — the text of the first `<p>` child, truncated to 140 chars.

For keywords with no `<ol>` (e.g. DIMENS, which describes its three
parameters in prose), `parameters: []` and the existing `description`
field covers them.

These `parameters` flow through three layers:

1. **Parser**: `scripts/build_keyword_rm_catalogue.py` adds
   `parameters: list[{name, brief}]` to each keyword record and
   `parameter_names: list[str]` for cheap consumer-side use.
2. **API**: `opm_ai/api/routes/keywords.py::KeywordRecord` gains
   `parameters: list[ParameterItem]`. `/api/keywords` surfaces them.
3. **Frontend**: `frontend/src/components/opmCompletions.ts` uses the
   first parameter's `brief` (or `description`) as the Monaco hover
   `documentation` field. Trigger characters and `sectionLabel` rules
   unchanged.

Acceptance:
- WELSPECS record has 18 parameters, first name = "Well name".
- EQUIL record has 7 parameters (one per `<li>`).
- DIMENS record has `parameters: []`.
- L016 calibration invariant preserved: zero L016 hits across 730 fixtures.
- npm test passes, pytest passes, tsc clean.

---

## Update: Stage 3.5 — DONE (2026-08-04)

Two parallel commits implementing per-keyword parameter extraction:

- `571f2e4` (parser): `_parse_parameters(html)` extracts each `<li>` as
  `{name, brief}`. name = text before first nested block element
  (`<p>`, `<table>`, `<div>`, `<ul>`, `<ol>`, `<pre>`); brief = first
  `<p>` child, truncated to 140 chars. Regenerated
  `keywords_rm.json` is 2.32 MB (was 18 KB) with `parameters` and
  `parameter_names` fields per record. WELSPECS = 18 params, EQUIL =
  11, DIMENS = `[]` (prose-only).
- `b90549e` (consumer): `ParameterItem(name, brief)` Pydantic model,
  threaded through `_load_catalogue()`. Frontend `opmCompletions.ts`
  builds `documentation` field as `"name — brief"` lines (truncated to
  600 chars), falling back to description when parameters is empty.

Acceptance verified:
- 446 passed, 2 skipped (was 440, +6: 4 parser + 2 API).
- 11 opmCompletions checks (was 9, +2).
- tsc clean.
- Live `GET /api/keywords` returns 2634 records with parameters.
- L016 calibration invariant preserved: zero hits across 730 fixtures.

Live API count breakdown: 1916 ERM + 1079 fixture - 361 overlap = 2634
unique keywords served. WELSPECS, COMPDAT, PVTO, EQUIL, etc. all now
have per-parameter hover documentation in Monaco.
