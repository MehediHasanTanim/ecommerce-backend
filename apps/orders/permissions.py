"""Permissions for Checkout & Orders module."""
from rest_framework import permissions


class IsOrderOwner(permissions.BasePermission):
    """Allow access only to the order owner."""

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
