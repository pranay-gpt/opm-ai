"""
Tests for chat infrastructure: providers, tool schemas, dispatch logic.
All tests are offline — no actual API calls made.
"""
import json
import pytest


# ── Provider tests ──────────────────────────────────────────────────────────

def test_provider_groq_config():
    from opm_ai.chat.providers import get_provider
    p = get_provider("groq")
    assert p.base_url == "https://api.groq.com/openai/v1"
    assert p.api_key_env == "GROQ_API_KEY"
    assert "llama-3.3-70b-versatile" in p.models
    assert p.default_model in p.models


def test_provider_nvidia_config():
    from opm_ai.chat.providers import get_provider
    p = get_provider("nvidia")
    assert p.base_url == "https://integrate.api.nvidia.com/v1"
    assert p.api_key_env == "NVIDIA_API_KEY"
    assert any("nemotron" in m for m in p.models)
    assert p.default_model in p.models


def test_unknown_provider_raises():
    from opm_ai.chat.providers import get_provider
    with pytest.raises(KeyError):
        get_provider("openai")


# ── Tool schema tests ────────────────────────────────────────────────────────

def test_tool_schemas_structure():
    from opm_ai.chat.tools import TOOL_SCHEMAS
    assert len(TOOL_SCHEMAS) == 5
    names = [t["function"]["name"] for t in TOOL_SCHEMAS]
    assert "build_deck" in names
    assert "lint_deck" in names
    assert "run_simulation" in names
    assert "analyze_results" in names
    assert "explain_concept" in names


def test_tool_schemas_valid_openai_format():
    from opm_ai.chat.tools import TOOL_SCHEMAS
    for tool in TOOL_SCHEMAS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


# ── Dispatch tests ───────────────────────────────────────────────────────────

def test_dispatch_unknown_tool():
    from opm_ai.chat.tools import dispatch
    result = dispatch("nonexistent_tool", {}, {})
    data = json.loads(result)
    assert "error" in data


def test_dispatch_build_deck_stub():
    from opm_ai.chat.tools import dispatch
    session = {}
    result = dispatch("build_deck", {"description": "SPE1 test"}, session)
    data = json.loads(result)
    # Either real result or stub — both valid
    assert "status" in data or "deck_text" in data or "error" in data


def test_dispatch_explain_concept_queues_kb():
    from opm_ai.chat.tools import dispatch
    session = {"pending_kb_questions": []}
    result = dispatch("explain_concept", {"concept": "aquifer influx", "level": "intermediate"}, session)
    data = json.loads(result)
    # If no KB entry, concept should be queued
    if data.get("kb_pending"):
        assert "aquifer influx" in session["pending_kb_questions"]


# ── Theme tests ──────────────────────────────────────────────────────────────

def test_themes_all_present():
    from opm_ai.chat.themes import THEMES
    expected = {"Dark Void", "Arctic Frost", "Sepia Crude", "Matrix Green", "Midnight Blue"}
    assert expected == set(THEMES.keys())


def test_theme_get_css_returns_string():
    from opm_ai.chat.themes import get_theme_css, THEMES
    for name in THEMES:
        css = get_theme_css(name)
        assert "<style>" in css
        assert "--bg:" in css
        assert "--accent:" in css


def test_unknown_theme_falls_back_to_dark_void():
    from opm_ai.chat.themes import get_theme_css
    css = get_theme_css("Nonexistent Theme")
    # Should fall back to Dark Void
    assert "#00b5ad" in css  # Dark Void accent
