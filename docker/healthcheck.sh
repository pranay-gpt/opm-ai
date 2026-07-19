#!/bin/bash
# Health check script for OPM-AI backend container
# Called by docker-compose healthcheck

set -e

curl -sf "http://localhost:8000/health" > /dev/null