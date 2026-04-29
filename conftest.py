import pytest
from rest_framework.test import APIClient
from apps.users.models import User

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user(db):
    def make_user(**kwargs):
        kwargs['password'] = 'testpass123'
        if 'email' not in kwargs:
            kwargs['email'] = 'testuser@example.com'
        return User.objects.create_user(**kwargs)
    return make_user
