import pytest
from apps.users.permissions import IsCustomer, IsAdmin, IsOwnerOrAdmin
from unittest.mock import Mock

@pytest.mark.django_db
class TestPermissions:
    def test_is_customer_permission(self, user, admin_user):
        permission = IsCustomer()
        request = Mock()
        
        request.user = user
        assert permission.has_permission(request, None) is True
        
        request.user = admin_user
        assert permission.has_permission(request, None) is False

    def test_is_admin_permission(self, admin_user, user):
        permission = IsAdmin()
        request = Mock()
        
        request.user = admin_user
        assert permission.has_permission(request, None) is True
        
        request.user = user
        assert permission.has_permission(request, None) is False

    def test_is_owner_or_admin_permission(self, user, admin_user, address):
        permission = IsOwnerOrAdmin()
        request = Mock()
        
        # Admin can access
        request.user = admin_user
        assert permission.has_object_permission(request, None, address) is True
        
        # Owner can access
        request.user = user
        assert permission.has_object_permission(request, None, address) is True
        
        # Other user cannot access
        other_user = Mock()
        other_user.is_authenticated = True
        other_user.role = 'customer'
        request.user = other_user
        assert permission.has_object_permission(request, None, address) is False
