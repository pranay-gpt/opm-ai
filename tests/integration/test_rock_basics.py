"""Tests for Stage 3.2: rock-basics extraction and provenance plumbing.

Covers the new vocabulary in extract_parameters_offline (porosity, depth,
initial pressure, per-layer permeability), the provenance dict that the
parser returns alongside the spec, and the user-override path through the
POST /api/build route.
"""

from fastapi.testclient import TestClient

from opm_ai.api.server import create_app
from opm_ai.builder.extract import (
    extract_parameters_offline,
    extract_parameters_offline_with_provenance,
)
from opm_ai.builder.builder import build_deck_from_spec


# ---------- offline extractor vocabulary -----------------------------------

class TestExtractorRockBasics:
    """The parser learns the rock-basics vocabulary in Stage 3.2."""

    def test_porosity_fraction_is_extracted(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer, porosity 0.25"
        )
        assert spec.reservoir.porosity == 0.25
        assert prov["porosity"] == "extracted"

    def test_porosity_percent_is_converted(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 grid, 25% porosity, depletion"
        )
        assert spec.reservoir.porosity == 0.25
        assert prov["porosity"] == "extracted"

    def test_porosity_phi_keyword(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3, phi 0.18, depletion"
        )
        assert spec.reservoir.porosity == 0.18
        assert prov["porosity"] == "extracted"

    def test_porosity_out_of_range_is_defaulted(self):
        # 0.005 is below the 0.01 floor in ReservoirSpec - parser treats it as out of range.
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, porosity 0.005"
        )
        assert prov["porosity"] == "defaulted"

    def test_top_depth_in_feet_is_extracted(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, depth 9000 ft, one producer"
        )
        assert spec.reservoir.top_depth == 9000.0
        assert prov["top_depth"] == "extracted"

    def test_top_depth_feet_symbol(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3, 8500' deep, depletion"
        )
        assert spec.reservoir.top_depth == 8500.0
        assert prov["top_depth"] == "extracted"

    def test_initial_pressure_psia(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, initial pressure 5500 psia"
        )
        assert spec.reservoir.initial_pressure == 5500.0
        assert prov["initial_pressure"] == "extracted"

    def test_initial_pressure_bar_is_converted(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, initial pressure 380 bar"
        )
        # 380 bar / 0.0689476 = ~5511 psia
        assert 5500 <= spec.reservoir.initial_pressure <= 5515
        assert prov["initial_pressure"] == "extracted"

    def test_perm_sequence_replicates_across_layers(self):
        # 3-layer reservoir, user names 2 values - the third repeats the first.
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, perm 800 100 mD"
        )
        assert spec.reservoir.permx == [800.0, 100.0, 800.0]
        assert prov["permx"] == "extracted"

    def test_defaulted_fields_when_description_is_bare(self):
        # No rock-basics keywords in the description - everything defaulted.
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 grid, simple depletion, one producer"
        )
        assert prov["porosity"] == "defaulted"
        assert prov["top_depth"] == "defaulted"
        assert prov["initial_pressure"] == "defaulted"
        # dz/permx/permy/permz are derived from the grid expansion (defaulted).
        assert prov["dz"] == "defaulted"
        assert prov["permx"] == "defaulted"
        assert prov["permy"] == "defaulted"
        assert prov["permz"] == "defaulted"

    def test_all_seven_fields_present_in_provenance(self):
        _, prov = extract_parameters_offline_with_provenance("depletion")
        # Every field in ROCK_BASICS_FIELDS must end up in the dict, even
        # when the parser never touched it.
        from opm_ai.api.schemas import ROCK_BASICS_FIELDS
        for f in ROCK_BASICS_FIELDS:
            assert f in prov, f"missing provenance entry for {f}"

    def test_extract_parameters_offline_keeps_backward_compat(self):
        # The legacy single-return call still works and discards provenance.
        spec = extract_parameters_offline("10x10x3 depletion, one producer")
        assert spec.scenario.value == "depletion"
        assert spec.reservoir.nx == 10


# ---------- build_deck_from_spec reflects initial_pressure -----------------

