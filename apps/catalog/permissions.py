from rest_framework import permissions
from apps.users.permissions import IsAdminOrStaff


class IsAdminOrStaffUser(IsAdminOrStaff):
    """
    Admin or Staff users can perform write operations on catalog resources.
    Delegates to the shared IsAdminOrStaff permission from apps.users.
    """
    pass


class ReadOnly(permissions.BasePermission):
    """
    Allows read-only access (GET, HEAD, OPTIONS) to any user including anonymous.
    """
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
