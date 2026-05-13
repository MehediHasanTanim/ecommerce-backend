import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
class TestLoginAPI:
    url = reverse('login')

    def test_login_success(self, api_client, user):
        payload = {
            "username": user.email,
            "password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert "user" in response.data
        assert response.data["user"]["email"] == user.email

    def test_login_with_phone_success(self, api_client, user):
        payload = {
            "username": user.phone,
            "password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user"]["phone"] == user.phone

    def test_login_invalid_password_fails(self, api_client, user):
        payload = {
            "username": user.email,
            "password": "WrongPassword"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "tokens" not in response.data

    def test_login_unknown_email_fails(self, api_client):
        payload = {
            "username": "unknown@example.com",
            "password": "SomePassword123!"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user_fails(self, api_client, user):
        user.is_active = False
        user.save()
        
        payload = {
            "username": user.email,
            "password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
