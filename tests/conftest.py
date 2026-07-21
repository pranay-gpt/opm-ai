"""
Pytest configuration for OPM-AI tests.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from opm_ai.settings import settings

# Repo-root-relative fixture locations, valid on any machine/CI runner.
TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"


@pytest.fixture(autouse=True)
def _force_offline_llm(request):
    """Keep the suite deterministic: force LLM offline regardless of .env.

    Tests marked @pytest.mark.live opt out (they gate themselves on env vars).
    """
    if request.node.get_closest_marker("live"):
        yield
        return
    saved = settings.llm_provider
    settings.llm_provider = "offline"
    yield
    settings.llm_provider = saved


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


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to tests/fixtures, resolved from the repo, not the CWD."""
    return FIXTURES_DIR


@pytest.fixture
def spe1_deck() -> Path:
    """Absolute path to the SPE1CASE1 reference deck."""
    return FIXTURES_DIR / "spe1" / "SPE1CASE1.DATA"
