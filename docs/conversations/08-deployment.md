# Part 8: Deployment and GitHub Packaging (module: opm_ai.deployment)

> Docker Compose packaging, CI, and one-command quick-start for students.

## 1. Role in the AIM

This part owns the "one `docker compose up`" promise from the project aim: a student clones the repo, runs one command, and within ~10 minutes has a running React + FastAPI workbench that can build, lint, run, and visualise an OPM Flow deck from plain English. It wraps the Python backend (Stages 0-4), the React frontend (Stage 6), the OPM Flow + ResInsight binaries, and the LLM providers behind a single Docker Compose stack. It also owns the GitHub Actions CI gate (pytest + npm build) and the public README that drives adoption.

## 2. Position in Build Order

| Phase | Stage | Depends on | Depended on by |
|-------|-------|------------|----------------|
| 2 (v1.1 tail) | Stage 7 | Stage 5 (FastAPI), Stage 6 (React build), Stage 4 (postprocess), Stage 1 (runner) | Phase 3 (explainer/RAG), Phase 3 end (release tag) |

- **Skeleton created in Phase 1** (`docker/`, `docker-compose.yml`, `README.md` placeholders) per IMPLEMENTATION_PLAN section 8 "Part 8 (Deployment) is set up first as a skeleton and finished at the end of each phase."
- **Completed at end of Phase 2** once backend + frontend are working and the SPE1 integration test passes in CI.

## 3. Hard API Contract

There are no Python unit tests for this part. The contract is **operational**:

| Check | Command | Must pass |
|-------|---------|-----------|
| Backend health | `curl -f http://localhost:8000/health` | 200 + JSON `{"status":"ok"}` |
| Frontend loads | `curl -f http://localhost:80/` | 200 + HTML with `<div id="root">` |
| CLI lint (in-container) | `docker compose exec backend opm-ai lint tests/fixtures/spe1/SPE1CASE1.DATA` | exit 0, prints `Passed` |
| CLI build (in-container) | `docker compose exec backend opm-ai build "5x5x3 depletion" -o /tmp/t.DATA` | exit 0, file exists |
| SPE1 integration (slow) | `docker compose exec backend pytest tests/integration/test_runner_spe1.py -v` | exit 0 |
| Frontend build | `docker compose run --rm frontend-build npm run build` | exit 0, `dist/` produced |
| CI (GitHub Actions) | `pytest` (unit + lint + builder) + `npm run build` | green on `main` |

These are verified by the **smoke script** `scripts/smoke.sh` (created in this part) which the CI pipeline runs.

## 4. Key Design Decisions

