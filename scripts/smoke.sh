#!/bin/bash
# Smoke test script for OPM-AI deployment
# Runs operational checks from 08-deployment.md section 3
# Usage: BASE_URL=http://localhost:8000 ./scripts/smoke.sh
#        (defaults to BASE_URL=http://localhost:8000)

set -e
set -o pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
DECK_DIR="${DECK_DIR:-/app/decks}"
RESULTS_DIR="${RESULTS_DIR:-/app/results}"

echo "========================================="
echo "OPM-AI Smoke Tests"
echo "Base URL: ${BASE_URL}"
echo "========================================="

# Helper function for assertions
assert_ok() {
    local cmd="$1"
    local msg="$2"
    echo -n "  ${msg}... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo "OK"
        return 0
    else
        echo "FAILED"
        echo "Command failed: $cmd"
        return 1
    fi
}

assert_json() {
    local url="$1"
    local jq_filter="$2"
    local msg="$3"
    echo -n "  ${msg}... "
    result=$(curl -sf "${url}" | jq -r "${jq_filter}" 2>/dev/null) || {
        echo "FAILED (curl or jq failed)"
        return 1
    }
    if [ "$result" = "true" ] || [ "$result" = "ok" ]; then
        echo "OK"
        return 0
    else
        echo "FAILED (got: $result)"
        return 1
    fi
}

# Check 1: Health endpoint returns {"status":"ok"}
echo "[1/8] Health check"
assert_json "${BASE_URL}/health" '.status' 'GET /health returns {"status":"ok"}'

# Check 2: Frontend loads (HTML with div#root)
echo "[2/8] Frontend load"
assert_ok "curl -sf '${BASE_URL}/' | grep -q '<div id=\"root\">'" 'GET / returns HTML with div#root'

# Check 3: POST /api/build with depletion description returns lint.passed=true
echo "[3/8] Build + Lint API"
BUILD_RESPONSE=$(curl -sf -X POST "${BASE_URL}/api/build" \
    -H "Content-Type: application/json" \
    -d '{"description": "5x5x3 depletion case with 1 producer and 1 injector", "deck_name": "smoke_test.DATA", "output_path": "/tmp/smoke_test.DATA"}' \
    | jq -r '.lint.passed // false')
if [ "$BUILD_RESPONSE" = "true" ]; then
    echo "  POST /api/build returns lint.passed=true... OK"
else
    echo "  POST /api/build returns lint.passed=true... FAILED (got: $BUILD_RESPONSE)"
    exit 1
fi

# Check 4: Full pipeline - build -> run -> poll -> results (kpis.days > 0)
echo "[4/8] Full pipeline: run -> poll -> results"

# Start a run job with the built deck (using output_path from build)
RUN_RESPONSE=$(curl -sf -X POST "${BASE_URL}/api/run" \
    -H "Content-Type: application/json" \
    -d '{"deck_path": "/tmp/smoke_test.DATA", "timeout": 120}')

JOB_ID=$(echo "$RUN_RESPONSE" | jq -r '.job_id // empty')
if [ -z "$JOB_ID" ] || [ "$JOB_ID" = "null" ]; then
    echo "  Failed to get job_id from run response"
    exit 1
fi
echo "  Run job ID: ${JOB_ID}"

# Poll for completion
for i in {1..30}; do
    STATUS=$(curl -sf "${BASE_URL}/api/run/${JOB_ID}" | jq -r '.status')
    echo -n "  Polling job ${JOB_ID} (attempt $i/30): ${STATUS}... "
    if [ "$STATUS" = "completed" ]; then
        echo "COMPLETED"
        break
    elif [ "$STATUS" = "failed" ]; then
        echo "FAILED"
        curl -sf "${BASE_URL}/api/run/${JOB_ID}" | jq '.error'
        exit 1
    else
        echo "pending"
        sleep 2
    fi
done

if [ "$STATUS" != "completed" ]; then
    echo "  Job did not complete in time"
    exit 1
