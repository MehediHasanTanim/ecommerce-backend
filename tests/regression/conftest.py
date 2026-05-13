"""
Regression-suite conftest
=========================
Fixtures shared across the five regression test modules:
  REGR-HEALTH-001  │ test_health.py
  REGR-SWAGGER-001 │ test_swagger.py
  REGR-SEC-001     │ test_security.py
  REGR-DOCKER-001  │ test_docker_stack.py
  REGR-CELERY-001  │ test_docker_stack.py
"""

import os
import subprocess
import time

import pytest
import requests
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOCKER_BASE_URL = os.environ.get("REGRESSION_BASE_URL", "http://localhost:8015")
COMPOSE_FILE = os.environ.get(
    "COMPOSE_FILE",
    os.path.join(os.path.dirname(__file__), "../../docker-compose.yml"),
)


def _wait_for_url(url: str, timeout: int = 120, interval: float = 3.0) -> bool:
    """Poll *url* until it returns HTTP 200 or *timeout* seconds elapse."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Unit / API-client fixtures  (no Docker needed)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def regression_client():
    """A bare DRF APIClient with no authentication – used in unit regression tests."""
    return APIClient()


# ---------------------------------------------------------------------------
# Docker-compose fixtures  (only activated for @pytest.mark.integration tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def docker_compose_up(tmp_path_factory):
    """
    Session-scoped fixture that:
      1. Brings the full docker-compose stack up.
      2. Waits until the health endpoint is reachable.
      3. Yields the resolved base URL.
      4. Tears the stack down after all integration tests finish.

    Skip this fixture if SKIP_DOCKER_UP=1 is set in the environment
    (useful when the stack is already running in CI).
    """
    if os.environ.get("SKIP_DOCKER_UP", "0") == "1":
        health_url = f"{DOCKER_BASE_URL}/api/v1/health/"
        if not _wait_for_url(health_url, timeout=30):
            pytest.skip("Stack not reachable and SKIP_DOCKER_UP=1 – skipping.")
        yield DOCKER_BASE_URL
        return

    compose_cmd = ["docker", "compose", "-f", COMPOSE_FILE]

    # Tear down any stale containers first
    subprocess.run(compose_cmd + ["down", "--remove-orphans"], check=False)

    # Start the stack
    result = subprocess.run(compose_cmd + ["up", "-d", "--build"], capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(f"docker compose up failed:\n{result.stderr}")

    # Wait until the app is responsive
    health_url = f"{DOCKER_BASE_URL}/api/v1/health/"
    ready = _wait_for_url(health_url, timeout=120)
    if not ready:
        logs = subprocess.run(compose_cmd + ["logs", "--tail=50"], capture_output=True, text=True)
        subprocess.run(compose_cmd + ["down", "--remove-orphans"], check=False)
        pytest.fail(
            f"Stack did not become healthy within 120 s.\n"
            f"Last 50 lines of logs:\n{logs.stdout}"
        )

    yield DOCKER_BASE_URL

    # Teardown
    subprocess.run(compose_cmd + ["down", "--remove-orphans"], check=False)
