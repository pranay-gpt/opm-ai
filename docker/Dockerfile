# Multi-stage Dockerfile for OPM-AI
# Stage 1: Builder (Node.js for frontend build)
# Stage 2: Runtime (Ubuntu 24.04 + OPM Flow + Python backend)

# =============================================================================
# STAGE 1: Frontend Builder
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app/frontend

# Install dependencies first (better caching)
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ ./
# Increase Node memory for plotly.js build
ENV NODE_OPTIONS=--max-old-space-size=4096
RUN npm run build

# =============================================================================
# STAGE 2: Runtime (Ubuntu 24.04 + OPM Flow + Python)
# =============================================================================
FROM ubuntu:24.04 AS runtime

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

# Install OPM PPA and required packages
# Package names verified against ppa:opm/ppa for noble on arm64 (2026-07):
#   libopm-simulators-bin owns /usr/bin/flow (there is no "opm-simulators" package).
#   ResInsight is NOT installed here; it runs as its own compose service.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        curl \
        ca-certificates && \
    add-apt-repository -y ppa:opm/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libopm-simulators-bin \
        python3-opm-simulators \
        python3-opm-common \
        python3.12 \
        python3-pip \
        python3.12-venv \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verify OPM Flow binary location (adjust OPM_FLOW_BINARY in .env if needed)
# Expected: /usr/bin/flow (from opm-simulators package)

# Create virtual environment and install Python dependencies
WORKDIR /app
RUN python3.12 -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install Python dependencies.
# Stub package dir first: the editable install must discover opm_ai at install
# time to record its import mapping; the real source is copied below into the
# same path. Keeps the dependency layer cached across code-only changes.
COPY pyproject.toml ./
RUN mkdir -p opm_ai && touch opm_ai/__init__.py && \
    pip install --no-cache-dir -e .

# Copy frontend build from builder stage
COPY --from=builder /app/frontend/dist ./static

# Copy application code
COPY opm_ai ./opm_ai

# Copy entrypoint and healthcheck scripts
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/healthcheck.sh /healthcheck.sh
RUN chmod +x /entrypoint.sh /healthcheck.sh

# Expose FastAPI port
EXPOSE 8000

# Entrypoint waits for ResInsight gRPC (optional) then starts uvicorn
ENTRYPOINT ["/entrypoint.sh"]