import pytest
from django.urls import reverse
from apps.users.models import Address

@pytest.mark.django_db
class TestProfileAndAddress:
    def test_get_me(self, api_client, create_user):
        user = create_user(email="me@example.com")
        api_client.force_authenticate(user=user)
        url = reverse('me')
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['email'] == "me@example.com"

    def test_update_profile(self, api_client, create_user):
        user = create_user(email="me@example.com", full_name="Old Name")
        api_client.force_authenticate(user=user)
        url = reverse('me')
        response = api_client.patch(url, {"full_name": "New Name"})
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.full_name == "New Name"

    def test_change_password(self, api_client, create_user):
        user = create_user(email="me@example.com")
        # create_user sets password to 'testpass123' by default
        api_client.force_authenticate(user=user)
        url = reverse('change_password')
        data = {
            "old_password": "testpass123",
            "new_password": "NewStrongPassword123!",
            "confirm_password": "NewStrongPassword123!"
        }
        response = api_client.post(url, data)
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password("NewStrongPassword123!")

    def test_address_crud(self, api_client, create_user):
        user = create_user(email="me@example.com")
        api_client.force_authenticate(user=user)
        
        # Create
        url = reverse('address-list')
        data = {
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
        response = api_client.post(url, data)
        assert response.status_code == 201
        assert Address.objects.filter(user=user).count() == 1

        # List
        response = api_client.get(url)
        assert len(response.data) == 1

        # Set default behavior test
        data2 = data.copy()
        data2['name'] = "Work"
        data2['is_default'] = True
        api_client.post(url, data2)
        
        assert Address.objects.filter(user=user, is_default=True).count() == 1
        assert Address.objects.get(name="Work", user=user).is_default is True
        assert Address.objects.get(name="Home", user=user).is_default is False

    def test_cannot_access_other_address(self, api_client, create_user):
        user1 = create_user(email="user1@example.com")
        user2 = create_user(email="user2@example.com")
        address = Address.objects.create(user=user2, name="Secret", phone="123", country="BD", city="DH", area="A", postal_code="1", address_line="L")
        
        api_client.force_authenticate(user=user1)
        url = reverse('address-detail', kwargs={'pk': address.id})
        response = api_client.get(url)
        assert response.status_code == 404
