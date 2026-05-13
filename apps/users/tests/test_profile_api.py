import pytest
from django.urls import reverse
from rest_framework import status

@pytest.mark.django_db
class TestProfileAPI:
    url = reverse('me')

    def test_get_profile_success(self, authenticated_client, user):
        response = authenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_update_profile_success(self, authenticated_client, user):
        payload = {"full_name": "Updated Name"}
        response = authenticated_client.patch(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.full_name == "Updated Name"

    def test_get_profile_unauthorized_fails(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile_unauthorized_fails(self, api_client):
        payload = {"full_name": "New Name"}
        response = api_client.patch(self.url, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
