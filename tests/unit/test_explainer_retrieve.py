"""Unit tests for explainer retrieval module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from opm_ai.explainer.ingest import read_teaching_notes
from opm_ai.explainer.retrieve import build_knowledge_base, retrieve_chunks, _load_kb, _bm25_score, _tokenize
from opm_ai.explainer.models import ExplanationLevel, Citation


def test_tokenize():
    """Test simple tokenizer."""
    tokens = _tokenize("Water Breakthrough WCONPROD!")
    assert tokens == ["water", "breakthrough", "wconprod"]


def test_bm25_score_basic():
    """Test BM25 scoring function."""
    from opm_ai.explainer.retrieve import _build_bm25_index

    chunks = [
        {"text": "water breakthrough fractional flow buckley leverett", "source_id": "a", "source_type": "teaching_note"},
        {"text": "oil recovery material balance depletion drive", "source_id": "b", "source_type": "teaching_note"},
    ]
    index = _build_bm25_index(chunks)

    # Query matching first doc
    score_a = _bm25_score(["water", "breakthrough"], index, 0)
    score_b = _bm25_score(["water", "breakthrough"], index, 1)

    assert score_a > score_b, "Doc 0 should score higher for water breakthrough query"


def test_retrieve_chunks_teaching_notes_only(tmp_path):
    """Test retrieval using only teaching notes KB."""
    persist_dir = tmp_path / "kb"
    build_knowledge_base([], persist_dir, "dummy-model")

    # Query for water breakthrough
    citations = retrieve_chunks("water breakthrough watercut", k=5, level="intermediate", persist_dir=persist_dir)

    assert len(citations) >= 1, "Should find at least 1 citation"
    assert all(isinstance(c, Citation) for c in citations)
    assert all(c.snippet for c in citations)

    # Check that waterflood-breakthrough teaching note is found
    source_ids = [c.source_id for c in citations]
    assert any("waterflood" in sid or "breakthrough" in sid for sid in source_ids), \
        f"Expected waterflood/breakthrough note, got {source_ids}"


def test_retrieve_chunks_respects_k(tmp_path):
    """Test that k parameter is respected."""
    persist_dir = tmp_path / "kb"
    build_knowledge_base([], persist_dir, "dummy-model")

    for k in [1, 2, 3, 5, 10]:
        citations = retrieve_chunks("test query", k=k, persist_dir=persist_dir)
        assert len(citations) <= k, f"Expected at most {k} citations, got {len(citations)}"


def test_retrieve_chunks_level_bias_beginner(tmp_path):
    """Test beginner level boosts teaching notes."""
    persist_dir = tmp_path / "kb"
    build_knowledge_base([], persist_dir, "dummy-model")

    # With only teaching notes, beginner should still work
    citations = retrieve_chunks("watercut", k=5, level="beginner", persist_dir=persist_dir)
    assert len(citations) >= 1


def test_retrieve_chunks_level_bias_advanced(tmp_path):
    """Test advanced level boosts technical docs (ecl_td)."""
    # With only teaching notes, both levels should work similarly
    persist_dir = tmp_path / "kb"
    build_knowledge_base([], persist_dir, "dummy-model")

    citations = retrieve_chunks("watercut", k=5, level="advanced", persist_dir=persist_dir)
    assert len(citations) >= 1


def test_kb_cache_reload(tmp_path):
    """Test that KB is cached and reused."""
    persist_dir = tmp_path / "kb"
    build_knowledge_base([], persist_dir, "dummy-model")

    # First load
    index1 = _load_kb(persist_dir)
    # Second load should return cached
    index2 = _load_kb(persist_dir)

    assert index1 is index2, "KB should be cached"


def test_build_knowledge_base_caps_ecl_rm(tmp_path):
    """Test that ecl_rm is capped at 500 files to keep build fast."""
    # Create a fake ecl_rm with many files
    fake_ecl_rm = tmp_path / "ecl_rm"
    fake_ecl_rm.mkdir()

    # Create 600 small HTML files
    for i in range(600):
        (fake_ecl_rm / f"KEYWORD{i}.html").write_text(f"<html><body>Keyword {i} content</body></html>")

    persist_dir = tmp_path / "kb"
    build_knowledge_base([fake_ecl_rm], persist_dir, "dummy-model")

    import json
    with (persist_dir / "kb.json").open() as f:
        data = json.load(f)

    # Should cap at 500 ecl_rm chunks + teaching notes
    ecl_rm_count = sum(1 for c in data["chunks"] if c["source_type"] == "ecl_rm")
    assert ecl_rm_count <= 500, f"ecl_rm chunks should be capped at 500, got {ecl_rm_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])