import pytest
import os
from rest_framework.test import APIClient
from apps.users.models import User

@pytest.fixture(autouse=True)
def set_test_settings(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_user(db):
    def make_user(**kwargs):
        if 'password' not in kwargs:
            kwargs['password'] = 'testpass123'
        if 'email' not in kwargs:
            kwargs['email'] = 'testuser@example.com'
        return User.objects.create_user(**kwargs)
    return make_user

@pytest.fixture
def auth_client(api_client, db):
    def _auth_client(user):
        api_client.force_authenticate(user=user)
        return api_client
    return _auth_client