| # | Decision | Rationale | Alternatives considered | Consequences |
|---|----------|-----------|-------------------------|--------------|
| 1 | **Base image: `ubuntu:24.04` + OPM PPA** | OPM Flow 2026.04 + ResInsight 2026.04 are in the OPM PPA for noble; avoids building from source (hours) | `ubuntu:22.04` + manual compile; `opm/flow` Docker Hub image (unofficial, stale) | PPA packages are **UNVERIFIED** exact names - must confirm at build time (`apt-cache policy opm-simulators`). |
| 2 | **Multi-stage Dockerfile**: `builder` (Node) -> `runtime` (Python + Flow + ResInsight) | Keeps final image ~2 GB instead of 4 GB+; frontend bundle copied as static files into FastAPI `/static` mount | Single-stage with both Node + Python; separate `backend` + `frontend` services in compose | Adds build complexity; need `COPY --from=builder` for `frontend/dist`. |
| 3 | **Single `backend` service in compose** (serves API + static frontend) | Simpler for students: one port (`:8000`), no CORS / proxy config; `uvicorn --host 0.0.0.0` serves React `index.html` at `/` | Two services (`backend:8000`, `frontend:5173` via nginx) | Dev mode still uses `npm run dev` (Vite proxy) locally; production uses the baked static mount. |
| 3b | **`scripts/run.sh` binds `0.0.0.0` (matches production)** | Local dev server is reachable from the LAN, so `BASE_URL=http://<lan-ip>:8000 ./scripts/smoke.sh` works without rebinding and a phone/tablet on the same network can hit the app. Override with `OPM_HOST=127.0.0.1` for loopback-only. | Bind `127.0.0.1` by default (matches an older version of `run.sh`) | Anything binding to all interfaces on a workstation is reachable to anyone on the LAN; behind a corporate network or when running an unrelated workload on the same host, set `OPM_HOST=127.0.0.1` (or use the Docker stack with its own network). |
| 4 | **Exposed port = 8000** (not 8555) | BUILD_GUIDE section 2 and IMPLEMENTATION_PLAN Stage 5 both specify FastAPI on 8000; Vite dev proxy targets 8000. GUIDE 1's "8555" was a Streamlit legacy port. | Keep 8555 for backward compatibility | Update README quick-start and `vite.config.ts` proxy target. |
| 5 | **Pre-baked chromadb vector store** (Phase 3) | Avoids first-run download / index build (~5 min, 500 MB); cross-ref 07-explainer.md section 4 | Download at runtime | Image grows ~600 MB; only baked at Phase 3, not Phase 2. |
| 6 | **`.env` sourced into compose via `env_file`** | Keeps API keys out of image and git; `docker compose --env-file .env up` | Bake keys into image (insecure) | Must document `.env.example` -> `.env` copy step in README. |
| 7 | **Volumes**: `./decks:/decks`, `./results:/results` | Persists user decks & results across container restarts; bind-mounts are simple for students | Named volumes | Bind mounts expose host paths - acceptable for local educational use. |
| 8 | **GitHub Actions: matrix `python-version: ["3.12"]` + `ubuntu-latest`** | Matches the dev container base; single version reduces CI minutes | Test 3.11, 3.12, 3.13 | Add matrix later if compatibility issues arise. |
| 9 | **CI gates SPE1 integration test with `if: runner.os == 'Linux' && env.FLOW_INSTALLED == 'true'`** | Flow binary is large (~500 MB) and slow to install in CI; run SPE1 only on self-hosted runner with Flow pre-installed | Install Flow in every CI run (adds 5+ min) | Document how to enable self-hosted runner in `docs/ci-selfhosted.md`. |
| 10 | **Repo hygiene actions owned here**: `git init`, `.gitignore` (add `.env`, `__pycache__`, `frontend/dist`, `*.log`), `pyproject.toml` cleanup (drop `streamlit`, add `fastapi`, `uvicorn[standard]`, `click`), `README.md` rewrite | These are one-time setup tasks that unblock CI and the quick-start | Leave to contributor | Must be done before first commit to GitHub. |

## 5. Toolchain Grounding

| Item | Value | Source | Verified |
|------|-------|--------|----------|
| Base OS | Ubuntu 24.04 (noble) | OPM.md section 7, BUILD_GUIDE section 7 | verified |
| OPM Flow binary | `/usr/bin/flow` (v2026.04) | OPM.md section 1, BUILD_GUIDE section 7 | verified |
| OPM Python bindings | `/usr/lib/python3/dist-packages/opm/` (`opm.io`, `opm.simulators`) | OPM.md section 7 | verified |
| ResInsight binary | `/usr/bin/ResInsight` | OPM.md section 7, BUILD_GUIDE section 7 | verified |
| ResInsight gRPC port | 50051 (default) | OPM.md section 7, BUILD_GUIDE section 7 | verified |
| Python | 3.12 (system) | BUILD_GUIDE section 2, pyproject.toml `>=3.12` | verified |
| Node.js | 20 LTS (for Vite) | Standard | UNVERIFIED - check `node -v` in builder stage |
| Flow PPA package | `opm-simulators` (provides `flow`) | OPM.md section 7 `libopm-simulators-bin` | **UNVERIFIED** - exact `apt` package name to confirm: `apt-cache search opm | grep flow` |
| ResInsight PPA package | `resinsight` | OPM.md section 7 | **UNVERIFIED** - check `apt-cache policy resinsight` |
| `python3-opm-simulators` | Provides `opm.simulators.BlackOilSimulator` | OPM.md section 7 | verified |
| `python3-opm-common` | Provides `opm.io.Parser`, `EclFile`, `SummaryState` | OPM.md section 7 | verified |
| `resfo` | >=5.0 (summary reader) | BUILD_GUIDE section 2, pyproject.toml | verified |
| `rips` | ResInsight Python client | pyproject.toml, BUILD_GUIDE section 3 | verified |

