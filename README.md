# OPM-AI

AI-assisted reservoir simulation workbench for petroleum engineering education.

## Architecture

```
Plain English → Builder → Linter → OPM Flow Runner → Postprocess → React UI
                    │         │          │                 │
                    ▼         ▼          ▼                 ▼
               Jinja2    Rule      /usr/bin/flow    resfo + rips
               Templates Engine   (2026.04)        Plotly + 3D
```

- **Builder**: Template-based deck generation (Jinja2) with LLM parameter extraction
- **Linter**: Pure-Python deck parser + rule engine (works offline)
- **Runner**: Subprocess to OPM Flow with crash parsing and structured results
- **Postprocess**: resfo-based summary reading, KPI extraction, Plotly charts, ResInsight 3D bridge
- **LLM**: Unified client (Groq / OpenAI / NVIDIA NIM / Offline) with offline fallback

## Quick Start (Docker)

```bash
git clone https://github.com/opm-ai/opm-ai
cd opm-ai
cp .env.example .env   # add GROQ_API_KEY or OPENAI_API_KEY for LLM features
docker compose up -d
# open http://localhost:8000
```

The backend serves the React frontend at `/` and the API at `/api`.

## Quick Start (Local Development)

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn opm_ai.api.server:create_app --factory --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api to :8000)
```

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Build deck from natural language | [OK] | Jinja2 templates + offline extractor |
| Lint deck (offline rule engine) | [OK] | 0 false positives on 133 SPE decks |
| Run simulation (OPM Flow) | [OK] | Subprocess with crash parsing |
| Post-process results | [OK] | KPIs + Plotly charts |
| ResInsight 3D visualization | [OK] | Headless gRPC bridge (optional) |
| Chat / LLM explanations | [OK] | Groq / OpenAI / NVIDIA NIM / Offline |
| Pre-process PVT correlations | [WIP] | Phase 3 |
| Educational RAG explainer | [WIP] | Phase 3 |

## LLM Configuration

| Provider | Environment Variables | Model |
|----------|----------------------|-------|
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| NVIDIA NIM | `NVIDIA_NIM_API`, `NVIDIA_NIM_BASE_URL` | Configurable |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Configurable |
| Offline | (none) | Rule-based fallback |

Set `LLM_PROVIDER=offline` to disable all LLM calls (default for CI).

## Test Suite

```bash
# Unit + lint-only integration (no Flow binary needed)
pytest tests/unit tests/integration/test_dataset_validation.py::test_linter_accepts_known_good_fixture -v

# Full integration (requires /usr/bin/flow 2026.04+)
pytest tests/integration -v
```

- 77 tests total
- Linter calibrated FP=0 over 133 reference decks (SPE1, SPE3, SPE9, WCONPROD)
- CI runs unit tests + lint-only integration + frontend build on every push/PR

## CI Pipeline

- **`.github/workflows/ci.yml`**: Runs on push/PR to main/master
  - Backend: pytest unit tests + lint-only integration tests (no Flow binary)
  - Frontend: `npm ci && npm run build` on Node 20
- **`.github/workflows/ci-integration.yml`**: Manual trigger, self-hosted runner with OPM Flow
  - Full SPE1 integration test suite including Flow dry-run and simulation runs
  - See [docs/ci-selfhosted.md](docs/ci-selfhosted.md) for runner setup

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) (to be created).