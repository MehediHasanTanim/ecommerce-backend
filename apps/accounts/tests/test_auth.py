import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import UserVerificationToken
import uuid
import hashlib
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

@pytest.mark.django_db
class TestAuth:
    def test_register_success(self, api_client):
        url = reverse('register')
        data = {
            "name": "Customer Name",
            "email": "customer@example.com",
            "phone": "01711111111",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 201
        assert response.data['user']['email'] == data['email']
        assert 'tokens' in response.data

    def test_register_duplicate_email(self, api_client, create_user):
        create_user(email="test@example.com")
        url = reverse('register')
        data = {
            "name": "New User",
            "email": "test@example.com",
            "phone": "01722222222",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 400
        assert 'email' in response.data

    def test_login_email_success(self, api_client, create_user):
        create_user(email="test@example.com", password="StrongPassword123!")
        url = reverse('login')
        data = {
            "username": "test@example.com",
            "password": "StrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 200
        assert 'tokens' in response.data

    def test_login_phone_success(self, api_client, create_user):
        create_user(email="test@example.com", phone="01711111111", password="StrongPassword123!")
        url = reverse('login')
        data = {
            "username": "01711111111",
            "password": "StrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 200
        assert 'tokens' in response.data

    def test_login_inactive_user(self, api_client, create_user):
        user = create_user(email="inactive@example.com", password="StrongPassword123!")
        user.is_active = False
        user.save()
        
        url = reverse('login')
        data = {
            "username": "inactive@example.com",
            "password": "StrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 401

    def test_forgot_password(self, api_client, create_user):
        from unittest.mock import patch
        create_user(email="test@example.com")
        with patch('apps.accounts.services.send_reset_notification.delay') as mock_send:
            url = reverse('forgot_password')
            response = api_client.post(url, {"username": "test@example.com"})
            assert response.status_code == 200
            assert UserVerificationToken.objects.filter(purpose='password_reset').exists()
            assert mock_send.called

    def test_reset_password_success(self, api_client, create_user):
        user = create_user(email="test@example.com")
        token = uuid.uuid4()
        token_hash = hashlib.sha256(str(token).encode()).hexdigest()
        UserVerificationToken.objects.create(
            user=user,
            token_hash=token_hash,
            purpose='password_reset',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        url = reverse('reset_password')
        data = {
            "token": str(token),
            "password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password("NewStrongPassword123!")
