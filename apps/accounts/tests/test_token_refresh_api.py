import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

@pytest.mark.django_db
class TestTokenRefreshAPI:
    url = reverse('token_refresh')

    def test_refresh_token_success(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        payload = {"refresh": str(refresh)}
        
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_refresh_token_invalid_fails(self, api_client):
        payload = {"refresh": "invalid-token"}
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_token_missing_fails(self, api_client):
        payload = {}
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
