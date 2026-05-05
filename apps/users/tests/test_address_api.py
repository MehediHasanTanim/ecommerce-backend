import pytest
from django.urls import reverse
from rest_framework import status
from common.tests.factories import UserFactory, AddressFactory
from apps.users.models import Address

@pytest.mark.django_db
class TestAddressAPI:
    list_url = reverse('address-list')

    def test_create_address_success(self, auth_client):
        user = UserFactory()
        client = auth_client(user)
        
        payload = {
            "name": "Home",
            "phone": "01711111111",
            "country": "Bangladesh",
            "city": "Dhaka",
            "area": "Gulshan",
            "postal_code": "1212",
            "address_line": "House 1, Road 1",
            "type": "shipping",
            "is_default": True
        }
        response = client.post(self.list_url, payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Address.objects.filter(user=user, name="Home").exists()

    def test_create_address_missing_required_fields_fails(self, auth_client):
        user = UserFactory()
        client = auth_client(user)
        
        payload = {
            "name": "Home"
            # Missing other fields
        }
        response = client.post(self.list_url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_only_own_addresses(self, auth_client):
        user_a = UserFactory()
        user_b = UserFactory()
        
        AddressFactory(user=user_a, name="User A Address")
        AddressFactory(user=user_b, name="User B Address")
        
        client = auth_client(user_a)
        response = client.get(self.list_url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['name'] == "User A Address"

    def test_get_own_address_success(self, auth_client):
        user = UserFactory()
        address = AddressFactory(user=user)
        url = reverse('address-detail', kwargs={'pk': address.id})
        
        client = auth_client(user)
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(address.id)

    def test_cannot_get_other_users_address(self, auth_client):
        user_a = UserFactory()
        user_b = UserFactory()
        address_b = AddressFactory(user=user_b)
        url = reverse('address-detail', kwargs={'pk': address_b.id})
        
        client = auth_client(user_a)
        response = client.get(url)
        
        # Depending on implementation, it might be 404 (not found in queryset) or 403
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    def test_update_own_address_success(self, auth_client):
        user = UserFactory()
        address = AddressFactory(user=user, name="Old Name")
        url = reverse('address-detail', kwargs={'pk': address.id})
        
        client = auth_client(user)
        payload = {"name": "New Name"}
        response = client.patch(url, payload)
        
        assert response.status_code == status.HTTP_200_OK
        address.refresh_from_db()
        assert address.name == "New Name"

    def test_cannot_update_other_users_address(self, auth_client):
        user_a = UserFactory()
        user_b = UserFactory()
        address_b = AddressFactory(user=user_b)
        url = reverse('address-detail', kwargs={'pk': address_b.id})
        
        client = auth_client(user_a)
        payload = {"name": "New Name"}
        response = client.patch(url, payload)
        
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    def test_delete_own_address_success(self, auth_client):
        user = UserFactory()
        address = AddressFactory(user=user)
        url = reverse('address-detail', kwargs={'pk': address.id})
        
        client = auth_client(user)
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Address.objects.filter(id=address.id).exists()

    def test_set_default_address_success(self, auth_client):
        user = UserFactory()
        addr1 = AddressFactory(user=user, is_default=True, type='shipping')
        addr2 = AddressFactory(user=user, is_default=False, type='shipping')
        
        # Implementation depends on how 'default' action is implemented.
        # router.register(r'addresses', AddressViewSet, basename='address')
        # We need to check AddressViewSet to see if there is a 'default' action.
        # If there's an action, url would be /api/v1/addresses/{id}/default/
        url = reverse('address-set-default', kwargs={'pk': addr2.id})
        
        client = auth_client(user)
        response = client.patch(url)
        
        assert response.status_code == status.HTTP_200_OK
        addr1.refresh_from_db()
        addr2.refresh_from_db()
        assert addr2.is_default is True
        assert addr1.is_default is False

    def test_set_default_address_does_not_affect_other_users(self, auth_client):
        user_a = UserFactory()
        user_b = UserFactory()
        addr_a = AddressFactory(user=user_a, is_default=True, type='shipping')
        addr_b = AddressFactory(user=user_b, is_default=False, type='shipping')
        
        url = reverse('address-set-default', kwargs={'pk': addr_b.id})
        
        client = auth_client(user_b)
        client.patch(url)
        
        addr_a.refresh_from_db()
        assert addr_a.is_default is True
