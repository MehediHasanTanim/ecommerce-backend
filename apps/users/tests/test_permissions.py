import pytest
from rest_framework import status
from django.urls import reverse
from common.tests.factories import (
    UserFactory, AdminUserFactory, StaffUserFactory, VendorUserFactory
)

@pytest.mark.django_db
class TestPermissionRules:
    # We need endpoints that use these permissions to test them.
    # UserViewSet uses IsAdminUser (which is built-in DRF)
    # Let's assume we have some endpoints using our custom permissions.
    # Since I don't see them in urls.py for Phase 2 specifically other than AddressViewSet (IsOwnerOrAdmin),
    # I will test IsOwnerOrAdmin and others by mocking or using existing views if possible.
    # Actually, the user asked to test reusable permission classes.
    
    def test_customer_cannot_access_admin_endpoint(self, auth_client):
        user = UserFactory(role='customer')
        url = reverse('user-list') # UserViewSet requires IsAdminUser
        client = auth_client(user)
        response = client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_admin_endpoint(self, auth_client):
        admin = AdminUserFactory()
        url = reverse('user-list')
        client = auth_client(admin)
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

    # For other permissions, if there are no views using them, I can create a dummy view or just test the classes directly.
    # But usually, it's better to test via API.
    # Let's see if there are any views using IsStaff, IsVendor etc.
    # I'll check permissions.py again.
    
    def test_staff_can_access_staff_allowed_endpoint(self, auth_client):
        staff = StaffUserFactory()
        # No specific staff endpoint yet, but we can check the permission class directly
        from apps.users.permissions import IsStaff
        permission = IsStaff()
        request = type('Request', (), {'user': staff})
        assert permission.has_permission(request, None) is True

    def test_vendor_can_access_vendor_resource(self, auth_client):
        vendor = VendorUserFactory()
        from apps.users.permissions import IsVendor
        permission = IsVendor()
        request = type('Request', (), {'user': vendor})
        assert permission.has_permission(request, None) is True

    def test_admin_or_staff_permission(self, auth_client):
        admin = AdminUserFactory()
        staff = StaffUserFactory()
        customer = UserFactory(role='customer')
        from apps.users.permissions import IsAdminOrStaff
        permission = IsAdminOrStaff()
        
        assert permission.has_permission(type('Request', (), {'user': admin}), None) is True
        assert permission.has_permission(type('Request', (), {'user': staff}), None) is True
        assert permission.has_permission(type('Request', (), {'user': customer}), None) is False

    def test_owner_can_access_own_resource(self, auth_client):
        user = UserFactory()
        client = auth_client(user)
        url = reverse('me')
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_non_owner_cannot_access_resource(self, auth_client):
        user_a = UserFactory()
        user_b = UserFactory()
        # User A trying to access User B's address
        from common.tests.factories import AddressFactory
        address_b = AddressFactory(user=user_b)
        url = reverse('address-detail', kwargs={'pk': address_b.id})
        
        client = auth_client(user_a)
        response = client.get(url)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
