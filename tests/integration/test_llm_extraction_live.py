"""Live LLM extraction test. Skipped unless a Groq key and provider opt-in
are present; default CI stays fully offline."""
import os

import pytest

from opm_ai.builder.builder import build_deck
from opm_ai.builder.extract import extract_parameters_llm
from opm_ai.builder.models import ModelSpec

_LIVE = bool(os.environ.get("GROQ_API_KEY")) and os.environ.get("LLM_PROVIDER") == "groq"


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.live
@pytest.mark.skipif(not _LIVE, reason="requires GROQ_API_KEY and LLM_PROVIDER=groq")
def test_live_llm_extraction_beyond_regex():
    """A description the regex extractor cannot parse yields a valid spec
    and a lint-passing deck via the LLM path."""
    desc = "a quarter five-spot pattern on a 12 by 12 by 2 grid with water injection at 1000 m3/day"
    spec = extract_parameters_llm(desc)
    assert isinstance(spec, ModelSpec)
    assert len(spec.wells) >= 1

    deck_string, lint_result = build_deck(desc, use_llm=True)
    assert "RUNSPEC" in deck_string
    assert lint_result.passed
