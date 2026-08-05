"""Unit tests for the Jinja2 template dispatch in `builder.py`.

`_load_scenario_template(env, scenario)` (builder.py:27-44) tries the
per-scenario child `scenarios/<scenario>.j2` first and falls back to
`base.j2`. These tests exercise the dispatch logic itself, independently
of the byte-identical golden renderers in `tests/unit/test_golden_decks.py`
(which only ever see the fallback path on a fresh checkout).

Three contracts:
- (a) Every ScenarioType resolves to the same bytes as `base.j2` when no
      child template exists.
- (b) When a child `{% extends "base.j2" %}` template exists, the loader
      returns it and the child's block override actually flows through.
- (c) `TemplateNotFound` (the only path that falls back) is the only
      exception caught. A syntax error in a child template is a bug and
      must surface, not silently degrade to base.j2.

Tests marked `@pytest.mark.unit` only; no `flow` binary required.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from jinja2 import FileSystemLoader, TemplateNotFound

from opm_ai.builder.builder import (
    _compute_template_context,
    _get_template_env,
    _load_scenario_template,
)
from opm_ai.builder.models import ModelSpec, ScenarioType


# One canonical ModelSpec per ScenarioType — small enough to stay a unit
# test (no `flow`, no LLM, no description parsing). The spec drives
# `_compute_template_context` exactly the way the call sites at
# builder.py:367 / builder.py:405 do.
def _spec_for(scenario: ScenarioType) -> ModelSpec:
    spec = ModelSpec(scenario=scenario)
    return spec


@pytest.mark.unit
@pytest.mark.parametrize("scenario", list(ScenarioType))
def test_fallback_renders_identical_to_base_for_every_scenario(scenario):
    """With no `scenarios/<name>.j2` present, the dispatch resolves to
    `base.j2` and produces byte-identical output for every ScenarioType.

    Uses `_compute_template_context(spec)` (the same context builder used
    at the call sites builder.py:367 and builder.py:405) so render output
    is comparable to a direct `env.get_template('base.j2').render()`.
    """
    env = _get_template_env()

    loaded = _load_scenario_template(env, scenario.value)
    base = env.get_template("base.j2")

    assert loaded.name == base.name, (
        f"fallback path should resolve to base.j2, got {loaded.name!r}"
    )
    # Both templates must be the actual base.j2 file on disk.
    assert Path(loaded.filename).resolve() == Path(base.filename).resolve()

    context = _compute_template_context(_spec_for(scenario))
    deck_via_dispatch = loaded.render(**context)
    deck_via_base = base.render(**context)

    assert deck_via_dispatch == deck_via_base, (
        f"dispatch output must equal base.j2 output for {scenario.value}"
    )


@pytest.mark.unit
def test_child_template_extends_base_and_overrides_block(tmp_path, monkeypatch):
    """When `scenarios/<name>.j2` exists, the loader returns it and the
    child's `{% block %}` override flows through to the rendered deck.

    We re-point the environment's loader at `tmp_path` so it can see a
    freshly laid-out tree containing `base.j2` and `scenarios/<name>.j2`.
    The real `base.j2` is copied verbatim (it still defines `equil`); the
    child only overrides the `equil` block.
    """
    base_src = Path(_get_template_env().loader.searchpath[0]) / "base.j2"
    assert base_src.is_file(), f"base.j2 missing at {base_src}"

    # Lay out: tmp_path/base.j2  and  tmp_path/scenarios/test_child.j2
    (tmp_path / "scenarios").mkdir()
    shutil.copy(base_src, tmp_path / "base.j2")
    child_name = "test_child"
    (tmp_path / "scenarios" / f"{child_name}.j2").write_text(
        '{% extends "base.j2" %}\n'
        '{% block equil %}EQUIL-OVERRIDE /\n{% endblock %}\n'
    )

    real_env = _get_template_env()
    # Swap the loader onto the real env; same trim/lstrip settings.
    new_loader = FileSystemLoader(str(tmp_path))
    monkeypatch.setattr(real_env, "loader", new_loader)

    loaded = _load_scenario_template(real_env, child_name)

    # The dispatch must have picked up the child, not the base.
    assert loaded.name == f"scenarios/{child_name}.j2", (
        f"expected child template, got {loaded.name!r}"
    )

    # Render the child against the same context the call sites use.
    context = _compute_template_context(_spec_for(ScenarioType.DEPLETION))
    rendered = loaded.render(**context)

    # The child's `{% block equil %}` override must appear verbatim.
    assert "EQUIL-OVERRIDE" in rendered
    # And the child must still inherit everything else from base.j2:
    # base always emits at least these top-level sections.
    for marker in ("RUNSPEC", "GRID", "PROPS", "SCHEDULE"):
        assert marker in rendered, (
            f"child template should still inherit {marker} from base.j2"
        )


@pytest.mark.unit
def test_syntax_error_in_child_template_propagates(monkeypatch):
    """A Jinja2 syntax error in a child template must NOT fall back to base.

    F9.1 audit: the old handler was `except Exception`, which silently
    swallowed `TemplateSyntaxError` and produced a wrong deck with no
    warning. The narrowed handler is `except TemplateNotFound`, so a
    syntax error in `scenarios/<name>.j2` propagates and the build
    fails loudly instead of producing garbage.
    """
    from jinja2 import TemplateSyntaxError

    env = _get_template_env()

    def fake_get_template(name):
        if name != "base.j2":
            raise TemplateSyntaxError(
                message="simulated child syntax error",
                lineno=1,
                name=name,
                filename=f"scenarios/{name}",
            )
        return env.loader.load(env, name)

    monkeypatch.setattr(env, "get_template", fake_get_template)

    with pytest.raises(TemplateSyntaxError):
        _load_scenario_template(env, "wag")


@pytest.mark.unit
def test_template_not_found_path_falls_back_to_base():
    """`TemplateNotFound` (the common case for a missing scenarios/ dir)
    resolves to `base.j2` via the catch clause.
    """
    env = _get_template_env()
    # No child template for this name on a fresh checkout.
    with pytest.raises(TemplateNotFound):
        env.get_template("scenarios/__definitely_missing__.j2")

    loaded = _load_scenario_template(env, "__definitely_missing__")
    assert loaded.name == "base.j2"
