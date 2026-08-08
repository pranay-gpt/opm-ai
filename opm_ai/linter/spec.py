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
    notes: list[str] = Field(default_factory=list)

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
    """Spec for one keyword in one section.

    The `min_items` and `max_items` fields are computed from the
    `items` list when not specified explicitly:

    - `min_items` defaults to 1 (the keyword must have at least one
      record).
    - `max_items` defaults to `len(items)` (the full schema).

    For keywords like WELLDIMS where some items have a default and
    can be omitted, set `min_items` lower than `len(items)` (e.g.
    `min_items: 1`) so a deck that supplies only 4 of the 12 items
    is accepted; items 5-12 default to 0.

    `min_items == max_items == len(items)` enforces the strict count
    (e.g. DIMENS, which must have exactly 3 items).
    """

    name: str
    section: Literal[
        "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS",
        "SOLUTION", "SUMMARY", "SCHEDULE",
    ]
    required: bool = False
    repeated: bool = False
    items: list[SpecItem] = Field(default_factory=list)
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    # When True, the L2.item_count check is skipped entirely (used for
    # keywords whose item count is data-dependent, e.g. DX/DY/DZ/PORO
    # where the count must equal nx*ny*nz per the L003 cross-rule).
    skip_item_count: bool = False
    # When True, the L2 layer promotes item_count and range issues
    # from INFO to WARNING for this spec. Set after the spec's bounds
    # have been verified against real fixtures. Required-keyword
    # absence is ERROR unconditionally.
    calibrated: bool = False
    mutually_exclusive_with: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def effective_min_items(self) -> int:
        """Minimum number of items this keyword accepts."""
        if self.min_items is not None:
            return self.min_items
        return 1  # at least one item; the keyword record exists.

    @property
    def effective_max_items(self) -> int:
        """Maximum number of items this keyword accepts.

        Defaults to len(items); spec authors can lower this for
        keywords that accept a prefix (e.g. WELLDIMS: max_items: 12
        but min_items: 1 because items 5-12 default to 0).
        """
        if self.max_items is not None:
            return self.max_items
        return len(self.items)

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
