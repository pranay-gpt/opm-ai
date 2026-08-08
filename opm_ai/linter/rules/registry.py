"""Rule engine registry - imports and runs all lint rules."""

from typing import Callable

from opm_ai.linter.deck import Deck
from opm_ai.linter.models import LintIssue


# Rule function type
RuleFunc = Callable[[Deck], list[LintIssue]]


def run_all(deck: Deck) -> list[LintIssue]:
    """Run all registered rules against the deck."""
    issues = []
    for rule in RULES:
        issues.extend(rule(deck))
    return issues


# Import all rule modules to register their rules
from opm_ai.linter.rules import (
    funvar_summary,
    general,
    grid,
    keywords,
    props,
    runspec,
    schedule,
    solution_summary,
)

# Rule registry - all seed rules L001-L019
# L014/L015 are claimed by general/runspec; L016 by keywords; L017/L018 by
# schedule (the historical L014/L015 schedule rules were renamed to clear
# the collision - see opm_ai/linter/context.md for the audit trail).
# L019 added in Phase 3.5 (funvar_summary).
RULES: list[RuleFunc] = [
    # General rules
    general.rule_L001_missing_terminator,
    general.rule_L013_keyword_order,
    general.rule_L014_include_depth,
    keywords.rule_L016_unknown_keyword,
    # RUNSPEC rules
    runspec.rule_L002_phase_mismatch,
    runspec.rule_L015_missing_dimens,
    # GRID rules
    grid.rule_L003_dimens_grid_match,
    grid.rule_L003b_missing_grid_keywords,
    grid.rule_L004_negative_permeability,
    grid.rule_L011_porosity_range,
    # PROPS rules
    props.rule_L005_pvt_phase_mismatch,
    props.rule_L012_sat_endpoint_consistency,
    # SCHEDULE rules
    schedule.rule_L006_wellspecs_no_compdat,
    schedule.rule_L007_well_not_in_wellspecs,
    schedule.rule_L008_wellspecs_auto_no_gruptree,
    schedule.rule_L017_producer_no_wconprod,
    schedule.rule_L018_injector_no_wconinje,
    # SOLUTION/SUMMARY rules
    solution_summary.rule_L009_missing_solution,
    solution_summary.rule_L010_missing_summary,
    # FU_* declaration cross-checks (Phase 3.5)
    funvar_summary.rule_L019_summary_funvar_missing,
]