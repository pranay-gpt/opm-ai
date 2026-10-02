"""Stage 3 tests: deterministic interview engine (pure, no HTTP, no LLM).

Covers the never-breaks invariant, the skip/advance semantics, the
scenario-conditioned question routing, and the semantic rules.
"""

import pytest

from opm_ai.builder.extract import (
    extract_parameters_offline,
    extract_parameters_offline_with_provenance,
)
from opm_ai.builder.builder import build_deck_from_spec
from opm_ai.builder.interview import (
    CATALOG,
    all_questions,
    apply_answer,
    build_spec,
    next_question,
    progress,
    validate,
)
from opm_ai.builder.models import ModelSpec, ScenarioType


def _spec(desc: str = "10x10x3 depletion, one producer") -> ModelSpec:
    return extract_parameters_offline(desc)


class TestNextQuestion:
    def test_first_question_is_scenario(self):
        q = next_question(_spec(), {})
        assert q.id == "intent.scenario"

    def test_one_answer_advances_one_question(self):
        spec = _spec()
        q1 = next_question(spec, {})
        q2 = next_question(spec, {q1.id: spec.scenario.value})
        assert q2.id != q1.id

    def test_answered_questions_are_skipped(self):
        spec = _spec()
        questions = all_questions(spec)
        answers = {q.id: None for q in questions}
        # All answered (even with None values) -> complete.
        assert next_question(spec, answers) is None

    def test_unknown_answer_ids_are_ignored(self):
        spec = _spec()
        q = next_question(spec, {"bogus.question": 1})
        assert q.id == "intent.scenario"

    def test_progress_counts(self):
        spec = _spec()
        questions = all_questions(spec)
        p = progress(spec, {})
        assert p["total"] == len(questions)
        assert p["answered"] == 0
        p2 = progress(spec, {questions[0].id: 1})
        assert p2["answered"] == 1


class TestNeverBreaks:
    def test_skip_all_still_builds_a_lint_passing_deck(self):
        # The never-breaks invariant: skipping every question reaches
        # complete and the spec builds a deck that lints clean.
        spec = _spec()
        answers: dict = {}
        while (q := next_question(spec, answers)) is not None:
            answers[q.id] = None  # skip = record nothing
        assert next_question(spec, answers) is None
        built = build_spec(spec, answers)
        deck, lint = build_deck_from_spec(built)
        assert lint.passed

    def test_skip_all_vs_answer_all_produce_different_decks(self):
        # Catches the interview not being wired to the spec at all.
        # build_spec mutates the spec, so each branch needs its own copy.
        spec = _spec()
        skipped = build_spec(spec.model_copy(deep=True), {})
        answered = build_spec(spec.model_copy(deep=True), {"rock.porosity": 0.18})
        d1, _ = build_deck_from_spec(skipped)
        d2, _ = build_deck_from_spec(answered)
        assert d1 != d2


class TestScenarioRouting:
    def test_gas_cap_reaches_goc_question(self):
        spec = _spec("10x10x3 gas cap reservoir, one producer")
        ids = [q.id for q in all_questions(spec)]
        assert "equil.goc_depth" in ids

    def test_depletion_does_not_ask_goc(self):
        spec = _spec("10x10x3 depletion, one producer")
        ids = [q.id for q in all_questions(spec)]
        assert "equil.goc_depth" not in ids

    def test_gas_cap_blocks_without_goc_answer(self):
        spec = _spec("10x10x3 gas cap reservoir, one producer")
        spec.equil_goc_depth = None
        findings = validate(spec, {})
        assert any(f.id == "R04" and f.severity == "block" for f in findings)

    def test_waterflood_blocks_without_injector(self):
        spec = _spec("10x10x3 waterflood, one producer")
        # Force-strip the injector to simulate a user answer set that
        # removed it.
        spec.wells = [w for w in spec.wells if w.well_type.value == "PROD"]
        findings = validate(spec, {})
        assert any(f.id == "R09" and f.severity == "block" for f in findings)

    def test_k2_beyond_nz_is_a_block(self):
        spec = _spec()
        spec.wells[0].k2 = spec.reservoir.nz + 1
        findings = validate(spec, {})
        assert any(f.id == "R06" for f in findings)

    def test_well_outside_grid_is_a_block(self):
        spec = _spec()
        spec.wells[0].i = spec.reservoir.nx + 5
        findings = validate(spec, {})
        assert any(f.id == "R07" for f in findings)

    def test_well_collision_is_a_block(self):
        spec = _spec("10x10x3 depletion, two producers")
        assert len(spec.wells) >= 2
        spec.wells[1].i = spec.wells[0].i
        spec.wells[1].j = spec.wells[0].j
        findings = validate(spec, {})
        assert any(f.id == "R06b" for f in findings)

    def test_dz_length_mismatch_is_a_block(self):
        spec = _spec()
        spec.reservoir.dz = [50.0, 50.0]  # nz=3
        findings = validate(spec, {})
        assert any(f.id == "R08" for f in findings)

    def test_changing_top_depth_brings_datum_into_question(self):
        # After the B2 fix the datum clamps into the grid; the equil
        # question only applies when an explicit datum override exists.
        spec = _spec("10x10x3 depletion, depth 2000 ft, one producer")
        ids = [q.id for q in all_questions(spec)]
        assert "equil.datum_depth" not in ids  # no override -> not asked

    def test_co2_carries_honesty_warning(self):
        spec = _spec("10x10x3 co2 eor, one injector one producer")
        findings = validate(spec, {})
        assert any(f.id == "R15" and f.severity == "warn" for f in findings)

    def test_fluid_pressure_range_too_low_blocks(self):
        spec = _spec("10x10x3 depletion, one producer")
        from opm_ai.preprocess import FluidDescriptor
        spec.fluid = FluidDescriptor(
            api_gravity=35, gas_specific_gravity=0.75, gor=800,
            reservoir_temp_c=93.33, salinity_ppm=50000,
            pressure_range_psi=(14.7, 3000), unit_system="FIELD",
        )
        findings = validate(spec, {})
        assert any(f.id == "R13" and f.severity == "block" for f in findings)


