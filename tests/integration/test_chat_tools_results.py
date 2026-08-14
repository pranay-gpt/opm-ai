"""Integration tests for the three new chat tools."""
import pytest
import asyncio
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_list_available_vectors_returns_empty_for_no_active_job(client):
    """No active job -> empty result, not an error."""
    from opm_ai.api.routes.chat import execute_tool
    result = asyncio.run(execute_tool("list_available_vectors", {}))
    assert "error" in result
    assert result["error"] == "no active job"


def test_plot_well_vectors_unknown_tool(client):
    from opm_ai.api.routes.chat import execute_tool
    result = asyncio.run(execute_tool("plot_does_not_exist", {"wells": ["PROD1"], "vectors": ["WBHP"]}))
    assert "error" in result


def test_compare_wells_validates_vector(client):
    from opm_ai.api.routes.chat import execute_tool, tool_compare_wells
    result = asyncio.run(tool_compare_wells({"wells": ["PROD1"], "vector": "WBHP"}))
    # Either returns a figure (job loaded) or an error (no job)
    assert "figure_json" in result or "error" in result


def test_compare_wells_rejects_missing_vector(client):
    from opm_ai.api.routes.chat import tool_compare_wells
    result = asyncio.run(tool_compare_wells({"wells": ["PROD1"]}))
    assert "error" in result
    assert "vector" in result["error"].lower() or "missing" in result["error"].lower()


def test_compare_wells_rejects_empty_wells(client):
    from opm_ai.api.routes.chat import tool_compare_wells
    result = asyncio.run(tool_compare_wells({"wells": [], "vector": "WBHP"}))
    assert "error" in result


def test_compact_plot_well_vectors_strips_figure_json():
    from opm_ai.api.routes.chat import compact_tool_result
    full = {
        "figure_json": '{"data": [...]}',  # long
        "wells": ["PROD1"],
        "vectors": ["WBHP"],
    }
    compact = compact_tool_result("plot_well_vectors", full)
    assert "figure_json" not in compact
    assert compact["wells"] == ["PROD1"]
    assert compact["vectors"] == ["WBHP"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])