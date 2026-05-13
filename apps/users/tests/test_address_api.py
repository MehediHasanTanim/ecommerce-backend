import pytest
from django.urls import reverse
from rest_framework import status
from apps.users.models import Address

@pytest.mark.django_db
class TestAddressAPI:
    list_url = reverse('address-list')

    def test_create_address_success(self, authenticated_client, user):
        payload = {
            "name": "Home",
            "phone": "01712345678",
            "country": "Bangladesh",
            "city": "Dhaka",
            "area": "Gulshan",
            "postal_code": "1212",
            "address_line": "House 1, Road 1",
            "type": "shipping",
            "is_default": True
        }
        response = authenticated_client.post(self.list_url, payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Address.objects.filter(user=user, name="Home").exists()

    def test_list_own_addresses(self, authenticated_client, user, address, other_user_address):
        response = authenticated_client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == str(address.id)

    def test_retrieve_own_address(self, authenticated_client, user, address):
        url = reverse('address-detail', kwargs={'pk': address.id})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_update_own_address(self, authenticated_client, user, address):
        url = reverse('address-detail', kwargs={'pk': address.id})
        payload = {"name": "Work"}
        response = authenticated_client.patch(url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        address.refresh_from_db()
        assert address.name == "Work"

    def test_delete_own_address(self, authenticated_client, user, address):
        url = reverse('address-detail', kwargs={'pk': address.id})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Address.objects.filter(id=address.id).exists()

    def test_unauthorized_access_fails(self, api_client):
        response = api_client.get(self.list_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_other_user_address_fails(self, authenticated_client, other_user_address):
        url = reverse('address-detail', kwargs={'pk': other_user_address.id})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_set_default_address_logic(self, authenticated_client, user, address):
        # Create another address and set it as default
        payload = {
            "name": "Work",
            "phone": "01712345679",
            "country": "Bangladesh",
            "city": "Dhaka",
            "area": "Banani",
            "postal_code": "1213",
            "address_line": "House 2, Road 2",
            "type": "shipping",
            "is_default": True
        }
        authenticated_client.post(self.list_url, payload)
        
        address.refresh_from_db()
        assert address.is_default is False
        assert Address.objects.filter(user=user, type='shipping', is_default=True).count() == 1
