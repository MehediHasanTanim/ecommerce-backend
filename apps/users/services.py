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
    address_type = data.get('type', 'shipping')

    if data.get('is_default'):
        # Lock matching rows until transaction completes
        existing_addresses = (
            Address.objects
            .select_for_update()
            .filter(
                user=user,
                type=address_type,
                is_default=True
            )
        )

        # Remove previous default
        existing_addresses.update(is_default=False)

    # Create new address
    address = Address.objects.create(
        user=user,
        **data
    )

    # Audit log
    create_audit_log(
        "ADDRESS_CREATED",
        user=user,
        resource_type="Address",
        resource_id=str(address.id)
    )

    return address

@transaction.atomic
def set_default_address(user, address_id):
    # Lock the target address row
    address = (
        Address.objects
        .select_for_update()
        .get(id=address_id, user=user)
    )

    # Lock all addresses of same type for this user
    addresses = (
        Address.objects
        .select_for_update()
        .filter(
            user=user,
            type=address.type
        )
    )

    # Remove existing defaults
    addresses.update(is_default=False)

    # Set new default
    address.is_default = True
    address.save(update_fields=["is_default"])

    # Audit log
    create_audit_log(
        "DEFAULT_ADDRESS_CHANGED",
        user=user,
        resource_type="Address",
        resource_id=str(address.id)
    )

    return address
