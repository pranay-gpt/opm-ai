"""File/paste ingestion: parse keyword exports into spec patches.

Uses the repo's pure-stdlib linter v2 tokenizer/parser (opm.io is not
importable in the app venv and aborts the process on a bad INCLUDE).
Uniform and per-layer data only: genuine per-cell variation is refused
with the array named rather than silently mean-averaged. Never raises.
"""

import re
from dataclasses import dataclass, field

from opm_ai.builder.models import ModelSpec

# Keywords a bare GRDECL fragment can start with (no section headers).
_GRDECL_PROPS = {
    "PORO", "PERMX", "PERMY", "PERMZ", "NTG", "ACTNUM", "TOPS",
    "DX", "DY", "DZ", "DXV", "DYV", "DZV", "COORD", "ZCORN",
}
# BOX scopes an array; it is not itself a property, so a paste that starts
# with BOX is a fragment (the following PORO/PERMX carries the data).

# Section keywords indicating a full deck. DIMENS is deliberately NOT here:
# a bare GRDECL fragment that happens to carry DIMENS (PORO + DIMENS) is still
# a fragment, not a deck - a deck needs a real section header.
_SECTION_KEYWORDS = {
    "RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS", "SOLUTION",
    "SUMMARY", "SCHEDULE",
}

# Arithmetic keywords we do not evaluate. Sniffed as a fragment so the
# refusal message is produced rather than "unrecognized".
_ARITHMETIC_KEYWORDS = {"EQUALREG", "EQUALS", "ADD", "MULTIPLY", "MULTIREGT", "COPY"}

# PVT table keywords.
_TABLE_KEYWORDS = {"SWOF", "SGOF", "PVTO", "PVDO", "PVTW", "PVDG"}

# Result-file signatures (EGRID etc.) - rejected with a clear message.
_RESULT_FILE_HINTS = ("EGRID", "FEGRID", "GOCAD", "TSURF", "INIT", "UNRST")

# Array keywords -> the ReservoirSpec field they feed.
_ARRAY_FIELDS = {
    "PORO": "porosity",
    "PERMX": "permx", "PERMY": "permy", "PERMZ": "permz",
    "DX": "dx", "DY": "dy", "DZ": "dz", "TOPS": "top_depth",
}


@dataclass
class IngestResult:
    """Outcome of parsing one paste/upload.

    patch: flat dict keyed by ReservoirSpec field names (porosity, dx, ...)
    or special slots ("pvdg_rows"). Values are FIELD-canonical.
    findings: human-readable notes (refusals, hints, warnings).
    detected: which format the sniff picked.
    """

    patch: dict = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    detected: str = "unknown"


def _strip_comments(text: str) -> str:
    """Strip Eclipse `--` comments line by line."""
    out = []
    for line in text.splitlines():
        idx = line.find("--")
        if idx >= 0:
            line = line[:idx]
        out.append(line)
    return "\n".join(out)


def _first_keyword(text: str) -> str | None:
    """First non-comment, non-empty token at column 0, uppercase."""
    for line in _strip_comments(text).splitlines():
        s = line.strip()
        if s:
            return s.split()[0].upper()
    return None


def _is_number(tok: str) -> bool:
    try:
        float(tok.replace("D", "E").replace("d", "e"))
        return True
    except ValueError:
        return False


def _to_float(text: str) -> float:
    """Parse a deck numeric literal: Fortran D-exponent -> E-exponent."""
    return float(text.replace("D", "E").replace("d", "e"))


