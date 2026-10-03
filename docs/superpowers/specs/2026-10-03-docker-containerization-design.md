# Docker Containerization: OPM-AI + OPM Flow in one image, distributed via GHCR

Date: 2026-10-03. Status: approved. Base: v0.1.1 tree
(`feat/reservoir-context-builder` @ 2a74e31).

## Goal

One image that runs the whole OPM-AI stack (FastAPI backend serving the built
React frontend, OPM Flow simulator binary, all Python dependencies) so a
student on any OS runs two commands and opens `http://localhost:8000`. The
image is published from GitHub so nobody builds it locally.

## Design

### Image (`docker/Dockerfile`, refresh of the July file)

Multi-stage, both architectures from one Dockerfile (the OPM PPA publishes
amd64 and arm64 packages; package names verified for noble on both arches in
July: `libopm-simulators-bin` owns `/usr/bin/flow`):

- **Stage 1 builder**: `node:20-alpine`, `npm ci`, `npm run build` with
  `NODE_OPTIONS=--max-old-space-size=4096` (plotly bundle).
- **Stage 2 runtime**: `ubuntu:24.04`, `ppa:opm/ppa`, installs
  `libopm-simulators-bin`, `python3-opm-simulators`, `python3-opm-common`,
  Python 3.12 + pip + venv. venv at `/app/.venv`. `pip install -e .` against a
  stub `opm_ai/__init__.py` first so the dependency layer caches across
  code-only changes (dependency list has grown since July: pandas 3, numpy
  2.5, resfo 5, plotly 6.8; the build verifies it on both arches).
- **Copies**: `opm_ai/` source, frontend dist to `/app/static`, entrypoint +
  healthcheck. Runs as root: standard for a student-run container, avoids
  bind-mount permission pain on the `decks`/`results` volumes.

### Runtime layout (unchanged from July, verified then)

- Entrypoint starts uvicorn on `0.0.0.0:8000` via `create_app --factory`; the
  app serves both `/api` and the SPA.
- `settings.flow_path` defaults to `/usr/bin/flow`; `decks_path`/`results_path`
  default to `/app/decks` and `/app/results` (bind-mount targets).
- ResInsight stays host-only by design: the bridge drives the batch CLI on a
  live X display, and the packaged build ships without gRPC. Everything else
  works in-container.

### Compose (`docker-compose.yml`, refresh of the July file)

`backend` service: port 8000, optional `.env`, `./decks:/app/decks` +
`./results:/app/results` volumes, curl healthcheck on `/health`. Students can
use compose or the plain `docker run` from the README.

### GHCR publishing (`.github/workflows/docker-publish.yml`, new)

- **Triggers**: push of `v*` tags (publishes `ghcr.io/pranay-gpt/opm-ai:vX.Y.Z`
  and moves `:latest`), push to `main` touching `docker/**`, `opm_ai/**`,
  `frontend/**`, or `pyproject.toml` (publishes `:main` + `:latest`), and
  `workflow_dispatch`.
- **Build strategy**: native per-arch, no QEMU. Two parallel buildx jobs:
  `ubuntu-latest` builds linux/amd64, `ubuntu-24.04-arm` builds linux/arm64
  (arm64 runners are in GitHub's standard free tier for public repos and ship
  Docker 28 + Buildx). Each pushes by digest; a merge job assembles the
  multi-arch manifest and applies tags. Permissions: `contents: read`,
  `packages: write`. Uses `GITHUB_TOKEN`, no secrets to configure.
- Action versions pinned to current majors: build-push-action v7, login-action
  v4, setup-buildx-action v4.

### Student UX

README "Run with Docker" section:

```
docker run -d --name opm-ai -p 8000:8000 \
  -v ./decks:/app/decks -v ./results:/app/results \
  ghcr.io/pranay-gpt/opm-ai:v0.1.1
```

then `http://localhost:8000`. Same on Windows/macOS/Linux with Docker Desktop.
`docker compose up -d` works the same via the checked-in compose file.

## Verification

1. Recreate the docker-in-LXD host (`dockerhost`, nesting=true, docker.io +
   compose-v2 inside, host port 8001 proxied to container 8000 because the
   host dev server already owns 8000).
2. Build the refreshed image against the v0.1.1 tree; fix whatever the new
   interview/ingest code breaks.
3. Run the container: `/health` ok, `scripts/smoke.sh` 7/7 (takes BASE_URL as
   env var), all 7 interview scenarios finish with lint-passing decks through
   the container API, one real OPM Flow simulation end to end inside the
   container (build deck -> run -> poll -> outputs on disk).
4. Browser pass on the served SPA through the proxied port (Python Playwright,
   host machine).
5. Push branch + workflow; watch the Actions run publish to GHCR; `docker pull`
   the published image and smoke it as the final check.

## Explicitly skipped

- ResInsight in the image (no gRPC in the packaged build, needs a display).
- CI (test) jobs on arm64: existing CI stays on ubuntu-latest; only the image
  build gains an arm64 leg.
- Distroless / rootless images: student-run containers bind-mount host dirs;
  root adds friction for no benefit here.
