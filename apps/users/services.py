from django.contrib.auth import get_user_model

User = get_user_model()

def create_user_account(email: str, password: str, **extra_fields) -> User:
    """Service to create a standard user account."""
    user = User.objects.create_user(email=email, password=password, **extra_fields)
    return user
