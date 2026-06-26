# opm-ai

As a petroleum engineer who has spent 7 years watching students struggle with ECLIPSE, I built this AI-assisted reservoir simulation workbench on top of the open-source OPM Flow simulator — so anyone can learn reservoir simulation through simple chat, not cryptic keywords.

## Key Features

- 💬 Chat-driven interface — describe a reservoir in plain English, get a valid simulation deck
- 🔍 AI Deck Linter — paste any broken deck, get plain-English diagnosis with fixes
- ▶️ One-click simulation — runs OPM Flow under the hood, no manual setup
- 📊 Visual results — ResInsight integration for 3D views, plots, and flow diagnostics
- 🎓 Educational explainer — asks "why did watercut spike?" and gets a textbook-cited answer
- 🆓 Free and open-source — GPL-3.0, no license, no SLB login

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose installed
- A free [Groq API key](https://console.groq.com) (takes 2 minutes)

### Run in 3 steps

```bash
# 1. Clone the repo (with test fixtures)
git clone --recurse-submodules https://github.com/pranay-gpt/opm-ai.git
cd opm-ai

# 2. Set your API keys
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

# 3. Launch
cd docker && docker compose up --build
```

Open **http://localhost:8501** in your browser. That's it.

## Architecture

```
opm-ai (this repo)
├── opm_ai/runner/       → OPM Flow Python wrapper
├── opm_ai/linter/       → AI deck linter & QC engine
├── opm_ai/builder/      → Natural language → OPM deck generator
├── opm_ai/preprocess/   → PVT & rel-perm table builder
├── opm_ai/postprocess/  → ResInsight bridge (rips API)
├── opm_ai/chat/         → Streamlit chat UI + LLM router
└── opm_ai/explainer/    → RAG-based educational explainer
```

**Physics engine:** [OPM Flow](https://opm-project.org)  
**Visualisation:** [ResInsight](https://resinsight.org) via `rips` Python API  
**AI:** Groq (Llama-3.3-70B) / NVIDIA NIM / OpenAI-compatible  

## Roadmap

- [x] Part 8 — Repo skeleton + Docker *(done)*
- [x] Part 1 — OPM Runner Python wrapper *(done)*
- [x] Part 2 — AI Deck Linter — rule engine + LLM explainer *(done)*
- [x] Part 3 — Description-to-Deck Builder — Jinja2 templates + LLM extraction *(done)*
- [x] Part 4 — Pre-Processing Pipeline — PVT correlations (Standing / Beggs-Robinson / Lee-Kesler) *(done)*
- [x] Part 5 — Post-Processing — KPI extractor + Plotly engine + ResInsight bridge *(done)*
- [x] Part 6 — Conversational Chat UI — Streamlit + LLM router (Groq + NVIDIA NIM) + tool calling *(done)*
- [ ] Part 7 — Educational Explainer (RAG) *(in progress — module scaffolded)*

See [ARCHITECTURE.md](ARCHITECTURE.md) for module-by-module design notes and data flow.

## Status

Parts 1-6 are implemented and covered by the test suite under `tests/`. The
chat UI, deck builder, linter, PVT pre-processing, OPM Flow runner, and
post-processing (KPIs + plots) are wired end to end. The RAG-based educational
explainer (Part 7) is scaffolded and under active development.

### Running the tests

```bash
pip install -e ".[dev]"
pytest
```

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon).  
For bugs or feature requests, open an [issue](https://github.com/pranay-gpt/opm-ai/issues).

## License

GPL-3.0 — same as OPM Flow and ResInsight.
