"""Unit tests for Cart services: add, update, remove, merge, coupon validation."""
from decimal import Decimal
import pytest

from apps.cart.models import Cart, CartItem, Coupon
from apps.cart.services import (
    CartService,
    CartCalculationService,
    CartMergeService,
    CouponValidationService,
)
from apps.catalog.models import ProductVariant
from common.tests.factories import (
    ProductVariantFactory,
    CartFactory,
    GuestCartFactory,
    CartItemFactory,
    CouponFactory,
    ExpiredCouponFactory,
    InactiveCouponFactory,
    PercentageCouponFactory,
)


# ---------------------------------------------------------------------------
# Cart Calculation Service
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartCalculationService:

    def test_calculate_subtotal_empty(self, cart):
        assert CartCalculationService.calculate_subtotal(cart.items) == Decimal('0.00')

    def test_calculate_subtotal_with_items(self, cart, product_variant):
        variant = product_variant
        CartItem.objects.create(cart=cart, product_variant=variant, quantity=2, unit_price=Decimal('15.00'))
        CartItem.objects.create(cart=cart, product_variant=ProductVariantFactory(), quantity=3, unit_price=Decimal('10.00'))

        subtotal = CartCalculationService.calculate_subtotal(cart.items.all())
        assert subtotal == Decimal('60.00')  # 2*15 + 3*10

    def test_calculate_discount_none(self):
        assert CartCalculationService.calculate_discount(Decimal('100.00'), None) == Decimal('0.00')

    def test_calculate_discount_fixed(self):
        coupon = CouponFactory(discount_type=Coupon.DiscountType.FIXED, discount_value=Decimal('20.00'))
        discount = CartCalculationService.calculate_discount(Decimal('100.00'), coupon)
        assert discount == Decimal('20.00')

    def test_calculate_discount_fixed_capped(self):
        coupon = CouponFactory(discount_type=Coupon.DiscountType.FIXED, discount_value=Decimal('150.00'))
        discount = CartCalculationService.calculate_discount(Decimal('100.00'), coupon)
        assert discount == Decimal('100.00')  # Capped at subtotal

    def test_calculate_discount_percentage(self):
        coupon = PercentageCouponFactory(discount_value=Decimal('10.00'))
        discount = CartCalculationService.calculate_discount(Decimal('200.00'), coupon)
        assert discount == Decimal('20.00')  # 10% of 200

    def test_calculate_total(self):
        total = CartCalculationService.calculate_total(
            Decimal('100.00'), Decimal('20.00')
        )
        assert total == Decimal('80.00')


# ---------------------------------------------------------------------------
# Cart Service – Add Item
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartAddItem:

    def test_add_valid_item(self, cart):
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)
        cart_item = CartService.add_item(cart, variant.id, quantity=2)
        assert cart_item.quantity == 2
        assert cart_item.product_variant == variant
        assert cart_item.unit_price == variant.effective_price
        assert cart.items.count() == 1

    def test_add_duplicate_item_merges_quantity(self, cart):
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        CartService.add_item(cart, variant.id, quantity=2)
        CartService.add_item(cart, variant.id, quantity=3)
        assert cart.items.count() == 1
        assert cart.items.first().quantity == 5

    def test_add_item_exceeding_stock_rejected(self, cart):
        variant = ProductVariantFactory(stock_quantity=3, is_active=True)
        with pytest.raises(ValueError, match='exceeds available stock'):
            CartService.add_item(cart, variant.id, quantity=10)

    def test_add_duplicate_exceeding_stock_rejected(self, cart):
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)
        CartService.add_item(cart, variant.id, quantity=3)
        with pytest.raises(ValueError, match='exceeds available stock'):
            CartService.add_item(cart, variant.id, quantity=3)  # 3+3=6 > 5

    def test_add_inactive_variant_rejected(self, cart):
        variant = ProductVariantFactory(stock_quantity=5, is_active=False)
        with pytest.raises(ValueError, match='no longer available'):
            CartService.add_item(cart, variant.id, quantity=1)

    def test_add_inactive_product_variant_rejected(self, cart):
        from common.tests.factories import ProductFactory
        product = ProductFactory(is_active=False)
        variant = ProductVariantFactory(product=product, stock_quantity=5, is_active=True)
        with pytest.raises(ValueError, match='no longer available'):
            CartService.add_item(cart, variant.id, quantity=1)


# ---------------------------------------------------------------------------
# Cart Service – Update Item
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartUpdateItem:

    def test_valid_quantity_update(self, cart, product_variant):
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=1)
        updated = CartService.update_item(item, 5)
        assert updated.quantity == 5

    def test_quantity_below_one_rejected(self, cart, product_variant):
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=1)
        with pytest.raises(ValueError, match='greater than zero'):
            CartService.update_item(item, 0)

    def test_quantity_above_stock_rejected(self, cart, product_variant):
        product_variant.stock_quantity = 3
        product_variant.save()
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=1)
        with pytest.raises(ValueError, match='exceeds available stock'):
            CartService.update_item(item, 10)


# ---------------------------------------------------------------------------
# Cart Service – Remove Item
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartRemoveItem:

    def test_remove_item_success(self, cart, product_variant):
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=1)
        CartService.remove_item(item)
        assert cart.items.count() == 0

    def test_remove_item_cart_remains(self, cart, product_variant):
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=1)
        item_id = item.id
        CartService.remove_item(item)
        assert Cart.objects.filter(pk=cart.id).exists()

    def test_remove_item_only_affects_target(self, cart):
        v1 = ProductVariantFactory(stock_quantity=10)
        v2 = ProductVariantFactory(stock_quantity=10)
        item1 = CartItemFactory(cart=cart, product_variant=v1, quantity=1)
        CartItemFactory(cart=cart, product_variant=v2, quantity=2)
        CartService.remove_item(item1)
        assert cart.items.count() == 1
        assert cart.items.first().product_variant == v2