def detect_format(text: str) -> str:
    """Sniff which format a paste/upload is. Returns one of:
    deck | grdecl | table | numeric_grid | unknown."""
    # Result files are rejected by their own signature keyword, not by a
    # bare substring search: "INIT" is a prefix of "initial", so any paste
    # whose header comment says "-- initial porosity estimate" would
    # otherwise be refused as an unreadable result file. Match whole tokens
    # only, and require a line to consist of nothing but that keyword - an
    # EGRID/FEGRID file opens with the file name on its own line.
    for line in text[:200].splitlines():
        if line.strip().upper() in _RESULT_FILE_HINTS:
            return "unknown"  # EGRID / result file: rejected with a message

    stripped = _strip_comments(text)
    lines = [l for l in stripped.splitlines() if l.strip()]

    # Full deck: a section keyword or DIMENS in the first ~40 lines.
    head = "\n".join(lines[:40])
    for kw in _SECTION_KEYWORDS:
        if re.search(rf"^{kw}\s*$", head, re.MULTILINE):
            return "deck"

    first = _first_keyword(text)
    # The keyword sniff runs BEFORE the numeric-grid check. A real GRDECL
    # export puts one value per line, so "PERMX\n100\n100\n100" is numeric
    # line by line; sniffing numbers first would detect it as a bare
    # numeric grid and write permeability into porosity. A genuine numeric
    # grid names no property anywhere, so it still falls through to the
    # numeric branch below. DIMENS/BOX are structural GRDECL keywords, not
    # section headers: a fragment that leads with them is still a fragment.
    if first in _GRDECL_PROPS or first in {"DIMENS", "BOX"}:
        return "grdecl"
    if first in _TABLE_KEYWORDS:
        return "table"
    if first in _ARITHMETIC_KEYWORDS:
        return "grdecl"  # refused by name in _extract_from_keywords

    # Rows of bare numbers with no keyword naming a field: a plain grid.
    # A leading non-numeric row (numpy/Petrel header) is allowed.
    def _all_numeric(rows: list[str]) -> bool:
        return len(rows) >= 2 and all(
            _is_number(tok) for line in rows for tok in line.split()
        )

    if _all_numeric(lines):
        return "numeric_grid"
    if len(lines) >= 3 and not _is_number(lines[0].split()[0]) and _all_numeric(lines[1:]):
        return "numeric_grid"

    return "unknown"


def _expand_repeat(items: list) -> list[float]:
    """Expand item pairs (text, column_count) through n*value repeats."""
    out: list[float] = []
    for item in items:
        if item.column_count > 1:
            out.extend([_to_float(item.text)] * item.column_count)
        else:
            out.append(_to_float(item.text))
    return out


def _apply_box(values: list[float], box_items: list, nx: int, ny: int, nz: int) -> list[float] | None:
    """Place boxed values into a full layer-major array.

    BOX items are I1 I2 J1 J2 K1 K2 (1-based, inclusive). Values are
    ordered i fastest, then j, then k inside the box. Returns None when the
    box does not cover the whole grid - a partial array is not usable and
    is refused rather than padded with a guessed value.
    """
    i1, i2, j1, j2, k1, k2 = (int(i.text) for i in box_items)
    n_cells = nx * ny * nz
    n_box = (i2 - i1 + 1) * (j2 - j1 + 1) * (k2 - k1 + 1)
    if n_box != n_cells:
        return None
    out = [0.0] * n_cells
    idx = 0
    for k in range(k1 - 1, k2):
        for j in range(j1 - 1, j2):
            for i in range(i1 - 1, i2):
                if idx >= len(values):
                    return None
                out[k * nx * ny + j * nx + i] = values[idx]
                idx += 1
    return out


def parse_paste(text: str) -> IngestResult:
    """text -> spec patch + findings. Never raises."""
    try:
        return _parse_paste_inner(text)
    except Exception as e:
        return IngestResult(findings=[f"Failed to parse input: {e}"], detected="unknown")


def _parse_paste_inner(text: str) -> IngestResult:
    from opm_ai.linter.v2.parser import parse_file

    fmt = detect_format(text)

    if fmt == "unknown":
        return IngestResult(
            findings=[
                "Unrecognized input format. Supported: an Eclipse-style deck "
                "(.DATA), a bare GRDECL property fragment (PORO/PERMX/...), "
                "a PVDG table, or a plain numeric grid."
            ],
            detected="unknown",
        )

    if fmt == "numeric_grid":
        return _parse_numeric_grid(text)

    if fmt == "table":
        return _parse_table(text)

    # deck / grdecl go through the v2 parser; _extract_from_keywords
    # refuses arithmetic keywords by name.
    deck = parse_file(text)
    return _extract_from_keywords(deck.all_keywords(), fmt)


