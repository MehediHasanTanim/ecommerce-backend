import pytest
from apps.users.models import User

@pytest.mark.django_db
def test_create_user(create_user):
    user = create_user(email="newuser@example.com", phone="1234567890")
    assert user.email == "newuser@example.com"
    assert user.phone == "1234567890"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False
