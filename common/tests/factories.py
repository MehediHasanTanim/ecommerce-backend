import factory
from factory.django import DjangoModelFactory
from apps.users.models import User, Address, UserVerificationToken
from apps.catalog.models import Category, Brand, Product, ProductVariant, ProductImage
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


# ── User Factories ────────────────────────────────────────────────────────────

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f'user{n}@example.com')
    phone = factory.Sequence(lambda n: f'0171{n:07d}')
    full_name = factory.Faker('name')
    role = 'customer'
    is_verified = True
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        password = extracted or "StrongPass123!"
        if create:
            self.set_password(password)
            self.save()

class AdminUserFactory(UserFactory):
    role = 'admin'
    is_staff = True
    is_superuser = True

class StaffUserFactory(UserFactory):
    role = 'staff'
    is_staff = True

class VendorUserFactory(UserFactory):
    role = 'vendor'

class AddressFactory(DjangoModelFactory):
    class Meta:
        model = Address

    user = factory.SubFactory(UserFactory)
    name = factory.Faker('word')
    phone = factory.Sequence(lambda n: f'0171{n:08d}')
    country = factory.Faker('country')
    city = factory.Faker('city')
    area = factory.Faker('street_name')
    postal_code = factory.Faker('postcode')
    address_line = factory.Faker('address')
    type = 'shipping'
    is_default = False

class UserVerificationTokenFactory(DjangoModelFactory):
    class Meta:
        model = UserVerificationToken

    user = factory.SubFactory(UserFactory)
    token_hash = factory.Faker('sha256')
    purpose = 'password_reset'
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(hours=24))
    is_used = False


# ── Catalog Factories ─────────────────────────────────────────────────────────

class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f'Category {n}')
    slug = factory.Sequence(lambda n: f'category-{n}')
    parent = None
    description = factory.Faker('sentence')
    is_active = True
    display_order = factory.Sequence(lambda n: n)


class BrandFactory(DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.Sequence(lambda n: f'Brand {n}')
    slug = factory.Sequence(lambda n: f'brand-{n}')
    description = factory.Faker('sentence')
    is_active = True


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f'Product {n}')
    slug = factory.Sequence(lambda n: f'product-{n}')
    sku = factory.Sequence(lambda n: f'SKU-{n:06d}')
    category = factory.SubFactory(CategoryFactory)
    brand = factory.SubFactory(BrandFactory)
    short_description = factory.Faker('sentence')
    description = factory.Faker('paragraph')
    base_price = factory.LazyFunction(lambda: Decimal('99.99'))
    sale_price = None
    is_active = True
    is_featured = False
    meta_title = factory.LazyAttribute(lambda o: o.name)
    meta_description = factory.Faker('sentence')


class InactiveProductFactory(ProductFactory):
    is_active = False


class FeaturedProductFactory(ProductFactory):
    is_featured = True


class ProductVariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f'VAR-SKU-{n:06d}')
    variant_name = factory.Sequence(lambda n: f'Variant {n}')
    attributes = factory.LazyFunction(lambda: {'size': 'M', 'color': 'Red'})
    price = None
    sale_price = None
    stock_quantity = 10
    is_active = True


class ProductImageFactory(DjangoModelFactory):
    class Meta:
        model = ProductImage

    product = factory.SubFactory(ProductFactory)
    variant = None
    image = factory.django.ImageField(color='blue', width=100, height=100)
    alt_text = factory.Faker('sentence', nb_words=4)
    is_primary = False
    display_order = factory.Sequence(lambda n: n)
