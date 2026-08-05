#!/usr/bin/env bash
# Launch OPM-AI locally (without Docker).
#
#   ./scripts/run.sh          serve on :8000; auto-builds frontend/dist if missing
#   ./scripts/run.sh dev      same, plus the Vite dev server on :5173 (hot reload)
#   ./scripts/run.sh build    force-rebuild frontend, then serve on :8000
#
# Stop with Ctrl-C; both processes are killed together.

set -euo pipefail

# Always run from the repo root. settings.fixtures_path defaults to the relative
# "tests/fixtures" and is resolved against the cwd, so starting elsewhere would
# leave the deck picker pointing at a directory that does not exist.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="${1:-serve}"

# The venv lives in the main checkout, so a git worktree shares it.
VENV="${OPM_VENV:-}"
if [ -z "$VENV" ]; then
  for candidate in "$REPO_ROOT/.venv" "$HOME/opm-ai/.venv"; do
    if [ -x "$candidate/bin/python" ]; then VENV="$candidate"; break; fi
  done
fi
if [ -z "$VENV" ] || [ ! -x "$VENV/bin/python" ]; then
  echo "No virtualenv found. Set OPM_VENV=/path/to/.venv, or create one:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi
PY="$VENV/bin/python"

command -v flow >/dev/null || echo "WARNING: 'flow' not on PATH; simulations will fail." >&2

# The package is imported from this tree, not from site-packages, so a worktree
# serves its own code even though the venv was installed from the main checkout.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export FIXTURES_PATH="${FIXTURES_PATH:-$REPO_ROOT/tests/fixtures}"

if [ "$MODE" = "build" ]; then
  echo "== building frontend =="
  # ~3 GB of heap: three.js pushes the minify step past the default ceiling.
  (cd frontend && NODE_OPTIONS=--max-old-space-size=3000 npm run build)
fi

# `serve` auto-builds if dist is missing so a fresh checkout just works.
# `dev` doesn't need dist (vite serves sources directly).
# `build` already produced dist above.
if [ ! -f frontend/dist/index.html ] && [ "$MODE" = "serve" ]; then
  echo "== building frontend (dist missing) =="
  (cd frontend && NODE_OPTIONS=--max-old-space-size=3000 npm run build)
fi

# Re-exec in a session of our own so cleanup can kill the whole process group
# in one shot. Needed because `npm run dev` re-parents vite: walking children
# with `pkill -P` misses it and it keeps port 5173. A group kill catches every
# descendant however deep, and being our own group leader means it cannot reach
# back into the caller's shell.
if [ "${OPM_RUN_LEADER:-}" != "1" ] && command -v setsid >/dev/null; then
  export OPM_RUN_LEADER=1
  exec setsid --wait "$0" "$@"
fi

cleanup() {
  trap - INT TERM EXIT
  kill -TERM 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Default host: 0.0.0.0 so the server is reachable from the LAN
# (e.g. http://10.211.55.5:8000 from another machine, or from a
# phone/tablet on the same network). This matches production
# (`uvicorn --host 0.0.0.0` in `docker/entrypoint.sh`) and lets
# `scripts/smoke.sh BASE_URL=http://<lan-ip>:8000` work without
# rebinding. Override with `OPM_HOST=127.0.0.1 ./scripts/run.sh`
# if you specifically want loopback-only (e.g. behind a reverse
# proxy you're developing).
HOST="${OPM_HOST:-0.0.0.0}"

echo "== backend  http://${HOST}:8000  (set OPM_HOST=127.0.0.1 for loopback-only) =="
"$PY" -m uvicorn opm_ai.api.server:create_app --factory \
  --host "$HOST" --port 8000 &

if [ "$MODE" = "dev" ]; then
  echo "== frontend http://localhost:5173  (hot reload; proxies /api to :8000) =="
  (cd frontend && npm run dev) &
fi

# Exit as soon as either process dies, so a crashed backend does not look like
# a working app with a blank page.
wait -n
