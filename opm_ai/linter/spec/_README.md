# Spec schema for Layer 2 validator

This directory contains hand-curated keyword specifications consumed by
`opm_ai/linter/validator.py` (Phase 3). Each YAML file corresponds to
one `.DATA` section (RUNSPEC, GRID, EDIT, PROPS, REGIONS, SOLUTION,
SUMMARY, SCHEDULE) and lists the keywords with structural validation
data.

## Schema (per keyword entry)

```yaml
KEYWORD:
  section: RUNSPEC                # one of: RUNSPEC, GRID, EDIT, PROPS,
                                  # REGIONS, SOLUTION, SUMMARY, SCHEDULE
  required: true                  # boolean; missing keyword -> ERROR
  repeated: false                 # can the keyword appear multiple times?
  items:
    - name: max_wells             # human-readable parameter name
      type: int                   # int | float | string | keyword | flag
      default: null               # default value if item is omitted
                                  # (cross-checked against keywords_rm.json
                                  # parameters[].brief)
      range: [1, 100000]          # inclusive [min, max]; null = no range
                                  # strict_min / strict_max for half-open
  mutually_exclusive_with:        # list of keyword names that must NOT
                                  # appear in the same section
    - OIL
    - GAS
```

## Validation rules

For each parsed keyword record in the deck:

1. **Required**: if `required: true` and the keyword is absent from the
   section, emit `LintIssue(severity=ERROR, rule_id="L2.<KEYWORD>.REQUIRED")`.
2. **Item count**: if the deck provides a number of items that doesn't
   match `len(items)`, emit ERROR (with strict count) or WARNING (with
   "expected up to N items, got M").
3. **Range**: if `range` is set and the item is numeric, emit ERROR if
   out of range. Strict bounds via `strict_min` / `strict_max`.
4. **Type**: if the item's value can't be parsed as `type`, emit
   WARNING. (Most parsers will silently accept numerics as strings; we
   only flag obvious malformations.)
5. **Mutually exclusive**: if any keyword in
   `mutually_exclusive_with` is also present in the section, emit ERROR.
6. **Repeated**: if `repeated: false` and the keyword appears more than
   once in the section, emit WARNING.

## What is NOT in the schema

- **Per-item descriptions**. The OPM Flow Reference Manual has them as
  prose; we link to it in the explainer (Phase 5) but don't try to
  inline it.
- **Cross-section rules**. Things like "DIMENS in RUNSPEC must match
  grid extent in GRID" are L3 work — they need cross-record reasoning
  that the per-record validator can't do.
- **Recognition** (i.e., "is this token a known keyword?"). That's L016,
  backed by `corpus_stats.json`. Spec layer doesn't own it.

## Status as of 2026-08-08

- Schema documented.
- One example: `runspec.yaml` with WELLDIMS.
- Other sections to follow in Phase 2.

## How to extend

1. Add the keyword to the appropriate `<section>.yaml`.
2. Add a positive + negative test in `tests/unit/test_linter_spec.py`.
3. If defaults differ from what `keywords_rm.json` says, cross-check
   against `flow --enable-dry-run=true` acceptance of a known-good deck
   that omits the defaulted items.
4. Update `LINTER_REDESIGN_TASKS.md` Phase 2 checkboxes.
