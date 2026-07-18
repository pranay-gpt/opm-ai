"""
Pytest configuration for OPM-AI tests.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_opm_input():
    """Provide a sample OPM input file content."""
    return """
RUNSPEC
  METRIC
  METRIC
  OIL
  GAS
  WATER
  DENSITY 700
  VISC 0.5
  PRESSURE 200
  TEMP 80
  /
GRID
  DX 100 100 100
  DY 100 100 100
  DZ 10 10 10
  /
PROPS
  PORO 
  0.2 0.2 0.2 0.2 0.2 0.2 0.2 0.2 0.2 0.2 *
  /
  PERMX
  100 100 100 100 100 100 100 100 100 100 *
  /
ENDFIN
"""
