from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from apps.users.services import create_audit_log, create_user_account
from apps.users.models import UserVerificationToken
import hashlib
import uuid
import secrets
from celery import shared_task

User = get_user_model()

def register_user(data):
    user = create_user_account(
        email=data['email'],
        password=data['password'],
        full_name=data['name'],
        phone=data['phone'],
        role='customer',
        is_active=True,
        is_verified=False
    )
    create_audit_log("USER_REGISTERED", user=user)
    return user

def authenticate_user(username, password):
    # Try email first
    user = User.objects.filter(email=username).first()
    if not user:
        # Try phone
        user = User.objects.filter(phone=username).first()
    
    if user and user.check_password(password):
        if not user.is_active:
            create_audit_log("LOGIN_FAILED", user=user, metadata={"reason": "inactive"})
            return None
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        create_audit_log("LOGIN_SUCCESS", user=user)
        return user
    
    create_audit_log("LOGIN_FAILED", metadata={"username": username, "reason": "invalid_credentials"})
    return None

def request_password_reset(username):
    user = User.objects.filter(email=username).first() or User.objects.filter(phone=username).first()
    if user:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(str(token).encode()).hexdigest()
        UserVerificationToken.objects.create(
            user=user,
            token_hash=token_hash,
            purpose='password_reset',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        # Send reset email/SMS asynchronously using Celery task placeholder
        send_reset_notification.delay(user.id, str(token))
        create_audit_log("PASSWORD_RESET_REQUESTED", user=user)
    return True # Always return True for security

def reset_password(token, password):
    token_hash = hashlib.sha256(str(token).encode()).hexdigest()
    verification = UserVerificationToken.objects.filter(
        token_hash=token_hash,
        purpose='password_reset',
        is_used=False,
        expires_at__gt=timezone.now()
    ).first()
    
    if not verification:
        return False
    
    user = verification.user
    user.set_password(password)
    user.save()
    
    verification.is_used = True
    verification.save()
    
    create_audit_log("PASSWORD_RESET_COMPLETED", user=user)
    return True

@shared_task
def send_reset_notification(user_id, token):
    """
    Celery task placeholder for sending password reset notification (Email/SMS).
    """
    # Placeholder for actual notification logic
    pass
