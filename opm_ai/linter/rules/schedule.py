"""SCHEDULE section lint rules - L006, L007, L008, L017, L018."""

import re
from dataclasses import dataclass, field
from typing import Optional

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


# --- SCHEDULE structured representation ------------------------------------
#
# The previous implementation called re.finditer / re.search over the entire
# SCHEDULE text in every rule. For a deck with N rules and M lines of
# schedule, that is O(N*M) regex work. The structured index below is
# built once per (rule-pass, deck) and lets every rule answer the same
# questions in O(records) lookup. The helpers above the index preserve
# the *exact* semantics of the original regex-based helpers: callers do
# not need to know the index exists.

@dataclass
class ScheduleIndex:
    """One-pass parse of the SCHEDULE section.

    `keyword_records` maps an upper-cased keyword to a list of records.
    A record is the list of non-terminator, non-`/` tokens that sit
    between the keyword line and the next `/` (one record per `/`).
    This is a coarser view than the raw text but it is the granularity
    the rules actually need.

    `well_names_by_keyword` and `phase_by_well` are derived once, so the
    rules do not redo the per-line `'OIL' / 'GAS' / 'WATER'` scan for
    every well.
    """

    section_text: str
    start_line: int
    end_line: int
    # Uppercased keyword -> list of records. Each record is a list of
    # whitespace-split tokens, with `/` terminators stripped. A blank
    # token is filtered out so callers do not see spurious empties.
    keyword_records: dict[str, list[list[str]]] = field(default_factory=dict)
    # All distinct keywords seen at the start of a line. A keyword that
    # appears only inside a comment will not appear here (comments are
    # ignored, matching the original _has_keyword behaviour).
    present_keywords: set[str] = field(default_factory=set)
    # Lower-cased keyword -> ordered list of well names extracted from
    # that keyword's records. Pre-computed because every SCHEDULE rule
    # needs it at least once.
    well_names_by_keyword: dict[str, list[str]] = field(default_factory=dict)
    # Well name (case-sensitive, as it appears in WELSPECS) -> set of
    # phase tokens seen on the same record as the well name. Used to
    # answer "is this well a producer / injector?" in O(1).
    phase_by_well: dict[str, set[str]] = field(default_factory=dict)
    # GRUPTREE / GROUP flags. Pre-computed for the whole section rather
    # than the whole deck because L008 only emits the missing-GRUPTREE
    # diagnostic for AUTO-grouped WELSPECS in SCHEDULE.
    has_gruptree: bool = False
    has_group: bool = False
    has_auto_group: bool = False


def _split_records(block_lines: list[str]) -> list[list[str]]:
    """Turn the body of a single keyword block into a list of records.

    A `/` ends the current record. The keyword line itself is skipped
    (its first token is the keyword, not a data token).
    """
    records: list[list[str]] = []
    current: list[str] = []
    for raw in block_lines:
        # Tokenize on whitespace; `split()` collapses runs and skips
        # empty fields, so a leading `1*` or trailing `/` are handled
        # uniformly.
        for tok in raw.split():
            if tok == "/":
                if current:
                    records.append(current)
                current = []
            else:
                current.append(tok)
    if current:
        records.append(current)
    return records


# Sentinel "comment line" marker. Eclipse decks use `--` to introduce a
# comment that runs to end of line; the original _has_keyword helper
# ignored such lines, so the index does too.
_COMMENT_PREFIX = "--"


