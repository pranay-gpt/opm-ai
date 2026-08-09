"""Phase 5 — Lint issue explainer.

Given a LintIssue produced by the linter, return a Markdown paragraph
explaining:
  - what the issue means in plain language,
  - why it matters (impact on the simulation),
  - how to fix it.

The explainer is *purely additive* — it never changes the issue's
severity, rule_id, or message. The frontend can render the
explanation in a collapsible panel; the user gets the same data
either way.

Two flavours:
- L2 issues (rule_id starts with `L2.`): look up the spec entry and
  generate a per-check explanation (required / item_count / range /
  mutex). The KeywordSpec carries notes and per-item ranges that
  power the explanation.
- L3 issues (rule_id starts with `L3.` or numeric `L00X`): pull the
  docstring of the rule function and surface it. The mapping from
  rule_id to function is in `RULES` (registry.py).

For unknown rule_ids (rare — should not happen): return a generic
explanation that includes the issue's message verbatim.

The module is small (~150 lines) on purpose. Explanations are
deterministic and synchronous; they must not call out to any LLM.
"""
from __future__ import annotations

import inspect
import re
from typing import Optional

from opm_ai.linter.models import LintIssue


def explain(issue: LintIssue) -> Optional[str]:
    """Return a Markdown explanation for `issue`, or None if unknown."""
    rule_id = issue.rule_id or ""
    if rule_id.startswith("L2."):
        return _explain_l2(issue)
    if rule_id.startswith("L3.") or re.match(r"^L\d{3}$", rule_id):
        return _explain_l3(issue)
    return None


# ---------------------------------------------------------------------- #
# L2 — schema-driven explanations                                         #
# ---------------------------------------------------------------------- #

def _explain_l2(issue: LintIssue) -> Optional[str]:
    """Generate Markdown for an L2.<KEYWORD>.<CHECK> rule_id."""
    rule_id = issue.rule_id or ""
    # Parse: L2.<KEYWORD>.<CHECK>
    parts = rule_id.split(".")
    if len(parts) != 3:
        return _generic(issue)
    _, keyword, check = parts
    keyword = keyword.upper()
    check = check.lower()

    # Lazy import to avoid circular dependency.
    from opm_ai.linter.spec import load_spec
    from pathlib import Path
    spec_dir = Path(__file__).resolve().parent / "spec"
    specs = load_spec(spec_dir)
    spec = specs.get(keyword)

    if check == "required":
        return _explain_required(issue, keyword, spec)
    if check == "item_count":
        return _explain_item_count(issue, keyword, spec)
    if check == "range":
        return _explain_range(issue, keyword, spec, specs)
    if check == "mutex":
        return _explain_mutex(issue, keyword, specs)
    return _generic(issue)


def _explain_required(issue: LintIssue, keyword: str, spec) -> str:
    section = getattr(spec, "section", "RUNSPEC")
    notes = _first_note(spec) or "OPM Flow requires this keyword."
    return (
        f"**{keyword}** is required in the `{section}` section.\n\n"
        f"OPM Flow will refuse to start the simulation without it. "
        f"{notes}\n\n"
        f"**Fix**: add a `{keyword}` keyword in the `{section}` section "
        f"of your deck."
    )


def _explain_item_count(issue: LintIssue, keyword: str, spec) -> str:
    spec_min = getattr(spec, "min_items", None)
    spec_max = getattr(spec, "max_items", None)
    if spec_min is None and spec_max is None and spec is not None and spec.items:
        spec_min = spec_max = len(spec.items)
    msg = issue.message
    # Extract actual item count from the message if possible.
    actual_match = re.search(r"has (\d+) items?", msg)
    actual = actual_match.group(1) if actual_match else "an unexpected number of"
    target = f"{spec_min}-{spec_max}" if spec_min != spec_max else str(spec_min or "?")
    notes = _first_note(spec) or ""
    notes_md = f"\n\n_{notes}_" if notes else ""
    return (
        f"**{keyword}** record contains {actual} items, "
        f"but the spec expects {target}.{notes_md}\n\n"
        f"**Fix**: adjust the record so it has the expected item count, "
        f"or use the default-value syntax (`1*`) to skip items."
    )


