import pytest
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestRegisterAPI:
    url = reverse('register')

    def test_register_success(self, api_client):
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
            "phone": "01722222222"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data
        assert "tokens" in response.data
        assert response.data["user"]["email"] == "jane@example.com"
        assert "password" not in response.data["user"]
        
        # Database check
        user = User.objects.get(email="jane@example.com")
        assert user.full_name == "Jane Doe"
        assert user.check_password("StrongPass123!")
        assert user.role == "customer"

    def test_register_missing_required_fields_fails(self, api_client):
        payload = {
            "email": "incomplete@example.com"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch_fails(self, api_client):
        payload = {
            "name": "Jane",
            "email": "mismatch@example.com",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!",
            "phone": "01733333333"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in response.data

    def test_register_weak_password_fails(self, api_client):
        payload = {
            "name": "Jane",
            "email": "weak@example.com",
            "password": "123",
            "confirm_password": "123",
            "phone": "01744444444"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email_blocked(self, api_client, user):
        payload = {
            "name": "Jane",
            "email": user.email,
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
            "phone": "01755555555"
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_register_duplicate_phone_blocked(self, api_client, user):
        payload = {
            "name": "Jane",
            "email": "new@example.com",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!",
            "phone": user.phone
        }
        response = api_client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone" in response.data