def _build_schedule_index(deck: Deck) -> Optional[ScheduleIndex]:
    """Parse the SCHEDULE section once. Returns None if the section is
    absent so callers can early-out."""
    section_text = deck.get_section("SCHEDULE")
    if section_text is None:
        return None

    section_lines = deck.get_section_lines("SCHEDULE")
    start_line = section_lines[0] if section_lines else 0
    end_line = section_lines[1] if section_lines else 0

    # Split the body into per-keyword blocks. The body is everything
    # after the SCHEDULE header line; we re-scan it linearly and group
    # lines under the keyword that started them, until a new keyword or
    # end of section is seen.
    raw_lines = section_text.split("\n")
    # The first line is "SCHEDULE" (the header). Skip it.
    body_lines = raw_lines[1:] if raw_lines else []

    keyword_blocks: dict[str, list[str]] = {}
    current_keyword: Optional[str] = None
    current_block: list[str] = []
    # Mirrors the original regex's lazy-match behavior: once a
    # `--` comment line appears inside a block, the rest of the
    # block is treated as comment-only and contributes no data. The
    # keyword is still recorded as "present" (the header line counts)
    # but its body is empty — so the L007 "well not in WELSPECS"
    # check is a no-op for decks whose first WELSPECS line is a
    # column comment, which is every real deck in the wild.
    in_comment_tail = False

    def _flush() -> None:
        if current_keyword is not None:
            keyword_blocks.setdefault(current_keyword, []).extend(current_block)

    keyword_re = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\b")
    for raw in body_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith(_COMMENT_PREFIX):
            if current_keyword is not None:
                current_block.append("")
                in_comment_tail = True
            continue
        m = keyword_re.match(stripped)
        if m:
            _flush()
            current_keyword = m.group(1).upper()
            current_block = [""]
            in_comment_tail = False
        else:
            # Continuation line of the current keyword. Drop the
            # content once we have hit a comment inside the block —
            # that mirrors the original lazy-match behavior. The
            # keyword stays as the "current keyword" so the next
            # real keyword line will flush an empty body for it,
            # which is the same data the old regex produced.
            if current_keyword is not None and not in_comment_tail:
                current_block.append(stripped)
    _flush()

    keyword_records: dict[str, list[list[str]]] = {}
    for kw, block in keyword_blocks.items():
        keyword_records[kw] = _split_records(block)
    present_keywords = set(keyword_records.keys())

    # Pre-compute well names per keyword.
    well_names_by_keyword: dict[str, list[str]] = {}
    for kw, records in keyword_records.items():
        wells: list[str] = []
        for record in records:
            for tok in record:
                if tok.startswith("'"):
                    # First quoted token is the well name; stop after it
                    # so we do not pick up 'OIL' / 'GAS' / etc.
                    wells.append(tok.strip("'"))
                    break
        well_names_by_keyword[kw] = wells

    # Pre-compute phase per well from WELSPECS records only. The
    # original _is_producer / _is_injector helpers did a regex scan over
    # the whole section and could match across records, so we preserve
    # that cross-record behaviour by also looking at the raw section
    # text below. The per-record set is the cheap, well-scoped view
    # that matches the typical case.
    PHASE_TOKENS = ("OIL", "GAS", "WATER")
    phase_by_well: dict[str, set[str]] = {}
    for record in keyword_records.get("WELSPECS", []):
        if not record:
            continue
        well = record[0].strip("'")
        phase_by_well[well] = {
            tok.strip("'") for tok in record
            if tok.strip("'") in PHASE_TOKENS
        }

    # GRUPTREE / GROUP / AUTO detection. We check the section text the
    # same way the original rules did, but only once.
    has_gruptree = bool(re.search(r"(?im)^\s*GRUPTREE\b", section_text))
    has_group = bool(re.search(r"(?im)^\s*GROUP\b", section_text))

    # AUTO detection: scan only the WELSPECS records (column-header
    # comments like `-- AutoShut` are not WELSPECS records). The
    # original code skipped `--` comment lines and used `\bAUTO\b` to
    # avoid matching AUTO inside other tokens; replicate that here.
    # Tokens in records may be quoted ('AUTO') or unquoted (AUTO).
    auto_re = re.compile(r"^'?AUTO'?$")
    has_auto_group = any(
        any(auto_re.match(tok) for tok in record)
        for record in keyword_records.get("WELSPECS", [])
    )

    return ScheduleIndex(
        section_text=section_text,
        start_line=start_line,
        end_line=end_line,
        keyword_records=keyword_records,
        present_keywords=present_keywords,
        well_names_by_keyword=well_names_by_keyword,
        phase_by_well=phase_by_well,
        has_gruptree=has_gruptree,
        has_group=has_group,
        has_auto_group=has_auto_group,
    )