**Action at implementation**: run `apt-cache policy opm-simulators resinsight python3-opm-simulators python3-opm-common` in a noble container and record exact versions in `docker/Dockerfile` comments.

## 6. Implementation Approach

### 6.1 Files to Create / Modify

```
docker/
|-- Dockerfile                 # Multi-stage: builder (Node) -> runtime (Python + OPM)
|-- docker-compose.yml         # Single 'backend' service + optional 'resinsight' service
|-- .dockerignore
|-- entrypoint.sh              # Wait for ResInsight gRPC, then uvicorn
|-- healthcheck.sh             # curl /health for compose healthcheck
scripts/
|-- smoke.sh                   # Runs the 7 operational checks from section 3
.github/workflows/
|-- ci.yml                     # pytest (unit) + npm run build
|-- ci-integration.yml         # Optional: SPE1 on self-hosted runner
docs/
|-- ci-selfhosted.md           # How to enable Flow in CI
opm_ai/
|-- api/
|   |-- server.py              # Add /health endpoint, static mount
|   |-- routes/health.py       # GET /health
frontend/                      # (created in Stage 6)
|-- package.json
|-- vite.config.ts             # proxy /api -> http://localhost:8000
|-- tsconfig.json
|-- index.html
|-- src/...
README.md                      # Rewrite: architecture diagram, quick-start, troubleshooting
pyproject.toml                 # Drop streamlit; add fastapi, uvicorn[standard], click
.env.example                   # Template for API keys
.gitignore                     # Add .env, __pycache__, frontend/dist, *.log, .coverage
```

### 6.2 Ordered Steps

1. **Repo hygiene (do first, before any commit)**
   - `git init && git remote add origin <github-url>`
   - Edit `.gitignore` (see section 6.1)
   - Edit `pyproject.toml`: remove `streamlit`, add `fastapi`, `uvicorn[standard]`, `click`
   - `pip install -e .` to verify
   - Commit: `chore: repo hygiene, drop streamlit, add fastapi deps`

2. **Dockerfile (multi-stage)**
   - Stage 1 (`builder`): `node:20-alpine`, `WORKDIR /app/frontend`, copy `package*.json`, `npm ci`, copy source, `npm run build` -> `/app/frontend/dist`
   - Stage 2 (`runtime`): `ubuntu:24.04`
     - `apt-get update && apt-get install -y software-properties-common && add-apt-repository -y ppa:opm/opm && apt-get update`
     - `apt-get install -y opm-simulators resinsight python3-opm-simulators python3-opm-common python3-pip python3-venv`
     - `pip install --no-cache-dir -r requirements.txt` (generated from `pyproject.toml` via `pip freeze` or `uv pip compile`)
     - `COPY --from=builder /app/frontend/dist /app/static`
     - `COPY opm_ai /app/opm_ai`
     - `COPY docker/entrypoint.sh /entrypoint.sh`
     - `EXPOSE 8000`
     - `ENTRYPOINT ["/entrypoint.sh"]`

