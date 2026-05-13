"""
REGR-HEALTH-001 – Health endpoint returns 200
==============================================
Spec reference: backend_api_regression_test_cases.md → Release Smoke Suite #1
Priority      : Critical

The `/api/v1/health/` endpoint must:
  • be reachable without authentication
  • return HTTP 200
  • return JSON with {"status": "ok"}
"""

import pytest


@pytest.mark.django_db
class TestHealthEndpoint:
    """REGR-HEALTH-001: Health endpoint returns 200"""

    def test_health_returns_200(self, client):
        """GET /api/v1/health/ → 200 OK (no auth required)."""
        response = client.get("/api/v1/health/")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. "
            "Health endpoint must be publicly accessible."
        )

    def test_health_response_is_json(self, client):
        """Response body must be valid JSON."""
        response = client.get("/api/v1/health/")
        assert response["Content-Type"].startswith("application/json"), (
            "Health endpoint must return Content-Type: application/json"
        )

    def test_health_response_contains_status_ok(self, client):
        """Response body must contain {"status": "ok"}."""
        response = client.get("/api/v1/health/")
        data = response.json()
        assert data.get("status") == "ok", (
            f"Expected 'status: ok' in response body, got: {data}"
        )

    def test_health_response_contains_service_name(self, client):
        """Response body must contain a 'service' key to identify the backend."""
        response = client.get("/api/v1/health/")
        data = response.json()
        assert "service" in data, (
            f"Expected 'service' key in health response, got: {data}"
        )

    def test_health_endpoint_does_not_require_auth(self, client):
        """
        The health probe must never require authentication so that
        load-balancers and CI smoke tests can reach it freely.
        """
        # client has no credentials – status must not be 401 or 403
        response = client.get("/api/v1/health/")
        assert response.status_code not in (401, 403), (
            "Health endpoint must NOT require authentication."
        )