def _parse_table(text: str) -> IngestResult:
    """Parse a PVT table (PVDG/PVDO/SWOF/SGOF/PVTO/PVTW).

    Table rows are newline-separated; the v2 parser collapses the whole
    table into one record, so we split the raw text on lines instead.
    """
    result = IngestResult(detected="table")
    first = _first_keyword(text)
    name = first.upper() if first else ""

    rows: list[list[str]] = []
    for line in _strip_comments(text).splitlines():
        s = line.strip()
        if not s:
            continue
        head = s.split()[0].upper()
        if head in _TABLE_KEYWORDS:
            continue
        if s.endswith("/"):
            s = s[:-1].strip()
        toks = s.replace(",", " ").split()
        if toks and all(_is_number(t) for t in toks):
            rows.append(toks)
        elif toks:
            result.findings.append(
                f"Row {rows and len(rows) + 1 or 1} of {name} is not numeric."
            )

    if not rows:
        result.findings.append(f"No numeric rows found in {name or 'table'}.")
        return result

    if name == "PVDG":
        result.patch["pvdg_rows"] = ["\t".join(r) for r in rows]
    else:
        result.patch[f"{name.lower()}_rows"] = ["\t".join(r) for r in rows]
    return result


def _extract_from_keywords(keywords: list, fmt: str) -> IngestResult:
    result = IngestResult(detected=fmt)
    patch: dict = result.patch

    # Refuse arithmetic keywords first: they modify properties by region
    # and must be flattened to explicit values before ingestion.
    for kw in keywords:
        if kw.header_token.text.upper() in _ARITHMETIC_KEYWORDS:
            result.findings.append(
                "This file modifies properties by region (EQUALREG/ADD/"
                "MULTIPLY/COPY); flatten it to explicit values first."
            )
            return result

    dimens: list[int] | None = None
    arrays: dict[str, list[float]] = {}
    box_items: list | None = None

    for kw in keywords:
        name = kw.header_token.text.upper()
        items = [i for r in kw.records for i in r.items]

        if name == "DIMENS":
            try:
                dims = [_to_float(i.text) for i in items[:3]]
                if len(dims) == 3 and all(d == int(d) and d > 0 for d in dims):
                    dimens = [int(d) for d in dims]
            except ValueError:
                pass
        elif name == "BOX":
            box_items = items
        elif name in _ARRAY_FIELDS:
            try:
                arrays[name] = _expand_repeat(items)
            except (ValueError, AttributeError):
                result.findings.append(f"Could not parse {name} values.")
        elif name == "PVDG":
            # Keep the raw rows (pressure Bg viscosity) verbatim for the
            # pvdg_rows ModelSpec slot.
            rows = []
            for r in kw.records:
                cells = [i.text for i in r.items]
                if cells:
                    rows.append("\t".join(cells))
            patch["pvdg_rows"] = rows

    if not arrays and "pvdg_rows" not in patch:
        result.findings.append(
            "No supported property arrays found (PORO/PERMX/PERMY/PERMZ/"
            "DX/DY/DZ/TOPS)."
        )
        return result

    if "pvdg_rows" not in patch and dimens is None:
        result.findings.append(
            "No DIMENS keyword found. Provide the grid dimensions "
            "(nx ny nz) so the arrays can be placed."
        )

    # Apply BOX scoping to the collected arrays. A BOX that does not cover the
    # whole grid leaves the rest of the array unpadded; that is not usable,
    # so the affected arrays are dropped and named in a finding.
    if box_items is not None and dimens is not None:
        nx, ny, nz = dimens
        for name, values in list(arrays.items()):
            expanded = _apply_box(values, box_items, nx, ny, nz)
            if expanded is None:
                result.findings.append(
                    f"BOX on {name} does not cover the whole grid; the "
                    "fragment is not usable. Flatten it to explicit values "
                    "first."
                )
                del arrays[name]
            else:
                arrays[name] = expanded

    # Reduce full arrays to per-layer or scalar ModelSpec values. Genuine
    # per-cell variation is refused with the array named.
    for name, field_name in _ARRAY_FIELDS.items():
        values = arrays.get(name)
        if values is None:
            continue
        cells_per_layer = (dimens[0] * dimens[1]) if dimens else len(values)

        if name in ("PORO", "TOPS", "DX", "DY"):
            # Scalar in the spec: uniform only. Per-layer-uniform values
            # (identical within each layer but different across layers) are
            # not a scalar either, and these fields have no per-layer slot,
            # so refuse with the array named rather than silently averaging.
            distinct = sorted(set(round(v, 6) for v in values))
            if len(distinct) == 1:
                patch[field_name] = values[0]
            elif dimens and _is_layer_uniform(values, cells_per_layer):
                result.findings.append(
                    f"{name} is per-layer uniform ({len(distinct)} distinct "
                    f"layers); the builder's {field_name} is a single "
                    "uniform value. Convert to a per-layer average first."
                )
            else:
                result.findings.append(
                    f"{name} varies per cell ({len(distinct)} distinct "
                    f"values); the builder supports uniform or per-layer "
                    "values. Convert to per-layer averages first."
                )
            continue

        # DZ / PERM*: per-layer in the spec. A uniform array (every value
        # identical) collapses to a scalar regardless of how many cells it
        # spans - that is the common case for a pasted 1.0E+03 PERMX.
        if len(set(round(v, 6) for v in values)) == 1:
            patch[field_name] = values[0]
            continue

        if len(values) == len(set(values)) and dimens and len(values) <= dimens[2]:
            # Already a per-layer export: one value per layer.
            patch[field_name] = list(values)
            continue

        if dimens:
            per_layer = _per_layer_values(values, cells_per_layer, dimens[2])
            distinct_layers: list[float] | None = []
            for layer_vals in per_layer:
                layer_distinct = set(round(v, 6) for v in layer_vals)
                if len(layer_distinct) > 1:
                    result.findings.append(
                        f"{name} varies within layer {len(distinct_layers) + 1} "
                        f"({len(layer_distinct)} distinct values); the builder "
                        "supports per-layer values only. Convert to per-layer "
                        "averages first."
                    )
                    distinct_layers = None
                    break
                distinct_layers.append(layer_vals[0])
            if distinct_layers:
                patch[field_name] = distinct_layers
        else:
            distinct = sorted(set(round(v, 6) for v in values))
            if len(distinct) == 1:
                patch[field_name] = values[0]
            else:
                # Layer-major distinct values when nz is unknown; the user
                # confirms the ordering via the interview.
                patch[field_name] = distinct

    return result