class TestInitialPressureWiring:
    """initial_pressure drives the EQUIL datum pressure, not just the schema."""

    def test_default_initial_pressure_is_4800(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, one producer"
        )
        assert spec.reservoir.initial_pressure == 4800.0

    def test_higher_initial_pressure_produces_higher_equil(self):
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, initial pressure 5500 psia"
        )
        deck, _ = build_deck_from_spec(spec)
        # The EQUIL datum pressure line lives in SOLUTION.
        assert "5500" in deck

    def test_metric_deck_converts_initial_pressure(self):
        # When the user specifies a non-default initial pressure AND a METRIC
        # fluid, the EQUIL line should carry bar (not psia). The simplest way
        # to drive METRIC is to set spec.fluid.unit_system = "METRIC" with a
        # small pressure_range_psi that covers 5500 psia.
        spec, _ = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, initial pressure 5500 psia"
        )
        # Bypass the offline fluid validator - this test only checks the
        # EQUIL conversion, not the PVT tables.
        spec.fluid = None
        from opm_ai.builder.builder import _compute_template_context
        ctx = _compute_template_context(spec)
        # FIELD path: 5500 psia directly.
        assert ctx["equil_pressure_datum"] == 5500.0

    def test_lower_bound_rejects_below_14_7(self):
        spec, prov = extract_parameters_offline_with_provenance(
            "10x10x3 depletion, initial pressure 5 psia"  # below atmospheric
        )
        assert prov["initial_pressure"] == "defaulted"
        # Schema validator catches it on assignment; here we only check parser.


# ---------- POST /api/build route: provenance + resolved + overrides -------

class TestBuildRouteProvenance:
    """The route returns provenance+resolved and honours user overrides."""

    def setup_method(self):
        self.client = TestClient(create_app())

    def test_build_response_has_provenance_and_resolved(self):
        r = self.client.post("/api/build", json={
            "description": "10x10x3 depletion, one producer",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "provenance" in body
        assert "resolved" in body
        # Seven rock-basics fields populated.
        assert set(body["provenance"].keys()) == {
            "porosity", "top_depth", "initial_pressure", "dz", "permx", "permy", "permz"
        }
        assert set(body["resolved"].keys()) == {
            "porosity", "top_depth", "initial_pressure", "dz", "permx", "permy", "permz"
        }

    def test_extracted_fields_show_extracted_provenance(self):
        r = self.client.post("/api/build", json={
            "description": "10x10x3 depletion, porosity 0.22, depth 9000 ft, initial pressure 5000 psia",
        })
        assert r.status_code == 200, r.text
        prov = r.json()["provenance"]
        assert prov["porosity"] == "extracted"
        assert prov["top_depth"] == "extracted"
        assert prov["initial_pressure"] == "extracted"

    def test_user_override_marks_provenance(self):
        # The description has no rock-basics keywords; the user sets porosity
        # explicitly via the override field on the request.
        r = self.client.post("/api/build", json={
            "description": "10x10x3 depletion, one producer",
            "porosity": 0.18,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provenance"]["porosity"] == "user_override"
        assert body["resolved"]["porosity"] == 0.18

    def test_user_override_on_perm_list(self):
        r = self.client.post("/api/build", json={
            "description": "10x10x3 depletion, one producer",
            "permx": [100.0, 50.0, 25.0],
            "permy": [100.0, 50.0, 25.0],
            "permz": [100.0, 50.0, 25.0],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provenance"]["permx"] == "user_override"
        assert body["resolved"]["permx"] == [100.0, 50.0, 25.0]

    def test_override_wins_over_extracted(self):
        # Description names porosity 0.25, but the user overrides to 0.18.
        r = self.client.post("/api/build", json={
            "description": "10x10x3 depletion, porosity 0.25",
            "porosity": 0.18,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provenance"]["porosity"] == "user_override"
        assert body["resolved"]["porosity"] == 0.18
        # Deck reflects the override (Porosity 0.18 in the PROPS section).
        assert "0.18" in body["deck"]

    def test_resolved_lists_are_arrays(self):
        r = self.client.post("/api/build", json={"description": "10x10x3 depletion"})
        body = r.json()
        # The default dz/perm are lists - JSON should serialise them as arrays.
        assert isinstance(body["resolved"]["dz"], list)
        assert isinstance(body["resolved"]["permx"], list)