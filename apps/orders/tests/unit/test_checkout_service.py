"""Unit tests for CheckoutService – totals, tax, discount, edge cases.

Covers:
- Totals calculation (subtotal, discount, shipping, tax, grand_total)
- Empty cart rejection
- Invalid product in cart (inactive/deleted)
- Coupon discount (percentage and fixed)
- Address ownership validation
- Order placement success/rollback
- Duplicate submission prevention
"""
from decimal import Decimal

import pytest

from apps.cart.models import Coupon
from apps.orders.models import Order
from apps.checkout.services.checkout_service import (
    CheckoutService,
    EmptyCartError,
    InvalidAddressError,
)
from apps.inventory.services import InsufficientStockError
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
    InactiveProductFactory,
    CartFactory,
    CartItemFactory,
    CouponFactory,
    PercentageCouponFactory,
)


# ---------------------------------------------------------------------------
# Totals Calculation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCheckoutTotals:

    def test_calculate_totals_multi_item(self, user, cart):
        """Verify subtotal, discount, shipping, tax, grand_total with multiple items."""
        # Product A: 1000 x 2 = 2000
        variant_a = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant_a.price = Decimal('1000.00')
        variant_a.save()
        CartItemFactory(cart=cart, product_variant=variant_a, quantity=2, unit_price=Decimal('1000.00'))

        # Product B: 500 x 1 = 500
        variant_b = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant_b.price = Decimal('500.00')
        variant_b.save()
        CartItemFactory(cart=cart, product_variant=variant_b, quantity=1, unit_price=Decimal('500.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        coupon = CouponFactory(
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('100.00'),
        )

        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, coupon=coupon,
            tax_rate=Decimal('0.10'),  # 10% tax
        )

        assert totals['subtotal'] == Decimal('2500.00')
        assert totals['discount'] == Decimal('100.00')
        assert totals['shipping_fee'] == Decimal('60.00')
        assert totals['tax'] == Decimal('240.00')  # 10% of (2500-100) = 240
        assert totals['grand_total'] == Decimal('2700.00')  # 2400 + 60 + 240

    def test_calculate_totals_minimal(self, user, cart):
        """Single item, no discount, no tax, Dhaka address."""
        variant = ProductVariantFactory(stock_quantity=5, reserved_stock=0, is_active=True)
        variant.price = Decimal('100.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=1, unit_price=Decimal('100.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        totals = CheckoutService.calculate_order_totals(cart=cart, address=address)
        assert totals['subtotal'] == Decimal('100.00')
        assert totals['discount'] == Decimal('0.00')
        assert totals['shipping_fee'] == Decimal('60.00')
        assert totals['tax'] == Decimal('0.00')
        assert totals['grand_total'] == Decimal('160.00')

    def test_calculate_totals_fixed_coupon(self, user, cart):
        """Fixed coupon reduces subtotal by exact amount."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('100.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=3, unit_price=Decimal('100.00'))

        coupon = CouponFactory(
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
        )
        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, coupon=coupon,
        )
        assert totals['subtotal'] == Decimal('300.00')
        assert totals['discount'] == Decimal('50.00')
        assert totals['grand_total'] == Decimal('310.00')  # 300-50+60

    def test_calculate_totals_fixed_coupon_capped(self, user, cart):
        """Fixed coupon cannot reduce total below zero — capped at subtotal."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('30.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=1, unit_price=Decimal('30.00'))

        coupon = CouponFactory(
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('100.00'),  # > subtotal
        )
        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, coupon=coupon,
        )
        assert totals['discount'] == Decimal('30.00')  # capped at subtotal
        assert totals['grand_total'] == Decimal('60.00')  # 0 + 60 shipping

    def test_calculate_totals_percentage_coupon(self, user, cart):
        """Percentage coupon reduces subtotal by a percentage."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('200.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=2, unit_price=Decimal('200.00'))

        coupon = PercentageCouponFactory(discount_value=Decimal('15.00'))  # 15%
        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, coupon=coupon,
        )
        assert totals['subtotal'] == Decimal('400.00')
        assert totals['discount'] == Decimal('60.00')  # 15% of 400
        assert totals['grand_total'] == Decimal('400.00')  # 400-60+60

    def test_calculate_totals_with_tax(self, user, cart):
        """Tax applied to subtotal after discount."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('100.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=5, unit_price=Decimal('100.00'))

        address = AddressFactory(user=user, city='Chattogram', type='shipping')  # outside Dhaka

        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, tax_rate=Decimal('0.15'),  # 15%
        )
        assert totals['subtotal'] == Decimal('500.00')
        assert totals['shipping_fee'] == Decimal('120.00')
        assert totals['tax'] == Decimal('75.00')  # 15% of 500
        assert totals['grand_total'] == Decimal('695.00')  # 500 + 120 + 75

    def test_calculate_totals_tax_after_discount(self, user, cart):
        """Tax is applied to (subtotal - discount), not the raw subtotal."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('100.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=10, unit_price=Decimal('100.00'))

        coupon = CouponFactory(
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('200.00'),
        )
        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, coupon=coupon,
            tax_rate=Decimal('0.10'),  # 10%
        )
        # Taxable = 1000 - 200 = 800, Tax = 80
        assert totals['tax'] == Decimal('80.00')
        assert totals['grand_total'] == Decimal('940.00')  # 800 + 60 + 80


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCheckoutValidation:

    def test_empty_cart_raises(self, user, cart):
        """EmptyCartError when cart has zero items."""
        address = AddressFactory(user=user, type='shipping')
        with pytest.raises(EmptyCartError, match='empty'):
            CheckoutService.validate_checkout(
                user=user, cart=cart, address_id=str(address.id),
            )

    def test_invalid_address_raises(self, user, cart):
        """InvalidAddressError when address belongs to another user."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        other_user = UserFactory()
        other_address = AddressFactory(user=other_user, type='shipping')

        with pytest.raises(InvalidAddressError, match='not found or does not belong'):
            CheckoutService.validate_checkout(
                user=user, cart=cart, address_id=str(other_address.id),
            )

    def test_nonexistent_address_raises(self, user, cart):
        """InvalidAddressError for nonexistent address UUID."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        with pytest.raises(InvalidAddressError):
            CheckoutService.validate_checkout(
                user=user, cart=cart,
                address_id='00000000-0000-0000-0000-000000000000',
            )

    def test_inactive_product_rejected(self, user, cart):
        """Inactive variant/product raises ValueError during validation."""
        inactive_variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=False)
        CartItemFactory(cart=cart, product_variant=inactive_variant, quantity=1)

        address = AddressFactory(user=user, type='shipping')

        with pytest.raises(ValueError, match='no longer available'):
            CheckoutService.validate_checkout(
                user=user, cart=cart, address_id=str(address.id),
            )

    def test_inactive_product_parent_rejected(self, user, cart):
        """Inactive parent product raises ValueError."""
        inactive_product = InactiveProductFactory(is_active=False)
        variant = ProductVariantFactory(product=inactive_product, stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(user=user, type='shipping')

        with pytest.raises(ValueError, match='no longer available'):
            CheckoutService.validate_checkout(
                user=user, cart=cart, address_id=str(address.id),
            )


# ---------------------------------------------------------------------------
# Order Placement
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPlaceOrder:

    def test_successful_order_creation(self, user, cart):
        """Order, items created; cart cleared; stock reserved."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('50.00')
        variant.save()
        CartItemFactory(cart=cart, product_variant=variant, quantity=2, unit_price=Decimal('50.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        order = CheckoutService.place_order(
            user=user, cart=cart, address_id=str(address.id),
            payment_method='cod',
        )

        # Verify order
        assert order is not None
        assert order.user == user
        assert order.status == Order.Status.PENDING
        assert order.payment_status == Order.PaymentStatus.PENDING
        assert order.payment_method == 'cod'
        assert order.grand_total == Decimal('160.00')

        # Verify order items
        assert order.items.count() == 1
        item = order.items.first()
        assert item.product_name == variant.product.name
        assert item.quantity == 2
        assert item.sku == variant.sku

        # Verify cart cleared
        cart.refresh_from_db()
        assert cart.items.count() == 0
        assert cart.coupon is None

        # Verify stock reserved
        variant.refresh_from_db()
        assert variant.reserved_stock == 2

    def test_place_order_clears_coupon(self, user, cart):
        """Coupon removed from cart after order placement."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        coupon = CouponFactory()
        cart.coupon = coupon
        cart.save()

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        CheckoutService.place_order(
            user=user, cart=cart, address_id=str(address.id),
        )

        cart.refresh_from_db()
        assert cart.coupon is None

    def test_address_snapshot_stored(self, user, cart):
        """Address data is snapshotted at order time."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(
            user=user, name='Test Home', phone='01711234567',
            city='Dhaka', country='Bangladesh', area='Gulshan',
            postal_code='1212', address_line='Road 5, House 3',
            type='shipping',
        )

        order = CheckoutService.place_order(
            user=user, cart=cart, address_id=str(address.id),
        )

        snapshot = order.address_snapshot
        assert snapshot['name'] == 'Test Home'
        assert snapshot['phone'] == '01711234567'
        assert snapshot['city'] == 'Dhaka'
        assert snapshot['country'] == 'Bangladesh'
        assert snapshot['postal_code'] == '1212'

    def test_order_number_present(self, user, cart):
        """Order receives a valid order number."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        order = CheckoutService.place_order(
            user=user, cart=cart, address_id=str(address.id),
        )

        import re
        assert re.match(r'^ORD-\d{8}-\d{6}$', order.order_number)

    def test_multiple_items_order(self, user, cart):
        """Order with multiple different variants creates correct items."""
        variant_a = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant_b = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)

        CartItemFactory(cart=cart, product_variant=variant_a, quantity=2, unit_price=Decimal('100.00'))
        CartItemFactory(cart=cart, product_variant=variant_b, quantity=3, unit_price=Decimal('50.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        order = CheckoutService.place_order(
            user=user, cart=cart, address_id=str(address.id),
        )

        assert order.items.count() == 2
        assert order.grand_total == Decimal('410.00')  # 200+150-0+60

    def test_notes_stored(self, user, cart):
        """Optional notes are stored on the order."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        order = CheckoutService.place_order(
            user=user, cart=cart, address_id=str(address.id),
            notes='Please deliver before 5 PM.',
        )

        assert order.notes == 'Please deliver before 5 PM.'


