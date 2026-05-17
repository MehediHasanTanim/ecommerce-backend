#!/usr/bin/env bash
# =============================================================================
# scripts/regression/run_docker_regression.sh
#
# End-to-end regression runner for the five Backend Regression Automation tasks:
#
#   REGR-HEALTH-001  │ Health endpoint returns 200
#   REGR-SWAGGER-001 │ Swagger docs load successfully
#   REGR-SEC-001     │ Anonymous request is rejected from protected API
#   REGR-DOCKER-001  │ Dockerized app starts with PostgreSQL and Redis
#   REGR-CELERY-001  │ Celery worker boots successfully
#
# Usage:
#   ./scripts/regression/run_docker_regression.sh [--keep-up]
#
# Flags:
#   --keep-up   Do NOT tear the stack down after tests complete.
#               Useful for local debugging.
#
# Environment variables (all optional):
#   REGRESSION_BASE_URL  Base URL of the running stack   (default: http://localhost:8015)
#   SKIP_DOCKER_UP       Set to "1" to skip docker compose up (stack already running)
#   COMPOSE_FILE         Path to docker-compose.yml       (default: ./docker-compose.yml)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BASE_URL="${REGRESSION_BASE_URL:-http://localhost:8015}"
HEALTH_URL="${BASE_URL}/api/v1/health/"
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_DIR}/docker-compose.yml}"
KEEP_UP=false
SKIP_DOCKER_UP="${SKIP_DOCKER_UP:-0}"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
for arg in "$@"; do
  case $arg in
    --keep-up) KEEP_UP=true ;;
    *) echo "Unknown argument: $arg"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILED=$((FAILED + 1)); }
info() { echo -e "${YELLOW}[INFO]${NC} $*"; }

FAILED=0

# ---------------------------------------------------------------------------
# Utility: wait for the health endpoint to respond 200
# ---------------------------------------------------------------------------
wait_for_health() {
  local url="$1"
  local timeout="${2:-120}"
  local elapsed=0

  info "Waiting for ${url} (timeout: ${timeout}s)…"
  while ! curl --silent --fail --max-time 5 "${url}" > /dev/null 2>&1; do
    if [[ $elapsed -ge $timeout ]]; then
      echo ""
      return 1
    fi
    printf "."
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo ""
  return 0
}

# ---------------------------------------------------------------------------
# 1. Bring the stack up
# ---------------------------------------------------------------------------
if [[ "$SKIP_DOCKER_UP" == "1" ]]; then
  info "SKIP_DOCKER_UP=1 – assuming stack is already running."
else
  info "Starting docker-compose stack from ${COMPOSE_FILE}…"
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans --quiet 2>/dev/null || true
  docker compose -f "${COMPOSE_FILE}" up -d --build

  if ! wait_for_health "${HEALTH_URL}" 120; then
    echo ""
    fail "Stack did not become healthy within 120 s."
    info "=== Last 60 lines of container logs ==="
    docker compose -f "${COMPOSE_FILE}" logs --tail=60
    docker compose -f "${COMPOSE_FILE}" down --remove-orphans
    exit 1
  fi
  pass "Stack is up and healthy."
fi

# ---------------------------------------------------------------------------
# Helper: assert HTTP status
# ---------------------------------------------------------------------------
assert_http_status() {
  local label="$1"
  local expected="$2"
  local url="$3"
  local actual
  actual=$(curl --silent --output /dev/null --write-out "%{http_code}" --max-time 10 "${url}")
  if [[ "$actual" == "$expected" ]]; then
    pass "${label} → HTTP ${actual}"
  else
    fail "${label} → expected HTTP ${expected}, got ${actual} (${url})"
  fi
}

# ---------------------------------------------------------------------------
# REGR-HEALTH-001 – Health endpoint returns 200
# ---------------------------------------------------------------------------
echo ""
info "=== REGR-HEALTH-001: Health endpoint returns 200 ==="
assert_http_status "GET /api/v1/health/" "200" "${BASE_URL}/api/v1/health/"

HEALTH_BODY=$(curl --silent --max-time 10 "${BASE_URL}/api/v1/health/")
if echo "${HEALTH_BODY}" | grep -q '"status".*"ok"'; then
  pass "Health body contains {\"status\": \"ok\"}"
else
  fail "Health body missing expected status:ok  →  ${HEALTH_BODY}"
fi

# ---------------------------------------------------------------------------
# REGR-SWAGGER-001 – Swagger docs load successfully
# ---------------------------------------------------------------------------
echo ""
info "=== REGR-SWAGGER-001: Swagger docs load successfully ==="
assert_http_status "GET /api/v1/schema/"        "200" "${BASE_URL}/api/v1/schema/"
assert_http_status "GET /api/v1/docs/swagger/"  "200" "${BASE_URL}/api/v1/docs/swagger/"
assert_http_status "GET /api/v1/docs/redoc/"    "200" "${BASE_URL}/api/v1/docs/redoc/"