# ---------------------------------------------------------------------------
# Cart Service – Clear Cart
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartClear:

    def test_clear_cart(self, cart):
        CartItemFactory(cart=cart, product_variant=ProductVariantFactory(stock_quantity=5))
        CartItemFactory(cart=cart, product_variant=ProductVariantFactory(stock_quantity=5))
        CartService.clear_cart(cart)
        assert cart.items.count() == 0


# ---------------------------------------------------------------------------
# Cart Merge Service
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCartMerge:

    def test_merge_guest_into_empty_user_cart(self, user):
        variant_a = ProductVariantFactory(stock_quantity=10, is_active=True)
        variant_b = ProductVariantFactory(stock_quantity=10, is_active=True)
        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant_a, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=variant_b, quantity=1)

        merged = CartMergeService.merge_guest_cart(user, guest_cart)
        assert merged.user == user
        assert merged.items.count() == 2
        # Check guest cart deleted
        assert not Cart.objects.filter(pk=guest_cart.id).exists()

    def test_merge_guest_into_existing_user_cart(self, user):
        variant_a = ProductVariantFactory(stock_quantity=10, is_active=True)
        variant_b = ProductVariantFactory(stock_quantity=10, is_active=True)
        variant_c = ProductVariantFactory(stock_quantity=10, is_active=True)

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=variant_a, quantity=1)
        CartItemFactory(cart=user_cart, product_variant=variant_c, quantity=3)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant_a, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=variant_b, quantity=1)

        merged = CartMergeService.merge_guest_cart(user, guest_cart)
        assert merged.items.count() == 3
        # Variant A: 1 + 2 = 3
        item_a = merged.items.get(product_variant=variant_a)
        assert item_a.quantity == 3
        # Variant B: 0 + 1 = 1
        item_b = merged.items.get(product_variant=variant_b)
        assert item_b.quantity == 1
        # Variant C: 3 + 0 = 3
        item_c = merged.items.get(product_variant=variant_c)
        assert item_c.quantity == 3

    def test_merge_respects_stock_limits(self, user):
        variant_a = ProductVariantFactory(stock_quantity=5, is_active=True)

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=variant_a, quantity=3)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant_a, quantity=4)

        merged = CartMergeService.merge_guest_cart(user, guest_cart)
        item_a = merged.items.get(product_variant=variant_a)
        # 3 + 4 = 7, capped at stock 5
        assert item_a.quantity == 5

    def test_merge_skips_inactive_variants(self, user):
        active_var = ProductVariantFactory(stock_quantity=10, is_active=True)
        inactive_var = ProductVariantFactory(stock_quantity=10, is_active=False)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=active_var, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=inactive_var, quantity=1)

        merged = CartMergeService.merge_guest_cart(user, guest_cart)
        assert merged.items.count() == 1
        assert merged.items.first().product_variant == active_var


# ---------------------------------------------------------------------------
# Coupon Validation Service
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCouponValidation:

    def test_valid_coupon_accepted(self):
        coupon = CouponFactory(code='VALID10', active=True)
        result = CouponValidationService.validate_coupon('VALID10', Decimal('100.00'))
        assert result['valid'] is True
        assert 'discount' in result

    def test_unknown_coupon_rejected(self):
        result = CouponValidationService.validate_coupon('NONEXIST')
        assert result['valid'] is False
        assert 'Invalid coupon' in result['message']

    def test_expired_coupon_rejected(self):
        coupon = ExpiredCouponFactory(code='EXPIRED')
        result = CouponValidationService.validate_coupon('EXPIRED')
        assert result['valid'] is False
        assert 'expired' in result['message'].lower()

    def test_inactive_coupon_rejected(self):
        coupon = InactiveCouponFactory(code='INACTIVE', active=False)
        result = CouponValidationService.validate_coupon('INACTIVE')
        assert result['valid'] is False
        assert 'active' in result['message'].lower()

    def test_min_cart_amount_not_met(self):
        coupon = CouponFactory(code='MIN100', min_cart_amount=Decimal('100.00'))
        result = CouponValidationService.validate_coupon('MIN100', Decimal('50.00'))
        assert result['valid'] is False
        assert 'minimum' in result['message'].lower()


# ---------------------------------------------------------------------------
# Guest Cart
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGuestCart:

    def test_guest_cart_created_with_token(self):
        cart = CartService._get_or_create_cart(guest_token='test-guest-token-123')
        assert cart.guest_token == 'test-guest-token-123'
        assert cart.user is None

    def test_guest_cart_auto_generates_token(self):
        cart = CartService._get_or_create_cart()
        assert cart.guest_token is not None
        assert cart.user is None

    def test_guest_cart_reused(self):
        cart1 = CartService._get_or_create_cart(guest_token='my-token')
        cart2 = CartService._get_or_create_cart(guest_token='my-token')
        assert cart1.id == cart2.id


# ---------------------------------------------------------------------------
# User Cart
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUserCart:

    def test_user_cart_created_once(self, user):
        cart1 = CartService._get_or_create_cart(user=user)
        cart2 = CartService._get_or_create_cart(user=user)
        assert cart1.id == cart2.id
        assert cart1.user == user
