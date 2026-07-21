# OPM-AI

AI-assisted reservoir simulation workbench for petroleum engineering education.

## Architecture

```
Plain English → Builder → Linter → OPM Flow Runner → Postprocess → React UI
                    │         │          │                 │
                    ▼         ▼          ▼                 ▼
               Jinja2 +   Rule      /usr/bin/flow    resfo + Plotly
               LLM extract Engine   (2026.04)        + ResInsight CLI
```

- **Builder**: Template-based deck generation (Jinja2); parameters extracted from
  plain English by an LLM (JSON mode + Pydantic validation) with a deterministic
  offline regex extractor as fallback. 8 scenario templates (depletion,
  waterfloods, WAG, gas cap, CO2, buildup, multilayer) with DATES schedules.
- **Linter**: Pure-Python deck parser + rule engine (works offline)
- **Runner**: Subprocess to OPM Flow with crash parsing and structured results
- **Postprocess**: resfo-based summary reading, KPI extraction, Plotly charts,
  ResInsight 3D snapshots (batch CLI; needs a live display, see caveat below)
- **LLM**: Unified client (Groq / OpenAI / NVIDIA NIM / Offline) with offline fallback
- **Chat**: WebSocket tool-calling loop driving all of the above from one conversation

## Quick Start (Docker)

```bash
git clone https://github.com/pranay-gpt/opm-ai.git
cd opm-ai
cp .env.example .env   # optional: add GROQ_API_KEY (+ LLM_PROVIDER=groq) for LLM features
docker compose up -d --build
# open http://localhost:8000
```

The backend serves the React frontend at `/` and the API at `/api`. The Docker
build compiles the frontend inside the image, so no local Node is required. The
app runs fully offline by default (`LLM_PROVIDER=offline`); LLM features (chat,
natural-language extraction) activate only when you set a provider and key.

3D ResInsight snapshots are not available inside the container: they require a
live X display and the packaged ResInsight build ships without gRPC. They work
only when running on a host with a display. Everything else (build, lint, run,
2D plots, KPIs, explanations) works in Docker.

## Quick Start (Local Development)

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn opm_ai.api.server:create_app --factory --host 0.0.0.0 --port 8000

# Frontend (separate terminal): dev server with hot reload
cd frontend
npm install
npm run dev   # http://localhost:5173 (proxies /api to :8000)

# Or build the SPA once and let the backend serve it at http://localhost:8000/
cd frontend
npm ci
NODE_OPTIONS=--max-old-space-size=4096 npm run build   # heap bump needed for Plotly
```

## Features

| Feature | Status | Notes |
|---------|--------|-------|
| Build deck from natural language | [OK] | LLM extraction (JSON mode) with offline regex fallback; 8 scenario templates |
| Lint deck (offline rule engine) | [OK] | 0 false positives on 133 SPE decks |
| Run simulation (OPM Flow) | [OK] | Subprocess with crash parsing |
| Post-process results | [OK] | Field + per-well KPIs, Plotly charts |
| ResInsight 3D snapshots | [OK]* | Batch CLI export; *host-only: needs a live X display, not available in Docker (packaged ResInsight has no gRPC) |
| Chat with tool calling | [OK] | WebSocket loop: build, lint, run, KPIs, snapshots, explain, quiz |
| Pre-process PVT correlations | [OK] | Standing/Beggs-Robinson correlations, PROPS renderers, validators |
| Educational explainer | [OK] | BM25 retrieval over curated KB, offline fallbacks, quiz generation |
| Runtime settings | [OK] | POST /api/settings switches LLM provider without restart (in-memory only) |

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

- 238 tests (237 pass offline; 1 live-LLM test skipped without an API key)
- Linter calibrated FP=0 over 133 reference decks (SPE1, SPE3, SPE9, WCONPROD)
- The suite forces `LLM_PROVIDER=offline` via an autouse fixture, so it is
  deterministic and needs no network or keys
- CI runs unit tests + lint-only integration + frontend build on every push/PR

## CI Pipeline

- **`.github/workflows/ci.yml`**: Runs on push/PR to main/master
  - Backend: pytest unit tests + lint-only integration tests (no Flow binary)
  - Frontend: `npm ci && npm run build` on Node 20
- **`.github/workflows/ci-integration.yml`**: Manual trigger, self-hosted runner with OPM Flow
  - Full SPE1 integration test suite including Flow dry-run and simulation runs
  - See [docs/ci-selfhosted.md](docs/ci-selfhosted.md) for runner setup

## Troubleshooting

- **OPM Flow crashes / "simulation failed"**: the runner parses the PRT/stderr
  and returns a structured crash report instead of raising; check the `error`
  and `crash_report` fields in the run result. Common causes: unphysical
  well controls, missing PVT coverage of the pressure range.
- **ResInsight snapshots return an error**: expected inside Docker or on
  headless machines. The packaged ResInsight (2026.06) has no gRPC and the
  batch CLI needs a live X display (`DISPLAY` set). Run on a desktop host to
  get 3D PNGs; everything else works without it.
- **Chat says "LLM provider offline"**: set `LLM_PROVIDER=groq` (or `nim` /
  `openai`) and the matching key in `.env`, or switch at runtime in the
  Settings panel. The default is offline on purpose.
- **Frontend build runs out of memory**: use
  `NODE_OPTIONS=--max-old-space-size=4096 npm run build` (Plotly is large).

## License

MIT (see [LICENSE](LICENSE))