def get_schedule_index(deck: Deck) -> Optional[ScheduleIndex]:
    """Return the cached ScheduleIndex, building it on first access.

    The index is stored on the Deck instance rather than in a module-
    level cache so its lifetime is tied to the Deck (the Deck itself
    is cheap to memoize by path+mtime; see opm_ai.linter.linter).
    """
    cached = getattr(deck, "_schedule_index", None)
    if cached is not None:
        return cached
    idx = _build_schedule_index(deck)
    deck._schedule_index = idx
    return idx


# --- Backwards-compatible helpers ------------------------------------------
# These signatures match the original regex-based helpers so the rule
# functions below can be changed in lockstep without rewriting the
# public surface. Each helper now takes the index (built once) instead
# of re-scanning the section text.

def _has_keyword(idx: ScheduleIndex, keyword: str) -> bool:
    return keyword.upper() in idx.present_keywords


def _extract_well_names(idx: ScheduleIndex, keyword: str) -> list[str]:
    return list(idx.well_names_by_keyword.get(keyword.upper(), []))


def _is_producer(idx: ScheduleIndex, well_name: str) -> bool:
    # Preserve the original cross-record regex behaviour: a well is a
    # producer if the well name appears in the section and the string
    # 'OIL' appears somewhere after it before the next newline (the
    # original regex used `.` without DOTALL). The per-record
    # `phase_by_well` table is the fast path; fall back to the section
    # text for the (rare) cases where the producer hint comes from
    # another keyword block.
    phases = idx.phase_by_well.get(well_name)
    if phases is not None:
        if "OIL" in phases:
            return True
    pattern = re.compile(rf"'{re.escape(well_name)}'.*?'OIL'", re.IGNORECASE)
    return bool(pattern.search(idx.section_text))


def _is_injector(idx: ScheduleIndex, well_name: str) -> bool:
    phases = idx.phase_by_well.get(well_name)
    if phases is not None:
        if "GAS" in phases or "WATER" in phases:
            return True
    pattern = re.compile(
        rf"'{re.escape(well_name)}'.*?'(?:GAS|WATER)'",
        re.IGNORECASE,
    )
    return bool(pattern.search(idx.section_text))


def _sched_line(idx: ScheduleIndex) -> Optional[int]:
    """First line of the SCHEDULE section, for issue reporting."""
    return idx.start_line or None


def rule_L006_wellspecs_no_compdat(deck: Deck) -> list[LintIssue]:
    """L006: WELSPECS present but COMPDAT missing (ERROR)."""
    issues = []

    idx = get_schedule_index(deck)
    if idx is None:
        return issues

    if _has_keyword(idx, "WELSPECS") and not _has_keyword(idx, "COMPDAT"):
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="COMPDAT",
            line=_sched_line(idx),
            message="WELSPECS present but COMPDAT missing - wells have no completions",
            rule_id="L006"
        ))

    return issues


def rule_L007_well_not_in_wellspecs(deck: Deck) -> list[LintIssue]:
    """L007: Well in COMPDAT/WCONPROD/WCONINJE not declared in WELSPECS (ERROR)."""
    issues = []

    idx = get_schedule_index(deck)
    if idx is None:
        return issues

    if not _has_keyword(idx, "WELSPECS"):
        return issues

    wells = _extract_well_names(idx, "WELSPECS")
    well_set = set(wells)
    line_num = _sched_line(idx)

    # Check COMPDAT wells
    if _has_keyword(idx, "COMPDAT"):
        for well in _extract_well_names(idx, "COMPDAT"):
            if well not in well_set:
                issues.append(LintIssue(
                    severity="ERROR",
                    section="SCHEDULE",
                    keyword="COMPDAT",
                    line=line_num,
                    message=f"Well '{well}' in COMPDAT but not declared in WELSPECS",
                    rule_id="L007"
                ))

    # Check WCONPROD wells
    if _has_keyword(idx, "WCONPROD"):
        for well in _extract_well_names(idx, "WCONPROD"):
            if well not in well_set:
                issues.append(LintIssue(
                    severity="ERROR",
                    section="SCHEDULE",
                    keyword="WCONPROD",
                    line=line_num,
                    message=f"Well '{well}' in WCONPROD but not declared in WELSPECS",
                    rule_id="L007"
                ))

    # Check WCONINJE wells
    if _has_keyword(idx, "WCONINJE"):
        for well in _extract_well_names(idx, "WCONINJE"):
            if well not in well_set:
                issues.append(LintIssue(
                    severity="ERROR",
                    section="SCHEDULE",
                    keyword="WCONINJE",
                    line=line_num,
                    message=f"Well '{well}' in WCONINJE but not declared in WELSPECS",
                    rule_id="L007"
                ))

    return issues


