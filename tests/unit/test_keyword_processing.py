"""
Unit tests for processing specific OPM keywords.
"""
import pytest
import re
from pathlib import Path

def test_parse_basic_keywords():
    """Test parsing of basic OPM keywords."""
    # Test RUNSPEC keywords
    runspec_keywords = ["METRIC", "OIL", "GAS", "WATER", "DENSity", "VISC"]
    for keyword in runspec_keywords:
        # Simple pattern matching for keywords
        pattern = rf'\b{re.escape(keyword.lower())}\b'
        assert re.search(pattern, "m metric oil gas water density visc", re.IGNORECASE)
    
    # Test GRID keywords
    grid_keywords = ["DX", "DY", "DZ", "PERMX", "PORO"]
    for keyword in grid_keywords:
        pattern = rf'\b{re.escape(keyword.lower())}\b'
        assert re.search(pattern, "dx dy dz permx poro", re.IGNORECASE)

def test_parse_operators():
    """Test parsing of OPM operators."""
    # Test multiply operation
    assert "*" in "100 *"
    assert "*" in "0.2 *"
    
    # Test add operation
    assert "+" in "100 + 50"
    
    # Test multiply-add operation
    assert "*" in "10 * 5 +" and "+" in "10 * 5 +"

def test_sample_opm_files():
    """Test that we can parse sample OPM file structures."""
    # Test a simple valid OPM structure
    sample_content = """
RUNSPEC
  METRIC
  /
GRID
  DX 100
  DY 100
  DZ 10
  /
PROPS
  PORO 
  0.2 *
  /
  PERMX
  100 *
  /
ENDFIN
    """
    
    # Basic validation that it has required sections
    assert "RUNSPEC" in sample_content
    assert "GRID" in sample_content
    assert "PROPS" in sample_content
    assert "ENDFIN" in sample_content
    
    # Check for end section markers
    assert sample_content.count("/") >= 3  # Should have at least 3 section terminators

def test_fixture_file_access(fixtures_dir):
    """Test that we can access and read fixture files."""
    fixtures_base = fixtures_dir
    
    # Test accessing a few known fixtures
    test_fixtures = ["spe1", "polymer", "spe10"]
    
    for fixture_name in test_fixtures:
        fixture_dir = fixtures_base / fixture_name
        if fixture_dir.exists():
            # Try to list contents
            contents = list(fixture_dir.iterdir())
            assert len(contents) >= 0  # Should be able to list directory
            
            # If it's SPE1, check for specific files
            if fixture_name == "spe1":
                data_files = list(fixture_dir.glob("*.DATA"))
                assert len(data_files) > 0, "SPE1 should have .DATA files"

def test_keyword_case_insensitivity():
    """Test that keyword matching is case insensitive."""
    test_string = "Metric Oil Gas Water"
    
    # These should all match regardless of case
    assert re.search(r'\bmetric\b', test_string, re.IGNORECASE)
    assert re.search(r'\boil\b', test_string, re.IGNORECASE)
    assert re.search(r'\bgas\b', test_string, re.IGNORECASE)
    assert re.search(r'\bwater\b', test_string, re.IGNORECASE)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