def _explain_range(issue: LintIssue, keyword: str, spec, _unused) -> str:
    msg = issue.message
    # Extract item name and offending value from the message.
    item_match = re.search(r"item \d+ \(([^)]+)\)", msg)
    value_match = re.search(r"is ([^\s.;]+)", msg)
    item_name = item_match.group(1) if item_match else "this item"
    value = value_match.group(1) if value_match else "the value"
    # Try to find the spec item's range.
    item_range = None
    if spec and spec.items:
        # Best-effort: pull the item from message context.
        idx_match = re.search(r"item (\d+)", msg)
        if idx_match:
            idx = int(idx_match.group(1)) - 1
            if 0 <= idx < len(spec.items):
                item_range = spec.items[idx].range
    if item_range:
        rng = f"[{item_range[0]}, {item_range[1]}]"
        range_md = (
            f"\n\nThe allowed range for `{item_name}` is **{rng}** "
            f"based on the OPM Flow reference manual."
        )
    else:
        range_md = ""
    return (
        f"**{keyword}** item `{item_name}` has value {value}, which is "
        f"outside the allowed range.{range_md}\n\n"
        f"**Fix**: clamp the value to the allowed range, or check that "
        f"the units are what you expect (reservoir simulations often "
        f"mix field units and lab units)."
    )


def _explain_mutex(issue: LintIssue, keyword: str, specs) -> str:
    msg = issue.message
    # Extract partner name from the message.
    partner_match = re.search(r"with (\w+)", msg)
    partner = partner_match.group(1) if partner_match else "the alternative keyword"
    return (
        f"**{keyword}** and **{partner}** describe mutually-exclusive "
        f"grid or fluid models. Using both in the same deck is a "
        f"configuration error: OPM Flow uses one and ignores the "
        f"other, silently, which leads to wasted runtime.\n\n"
        f"**Fix**: remove one of the two keywords. The choice between "
        f"them is set by the model geometry (corner-point vs "
        f"rectangular) and the fluid model (live-oil vs dead-oil, "
        f"wet-gas vs dry-gas, etc.)."
    )


# ---------------------------------------------------------------------- #
# L3 — rule-driven explanations                                          #
# ---------------------------------------------------------------------- #

def _explain_l3(issue: LintIssue) -> Optional[str]:
    """Generate Markdown for an L3 rule by reading its docstring."""
    rule_id = issue.rule_id or ""
    # Lazy import to avoid circular dependency.
    from opm_ai.linter.rules.registry import RULES
    # Match rule function by name. Rule functions follow the
    # convention `rule_LNNN_<slug>` where slug is optional. We
    # match on the `rule_LNNN` prefix and let any suffix win
    # (so `rule_L015_missing_dimens` matches both `L015` and a
    # hypothetical `L015_extra`).
    prefix = f"rule_{rule_id}_"
    plain = f"rule_{rule_id}"
    for rule_func in RULES:
        name = getattr(rule_func, "__name__", "")
        if name == plain or name.startswith(prefix):
            doc = inspect.getdoc(rule_func) or ""
            # Strip the rule_id prefix line and the leading description.
            doc = re.sub(
                rf"^{re.escape(rule_id)}:\s*",
                "",
                doc.strip(),
                flags=re.MULTILINE,
            )
            if not doc:
                return _generic(issue)
            # First sentence: short summary. Rest: detail.
            sentences = _split_sentences(doc)
            summary = sentences[0] if sentences else ""
            detail = " ".join(sentences[1:]) if len(sentences) > 1 else ""
            md = f"_{summary}_\n\n{detail}".strip()
            return md
    return _generic(issue)


# ---------------------------------------------------------------------- #
# Helpers                                                                #
# ---------------------------------------------------------------------- #

def _generic(issue: LintIssue) -> str:
    """Fallback explanation when we can't look up the rule."""
    return (
        f"_{issue.message}_\n\n"
        f"**Severity**: {issue.severity}. "
        f"This is a generic explanation because the rule "
        f"`{issue.rule_id}` does not have a registered explainer."
    )


def _first_note(spec) -> Optional[str]:
    if spec is None:
        return None
    notes = getattr(spec, "notes", None)
    if notes:
        return notes[0]
    return None


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter on `. ` followed by capital letter.

    Good enough for docstrings — they don't contain edge cases like
    decimals or abbreviations often enough to matter.
    """
    parts = re.split(r"(?<=\.)\s+(?=[A-Z])", text.strip())
    return [p for p in parts if p]


def explain_issue(issue: LintIssue) -> LintIssue:
    """Return a new LintIssue with `explanation` populated (in-place copy).

    Convenience wrapper for callers that want the explanation
    attached to the issue directly.
    """
    explanation = explain(issue)
    if explanation is None:
        return issue
    return issue.model_copy(update={"explanation": explanation})