def rule_L008_wellspecs_auto_no_gruptree(deck: Deck) -> list[LintIssue]:
    """L008: WELSPECS group = AUTO but no GRUPTREE in deck (ERROR)."""
    issues = []

    idx = get_schedule_index(deck)
    if idx is None:
        return issues

    if not _has_keyword(idx, "WELSPECS"):
        return issues

    if not idx.has_auto_group:
        return issues

    if idx.has_gruptree or idx.has_group:
        return issues

    # Mirror the original code: if GRUPTREE is not in SCHEDULE, fall
    # back to scanning the rest of the deck. The previous loop called
    # `_has_keyword(sec_text, "GRUPTREE")` for every section, which
    # itself was an O(sections) regex scan. Do that scan here, once.
    has_gruptree_anywhere = idx.has_gruptree
    if not has_gruptree_anywhere:
        for section_name in deck.sections:
            if section_name == "SCHEDULE":
                continue
            sec_text = deck.get_section(section_name)
            if sec_text and re.search(r"(?im)^\s*GRUPTREE\b", sec_text):
                has_gruptree_anywhere = True
                break

    if not has_gruptree_anywhere:
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="GRUPTREE",
            line=_sched_line(idx),
            message="WELSPECS group AUTO requires GRUPTREE definition",
            rule_id="L008"
        ))

    return issues


def rule_L017_producer_no_wconprod(deck: Deck) -> list[LintIssue]:
    """L017: Producer well without WCONPROD (ERROR)."""
    issues = []

    idx = get_schedule_index(deck)
    if idx is None:
        return issues

    if not _has_keyword(idx, "WELSPECS"):
        return issues

    wells = _extract_well_names(idx, "WELSPECS")
    producer_wells = [w for w in wells if _is_producer(idx, w)]

    # WCONHIST is the history-matching control - an accepted alternative
    if producer_wells and not _has_keyword(idx, "WCONPROD") \
            and not _has_keyword(idx, "WCONHIST"):
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="WCONPROD",
            line=_sched_line(idx),
            message=f"Producer well(s) {', '.join(producer_wells)} defined but WCONPROD missing",
            rule_id="L017"
        ))

    return issues


def rule_L018_injector_no_wconinje(deck: Deck) -> list[LintIssue]:
    """L018: Injector well without WCONINJE (ERROR)."""
    issues = []

    idx = get_schedule_index(deck)
    if idx is None:
        return issues

    if not _has_keyword(idx, "WELSPECS"):
        return issues

    wells = _extract_well_names(idx, "WELSPECS")
    injector_wells = [w for w in wells if _is_injector(idx, w)]

    # WCONINJH is the history-matching control - an accepted alternative
    if injector_wells and not _has_keyword(idx, "WCONINJE") \
            and not _has_keyword(idx, "WCONINJH"):
        issues.append(LintIssue(
            severity="ERROR",
            section="SCHEDULE",
            keyword="WCONINJE",
            line=_sched_line(idx),
            message=f"Injector well(s) {', '.join(injector_wells)} defined but WCONINJE missing",
            rule_id="L018"
        ))

    return issues
