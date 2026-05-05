import pytest
from django.db import transaction, models
from common.uow import UnitOfWork

# Creating a simple test model dynamically is tricky in Django tests without an app.
# Since we have apps like 'users', we can use User model or mock it.
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestUnitOfWork:
    def test_commit_success(self):
        """Create a test model instance inside UnitOfWork. Data persists after block exits."""
        with UnitOfWork():
            user = User.objects.create(email="commit@test.com")
            assert user.pk is not None
        
        assert User.objects.filter(email="commit@test.com").exists()

    def test_rollback_on_exception(self):
        """Raise exception inside block. Assert data does not persist."""
        with pytest.raises(ValueError, match="Force rollback"):
            with UnitOfWork():
                User.objects.create(email="rollback@test.com")
                raise ValueError("Force rollback")
        
        assert not User.objects.filter(email="rollback@test.com").exists()

    def test_nested_transaction(self):
        """UnitOfWork works inside existing transaction.atomic()"""
        with transaction.atomic():
            with UnitOfWork():
                User.objects.create(email="nested@test.com")
        
        assert User.objects.filter(email="nested@test.com").exists()
        
        # Test rollback in nested transaction
        with pytest.raises(ValueError):
            with transaction.atomic():
                with UnitOfWork():
                    User.objects.create(email="nested_rb@test.com")
                    raise ValueError("Force nested rollback")
        
        assert not User.objects.filter(email="nested_rb@test.com").exists()

    def test_database_alias(self):
        """UnitOfWork accepts using='default'"""
        with UnitOfWork(using="default"):
            user = User.objects.create(email="alias@test.com")
        
        assert User.objects.using("default").filter(email="alias@test.com").exists()
