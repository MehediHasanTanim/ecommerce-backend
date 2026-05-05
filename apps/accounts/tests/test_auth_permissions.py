import pytest
from django.urls import reverse
from rest_framework import status
from common.tests.factories import UserFactory

@pytest.mark.django_db
class TestAuthPermissions:
    def test_me_requires_authentication(self, api_client):
        url = reverse('me')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_addresses_requires_authentication(self, api_client):
        url = reverse('address-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_rejected(self, api_client):
        url = reverse('me')
        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
