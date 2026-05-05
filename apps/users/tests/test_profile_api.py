import pytest
from django.urls import reverse
from rest_framework import status
from common.tests.factories import UserFactory

@pytest.mark.django_db
class TestProfileAPI:
    url = reverse('me')

    def test_get_profile_success(self, auth_client):
        user = UserFactory(full_name="Test User")
        client = auth_client(user)
        
        response = client.get(self.url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['full_name'] == "Test User"
        assert response.data['email'] == user.email

    def test_update_profile_success(self, auth_client):
        user = UserFactory(full_name="Old Name")
        client = auth_client(user)
        
        payload = {
            "full_name": "New Name",
            "phone": "01999999999"
        }
        response = client.patch(self.url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.full_name == "New Name"
        assert user.phone == "01999999999"
