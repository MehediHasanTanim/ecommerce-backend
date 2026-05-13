"""
REGR-SWAGGER-001 – Swagger / OpenAPI docs load successfully
===========================================================
Spec reference: backend_api_regression_test_cases.md → Release Smoke Suite
Priority      : High

Three documentation endpoints must return HTTP 200 without authentication:
  • /api/schema/            – raw OpenAPI schema (JSON/YAML)
  • /api/docs/swagger/      – Swagger UI HTML
  • /api/docs/redoc/        – ReDoc HTML
"""

import pytest


@pytest.mark.django_db
class TestSwaggerDocs:
    """REGR-SWAGGER-001: Swagger / OpenAPI docs load successfully"""

    # -----------------------------------------------------------------------
    # OpenAPI schema endpoint
    # -----------------------------------------------------------------------

    def test_schema_endpoint_returns_200(self, client):
        """GET /api/schema/ → 200 OK."""
        response = client.get("/api/schema/")
        assert response.status_code == 200, (
            f"OpenAPI schema endpoint returned {response.status_code}, expected 200."
        )

    def test_schema_endpoint_content_type(self, client):
        """Schema response must be YAML or JSON (OpenAPI-compatible)."""
        response = client.get("/api/schema/")
        content_type = response.get("Content-Type", "")
        assert any(
            ct in content_type
            for ct in ("application/vnd.oai.openapi", "application/json", "text/yaml")
        ), f"Unexpected Content-Type for schema: {content_type}"

    # -----------------------------------------------------------------------
    # Swagger UI
    # -----------------------------------------------------------------------

    def test_swagger_ui_returns_200(self, client):
        """GET /api/docs/swagger/ → 200 OK with HTML body."""
        response = client.get("/api/docs/swagger/")
        assert response.status_code == 200, (
            f"Swagger UI returned {response.status_code}, expected 200."
        )

    def test_swagger_ui_content_type_is_html(self, client):
        """Swagger UI must respond with text/html."""
        response = client.get("/api/docs/swagger/")
        assert "text/html" in response.get("Content-Type", ""), (
            "Swagger UI must return an HTML page."
        )

    def test_swagger_ui_body_contains_swagger_keyword(self, client):
        """The Swagger UI page must reference the word 'swagger' (case-insensitive)."""
        response = client.get("/api/docs/swagger/")
        assert b"swagger" in response.content.lower(), (
            "Swagger UI page body does not contain expected 'swagger' content."
        )

    # -----------------------------------------------------------------------
    # ReDoc UI
    # -----------------------------------------------------------------------

    def test_redoc_returns_200(self, client):
        """GET /api/docs/redoc/ → 200 OK."""
        response = client.get("/api/docs/redoc/")
        assert response.status_code == 200, (
            f"ReDoc endpoint returned {response.status_code}, expected 200."
        )

    def test_redoc_content_type_is_html(self, client):
        """ReDoc must respond with text/html."""
        response = client.get("/api/docs/redoc/")
        assert "text/html" in response.get("Content-Type", ""), (
            "ReDoc endpoint must return an HTML page."
        )

    # -----------------------------------------------------------------------
    # Docs must not require authentication
    # -----------------------------------------------------------------------

    def test_swagger_does_not_require_auth(self, client):
        """Documentation endpoints must be publicly accessible (no auth)."""
        for path in ("/api/schema/", "/api/docs/swagger/", "/api/docs/redoc/"):
            response = client.get(path)
            assert response.status_code not in (401, 403), (
                f"{path} must NOT require authentication, got {response.status_code}."
            )