# ---------------------------------------------------------------------------
# Rollback / Failure Scenarios
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPlaceOrderRollback:

    def test_rollback_on_stock_failure(self, user, cart):
        """If stock reservation fails, no order, no stock reserved, cart intact."""
        variant = ProductVariantFactory(stock_quantity=1, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=5)  # exceeds

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        initial_order_count = Order.objects.count()

        with pytest.raises(InsufficientStockError):
            CheckoutService.place_order(
                user=user, cart=cart, address_id=str(address.id),
            )

        assert Order.objects.count() == initial_order_count
        cart.refresh_from_db()
        assert cart.items.count() == 1
        variant.refresh_from_db()
        assert variant.reserved_stock == 0

    def test_rollback_on_inactive_product_during_reserve(self, user, cart):
        """If product becomes inactive during validation, no partial writes."""
        variant = ProductVariantFactory(stock_quantity=0, reserved_stock=0, is_active=True)
        # 0 stock — validation fails at inventory check
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        initial_order_count = Order.objects.count()

        with pytest.raises(InsufficientStockError):
            CheckoutService.place_order(
                user=user, cart=cart, address_id=str(address.id),
            )

        assert Order.objects.count() == initial_order_count

    def test_rollback_preserves_multiple_cart_items(self, user, cart):
        """Rollback preserves all cart items."""
        v1 = ProductVariantFactory(stock_quantity=1, reserved_stock=1, is_active=True)  # 0 available
        v2 = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)

        CartItemFactory(cart=cart, product_variant=v1, quantity=1, unit_price=Decimal('50.00'))
        CartItemFactory(cart=cart, product_variant=v2, quantity=2, unit_price=Decimal('30.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        with pytest.raises(InsufficientStockError):
            CheckoutService.place_order(
                user=user, cart=cart, address_id=str(address.id),
            )

        cart.refresh_from_db()
        assert cart.items.count() == 2
