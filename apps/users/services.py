from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Address, AuditLog, UserVerificationToken
import uuid

User = get_user_model()

def create_audit_log(action: str, user=None, resource_type=None, resource_id=None, metadata=None):
    return AuditLog.objects.create(
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata or {}
    )

def create_user_account(email: str, password: str, **extra_fields) -> User:
    """Service to create a standard user account."""
    user = User.objects.create_user(email=email, password=password, **extra_fields)
    return user

def update_profile(user, data):
    for attr, value in data.items():
        setattr(user, attr, value)
    user.save()
    create_audit_log("PROFILE_UPDATED", user=user)
    return user

def change_password(user, old_password, new_password):
    if not user.check_password(old_password):
        return False
    user.set_password(new_password)
    user.save()
    create_audit_log("PASSWORD_CHANGED", user=user)
    return True

@transaction.atomic
def create_address(user, data):
    if data.get('is_default'):
        Address.objects.filter(user=user, type=data.get('type', 'shipping')).update(is_default=False)
    address = Address.objects.create(user=user, **data)
    create_audit_log("ADDRESS_CREATED", user=user, resource_type="Address", resource_id=str(address.id))
    return address

@transaction.atomic
def set_default_address(user, address_id):
    address = Address.objects.get(id=address_id, user=user)
    Address.objects.filter(user=user, type=address.type).update(is_default=False)
    address.is_default = True
    address.save()
    create_audit_log("DEFAULT_ADDRESS_CHANGED", user=user, resource_type="Address", resource_id=str(address.id))
    return address
