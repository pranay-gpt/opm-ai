#!/bin/bash
# Entrypoint script for OPM-AI backend container
# Waits for ResInsight gRPC (optional), then starts uvicorn

set -e

# Wait for ResInsight gRPC if configured
if [ -n "$RESINSIGHT_HOST" ] && [ -n "$RESINSIGHT_GRPC_PORT" ]; then
    echo "Waiting for ResInsight gRPC at ${RESINSIGHT_HOST}:${RESINSIGHT_GRPC_PORT}..."
    for i in {1..30}; do
        if nc -z "$RESINSIGHT_HOST" "$RESINSIGHT_GRPC_PORT" 2>/dev/null; then
            echo "ResInsight gRPC is ready"
            break
        fi
        echo "Waiting... ($i/30)"
        sleep 2
    done
    # Don't fail if ResInsight isn't ready - backend can start without it
fi

# Start FastAPI with uvicorn
echo "Starting OPM-AI API server on ${API_HOST:-0.0.0.0}:${API_PORT:-8000}"
exec uvicorn opm_ai.api.server:create_app --factory --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"