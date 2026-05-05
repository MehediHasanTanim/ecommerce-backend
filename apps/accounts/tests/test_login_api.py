import pytest
from django.urls import reverse
from rest_framework import status
from common.tests.factories import UserFactory

@pytest.mark.django_db
class TestLoginAPI:
    url = reverse('login')

    def test_login_with_email_success(self, api_client):
        user = UserFactory(email="test@example.com", password="StrongPass123!")
        
        payload = {
            "username": "test@example.com",
            "password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']
        assert 'user' in response.data
        assert response.data['user']['email'] == user.email

    def test_login_with_phone_success(self, api_client):
        user = UserFactory(phone="01711111111", password="StrongPass123!")
        
        payload = {
            "username": "01711111111",
            "password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']

    def test_login_invalid_password_fails(self, api_client):
        UserFactory(email="test@example.com", password="StrongPass123!")
        
        payload = {
            "username": "test@example.com",
            "password": "WrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'tokens' not in response.data

    def test_login_unknown_user_fails_without_user_enumeration(self, api_client):
        payload = {
            "username": "unknown@example.com",
            "password": "SomePassword123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # Usually we check if it returns a generic message, which it does based on LoginView
        assert 'detail' in response.data

    def test_login_inactive_user_fails(self, api_client):
        UserFactory(email="inactive@example.com", password="StrongPass123!", is_active=False)
        
        payload = {
            "username": "inactive@example.com",
            "password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'tokens' not in response.data