def _is_layer_uniform(values: list[float], cells_per_layer: int) -> bool:
    """True when each block of cells_per_layer values is uniform."""
    if cells_per_layer <= 0 or len(values) % cells_per_layer != 0:
        return False
    for k in range(0, len(values), cells_per_layer):
        if len(set(values[k:k + cells_per_layer])) > 1:
            return False
    return True


def _per_layer_values(values: list[float], cells_per_layer: int, nz: int) -> list[list[float]]:
    """Split a layer-major full array into per-layer value lists."""
    out = []
    for k in range(nz):
        layer = values[k * cells_per_layer:(k + 1) * cells_per_layer]
        if layer:
            out.append(layer)
    return out


def _parse_numeric_grid(text: str) -> IngestResult:
    """Plain pasted numeric rows (tab/space/comma separated).

    A 2-D grid with uniform rows collapses to a scalar porosity only if
    the user confirms the mapping; here we return the values and a hint.
    Petrel exports are often a flat column with a header: nx/ny are NOT
    inferred from len(values) - the interview asks.
    """
    result = IngestResult(detected="numeric_grid")
    lines = [l.strip() for l in _strip_comments(text).splitlines() if l.strip()]

    # Strip a leading non-numeric header row (numpy-style exports).
    if lines and not all(_is_number(tok) for tok in lines[0].split()):
        result.findings.append("Ignored a leading header row.")
        lines = lines[1:]

    try:
        values: list[float] = []
        for line in lines:
            for tok in line.replace(",", " ").split():
                values.append(_to_float(tok))
    except ValueError as e:
        result.findings.append(f"Could not parse numeric grid: {e}")
        return result

    if not values:
        result.findings.append("No numeric values found.")
        return result

    distinct = sorted(set(values))
    if len(distinct) == 1:
        # A single repeated value: most plausibly a uniform property.
        result.patch["porosity"] = values[0]
        result.findings.append(
            "Single uniform value parsed; mapped to porosity. Move it to "
            "another field in the interview if this is not porosity."
        )
    else:
        result.findings.append(
            f"Parsed {len(values)} values ({len(distinct)} distinct). Paste "
            "a GRDECL fragment (PORO/PERMX/...) instead so the values map "
            "to named fields, or confirm the mapping in the interview."
        )
    return result


def apply_ingest(spec: ModelSpec, result: IngestResult) -> ModelSpec:
    """Apply an IngestResult patch onto the spec. Ingested values are
    provenance 'extracted' (they came from a source, exactly as 'from the
    description' means)."""
    for field_name, value in result.patch.items():
        if hasattr(spec.reservoir, field_name):
            setattr(spec.reservoir, field_name, value)
        elif field_name == "pvdg_rows":
            spec.pvdg_rows = value
    return spec