# ---------------------------------------------------------------------------
# REGR-SEC-001 – Anonymous request is rejected from protected API
# ---------------------------------------------------------------------------
echo ""
info "=== REGR-SEC-001: Anonymous request is rejected from protected API ==="

PROTECTED_ENDPOINTS=(
  "GET /api/v1/me/"
  "GET /api/v1/addresses/"
  "PUT /api/v1/me/password/"
)

for ep in "${PROTECTED_ENDPOINTS[@]}"; do
  METHOD="${ep%% *}"
  PATH_PART="${ep##* }"
  STATUS=$(curl --silent --output /dev/null --write-out "%{http_code}" \
    --max-time 10 --request "${METHOD}" "${BASE_URL}${PATH_PART}")
  if [[ "$STATUS" == "401" ]]; then
    pass "${METHOD} ${PATH_PART} (anonymous) → HTTP 401"
  else
    fail "${METHOD} ${PATH_PART} (anonymous) → expected 401, got ${STATUS}"
  fi
done

# Also verify invalid JWT is rejected
STATUS=$(curl --silent --output /dev/null --write-out "%{http_code}" \
  --max-time 10 \
  --header "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmYWtlIn0.INVALID" \
  "${BASE_URL}/api/v1/me/")
if [[ "$STATUS" == "401" ]]; then
  pass "GET /api/v1/me/ (invalid JWT) → HTTP 401"
else
  fail "GET /api/v1/me/ (invalid JWT) → expected 401, got ${STATUS}"
fi

# ---------------------------------------------------------------------------
# REGR-DOCKER-001 – Dockerized app starts with PostgreSQL and Redis
# ---------------------------------------------------------------------------
echo ""
info "=== REGR-DOCKER-001: Dockerized app starts with PostgreSQL and Redis ==="

# Check containers are running
for SVC in web db redis; do
  if docker compose -f "${COMPOSE_FILE}" ps --status running "${SVC}" 2>/dev/null \
      | grep -q "${SVC}"; then
    pass "Container '${SVC}' is running"
  else
    fail "Container '${SVC}' is NOT running"
  fi
done

# pg_isready inside the db container
if docker compose -f "${COMPOSE_FILE}" exec -T db \
    pg_isready -U "${DB_USER:-postgres}" > /dev/null 2>&1; then
  pass "PostgreSQL pg_isready OK"
else
  fail "PostgreSQL pg_isready FAILED"
fi

# redis-cli PING inside the redis container
PONG=$(docker compose -f "${COMPOSE_FILE}" exec -T redis redis-cli PING 2>/dev/null || true)
if echo "${PONG}" | grep -qi "PONG"; then
  pass "Redis PING → PONG"
else
  fail "Redis PING did not return PONG  →  ${PONG}"
fi

# ---------------------------------------------------------------------------
# REGR-CELERY-001 – Celery worker boots successfully
# ---------------------------------------------------------------------------
echo ""
info "=== REGR-CELERY-001: Celery worker boots successfully ==="

# Container running?
if docker compose -f "${COMPOSE_FILE}" ps --status running celery 2>/dev/null \
    | grep -q "celery"; then
  pass "Container 'celery' is running"
else
  fail "Container 'celery' is NOT running"
fi

# Worker responds to ping
PING_OUT=$(docker compose -f "${COMPOSE_FILE}" exec -T celery \
  celery -A config inspect ping --timeout 15 2>&1 || true)
if echo "${PING_OUT}" | grep -qi "pong"; then
  pass "Celery worker responded to 'inspect ping'"
else
  fail "Celery worker did not respond to ping\n  output: ${PING_OUT}"
fi

# Worker has tasks registered
REG_OUT=$(docker compose -f "${COMPOSE_FILE}" exec -T celery \
  celery -A config inspect registered --timeout 10 2>&1 || true)
if echo "${REG_OUT}" | grep -q "debug_task"; then
  pass "Celery worker has tasks registered (debug_task found)"
else
  fail "debug_task not found in registered tasks\n  output: ${REG_OUT}"
fi

# celery-beat running?
if docker compose -f "${COMPOSE_FILE}" ps --status running celery-beat 2>/dev/null \
    | grep -q "celery-beat"; then
  pass "Container 'celery-beat' is running"
else
  fail "Container 'celery-beat' is NOT running"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}All regression checks PASSED.${NC}"
else
  echo -e "${RED}${FAILED} regression check(s) FAILED.${NC}"
fi
echo "============================================================"

# ---------------------------------------------------------------------------
# Teardown (unless --keep-up)
# ---------------------------------------------------------------------------
if [[ "$KEEP_UP" == "false" && "$SKIP_DOCKER_UP" != "1" ]]; then
  info "Tearing down docker-compose stack…"
  docker compose -f "${COMPOSE_FILE}" down --remove-orphans
fi

exit $FAILED
