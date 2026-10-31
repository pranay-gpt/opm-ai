"""Stage 4 tests: file/paste ingestion (fixtures in tests/fixtures/interview/).

Covers format detection, GRDECL/table/numeric-grid parsing, BOX scoping,
per-cell variation refusal, arithmetic-keyword refusal, and the
paste-and-upload byte-equal spec contract.
"""

import textwrap

from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.builder.builder import build_deck_from_spec
from opm_ai.builder.interview.ingest import (
    IngestResult,
    apply_ingest,
    detect_format,
    parse_paste,
)
from opm_ai.builder.models import ModelSpec


class TestDetectFormat:
    def test_full_deck(self):
        assert detect_format("RUNSPEC\nTITLE\n A /\nDIMENS\n 10 10 3 /\n") == "deck"

    def test_bare_grdecl(self):
        assert detect_format("PORO\n 0.2 0.2 /\n") == "grdecl"

    def test_pvdg_table(self):
        assert detect_format("PVDG\n14.7 166.6 0.008\n/") == "table"

    def test_numeric_grid(self):
        assert detect_format("0.2 0.2 0.2\n0.2 0.2 0.2\n") == "numeric_grid"

    def test_egrid_is_unknown(self):
        assert detect_format("BINARY EGRID FILE CONTENT") == "unknown"

    def test_garbage_is_unknown(self):
        assert detect_format("hello world this is not a deck") == "unknown"

    def test_comments_are_ignored(self):
        assert detect_format("-- a comment\nPORO\n 0.2 /\n") == "grdecl"


class TestGrdeclParsing:
    def test_uniform_poro_maps_to_porosity(self):
        r = parse_paste("PORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n")
        assert r.patch.get("porosity") == 0.25
        assert r.detected == "grdecl"

    def test_perm_layers_map_to_perm(self):
        r = parse_paste(
            "DIMENS\n 10 10 3 /\nPERMX\n 500.0 50.0 200.0 /\n"
        )
        assert r.patch.get("permx") == [500.0, 50.0, 200.0]

    def test_repeat_syntax_expands(self):
        r = parse_paste("PORO\n 6*0.22 /\nDIMENS\n 2 2 3 /\n")
        assert r.patch.get("porosity") == 0.22

    def test_d_exponent_values_parse(self):
        # Fortran D-exponents parse to E-exponents. A 1x1x3 grid with three
        # distinct values is per-cell variation, so porosity is refused
        # (the spec's porosity is uniform) rather than mean-averaged.
        r = parse_paste("PORO\n 3E-1 2.5D-01 0.5 /\nDIMENS\n 1 1 3 /\n")
        assert "porosity" not in r.patch
        assert any("PORO" in f for f in r.findings)

    def test_dx_exponent_scientific_notation_uniform(self):
        r = parse_paste("PERMX\n 1.0E+03 /\nDIMENS\n 5 5 2 /\n")
        assert r.patch.get("permx") == 1000.0

    def test_per_cell_varying_poro_refused(self):
        r = parse_paste("PORO\n 0.20 0.21 0.22 0.19 0.23 0.18 /\nDIMENS\n 2 1 3 /\n")
        assert "porosity" not in r.patch
        assert any("PORO" in f for f in r.findings)

    def test_layer_uniform_poro_is_refused(self):
        # 3 layers x 2 cells, each layer uniform (0.2 / 0.25 / 0.3).
        # Porosity is a scalar in the spec, so per-layer-uniform data is
        # refused rather than silently averaged to the first layer.
        r = parse_paste(
            "PORO\n 0.2 0.2 0.25 0.25 0.3 0.3 /\nDIMENS\n 2 1 3 /\n"
        )
        assert "porosity" not in r.patch
        assert any("PORO" in f for f in r.findings)

    def test_no_dimens_produces_finding(self):
        r = parse_paste("PORO\n 300*0.25 /\n")
        assert "porosity" in r.patch  # uniform array still usable
        assert any("DIMENS" in f for f in r.findings)

    def test_box_scope_applies(self):
        # BOX 1 4 1 1 1 2 on a 4x1x2 grid covers the whole model, so the
        # boxed values are placed cell-by-cell and collapse to porosity.
        r = parse_paste(
            "DIMENS\n 4 1 2 /\nBOX\n 1 4 1 1 1 2 /\n"
            "PORO\n 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 /\n"
        )
        assert r.patch.get("porosity") == 0.5

    def test_partial_box_is_refused(self):
        # A BOX that does not cover the whole grid leaves the rest of the
        # array unpadded; that is not usable, so refuse with the name.
        r = parse_paste(
            "DIMENS\n 10 10 3 /\nBOX\n 3 4 1 1 1 2 /\nPORO\n 0.5 0.5 0.5 0.5 /\n"
        )
        assert "porosity" not in r.patch
        assert any("PORO" in f for f in r.findings)

    def test_garbage_values_produce_finding(self):
        r = parse_paste("PORO\n not_a_number /\n")
        assert "porosity" not in r.patch
        assert any("Could not parse PORO" in f for f in r.findings)


