#!/usr/bin/env bash
# Invoke the project's pinned Python without relying on an activated venv.
# The bash tool runs each command in a fresh shell, so `source activate`
# does not persist between calls. This wrapper is the equivalent for
# one-shot invocations.
exec /home/parallels/opm-ai/.venv/bin/python "$@"