"""Spec loader for Layer 2 validator (Phase 3).

This module loads the hand-curated YAML specs from `opm_ai/linter/spec/`
and exposes them as Pydantic models. It is the input side of the L2
validator pipeline. Phase 0 ships this loader + one example spec
(WELLDIMS) to validate the schema; Phase 3 wires it into
`linter.lint_deck`.

The loader is deliberately dumb:
- Reads every `*.yaml` file in the spec directory (excluding `_README.md`
  and any dotfile).
- Each file is a dict of keyword -> Spec.
- Multiple files are merged into one dict keyed by keyword.
- Validation: Pydantic enforces field types.

If a YAML file is malformed, this module raises at import time. Phase 0
needs the loader to fail fast so we can iterate on the schema before
writing the validator.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


ItemType = Literal["int", "float", "string", "keyword", "flag"]


class SpecItem(BaseModel):
    """One parameter of a keyword (item in the .DATA record)."""

    name: str
    type: ItemType
    default: Optional[float | int | str] = None
    range: Optional[tuple[float | int, float | int]] = None
    # Strict bounds for half-open intervals. Default None means inclusive.
    strict_min: Optional[bool] = None
    strict_max: Optional[bool] = None

    @field_validator("range")
    @classmethod
    def _validate_range(cls, v):
        if v is None:
            return v
        if len(v) != 2:
            raise ValueError(f"range must be [min, max], got {v!r}")
        if v[0] > v[1]:
            raise ValueError(f"range minimum > maximum: {v!r}")
        return tuple(v)


class KeywordSpec(BaseModel):
    """Spec for one keyword in one section."""

    name: str
    section: Literal[
        "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
        "SOLUTION", "SUMMARY", "SCHEDULE",
    ]
    required: bool = False
    repeated: bool = False
    items: list[SpecItem] = Field(default_factory=list)
    mutually_exclusive_with: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _uppercase_name(cls, v):
        if not v.isupper():
            raise ValueError(f"keyword name must be uppercase, got {v!r}")
        return v


def load_spec(spec_dir: Path) -> dict[str, KeywordSpec]:
    """Load all YAML spec files in `spec_dir`, merge into one dict.

    Args:
        spec_dir: Path to the directory containing `runspec.yaml`,
            `grid.yaml`, etc. Excludes `_README.md` and dotfiles.

    Returns:
        Dict keyed by uppercase keyword name, value is KeywordSpec.

    Raises:
        FileNotFoundError: if spec_dir doesn't exist.
        yaml.YAMLError: on malformed YAML.
        pydantic.ValidationError: on malformed schema.
    """
    if not spec_dir.exists():
        raise FileNotFoundError(f"spec dir does not exist: {spec_dir}")

    merged: dict[str, KeywordSpec] = {}
    for path in sorted(spec_dir.glob("*.yaml")):
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a YAML mapping, got {type(data).__name__}")
        for keyword, raw in data.items():
            if keyword.startswith("_"):
                # Convention: leading-underscore keys are reserved for
                # YAML-level metadata; ignore them.
                continue
            spec = KeywordSpec(name=keyword, **raw)
            if spec.name in merged:
                raise ValueError(f"duplicate keyword spec: {spec.name!r} (in {path})")
            merged[spec.name] = spec
    return merged


__all__ = ["KeywordSpec", "SpecItem", "load_spec"]
