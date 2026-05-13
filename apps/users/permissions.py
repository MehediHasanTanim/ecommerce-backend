from rest_framework import permissions

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "customer"
        )   

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "admin"
        )

class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
               and getattr(request.user, "role", None) == "staff"
        )

class IsVendor(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) == "vendor"
        )

class IsAdminOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and getattr(request.user, "role", None) in ["admin", "staff"]
        )

class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "admin":
            return True
        if hasattr(obj, "user"):
            return obj.user == request.user

        # 4. Self Check (for singleton resources like /me)
        return obj == request.user
