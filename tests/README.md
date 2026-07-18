# OPM-AI Test Suite

This directory contains the test suite for the OPM-AI tool.

## Test Structure

```
tests/
├── unit/                 # Unit tests
│   ├── test_input_parser.py     # Tests for parsing OPM input files
│   └── test_keyword_processing.py # Tests for keyword processing
├── integration/          # Integration tests (to be implemented)
├── fixtures/             # Test data fixtures (provided)
├── eclipse/
   ├── data/ # Test data fixtures (provided)
├── eclipse_fileformat/             # Eclipse DATA format rule & test examples (provided)
├── conftest.py          # Pytest configuration and fixtures
├── pytest.ini           # Pytest configuration
└── README.md            # This file
```

## Test Fixtures

The test fixtures are located in `tests/fixtures/` and contain various OPM simulation test cases including:

- SPE1: Single phase oil model
- SPE10: Black oil model with water injection
- Polymer: Polymer flooding simulation
- And many others...

Each fixture directory typically contains:
- `.DATA` files: OPM input files
- Reference output files: For comparison with simulation results
- Documentation files: `.md` files describing the test case

## Running Tests

To run the test suite:

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run tests with verbose output
pytest -v

# Run tests for a specific fixture
pytest -k "spe1"
```

## Test Categories

1. **Unit Tests**: Test individual components like file parsing, keyword processing
2. **Integration Tests**: Test end-to-end workflows (to be implemented)
3. **Fixture Validation**: Tests that verify the test data is accessible and valid

## Writing Tests

When adding new tests:
1. Place unit tests in `tests/unit/`
2. Place integration tests in `tests/integration/`
3. Use the fixtures in `tests/fixtures/` for test data
4. Follow the naming convention: `test_*.py`
5. Use appropriate pytest markers for test categorization

## Dependencies

The test suite requires:
- pytest
- opm_ai package (should be installed in development mode)

Install test dependencies:
```bash
pip install pytest
```

The opm_ai package should be available via the editable installation.
