import pytest
from django.urls import reverse
from rest_framework import status
from apps.users.models import User
from common.tests.factories import UserFactory

@pytest.mark.django_db
class TestRegisterAPI:
    url = reverse('register')

    def test_register_success(self, api_client):
        payload = {
            "name": "Test Customer",
            "email": "customer@example.com",
            "phone": "01711111111",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(email="customer@example.com").exists()
        
        user = User.objects.get(email="customer@example.com")
        assert user.check_password("StrongPass123!")
        assert user.role == 'customer'
        assert user.full_name == "Test Customer"
        
        # Response should contain user object and tokens
        assert 'user' in response.data
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']
        
        # Response should NOT contain password
        assert 'password' not in response.data['user']

    def test_register_password_mismatch_fails(self, api_client):
        payload = {
            "name": "Test Customer",
            "email": "customer@example.com",
            "phone": "01711111111",
            "password": "StrongPass123!",
            "confirm_password": "WrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not User.objects.filter(email="customer@example.com").exists()
        assert 'confirm_password' in response.data

    def test_register_weak_password_fails(self, api_client):
        payload = {
            "name": "Test Customer",
            "email": "customer@example.com",
            "phone": "01711111111",
            "password": "123",
            "confirm_password": "123"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not User.objects.filter(email="customer@example.com").exists()

    def test_register_missing_required_fields_fails(self, api_client):
        payload = {
            "name": "Test Customer",
            # Missing email, phone, password
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email_blocked(self, api_client):
        # Precondition: Existing user
        UserFactory(email="customer@example.com")
        
        payload = {
            "name": "Another User",
            "email": "customer@example.com",
            "phone": "01722222222",
            "password": "StrongPass123!",
            "confirm_password": "StrongPass123!"
        }
        response = api_client.post(self.url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert User.objects.filter(email="customer@example.com").count() == 1
        assert "email" in response.data