3. **docker-compose.yml**
   ```yaml
   services:
     backend:
       build:
         context: .
         dockerfile: docker/Dockerfile
       ports: ["8000:8000"]
       env_file: .env
       volumes:
         - ./decks:/decks
         - ./results:/results
       healthcheck:
         test: ["CMD", "/healthcheck.sh"]
         interval: 10s
         timeout: 5s
         retries: 5
       depends_on:
         resinsight:
           condition: service_started
     resinsight:
       image: ghcr.io/opm/resinsight:2026.04  # or local build from PPA
       ports: ["50051:50051"]
       command: ["--grpc-port", "50051"]
       # Note: ResInsight GUI needs X11; headless gRPC works without display
   ```

4. **FastAPI static mount + health endpoint**
   - `api/server.py`: `app.mount("/", StaticFiles(directory="static", html=True), name="static")` **after** all `/api` routes.
   - `api/routes/health.py`: `GET /health` -> `{"status": "ok", "flow": settings.flow_path.exists()}`.

5. **Entrypoint / healthcheck scripts**
   - `entrypoint.sh`: wait for ResInsight gRPC (optional), then `exec uvicorn opm_ai.api.server:create_app --factory --host 0.0.0.0 --port 8000`
   - `healthcheck.sh`: `curl -sf http://localhost:8000/health || exit 1`

6. **Frontend Vite config**
   - `vite.config.ts`: `server: { proxy: { '/api': 'http://localhost:8000' } }`

7. **GitHub Actions CI (`.github/workflows/ci.yml`)**
   ```yaml
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: "3.12" }
         - run: pip install -e .[dev]
         - run: pytest tests/unit tests/integration/test_builder.py -v -m "not slow"
     frontend-build:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4
           with: { node-version: "20" }
         - run: cd frontend && npm ci && npm run build
   ```
   - **No OPM Flow** in this workflow; unit tests use mocks / offline mode.

8. **Optional integration workflow (`.github/workflows/ci-integration.yml`)**
   - `if: runner.os == 'Linux' && vars.FLOW_INSTALLED == 'true'`
   - Runs on self-hosted runner with Flow pre-installed.
   - Executes `pytest tests/integration/test_runner_spe1.py -v`.

9. **README.md rewrite** (primary adoption asset)
   - Architecture diagram (Mermaid, matching 00-overview-and-architecture.md)
   - Quick-start:
     ```bash
     git clone https://github.com/.../opm-ai
     cd opm-ai
     cp .env.example .env   # add GROQ_API_KEY or OPENAI_API_KEY
     docker compose up -d
     # open http://localhost:8000
     ```
   - Dev mode (hot reload):
     ```bash
     docker compose up -d backend
     cd frontend && npm run dev   # http://localhost:5173
     ```
   - Troubleshooting table (seed from OPM.md section 7):
     | Symptom | Cause | Fix |
     |---------|-------|-----|
     | `flow: error while loading shared libraries: libopm-common.so` | PPA install missed `libopm-common` | `apt-get install -y libopm-common` |
     | `MPI_Init_thread failed` / `ORTED error` | OpenMPI version mismatch | Use `mpirun --oversubscribe` or pin `libopenmpi-dev=4.1.6` |
     | `resfo.read()` returns empty | Missing `.ESMRY` / `.UNSMRY` | Check deck has `SUMMARY` section with `FOPR` etc. |
     | `rips` connection refused | ResInsight gRPC not ready | `docker compose logs resinsight`; ensure port 50051 |
     | `LLMClient.available == False` | No API key in `.env` | Add `GROQ_API_KEY` or `OPENAI_API_KEY` |

10. **Smoke script (`scripts/smoke.sh`)**
    - Runs the 8 checks from section 3 (1 health, 1 frontend load, 1 build+lint, 1 full pipeline, 1 KPI, 1 deck upload, 1 CLI lint, 1 frontend build artifact); used locally and in CI-integration.
    - `BASE_URL=http://<lan-ip>:8000 ./scripts/smoke.sh` exercises the same checks against the LAN-reachable URL, matching what `scripts/run.sh` now exposes by default.

