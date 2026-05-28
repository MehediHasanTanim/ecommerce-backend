import pytest
import os
from rest_framework.test import APIClient
from apps.users.models import User
from common.tests.factories import (
    UserFactory, AdminUserFactory, StaffUserFactory, AddressFactory,
    CategoryFactory, BrandFactory, ProductFactory, InactiveProductFactory,
    FeaturedProductFactory, ProductVariantFactory, ProductImageFactory,
)

@pytest.fixture(autouse=True)
def set_test_settings(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user(db):
    return UserFactory()

@pytest.fixture
def admin_user(db):
    return AdminUserFactory()

@pytest.fixture
def staff_user(db):
    return StaffUserFactory()

@pytest.fixture
def create_user(db):
    def make_user(**kwargs):
        if 'password' not in kwargs:
            kwargs['password'] = 'testpass123'
        if 'email' not in kwargs:
            kwargs['email'] = 'testuser@example.com'
        return User.objects.create_user(**kwargs)
    return make_user

@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client

@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client

@pytest.fixture
def staff_client(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    return api_client

@pytest.fixture
def auth_client(api_client, db):
    def _auth_client(user):
        api_client.force_authenticate(user=user)
        return api_client
    return _auth_client

@pytest.fixture
def address(user):
    return AddressFactory(user=user)

@pytest.fixture
def other_user_address(db):
    return AddressFactory()

# ── Catalog fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def category(db):
    return CategoryFactory()

@pytest.fixture
def inactive_category(db):
    return CategoryFactory(is_active=False)

@pytest.fixture
def brand(db):
    return BrandFactory()

@pytest.fixture
def inactive_brand(db):
    return BrandFactory(is_active=False)

@pytest.fixture
def product(db, category, brand):
    return ProductFactory(category=category, brand=brand)

@pytest.fixture
def inactive_product(db, category, brand):
    return InactiveProductFactory(category=category, brand=brand)

@pytest.fixture
def featured_product(db, category, brand):
    return FeaturedProductFactory(category=category, brand=brand)

@pytest.fixture
def product_variant(db, product):
    return ProductVariantFactory(product=product)

@pytest.fixture
def product_image(db, product):
    return ProductImageFactory(product=product, is_primary=True)