fi

# Check 5: Results endpoint returns KPIs with days > 0
echo "[5/8] Results KPI check"
KPI_DAYS=$(curl -sf "${BASE_URL}/api/results/${JOB_ID}" | jq -r '.kpis.days // 0')
# Use awk for float comparison
if awk -v d="$KPI_DAYS" 'BEGIN {exit (d > 0) ? 0 : 1}'; then
    echo "  KPIs.days = ${KPI_DAYS} > 0... OK"
else
    echo "  KPIs.days = ${KPI_DAYS} > 0... FAILED"
    exit 1
fi

# Check 5b: Deck upload endpoint accepts a multipart POST with
# the .DATA file plus an optional include/ folder and returns
# a server-side deck_path that validate_deck_path would accept.
# This is the end-to-end shape: the frontend Upload button
# builds the same FormData; a curl call here proves the wire
# contract over the network.
echo "[5b/8] Deck upload API"
TMPDIR_UPLOAD="$(mktemp -d)"
TMP_DECK="${TMPDIR_UPLOAD}/UP_DECK.DATA"
TMP_INC="${TMPDIR_UPLOAD}/include/INC.GRDECL"
mkdir -p "${TMPDIR_UPLOAD}/include"
cat > "${TMP_DECK}" <<'EOF'
RUNSPEC
DIMENS
 1 1 1 /
GRID
DX
 1 /
DY
 1 /
DZ
 1 /
TOPS
 0 /
/
PROPS
EOF
echo "INC contents" > "${TMP_INC}"
UPLOAD_RESP="$(curl -sf -X POST "${BASE_URL}/api/upload_deck" \
    -F "deck=@${TMP_DECK}" \
    -F "include=@${TMP_INC};filename=include/INC.GRDECL")"
UPLOAD_PATH="$(echo "${UPLOAD_RESP}" | jq -r '.deck_path // empty')"
if [ -z "${UPLOAD_PATH}" ] || [ ! -f "${UPLOAD_PATH}" ]; then
    echo "  Upload did not return a writable deck_path (got: ${UPLOAD_RESP})... FAILED"
    rm -rf "${TMPDIR_UPLOAD}"
    exit 1
fi
UPLOAD_INC_DIR="$(echo "${UPLOAD_RESP}" | jq -r '.include_dir // empty')"
if [ -n "${UPLOAD_INC_DIR}" ] && [ ! -f "${UPLOAD_INC_DIR}/INC.GRDECL" ]; then
    echo "  Upload include_dir missing INC.GRDECL under ${UPLOAD_INC_DIR}... FAILED"
    rm -rf "${TMPDIR_UPLOAD}"
    exit 1
fi
echo "  POST /api/upload_deck writes deck + include/ at ${UPLOAD_PATH}... OK"
rm -rf "${TMPDIR_UPLOAD}"

# Check 6: CLI lint command works (in-container)
echo "[6/8] CLI lint check"
TEST_DECK="tests/fixtures/spe1/SPE1CASE1.DATA"
if [ -f "$TEST_DECK" ]; then
    assert_ok "opm-ai lint '${TEST_DECK}' | grep -q 'Passed'" "opm-ai lint on SPE1 fixture passes"
else
    echo "  Test deck not found at ${TEST_DECK}, skipping CLI lint check"
fi

# Check 7: Frontend production build exists (in Docker, this is baked in; locally check frontend/dist)
echo "[7/8] Frontend production build"
if [ -f "/app/static/index.html" ] && grep -q '<div id="root">' /app/static/index.html; then
    echo "  Frontend production build exists (Docker)... OK"
elif [ -f "frontend/dist/index.html" ] && grep -q '<div id="root">' frontend/dist/index.html; then
    echo "  Frontend production build exists (local)... OK"
else
    echo "  Frontend production build not found... FAILED"
    exit 1
fi

echo "========================================="
echo "All smoke tests PASSED"
echo "========================================="