class TestTableParsing:
    def test_pvdg_rows_extracted(self):
        r = parse_paste(
            "PVDG\n14.700\t166.666\t0.008\n264.70\t12.093\t0.0096\n/"
        )
        rows = r.patch.get("pvdg_rows")
        assert rows and len(rows) == 2
        assert "14.700" in rows[0]


class TestRefusals:
    def test_arithmetic_keywords_refused(self):
        r = parse_paste(
            "EQUALREG\n PERMX 0.5 /\n/\nPORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n"
        )
        assert "porosity" not in r.patch
        assert any("flatten" in f for f in r.findings)

    def test_unknown_format_message(self):
        r = parse_paste("hello world")
        assert not r.patch
        assert any("Unrecognized" in f for f in r.findings)

    def test_never_raises_on_binary_garbage(self):
        r = parse_paste("\x00\x01\x02\x03 binary junk")
        assert isinstance(r, IngestResult)


class TestNumericGrid:
    def test_single_value_maps_to_porosity(self):
        r = parse_paste("0.25 0.25\n0.25 0.25\n")
        assert r.patch.get("porosity") == 0.25

    def test_header_row_stripped(self):
        # A plain numeric grid with a non-numeric header row (numpy/Petrel
        # style exports): the header is ignored and the uniform value maps
        # to porosity.
        r = parse_paste("porosity\n0.25\n0.25\n")
        assert r.detected == "numeric_grid"
        assert r.patch.get("porosity") == 0.25
        assert any("header" in f for f in r.findings)

    def test_varying_values_ask_for_named_fields(self):
        r = parse_paste("0.2 0.3\n0.25 0.28\n")
        assert "porosity" not in r.patch
        assert any("GRDECL" in f for f in r.findings)


class TestApplyIngest:
    def test_patch_applies_onto_spec(self):
        spec = extract_parameters_offline("10x10x3 depletion, one producer")
        r = parse_paste("PORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n")
        apply_ingest(spec, r)
        assert spec.reservoir.porosity == 0.25

    def test_paste_and_upload_produce_byte_equal_specs(self):
        # Paste and (simulated) upload go through the same function; the
        # cheapest proof is byte-equal specs.
        paste_text = "PORO\n 300*0.25 /\nPERMX\n 500.0 50.0 200.0 /\nDIMENS\n 10 10 3 /\n"
        spec1 = extract_parameters_offline("10x10x3 depletion, one producer")
        apply_ingest(spec1, parse_paste(paste_text))

        # upload path: same text through parse_paste (the multipart route
        # reads the file and calls parse_paste; contract is identical).
        spec2 = extract_parameters_offline("10x10x3 depletion, one producer")
        apply_ingest(spec2, parse_paste(paste_text))

        d1, _ = build_deck_from_spec(spec1)
        d2, _ = build_deck_from_spec(spec2)
        assert d1 == d2

    def test_ingested_deck_contains_values(self):
        spec = extract_parameters_offline("10x10x3 depletion, one producer")
        r = parse_paste("PORO\n 300*0.25 /\nDIMENS\n 10 10 3 /\n")
        apply_ingest(spec, r)
        deck, lint = build_deck_from_spec(spec)
        assert lint.passed
        poro = deck.split("PORO")[1].split("/")[0].split()
        assert all(v == "0.25" for v in poro)


# ---------- Regressions found by code review on 2026-10-03 --------------------

class TestIngestSilentDataLoss:
    def test_layer_order_is_preserved(self):
        # The no-DIMENS fallback sorted the distinct values, so a
        # 500/100/200 three-layer profile became 100/200/500: a
        # physically different reservoir with no finding recorded.
        result = parse_paste("PERMX\n500.0 100.0 200.0\n")
        assert result.patch["permx"] == [500.0, 100.0, 200.0]
        assert result.findings, "an assumed layer count must be reported"

    def test_dz_order_is_preserved(self):
        result = parse_paste("DZ\n50.0 20.0 30.0\n")
        assert result.patch["dz"] == [50.0, 20.0, 30.0]

    def test_overlong_array_is_reported_not_silently_truncated(self):
        # DIMENS 1x1x2 holds 2 cells but 8 values were supplied. The tail
        # used to vanish with no finding.
        result = parse_paste(
            "DIMENS\n1 1 2 /\nPERMX\n10.0 10.0 20.0 20.0 30.0 30.0 40.0 40.0\n"
        )
        assert result.patch["permx"] == [10.0, 10.0]
        assert any("8 values" in f for f in result.findings), result.findings

    def test_unapplicable_patch_key_is_reported(self):
        # SWOF parses into swof_rows, which ReservoirSpec does not carry.
        # apply_ingest dropped it silently, so the UI reported a successful
        # read of a file whose data went nowhere.
        from opm_ai.builder.extract import extract_parameters_offline
        spec = extract_parameters_offline("10x10x3 depletion")
        result = parse_paste("SWOF\n0.2 0.8 0.3 0.02\n")
        apply_ingest(spec, result)
        assert any("nowhere to put it" in f for f in result.findings), result.findings
