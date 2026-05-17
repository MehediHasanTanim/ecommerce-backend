"""
REGR-SEC-001 – Anonymous request is rejected from protected APIs
================================================================
Spec references:
  SEC-001  → Protected endpoints reject missing token   (Critical)
  SEC-002  → Invalid JWT token rejected                 (Critical)
  USER-ME-002 → Unauthenticated profile access → 401   (Critical)
  ADM-AUTH-001 → Customer blocked from admin endpoints → 403 (Critical)
Priority: Critical

Rules enforced:
  1. Every protected endpoint returns 401 when no token is supplied.
  2. Every protected endpoint returns 401 when a forged/invalid JWT is supplied.
  3. Admin-only endpoints return 403 when a regular customer hits them.
"""

import pytest


# ---------------------------------------------------------------------------
# Endpoints that MUST require authentication (SEC-001)
# ---------------------------------------------------------------------------

PROTECTED_ENDPOINTS = [
    # Profile
    ("GET",   "/api/v1/users/me/"),
    ("PATCH", "/api/v1/users/me/"),
    ("PUT",   "/api/v1/users/me/password/"),
    # Addresses
    ("GET",   "/api/v1/users/addresses/"),
    ("POST",  "/api/v1/users/addresses/"),
]

INVALID_JWT = (
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJmYWtlIiwiaWF0IjoxNjAwMDAwMDAwfQ"
    ".INVALID_SIGNATURE_HERE"
)


@pytest.mark.django_db
class TestAnonymousRejectedFromProtectedEndpoints:
    """
    SEC-001 – Every protected endpoint must return 401 when
    no Authorization header is present.
    """

    @pytest.mark.parametrize("method,endpoint", PROTECTED_ENDPOINTS)
    def test_no_token_returns_401(self, api_client, method, endpoint):
        """
        Unauthenticated request → 401 Unauthorized.
        The client has NO Authorization header set.
        """
        api_client.credentials()          # clear any credentials
        call = getattr(api_client, method.lower())
        response = call(endpoint)
        assert response.status_code == 401, (
            f"{method} {endpoint}: expected 401 for anonymous request, "
            f"got {response.status_code}."
        )

    @pytest.mark.parametrize("method,endpoint", PROTECTED_ENDPOINTS)
    def test_invalid_jwt_returns_401(self, api_client, method, endpoint):
        """
        SEC-002 – A syntactically valid but cryptographically forged JWT
        must be rejected with 401.
        """
        api_client.credentials(HTTP_AUTHORIZATION=INVALID_JWT)
        call = getattr(api_client, method.lower())
        response = call(endpoint)
        assert response.status_code == 401, (
            f"{method} {endpoint}: expected 401 for invalid JWT, "
            f"got {response.status_code}."
        )
        api_client.credentials()          # clean up


@pytest.mark.django_db
class TestMeEndpointAnonymousRejection:
    """
    USER-ME-002 – Unauthenticated user cannot access /api/v1/users/me/.
    Mirrors the exact scenario defined in the regression test doc.
    """

    def test_get_me_without_auth_returns_401(self, api_client):
        """GET /api/v1/users/me/ without token → 401."""
        api_client.credentials()
        response = api_client.get("/api/v1/users/me/")
        assert response.status_code == 401, (
            f"Expected 401 for unauthenticated GET /api/v1/users/me/, "
            f"got {response.status_code}."
        )

    def test_patch_me_without_auth_returns_401(self, api_client):
        """PATCH /api/v1/users/me/ without token → 401."""
        api_client.credentials()
        response = api_client.patch("/api/v1/users/me/", {"first_name": "Eve"}, format="json")
        assert response.status_code == 401, (
            f"Expected 401 for unauthenticated PATCH /api/v1/users/me/, "
            f"got {response.status_code}."
        )

    def test_change_password_without_auth_returns_401(self, api_client):
        """PUT /api/v1/users/me/password/ without token → 401."""
        api_client.credentials()
        response = api_client.put(
            "/api/v1/users/me/password/",
            {"old_password": "x", "new_password": "y", "confirm_password": "y"},
            format="json",
        )
        assert response.status_code == 401, (
            f"Expected 401 for unauthenticated PUT /api/v1/users/me/password/, "
            f"got {response.status_code}."
        )


@pytest.mark.django_db
class TestAuthenticatedUserStillRestricted:
    """
    ADM-AUTH-001 / SEC-004 – A regular customer must receive 403
    when attempting to reach admin-only list endpoints.
    """

    def test_customer_blocked_from_admin_user_list(self, create_user, auth_client):
        """
        Authenticated customer hitting the admin user-list endpoint → 403.
        Uses force_authenticate so we isolate permission logic only.
        """
        customer = create_user(
            email="customer_sec@example.com",
            phone="+8801700000001",
            password="TestPass123!",
        )
        client = auth_client(customer)
        response = client.get("/api/v1/users/")
        assert response.status_code == 403, (
            f"Expected 403 for customer accessing /api/v1/users/, "
            f"got {response.status_code}."
        )
