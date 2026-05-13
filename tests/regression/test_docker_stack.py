"""
REGR-DOCKER-001 – Dockerized app starts with PostgreSQL and Redis
REGR-CELERY-001 – Celery worker boots successfully
=================================================================
Spec references: backend_api_regression_test_cases.md
Priority       : Critical

These are **integration** tests.  They require the full docker-compose
stack to be running (or this module manages its lifecycle via the
`docker_compose_up` session fixture defined in conftest.py).

Run only these tests:
    pytest -m integration tests/regression/test_docker_stack.py -v

Skip docker bring-up when the stack is already up (e.g. in CI):
    SKIP_DOCKER_UP=1 pytest -m integration tests/regression/test_docker_stack.py -v
"""

import os
import subprocess
import time

import pytest
import requests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOCKER_BASE_URL = os.environ.get("REGRESSION_BASE_URL", "http://localhost:8015")
COMPOSE_FILE = os.environ.get(
    "COMPOSE_FILE",
    os.path.join(os.path.dirname(__file__), "../../docker-compose.yml"),
)


def _compose(*args, check=True):
    """Run a docker compose command and return CompletedProcess."""
    cmd = ["docker", "compose", "-f", COMPOSE_FILE] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# ---------------------------------------------------------------------------
# REGR-DOCKER-001 – Stack health (PostgreSQL + Redis + Web)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDockerStack:
    """REGR-DOCKER-001: Dockerized app starts with PostgreSQL and Redis."""

    def test_health_endpoint_reachable_via_nginx(self, docker_compose_up):
        """
        The web app must respond 200 on /api/v1/health/ through the nginx
        reverse-proxy, proving web + db + redis all started correctly.
        """
        base_url = docker_compose_up
        response = requests.get(f"{base_url}/api/v1/health/", timeout=15)
        assert response.status_code == 200, (
            f"Health endpoint returned {response.status_code} after stack started. "
            "Likely a DB or Redis connection failure in the web container."
        )

    def test_health_response_body(self, docker_compose_up):
        """Health response must carry {'status': 'ok'} in the live stack."""
        base_url = docker_compose_up
        data = requests.get(f"{base_url}/api/v1/health/", timeout=15).json()
        assert data.get("status") == "ok", f"Unexpected health body: {data}"

    def test_postgres_container_is_running(self, docker_compose_up):
        """
        `docker compose ps db` must show the db container is running/healthy.
        This confirms PostgreSQL started and accepted the entrypoint's migrations.
        """
        result = _compose("ps", "--status", "running", "db", check=False)
        assert "db" in result.stdout, (
            f"PostgreSQL container does not appear to be running.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_redis_container_is_running(self, docker_compose_up):
        """
        `docker compose ps redis` must show the redis container is running.
        Redis is required by both the web app (caching/sessions) and Celery.
        """
        result = _compose("ps", "--status", "running", "redis", check=False)
        assert "redis" in result.stdout, (
            f"Redis container does not appear to be running.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_web_container_is_running(self, docker_compose_up):
        """Web (gunicorn) container must be in the running state."""
        result = _compose("ps", "--status", "running", "web", check=False)
        assert "web" in result.stdout, (
            f"Web container does not appear to be running.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_postgres_ping_via_exec(self, docker_compose_up):
        """
        Use `docker compose exec` to run pg_isready inside the db container,
        confirming PostgreSQL is accepting connections on its internal port.
        """
        result = _compose(
            "exec", "-T", "db",
            "pg_isready", "-U", os.environ.get("DB_USER", "postgres"),
            check=False,
        )
        assert result.returncode == 0, (
            f"pg_isready failed inside db container.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_redis_ping_via_exec(self, docker_compose_up):
        """
        Run `redis-cli PING` inside the redis container – must return PONG.
        """
        result = _compose(
            "exec", "-T", "redis",
            "redis-cli", "PING",
            check=False,
        )
        assert "PONG" in result.stdout, (
            f"redis-cli PING did not return PONG.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_swagger_docs_reachable_on_live_stack(self, docker_compose_up):
        """Swagger UI must be accessible on the live docker stack."""
        base_url = docker_compose_up
        response = requests.get(f"{base_url}/api/docs/swagger/", timeout=15)
        assert response.status_code == 200, (
            f"Swagger UI returned {response.status_code} on the live stack."
        )


# ---------------------------------------------------------------------------
# REGR-CELERY-001 – Celery worker boots successfully
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCeleryWorker:
    """REGR-CELERY-001: Celery worker boots and responds to ping."""

    def test_celery_container_is_running(self, docker_compose_up):
        """The `celery` service container must be in a running state."""
        result = _compose("ps", "--status", "running", "celery", check=False)
        assert "celery" in result.stdout, (
            f"Celery container is not running.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_celery_worker_responds_to_ping(self, docker_compose_up):
        """
        `celery inspect ping` must receive a pong from at least one worker,
        confirming the worker connected to the broker (Redis) and is alive.
        """
        result = _compose(
            "exec", "-T", "celery",
            "celery", "-A", "config", "inspect", "ping",
            "--timeout", "10",
            check=False,
        )
        # The command prints responses like: "celery@<hostname>: {'ok': 'pong'}"
        assert result.returncode == 0, (
            f"'celery inspect ping' exited with code {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "pong" in result.stdout.lower(), (
            f"Expected 'pong' in celery inspect ping output.\n"
            f"stdout: {result.stdout}"
        )

    def test_celery_worker_has_registered_tasks(self, docker_compose_up):
        """
        `celery inspect registered` must return a non-empty task list,
        proving autodiscover_tasks() loaded the app's tasks correctly.
        """
        result = _compose(
            "exec", "-T", "celery",
            "celery", "-A", "config", "inspect", "registered",
            "--timeout", "10",
            check=False,
        )
        assert result.returncode == 0, (
            f"'celery inspect registered' failed with code {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )
        # Must contain at minimum the built-in debug_task
        assert "config.celery.debug_task" in result.stdout, (
            f"debug_task not found in registered tasks.\nstdout: {result.stdout}"
        )

    def test_celery_beat_container_is_running(self, docker_compose_up):
        """The `celery-beat` scheduler container must also be running."""
        result = _compose("ps", "--status", "running", "celery-beat", check=False)
        assert "celery-beat" in result.stdout, (
            f"celery-beat container is not running.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
