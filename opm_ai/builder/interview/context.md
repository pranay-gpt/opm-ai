# builder/interview — reservoir-context interview and file ingestion

Pure Python, no HTTP and no LLM. Everything here is a function over a
`ModelSpec` and an answers dict, which is what makes the whole feature
testable without a server and reload-proof without a session store.

## Invariants

1. **Never breaks.** Every question is skippable. `build_spec` treats an
   absent-or-`None` answer as "record the declared default", so the
   terminal state always builds a lint-passing deck. There is no
   "interview hung" state to represent.
2. **Stateless.** The server holds nothing: the client owns `answers` and
   round-trips it on every call. `next_question` is a fold over a static
   catalog, so it is a pure function of `(spec, answers)`.
3. **Provenance triad only.** `extracted | defaulted | user_override`.
   Ingested file values are tagged `extracted` — they came from a source,
   which is exactly what "extracted" means. No new tags.
4. **Never mean-average.** `ReservoirSpec` is a layered box model. Data
   it cannot represent (per-cell variation, a partial BOX, per-layer
   variation in a scalar field) is refused with the array named, not
   collapsed to an average that would silently change the physics.

## Files

| File | Owns |
|---|---|
| `catalog.py` | The questions. Data, not code: a frozen `Question` per entry with `applies_when`, `default`, and an `apply` that writes onto the spec. `dynamic_questions(spec)` generates the per-well block. |
| `engine.py` | `all_questions`, `next_question`, `apply_answer`, `progress`, `build_spec`. Folds the catalog; no policy of its own. |
| `rules.py` | `validate(spec)` -> findings with `block`/`warn` severity. The linter owns deck structure (L-rules); this owns spec-level semantics (R-rules). |
| `ingest.py` | `parse_paste(text)` -> patch + findings. Uses the pure-stdlib linter v2 parser. Never raises. |

## Gotchas found the hard way

- **`opm.io` is not usable here.** Not in `pyproject.toml`, the Dockerfile
  venv has no `--system-site-packages`, and a bad INCLUDE aborts the
  *process* (uncatchable). The v2 tokenizer/parser is stdlib-only and is
  the right tool anyway.
- **`FluidDescriptor` is a frozen dataclass.** A fluid answer has to
  `dataclasses.replace` the whole descriptor; `setattr` raises.
- **The v2 parser collapses a PVDG table into one record** and returns
  `DIMENS`-bearing fragments as keywords even without section headers, so
  format detection cannot lean on "is there a DIMENS" to mean "deck".
- **`finish()` must apply answers before validating.** Validating the
  pre-answer spec can never produce a block, because a skipped blocking
  question gets its default applied at build time.
- **EGRID is a result file.** It carries no petrophysics, so it is
  refused by name as an input.

## Contract with the API

`api/routes/interview.py` evaluates the callable `default` against the
spec before putting it on the wire, and unwraps `ScenarioType` to its
value — the UI receives plain JSON. A pasted/uploaded file rides along as
the `__ingest` answer key and is stripped before the dict reaches the
engine; the two features compose without the engine knowing about files.

## Future

- Per-cell property arrays in `ReservoirSpec` would need a real static
  model use case first; until then the refusal is the correct answer.
- Per-step LLM calls only if a measured gap appears that both the regex
  extractor and the parser miss.
