# Per-scenario Jinja2 children

This directory is empty by design. The builder's `_load_scenario_template`
helper at `opm_ai/builder/builder.py` looks for `scenarios/<scenario>.j2`
first and falls back to `base.j2` if not found. Every existing scenario
produces byte-identical output through `base.j2` today (verified by
`tests/unit/test_golden_decks.py`).

## When to add a child template

Add `scenarios/<name>.j2` only when:
- a future per-scenario layout change cannot be expressed as a data
  switch in `extract.py`, AND
- the byte-identical golden test is re-recorded as part of that change.

## Format

```jinja2
{% extends "base.j2" %}

{% block pvdg %}
...your override...
{% endblock %}
```

Block names exposed by `base.j2`: `pvdg`, `equil`, `schedule_tail`.