11. **Phase 3: bake chromadb vector store**
    - Add `COPY --from=explainer-builder /chroma /app/chroma` in Dockerfile (new stage).
    - Set `CHROMA_PATH=/app/chroma` in compose env.
    - Document in 07-explainer.md section 4.

12. **Final verification**
    - `docker compose up -d && ./scripts/smoke.sh` -> all green.
    - Tag `v1.1.0` (Phase 2 complete).

## 7. Risks and Open Questions

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OPM PPA package names differ from OPM.md section 7 | Medium | Build fails | Verify in noble container before writing Dockerfile; fallback to `opm/flow` Docker Hub image (UNVERIFIED) |
| ResInsight headless gRPC requires Xvfb | Medium | ResInsight service unhealthy | Test `ResInsight --grpc-port 50051` in container; add `xvfb-run -a` if needed |
| Image size > 3 GB (student download barrier) | High | Adoption friction | Multi-stage + `.dockerignore`; consider `ubuntu:24.04` -> `ubuntu-minimal`; strip docs/locales |
| Vite dev proxy + FastAPI CORS misconfig | Medium | Frontend dev mode broken | Explicit `CORSMiddleware(allow_origins=["http://localhost:5173"])` in `server.py` |
| GitHub Actions Ubuntu runners lack GPU for future ML | Low | Phase 3 blocked | Self-hosted runner doc; CPU fallback for LLMs (Groq API is cloud) |
| `.env` committed by accident | Low | Secret leak | Pre-commit hook `detect-secrets`; `.gitignore` entry; CI secret scan |
| SPE1 test flaky in CI (OOM, MPI) | Medium | False negatives | Gate behind self-hosted runner; allocate 4 GB RAM + 2 CPUs |

**Open questions to resolve at implementation:**
1. Exact `apt` package names for `flow`, `resinsight`, `python3-opm-*` on noble (run `apt-cache policy`).
2. Does ResInsight 2026.04 PPA package include headless gRPC server, or must we build from source?
3. Frontend bundle size after `npm run build` - impacts image size budget.
4. Whether to publish pre-built images to GHCR (`ghcr.io/opm-ai/backend:latest`) for `docker compose pull` quick-start.

## 8. Verification and Done-Criteria

| Criterion | How Verified |
|-----------|--------------|
| `docker compose up -d` starts backend + resinsight | `docker compose ps` shows both `running` |
| `curl localhost:8000/health` returns 200 | `scripts/smoke.sh` check 1 |
| Frontend loads at `localhost:8000` | `scripts/smoke.sh` check 2 |
| CLI lint/build work inside container | `scripts/smoke.sh` checks 3-4 |
| SPE1 integration passes (on host with Flow) | `scripts/smoke.sh` check 5 |
| Frontend production build succeeds | `scripts/smoke.sh` check 6 |
| CI (GitHub Actions) green on `main` | Push to GitHub, watch Actions tab |
| README quick-start works for fresh clone | Manual test on clean VM / Codespaces |
| Image size < 2.5 GB | `docker images opm-ai_backend` |
| No secrets in image / git history | `docker history --no-trunc` + `git log --all --oneline --grep=secret` |

## 9. Future Extensions

- **GHCR publishing**: `docker/build-push-action` on tag push -> `ghcr.io/opm-ai/backend:v1.x`, `ghcr.io/opm-ai/frontend:v1.x`; compose pulls instead of building.
- **Helm chart / k8s manifests** for classroom deployments (JupyterHub sidecar).
- **DevContainer** (`.devcontainer/devcontainer.json`) for GitHub Codespaces / VS Code Remote - one-click cloud dev env.
- **Automated release notes** from conventional commits (`release-please` action).
- **SBOM generation** (`syft`) in CI for supply-chain transparency.
- **Multi-arch images** (amd64 + arm64) for Apple Silicon students - requires OPM Flow arm64 build (available in PPA).
- **Pre-baked ResInsight project templates** (`.rsp` files) copied into image for one-click 3D view.