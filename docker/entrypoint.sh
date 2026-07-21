#!/bin/bash
# Entrypoint script for OPM-AI backend container
# Waits for ResInsight gRPC (optional), then starts uvicorn

set -e

# Note: the ResInsight bridge uses the batch CLI on a live X display, not gRPC,
# so there is no gRPC port to wait for. Snapshots are unavailable in-container
# by design (no display); the backend starts and serves everything else.

# Start FastAPI with uvicorn
echo "Starting OPM-AI API server on ${API_HOST:-0.0.0.0}:${API_PORT:-8000}"
exec uvicorn opm_ai.api.server:create_app --factory --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"