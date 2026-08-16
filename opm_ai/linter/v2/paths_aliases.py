"""PATHS alias substitution for the v2 linter.

In Eclipse decks, the `PATHS` directive declares path aliases used in
INCLUDE / IMPORT / GDFILE / RESTART statements:

  PATHS
    $DATA  /path/to/data
    $GRID  $DATA/grids
  /

Then `INCLUDE '$GRID/main.GRDECL' /` resolves to
`/path/to/data/grids/main.GRDECL`.

This module provides `PathsTable`, a dict-like object that tracks
aliases and substitutes `$ALIAS` references in path strings. Aliases
may themselves reference other aliases (`$GRID = $DATA/grids`), which
the substitution handles recursively.

PATHS records are tokenized like any other list-kind keyword and
collected by the parser. The resolver is responsible for:
  1. Detecting PATHS keywords during composite-deck construction.
  2. Building a PathsTable from the records.
  3. Substituting aliases in INCLUDE / IMPORT / GDFILE / RESTART
     path tokens before file resolution.

PATHS itself is technically valid in any section, but its aliases
have file-wide scope (no section boundaries).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast import Keyword
from .tokens import Token


@dataclass
class PathsTable:
    """Maps `$ALIAS` → path or `$OTHER_ALIAS` reference.

    Aliases are case-sensitive and start with `$`. The substitution
    is recursive: if `$A = $B/x` and `$B = /y`, then `$A` resolves
    to `/y/x`. Cycles in the alias graph produce the literal
    `$ALIAS` (no substitution).
    """

    entries: dict[str, str] = field(default_factory=dict)

    def define(self, alias: str, value: str) -> None:
        """Define or replace an alias."""
        if not alias.startswith("$"):
            raise ValueError(f"alias must start with '$': {alias!r}")
        self.entries[alias] = value

    def substitute(self, path: str) -> str:
        """Resolve all `$ALIAS` references in `path`.

        Scans left-to-right. For each `$ALIAS`, looks it up in the
        table; if found, replaces it with the alias value (which may
        itself contain other `$ALIAS` references — we resolve those
        recursively).

        Cycle handling: if alias resolution exceeds a recursion depth
        threshold, the unresolved alias is kept verbatim.
        """
        return _substitute(path, self.entries, _seen=set(), depth=0)


def _substitute(path: str, entries: dict[str, str], _seen: set[str], depth: int) -> str:
    """Recursively resolve `$ALIAS` references in `path`."""
    if depth > 16:
        # Recursion depth guard: cycles in alias graph would loop
        # forever; bail out with the literal path.
        return path

    out_parts: list[str] = []
    i = 0
    while i < len(path):
        if path[i] != "$":
            out_parts.append(path[i])
            i += 1
            continue
        # Look for $[A-Z0-9_]+
        j = i + 1
        while j < len(path) and (path[j].isalnum() or path[j] == "_"):
            j += 1
        alias = path[i:j]
        if alias in entries:
            if alias in _seen:
                # Cycle: leave the alias verbatim.
                out_parts.append(alias)
                i = j
                continue
            value = entries[alias]
            # Recursively substitute the value (might contain $OTHER).
            substituted = _substitute(value, entries, _seen | {alias}, depth + 1)
            out_parts.append(substituted)
            i = j
        else:
            # Unknown alias: leave it as literal text.
            out_parts.append(alias)
            i = j
    return "".join(out_parts)


def paths_table_from_keywords(keywords: list[Keyword]) -> PathsTable:
    """Extract a PathsTable from a list of PATHS keywords.

    Iterates over each PATHS keyword in order; each record contributes
    (alias, value) pairs. Multiple PATHS directives may coexist (e.g.
    one per section); later definitions override earlier ones.

    PATHS records have a quirk: the value may contain `/` separators
    (e.g. `$GRID $DATA/grid/` parses to three items because the `/`
    is its own token). To recover the original value, we join items
    1..N with `/` (assuming the path components were originally
    slash-separated).

    PATHS records can have either:
      - token kind STRING: `'$DATA' '/path/to/data'` (quoted)
      - token kind PATHS_VAR: `$DATA /path/to/data` (unquoted alias)
      - token kind VALUE: `/path/to/data` (path with embedded /)
    Aliases from STRING quotes get the `$` prefix if missing.
    """
    table = PathsTable()
    for kw in keywords:
        if kw.name != "PATHS":
            continue
        for rec in kw.records:
            if len(rec.items) < 2:
                continue
            alias_tok = rec.items[0]
            value_toks = rec.items[1:]

            # Extract alias text — handle both quoted and unquoted.
            if alias_tok.kind.name == "STRING":
                alias = alias_tok.text
                if not alias.startswith("$"):
                    alias = f"${alias}"
            elif alias_tok.kind.name in ("PATHS_VAR", "VALUE"):
                alias = alias_tok.text
                if not alias.startswith("$"):
                    alias = f"${alias}"
            else:
                continue

            # Reconstruct the value: each item contributes text, but
            # if an item is a path-like VALUE starting with `/`, it
            # represents one or more path components separated by `/`.
            # We join everything with `/`.
            value_parts: list[str] = []
            for vt in value_toks:
                if vt.kind.name == "STRING":
                    value_parts.append(vt.text)
                else:
                    value_parts.append(vt.text)
            # If the first value part starts with `/`, it's a path.
            # We join all parts with `/` (preserving trailing slashes).
            value = "/".join(value_parts)
            # Clean up multiple slashes from consecutive parts.
            while "//" in value:
                value = value.replace("//", "/")

            table.define(alias, value)
    return table


def path_token_to_string(tok: Token) -> str:
    """Extract the path string from an INCLUDE/IMPORT path token.

    The path token may be:
      - STRING: `'path/to/file' /` → strip quotes, return path/to/file
      - PATHS_VAR: `$DATA/file` → return $DATA/file (substituted later)
      - VALUE: `path/to/file` (unquoted) → return path/to/file
      - FU_VAR / UDQ_VAR: rare; treat as literal.
    """
    return tok.text