import factory
from factory.django import DjangoModelFactory
from apps.users.models import User, Address, AuditLog, UserVerificationToken
from apps.catalog.models import Category, Brand, Product, ProductVariant, ProductImage
from apps.cart.models import Cart, CartItem, Coupon
from apps.wishlist.models import WishlistItem
from apps.orders.models import Order, OrderItem
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
    reserved_stock = 0
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


# ── Cart & Coupon Factories ───────────────────────────────────────────────────

class CouponFactory(DjangoModelFactory):
    class Meta:
        model = Coupon

    code = factory.Sequence(lambda n: f'COUPON{n:05d}')
    discount_type = Coupon.DiscountType.FIXED
    discount_value = Decimal('10.00')
    active = True
    start_date = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    end_date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    max_usage = 0
    usage_count = 0
    min_cart_amount = Decimal('0.00')


class ExpiredCouponFactory(CouponFactory):
    """Coupon whose end_date is in the past."""
    end_date = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))


class InactiveCouponFactory(CouponFactory):
    """Coupon with active=False."""
    active = False


class PercentageCouponFactory(CouponFactory):
    """Percentage-based coupon."""
    discount_type = Coupon.DiscountType.PERCENTAGE
    discount_value = Decimal('10.00')


class FutureCouponFactory(CouponFactory):
    """Coupon whose start_date is in the future (not yet valid)."""
    start_date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=5))


class CartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    user = factory.SubFactory(UserFactory)
    guest_token = None
    coupon = None


class GuestCartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    user = None
    guest_token = factory.Faker('uuid4')
    coupon = None


class CartItemFactory(DjangoModelFactory):
    class Meta:
        model = CartItem

    cart = factory.SubFactory(CartFactory)
    product_variant = factory.SubFactory(ProductVariantFactory)
    quantity = 1
    unit_price = factory.LazyAttribute(lambda o: o.product_variant.effective_price)


# ── Wishlist Factory ──────────────────────────────────────────────────────────

class WishlistItemFactory(DjangoModelFactory):
    class Meta:
        model = WishlistItem

    user = factory.SubFactory(UserFactory)
    product = factory.SubFactory(ProductFactory)


# ── Order Factories ──────────────────────────────────────────────────────────

class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    user = factory.SubFactory(UserFactory)
    order_number = factory.Sequence(lambda n: f'ORD-20260611-{n:06d}')
    address_snapshot = factory.LazyFunction(lambda: {
        'name': 'Test User',
        'phone': '01710000000',
        'city': 'Dhaka',
        'country': 'Bangladesh',
        'area': 'Gulshan',
        'postal_code': '1212',
        'address_line': '123 Test Street',
        'type': 'shipping',
    })
    status = Order.Status.PENDING
    payment_status = Order.PaymentStatus.PENDING
    payment_method = 'cod'
    subtotal = Decimal('200.00')
    discount = Decimal('0.00')
    shipping_fee = Decimal('60.00')
    tax = Decimal('0.00')
    grand_total = Decimal('260.00')


class OrderItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    variant = factory.SubFactory(ProductVariantFactory)
    sku = factory.Sequence(lambda n: f'ORD-SKU-{n:06d}')
    product_name = factory.LazyAttribute(lambda o: o.product.name)
    variant_name = factory.LazyAttribute(lambda o: o.variant.variant_name)
    unit_price = Decimal('100.00')
    quantity = 1


# ── Audit Log Factory ────────────────────────────────────────────────────────

class AuditLogFactory(DjangoModelFactory):
    class Meta:
        model = AuditLog

    user = factory.SubFactory(UserFactory)
    action = 'TEST_ACTION'
    resource_type = 'Test'
    resource_id = factory.Faker('uuid4')
    metadata = factory.LazyFunction(dict)
