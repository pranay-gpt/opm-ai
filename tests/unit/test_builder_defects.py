"""Stage 1 regression tests: builder defects found by the reservoir-context
research workflow (runId wf_98eb33d6-42c), each verified against the code
before fixing.

- B2: EQUIL datum depth hardcoded to SPE1 (8400 ft) does not follow
  top_depth. Fix: when the SPE1 default falls outside the grid span, the
  datum is clamped to the grid midpoint. Default decks stay byte-identical.
- B3: ReservoirSpec.dx/dy accept lists but base.j2 string-multiplies them
  and _compute_metric_context multiplies a list by a float.
- B4: spec.field_units=False is silently ignored (deck always renders
  FIELD). Fix: honour it, rejecting METRIC-without-fluid with ValueError
  because the built-in PVT tables are FIELD-only.
- Tokenizer: bare-exponent (1E5, 3E-6) and Fortran D-exponent (2.5D+01)
  real exports were classified UNKNOWN and silently discarded.
"""

import pytest

from opm_ai.builder.builder import build_deck_from_spec, _compute_template_context
from opm_ai.builder.extract import extract_parameters_offline_with_provenance
from opm_ai.preprocess import FluidDescriptor


# ---------- B2: EQUIL datum follows the grid --------------------------------

class TestDatumFollowsGrid:
    def test_datum_clamped_into_grid_for_shallow_reservoir(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, depth 2000 ft, one producer"
        )
        spec.reservoir.dz = [50.0, 50.0]
        spec.reservoir.nz = 2
        deck, lint = build_deck_from_spec(spec)
        assert lint.passed
        equil = deck.split("EQUIL")[1].splitlines()[1]
        datum = float(equil.replace("/", "").split()[0])
        # Grid spans 2000..2100 ft; the SPE1 default 8400 is far outside.
        assert 2000.0 <= datum <= 2100.0

    def test_default_deck_keeps_spe1_datum(self):
        # SPE1 default: top 8325, dz 20+30+50 -> span 8325..8445. The
        # 8400 default datum lies inside it and must not move.
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        deck, _ = build_deck_from_spec(spec)
        equil = deck.split("EQUIL")[1].splitlines()[1]
        assert float(equil.replace("/", "").split()[0]) == 8400.0

    def test_explicit_datum_override_still_wins(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, depth 2000 ft, one producer"
        )
        spec.reservoir.dz = [50.0, 50.0]
        spec.reservoir.nz = 2
        spec.equil_datum_depth = 2050.0
        deck, _ = build_deck_from_spec(spec)
        equil = deck.split("EQUIL")[1].splitlines()[1]
        assert float(equil.replace("/", "").split()[0]) == 2050.0


# ---------- B3: dx/dy list support -------------------------------------------

class TestDxDyLists:
    def test_dx_list_renders_numeric_deck_that_lints(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        spec.reservoir.dx = [100.0, 200.0]  # per-layer uniform dx
        deck, lint = build_deck_from_spec(spec)
        assert lint.passed
        dx_block = deck.split("DX\n")[1].split("/")[0].split()
        assert len(dx_block) == spec.reservoir.nx * spec.reservoir.ny * spec.reservoir.nz
        assert all(v.replace(".", "", 1).isdigit() for v in dx_block)

    def test_dy_list_renders_numeric_deck_that_lints(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        spec.reservoir.dy = [150.0, 250.0]
        deck, lint = build_deck_from_spec(spec)
        assert lint.passed

    def test_dx_list_with_metric_fluid_does_not_raise(self):
        # METRIC path multiplied the list by a float -> TypeError, which
        # routes/build.py's except ValueError does not catch (500).
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        spec.reservoir.dx = [100.0, 200.0, 300.0]
        spec.fluid = FluidDescriptor(
            api_gravity=35, gas_specific_gravity=0.75, gor=800,
            reservoir_temp_c=93.33, salinity_ppm=50000,
            pressure_range_psi=(1.01325, 344.74), unit_system="METRIC",
        )
        ctx = _compute_template_context(spec)
        assert isinstance(ctx["dx_list"], list)
        assert ctx["dx_list"][0] == pytest.approx(100.0 * 0.3048)


# ---------- B4: field_units honoured -----------------------------------------

class TestFieldUnitsHonoured:
    def test_metric_without_fluid_is_rejected(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        spec.field_units = False
        spec.fluid = None
        with pytest.raises(ValueError, match="METRIC"):
            build_deck_from_spec(spec)

    def test_field_default_unchanged(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        deck, lint = build_deck_from_spec(spec)
        assert lint.passed
        assert "FIELD" in deck.split("START")[0]


# ---------- Tokenizer: exponent real literals --------------------------------

class TestTokenizerExponentReals:
    @pytest.mark.parametrize("text", ["1E5", "3E-6", "1e-3", "2.5D+01", ".5", "1.0E+02"])
    def test_exponent_forms_classify_real(self, text):
        from opm_ai.linter.v2.tokenizer import tokenize_line, TokenKind
        tokens = [t for t in tokenize_line(text) if t.kind != TokenKind.EOL]
        assert tokens[0].kind == TokenKind.REAL, f"{text} -> {tokens[0].kind}"

    def test_plain_int_still_int(self):
        from opm_ai.linter.v2.tokenizer import tokenize_line, TokenKind
        tokens = [t for t in tokenize_line("250") if t.kind != TokenKind.EOL]
        assert tokens[0].kind == TokenKind.INT
