# OPM-AI

AI-assisted reservoir simulation workbench for petroleum engineering education.

## Features

- **Natural Language Deck Building**: Describe a reservoir in plain English, get a valid OPM Flow deck
- **Smart Linting**: Static analysis + optional LLM explanations for deck diagnostics
- **One-Click Simulation**: Run OPM Flow simulations with automatic output parsing
- **Interactive Results**: Plotly charts + optional ResInsight 3D visualization
- **Educational Explanations**: LLM-powered concept explanations

## Quick Start

```bash
# Install dependencies
pip install -e .

# Configure (copy .env.example to .env and add your API keys)
cp .env.example .env

# Run the Streamlit app
streamlit run opm_ai/app/streamlit_app.py

# Or use the CLI
opm-ai build "10x10x5 grid, simple depletion, one producer"
opm-ai lint deck.DATA
opm-ai run deck.DATA
```

## Architecture

- **Builder**: Template-based deck generation (Jinja2) with LLM parameter extraction
- **Linter**: Pure-Python deck parser + rule engine
- **Runner**: Subprocess to OPM Flow with crash parsing
- **Postprocess**: resfo-based summary reading, KPI extraction, Plotly charts, ResInsight 3D bridge
- **LLM**: Unified client (Groq/OpenAI/NVIDIA NIM) with offline fallback

## Development

```bash
# Run tests
pytest

# Run specific test
pytest tests/unit/test_input_parser.py -v
```

## Requirements

- Python 3.12+
- OPM Flow 2026.04+ (at `/usr/bin/flow`)
- Optional: ResInsight (at `/usr/bin/ResInsight`) for 3D visualization
- Optional: Groq/OpenAI API key for LLM features

## License

MIT
