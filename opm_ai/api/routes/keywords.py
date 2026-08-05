"""Keyword catalogue route: GET /api/keywords -> merged catalogue.

Returns the union of the fixture-derived observational catalogue
(`opm_ai/linter/keywords.json`) and the Eclipse Reference Manual-derived
authoritative catalogue (`opm_ai/linter/keywords_rm.json`). Used by the
Monaco editor's autocomplete and hover provider.

The shape is a flat array of records sorted by `name`; consumers (the
frontend) can group, filter, or fuzzy-search as needed.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

_FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "linter" / "keywords.json"
_RM_PATH = Path(__file__).resolve().parent.parent.parent / "linter" / "keywords_rm.json"


class ParameterItem(BaseModel):
    """One named parameter of an ERM keyword (name + short brief)."""

    name: str
    brief: str = ""


class KeywordRecord(BaseModel):
    """One keyword in the merged catalogue."""

    name: str
    sections: list[str] = Field(
        default_factory=list,
        description="Authoritative sections from the ERM flagtable.",
    )
    sections_observed: dict[str, int] = Field(
        default_factory=dict,
        description="Per-section observation counts from fixtures.",
    )
    deck_count: int = 0
    parameter_count: int = 0
    description: str = ""
    source: str = ""
    parameters: list[ParameterItem] = Field(
        default_factory=list,
        description="Per-keyword parameter list extracted from the ERM "
        "(name + brief). Empty for fixture-only records.",
    )


class KeywordCatalogue(BaseModel):
    keyword_count: int
    keywords: list[KeywordRecord]


def _load_catalogue() -> KeywordCatalogue:
    """Union the fixture and ERM catalogues into a single KeywordCatalogue."""
    merged: dict[str, KeywordRecord] = {}

    if _FIXTURE_PATH.is_file():
        with _FIXTURE_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        for name, rec in data.get("keywords", {}).items():
            merged[name] = KeywordRecord(
                name=name,
                sections_observed=rec.get("sections_observed", {}),
                deck_count=rec.get("deck_count", 0),
                parameter_count=rec.get("first_token_count", 0),
                source="fixture",
            )

    if _RM_PATH.is_file():
        with _RM_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        for name, rec in data.get("keywords", {}).items():
            existing = merged.get(name)
            sections = rec.get("sections_authoritative", [])
            description = rec.get("description", "")
            param_count = rec.get("parameter_count_authoritative", 0)
            parameters = [
                ParameterItem(name=p.get("name", ""), brief=p.get("brief", ""))
                for p in rec.get("parameters", [])
            ]
            if existing is None:
                merged[name] = KeywordRecord(
                    name=name,
                    sections=sections,
                    parameter_count=param_count,
                    description=description,
                    source="erm",
                    parameters=parameters,
                )
            else:
                # Fixture record wins for observation; ERM fills in
                # authoritative sections + description. Calibration
                # invariant: do NOT overwrite a fixture record's
                # parameters — the fixture catalogue has no `parameters`
                # field, so this branch is a no-op there; any future
                # fixture-derived parameters would be preserved.
                existing.sections = sections or existing.sections
                existing.description = description or existing.description
                if param_count and not existing.parameter_count:
                    existing.parameter_count = param_count
                if not existing.parameters:
                    existing.parameters = parameters
                existing.source = "fixture+erm"

    return KeywordCatalogue(
        keyword_count=len(merged),
        keywords=sorted(merged.values(), key=lambda r: r.name),
    )


@router.get("/keywords", response_model=KeywordCatalogue)
async def get_keywords() -> KeywordCatalogue:
    """Return the merged keyword catalogue for editor autocomplete.

    Cached per process: the catalogues are JSON files loaded once per
    server lifetime. Restart the server to pick up catalogue updates.
    """
    global _CACHE  # noqa: PLW0603  (process-local cache; documented)
    cache = globals().get("_CACHE")
    if cache is None:
        cache = _load_catalogue()
        globals()["_CACHE"] = cache
    return cache