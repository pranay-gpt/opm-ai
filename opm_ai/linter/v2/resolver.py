"""CompositeDeck and the INCLUDE/IMPORT resolver.

A `CompositeDeck` represents a deck + all of its INCLUDE/IMPORT
references, plus the resolved section structure.

The resolver walks the parsed deck's keywords and:
  1. Collects PATHS aliases (any section).
  2. For each INCLUDE keyword, resolves the path (after PATHS
     substitution), reads the referenced file, and recursively
     resolves any INCLUDE statements in the included file.
  3. For each IMPORT keyword, records the path (the file is binary
     and not parsed).
  4. Tracks visited files for cycle detection.
  5. Records file-not-found errors with line context.

The composite deck is the union of all included file keywords,
attributed by source file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ast import Deck, Keyword, Section
from .catalogue import get_keyword
from .paths_aliases import PathsTable, path_token_to_string, paths_table_from_keywords
from .parser import parse
from .spec import SectionName
from .tokenizer import tokenize_file
from .tokens import Token, TokenKind


@dataclass
class ResolvedInclude:
    """A resolved INCLUDE statement.

    Attributes:
        source_file: The deck where the INCLUDE statement lives.
        source_line: Line number of the INCLUDE statement.
        target_file: The resolved (path-substituted) target path.
        actual_file: The actual file path on disk (after resolution
            relative to source_file's directory).
        keywords: Keywords from the included file (already parsed).
        depth: How deep this include is (1 = direct, 2 = include-of-include).
    """

    source_file: Path
    source_line: int
    target_file: str
    actual_file: Path
    keywords: list[Keyword] = field(default_factory=list)
    depth: int = 1


@dataclass
class ResolvedImport:
    """A resolved IMPORT statement (binary file reference).

    Attributes:
        source_file: The deck where the IMPORT statement lives.
        source_line: Line number of the IMPORT statement.
        target_file: The path being imported.
        actual_file: The actual file path on disk.
    """

    source_file: Path
    source_line: int
    target_file: str
    actual_file: Path


@dataclass
class CompositeDeck:
    """The result of resolving a deck's INCLUDE/IMPORT chain.

    Attributes:
        main_deck: The parsed top-level deck.
        source_files: All files that participated in the resolution,
            keyed by absolute path.
        includes: All INCLUDE statements resolved, in order.
        imports: All IMPORT statements resolved, in order.
        errors: Resolution errors (cycles, file-not-found, parse errors).
        paths_table: The accumulated PATHS aliases.
    """

    main_deck: Deck
    source_files: dict[Path, Deck] = field(default_factory=dict)
    includes: list[ResolvedInclude] = field(default_factory=list)
    imports: list[ResolvedImport] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    paths_table: PathsTable = field(default_factory=PathsTable)

    def error_count(self) -> int:
        return len(self.errors)

    def keyword_count(self) -> int:
        return sum(d.keyword_count() for d in self.source_files.values())


class Resolver:
    """Walks a parsed deck and resolves INCLUDE/IMPORT references."""

    def __init__(self, deck: Deck, base_dir: Path | str | None = None) -> None:
        self.deck = deck
        self.base_dir = (
            Path(base_dir).resolve() if base_dir is not None
            else (deck.source_file.parent.resolve() if deck.source_file else Path.cwd())
        )
        self.visited: set[Path] = set()
        self.composite = CompositeDeck(main_deck=deck)
        if deck.source_file is not None:
            self.composite.source_files[Path(deck.source_file).resolve()] = deck

    def resolve(self) -> CompositeDeck:
        """Walk the deck and resolve all references.

        Returns the populated CompositeDeck. Errors are recorded in
        `composite.errors`.
        """
        if self.deck.source_file is None:
            self.composite.errors.append(
                "cannot resolve INCLUDEs: deck has no source_file"
            )
            return self.composite

        self.visited.add(Path(self.deck.source_file).resolve())
        # Pass `root_deck=self.deck` so that included files' keywords
        # always merge into the root deck (not into a sub-deck).
        self._resolve_deck(self.deck, root_deck=self.deck, depth=1)
        return self.composite

    def _resolve_deck(self, deck: Deck, root_deck: Deck, depth: int) -> None:
        """Walk all keywords in all sections of `deck`.

        For INCLUDE: read the file, parse it, and (a) record the
        keywords on a ResolvedInclude and (b) merge them into the
        root deck's same-named section (so the section-level AST
        always reflects the full merged deck).
        """
        # Collect PATHS first (so subsequent INCLUDEs can use them).
        all_keywords = deck.all_keywords()
        for kw in all_keywords:
            if kw.name == "PATHS":
                # Add to the cumulative paths table.
                new = paths_table_from_keywords([kw])
                for alias, value in new.entries.items():
                    self.composite.paths_table.define(alias, value)

        # Walk keywords; resolve INCLUDE / IMPORT as we find them.
        for kw in all_keywords:
            if kw.name == "INCLUDE":
                self._resolve_include(kw, deck, root_deck, depth)
            elif kw.name == "IMPORT":
                self._resolve_import(kw, depth)

    def _resolve_include(self, kw: Keyword, parent_deck: Deck, root_deck: Deck, depth: int) -> None:
        """Resolve a single INCLUDE statement."""
        if not kw.records:
            return
        # An INCLUDE keyword may have multiple records (multiple files
        # in one INCLUDE block). Each record is one path.
        for rec in kw.records:
            if not rec.items:
                continue
            path_tok = rec.items[0]
            raw_path = path_token_to_string(path_tok)
            resolved_path_str = self.composite.paths_table.substitute(raw_path)

            # Resolve relative to the deck's directory (NOT the cwd).
            # The INCLUDE keyword's deck might be an included file; we
            # need its own directory.
            source_file = (
                Path(kw.header_token.source_file).resolve()
                if kw.header_token.source_file
                else self.deck.source_file
            )
            base_dir = source_file.parent if source_file else self.base_dir
            target = Path(resolved_path_str)
            if not target.is_absolute():
                target = (base_dir / target).resolve()

            if target in self.visited:
                self.composite.errors.append(
                    f"{source_file}:{kw.header_token.line}: "
                    f"cycle detected: {target} already included"
                )
                continue

            if not target.exists():
                self.composite.errors.append(
                    f"{source_file}:{kw.header_token.line}: "
                    f"INCLUDE file not found: {target} "
                    f"(resolved from '{raw_path}')"
                )
                continue

            self.visited.add(target)

            # Read and parse the included file.
            try:
                text = target.read_text(errors="replace")
            except OSError as e:
                self.composite.errors.append(
                    f"{source_file}:{kw.header_token.line}: "
                    f"failed to read {target}: {e}"
                )
                continue

            from .tokenizer import tokenize_file as tf
            tokens = tf(text, source_file=target)
            try:
                sub_deck = parse(tokens)
            except Exception as e:
                self.composite.errors.append(
                    f"{source_file}:{kw.header_token.line}: "
                    f"parse error in {target}: {e}"
                )
                continue

            sub_deck.include_depth = depth
            self.composite.source_files[target] = sub_deck

            # Merge parse errors from the included deck into the root
            # deck so the L160 rule surfaces them. Each error's
            # source_file is rewritten to the included file path so
            # the line/col remain meaningful (they're relative to
            # the included file's text).
            for err in sub_deck.parse_errors:
                if err.source_file is None:
                    err.source_file = target
                root_deck.parse_errors.append(err)

            # Merge included keywords into the parent deck's AST.
            # Find the section that contains the INCLUDE keyword — that
            # is where PRELUDE keywords from the included file should land.
            parent_section = self._find_section_for_keyword(parent_deck, kw)
            if parent_section is None:
                parent_section = self._get_or_create_section(
                    root_deck, SectionName.GRID
                )

            for sub_section_name, sub_section in sub_deck.sections.items():
                if not sub_section.keywords:
                    continue
                if sub_section_name == SectionName.PRELUDE:
                    # PRELUDE keywords join the parent's INCLUDE-section.
                    target_section = parent_section
                else:
                    # Non-PRELUDE sections merge into the root deck's
                    # same-named section (creating it if absent).
                    target_section = self._get_or_create_section(
                        root_deck, sub_section_name
                    )
                for sub_kw in sub_section.keywords:
                    if sub_kw.name == "INCLUDE":
                        continue
                    target_section.keywords.append(sub_kw)

            resolved = ResolvedInclude(
                source_file=source_file,
                source_line=kw.header_token.line,
                target_file=resolved_path_str,
                actual_file=target,
                keywords=sub_deck.all_keywords(),
                depth=depth,
            )
            self.composite.includes.append(resolved)

            # Recursively resolve INCLUDE statements in the included file.
            self._resolve_deck(sub_deck, root_deck=root_deck, depth=depth + 1)

    def _find_section_for_keyword(self, deck: Deck, kw: Keyword) -> Section | None:
        """Find the Section object that contains the given keyword."""
        for section in deck.sections.values():
            if kw in section.keywords:
                return section
        return None

    def _get_or_create_section(self, deck: Deck, name: SectionName) -> Section:
        """Return the named section, creating an empty one if needed."""
        s = deck.sections.get(name)
        if s is None:
            from .ast import Section as _Section
            s = _Section(
                name=name,
                header_token=Token(
                    TokenKind.SECTION_HEADER, name.value, name.value, 0, 0, 0
                ),
            )
            deck.sections[name] = s
        return s

    def _resolve_import(self, kw: Keyword, depth: int) -> None:
        """Resolve a single IMPORT statement (binary file; record only)."""
        if not kw.records:
            return
        for rec in kw.records:
            if not rec.items:
                continue
            path_tok = rec.items[0]
            raw_path = path_token_to_string(path_tok)
            resolved_path_str = self.composite.paths_table.substitute(raw_path)

            source_file = (
                Path(kw.header_token.source_file).resolve()
                if kw.header_token.source_file
                else self.deck.source_file
            )
            base_dir = source_file.parent if source_file else self.base_dir
            target = Path(resolved_path_str)
            if not target.is_absolute():
                target = (base_dir / target).resolve()

            if target in self.visited:
                self.composite.errors.append(
                    f"{source_file}:{kw.header_token.line}: "
                    f"cycle detected: IMPORT {target} already imported"
                )
                continue

            if not target.exists():
                self.composite.errors.append(
                    f"{source_file}:{kw.header_token.line}: "
                    f"IMPORT file not found: {target} "
                    f"(resolved from '{raw_path}')"
                )
                continue

            self.visited.add(target)
            self.composite.imports.append(
                ResolvedImport(
                    source_file=source_file,
                    source_line=kw.header_token.line,
                    target_file=resolved_path_str,
                    actual_file=target,
                )
            )


def resolve_deck(deck: Deck, base_dir: Path | str | None = None) -> CompositeDeck:
    """Resolve a parsed deck's INCLUDE/IMPORT chain.

    Convenience wrapper around `Resolver`.
    """
    resolver = Resolver(deck, base_dir=base_dir)
    return resolver.resolve()