"""Audit v2 catalogue sections against the OPM Flow Reference Manual catalogue.

Reads opm_ai/linter/keywords_rm.json (RM-catalogue snapshot) and compares
each v2 catalogue entry's SectionName list against the RM
`sections_authoritative` field.

Prints the mismatches so a developer can decide whether to widen the
catalogue (the safe direction for false-positive mitigation).

Run from repo root: .venv/bin/python scripts/audit_catalogue_sections.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RM_PATH = REPO_ROOT / "opm_ai" / "linter" / "keywords_rm.json"


def main() -> None:
    from opm_ai.linter.v2.catalogue import get_keyword, known_keywords

    with open(RM_PATH) as f:
        rm = json.load(f)["keywords"]

    too_strict: list[tuple[str, list[str], list[str]]] = []
    too_loose: list[tuple[str, list[str], list[str]]] = []

    for name in sorted(known_keywords()):
        spec = get_keyword(name)
        if spec is None:
            continue
        spec_sections = {s.value for s in spec.sections}
        rm_spec = rm.get(name)
        if rm_spec is None:
            continue
        if isinstance(rm_spec, list):
            rm_spec = rm_spec[0]
        rm_sections = set(rm_spec.get("sections_authoritative") or [])
        if not rm_sections:
            continue

        missing = rm_sections - spec_sections
        extra = spec_sections - rm_sections
        if missing:
            too_strict.append((name, sorted(spec_sections), sorted(rm_sections)))
        elif extra:
            too_loose.append((name, sorted(spec_sections), sorted(rm_sections)))

    print(f"Catalog too strict (missing valid RM sections): {len(too_strict)}")
    for name, cat_sec, rm_sec in too_strict:
        missing = sorted(set(rm_sec) - set(cat_sec))
        print(f"  {name}: missing={missing}, catalogue={cat_sec}, RM={rm_sec}")
    print()
    print(f"Catalog too loose (has sections RM does not list): {len(too_loose)}")
    for name, cat_sec, rm_sec in too_loose:
        extra = sorted(set(cat_sec) - set(rm_sec))
        print(f"  {name}: extra={extra}, catalogue={cat_sec}, RM={rm_sec}")


if __name__ == "__main__":
    main()