class TestApplyAnswer:
    def test_answer_writes_onto_spec(self):
        spec = _spec()
        apply_answer(spec, "rock.porosity", 0.22)
        assert spec.reservoir.porosity == 0.22

    def test_unknown_id_is_ignored(self):
        spec = _spec()
        apply_answer(spec, "bogus.path", 999)
        assert spec.reservoir.porosity != 999

    def test_well_answer_writes_onto_well(self):
        spec = _spec()
        apply_answer(spec, "wells[0].target_rate", 1234.0)
        assert spec.wells[0].target_rate == 1234.0

    def test_scenario_answer_writes_enum(self):
        spec = _spec()
        apply_answer(spec, "intent.scenario", "wag")
        assert spec.scenario == ScenarioType.WAG


class TestBuildSpec:
    def test_defaults_fill_unanswered(self):
        spec = _spec()
        built = build_spec(spec, {"rock.porosity": 0.25})
        # dz default comes from the extraction (SPE1 pattern).
        assert built.reservoir.porosity == 0.25

    def test_none_answers_record_defaults(self):
        spec = _spec()
        built = build_spec(spec, {"rock.porosity": None})
        assert built.reservoir.porosity == spec.reservoir.porosity


def test_catalog_has_no_duplicate_ids():
    ids = [q.id for q in CATALOG]
    assert len(ids) == len(set(ids))


# ---------- Regressions found by code review on 2026-10-03 --------------------

class TestRuleDefaultsMatchBuilder:
    def test_thin_reservoir_datum_rule_follows_the_builder_clamp(self, tmp_path):
        # R02 fell back to top_depth + 50 while the builder clamps the EQUIL
        # datum to the grid midpoint. On a 20 ft-thick grid the rule then
        # blocked a deck the builder renders happily.
        from opm_ai.builder.builder import build_deck_from_spec
        from opm_ai.builder.interview.rules import validate

        spec, _ = extract_parameters_offline_with_provenance(
            "5x5x2 depletion, depth 9000 ft, one producer"
        )
        spec.reservoir.nz = 2
        spec.reservoir.dz = [10.0, 10.0]
        blocking = [f for f in validate(spec, {}) if f.severity == "block"]
        assert not blocking, [f.message for f in blocking]
        deck, lint = build_deck_from_spec(spec)
        assert lint.passed

    def test_datum_outside_the_grid_is_still_blocked(self):
        from opm_ai.builder.interview.rules import validate

        spec, _ = extract_parameters_offline_with_provenance(
            "5x5x2 depletion, depth 9000 ft, one producer"
        )
        spec.reservoir.nz = 2
        spec.reservoir.dz = [10.0, 10.0]
        spec.equil_datum_depth = 900.0  # far above the grid
        blocking = [f for f in validate(spec, {}) if f.severity == "block"]
        assert any("outside the grid span" in f.message for f in blocking)


class TestWellIndexBounds:
    """Grid indices are 1-based on both ends.

    WellSpec validates on construction, but the interview writes answers
    with setattr, which skips pydantic. So an out-of-range index only ever
    arrives that way - which is why R07 needs the lower bound.
    """

    def _spec_with_mutated_well(self, **field_values):
        from opm_ai.builder.extract import extract_parameters_offline

        spec = extract_parameters_offline("10x10x3 depletion, one producer")
        assert spec.wells, "expected the extractor to produce a well"
        for name, value in field_values.items():
            setattr(spec.wells[0], name, value)  # the unvalidated path
        return spec

    def test_zero_index_is_blocked(self):
        from opm_ai.builder.interview import validate

        spec = self._spec_with_mutated_well(i=0)
        blocking = [f for f in validate(spec, {}) if f.severity == "block"]
        assert any("outside the grid" in f.message for f in blocking), \
            [f.message for f in blocking]

    def test_negative_completion_layer_is_blocked(self):
        from opm_ai.builder.interview import validate

        spec = self._spec_with_mutated_well(k1=0)
        blocking = [f for f in validate(spec, {}) if f.severity == "block"]
        assert any("completion layers" in f.message for f in blocking), \
            [f.message for f in blocking]

    def test_index_past_the_grid_is_blocked(self):
        from opm_ai.builder.interview import validate

        spec = self._spec_with_mutated_well(i=999)
        blocking = [f for f in validate(spec, {}) if f.severity == "block"]
        assert any("outside the grid" in f.message for f in blocking)

    def test_valid_well_is_not_blocked(self):
        from opm_ai.builder.interview import validate

        spec = extract_parameters_offline("10x10x3 depletion, one producer")
        blocking = [f for f in validate(spec, {}) if f.severity == "block"]
        assert not blocking, [f.message for f in blocking]
