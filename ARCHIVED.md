# ARCHIVED BRANCH — DO NOT MERGE

This branch (`archive/linter-redesign`) is kept on origin for
historical reference only. It must never receive new commits or be
merged into `main`.

## Why

Three independent reviews of this branch found critical flaws that
made it unfit to ship:

- 5 INCLUDE-based known-good fixtures fail lint with false-positive
  ERRORs (Flow accepts them; we reject them).
- 11 of 47 specs are flagged by the calibration script as wrong.
- 61-second performance regression on `DROGON_HIST.DATA`.
- L015 rule_id collision in `linter.py`.
- L019 false-positives on UDQ-inlined FU_* declarations.
- DX/DY/DZ/PORO/PERMX spec ranges too narrow for real Eclipse values.
- EDIT operands misread as data records.

The lessons from this work are documented at
`docs/personal/LINTER_FAILED_DESIGN_LESSON.md`.

## What happened to the design

The plan was a schema-driven L2 layer co-existing with the existing
L3 rules. Reviews found the architecture was wrong at a fundamental
level: OPM decks aren't a fixed schema — they're a program with
cross-keyword references. A grammar-based parser would have been the
correct primitive, not a YAML schema.

## Guards in place

1. The branch is renamed with the `archive/` prefix.
2. A CI workflow (`.github/workflows/archive-branch-guard.yml` on
   `main`) fails any PR targeting an `archive/*` branch.
3. The original `linter-redesign` name has been deleted from origin.

If you need to read or reference this work, `git checkout
archive/linter-redesign` works as normal. To start a new linter
redesign (v3), branch off `main` — do not extend this one.