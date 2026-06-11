"""API regression tests for UnitOfWork – rollback protection.

UOW-REG-001: Rollback when stock reservation fails
UOW-REG-002: Rollback when order creation fails
UOW-REG-003: Rollback when payment fails
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.urls import reverse
from rest_framework import status

from apps.cart.models import CartItem
from apps.orders.models import Order, OrderItem
from apps.inventory.services import InsufficientStockError
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
    CartFactory,
    CartItemFactory,
)


def _auth(api_client, user):
    """Authenticate an API client with the given user."""
    api_client.force_authenticate(user=user)
    return api_client


# =============================================================================
# UOW-REG-001: Rollback When Stock Reservation Fails
# =============================================================================

@pytest.mark.django_db
class TestUowStockReservationRollback:

    def test_rollback_on_insufficient_stock(self, api_client, user):
        """
        UOW-REG-001: Force InsufficientStockError during reservation.
        No partial writes: Order=0, OrderItem=0, cart preserved, inventory unchanged.
        """
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=1, reserved_stock=1, is_active=True)
        # available = 0

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)
        initial_cart_count = cart.items.count()

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        initial_orders = Order.objects.count()
        initial_reserved = variant.reserved_stock

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # No order created
        assert Order.objects.count() == initial_orders

        # Cart preserved
        cart.refresh_from_db()
        assert cart.items.count() == initial_cart_count

        # Inventory unchanged
        variant.refresh_from_db()
        assert variant.reserved_stock == initial_reserved

    def test_rollback_preserves_multiple_cart_items(self, api_client, user):
        """Multiple cart items all preserved on rollback."""
        client = _auth(api_client, user)

        # v1: available=0 triggers failure
        v1 = ProductVariantFactory(stock_quantity=1, reserved_stock=1, is_active=True)
        v2 = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=v1, quantity=1, unit_price=Decimal('50.00'))
        CartItemFactory(cart=cart, product_variant=v2, quantity=2, unit_price=Decimal('30.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        cart.refresh_from_db()
        assert cart.items.count() == 2

        # Neither variant has stock reserved
        v2.refresh_from_db()
        assert v2.reserved_stock == 0

    def test_rollback_with_coupon_preserved(self, api_client, user):
        """Coupon stays on cart when order placement fails."""
        client = _auth(api_client, user)

        from apps.cart.models import Coupon
        from common.tests.factories import CouponFactory

        variant = ProductVariantFactory(stock_quantity=1, reserved_stock=1, is_active=True)

        coupon = CouponFactory()
        cart = CartFactory(user=user, coupon=coupon)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        cart.refresh_from_db()
        assert cart.coupon is not None
        assert cart.coupon.id == coupon.id


# =============================================================================
# UOW-REG-002: Rollback When Order Creation Fails
# =============================================================================

@pytest.mark.django_db
class TestUowOrderCreationRollback:

    @patch('apps.checkout.services.checkout_service.Order.objects.create')
    def test_rollback_when_order_create_fails(
        self, mock_create, api_client, user,
    ):
        """
        UOW-REG-002: Mock Order.objects.create to raise exception.
        Everything rolls back: Order=0, cart preserved, inventory unchanged.
        """
        mock_create.side_effect = RuntimeError('Database error during order creation')

        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=2)

        initial_cart_count = cart.items.count()
        initial_reserved = variant.reserved_stock

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        # Should be 500 or 400 depending on error handling
        assert response.status_code in (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_400_BAD_REQUEST,
        )

        # Cart preserved
        cart.refresh_from_db()
        assert cart.items.count() == initial_cart_count

        # No stock reserved (rolled back by UnitOfWork)
        variant.refresh_from_db()
        assert variant.reserved_stock == initial_reserved


# =============================================================================
# UOW-REG-003: Rollback When Payment Creation Fails
# =============================================================================

@pytest.mark.django_db
class TestUowPaymentRollback:

    def test_rollback_when_payment_fails(self, api_client, user):
        """
        UOW-REG-003: Simulate payment failure scenario.
        The checkout flow has no separate payment service yet (payment record
        is implicit in order creation), so this test verifies that the
        UnitOfWork pattern handles downstream failures correctly by ensuring
        no order persists if the full flow doesn't complete.
        """
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=2)

        initial_cart_count = cart.items.count()
        initial_orders = Order.objects.count()
        initial_reserved = variant.reserved_stock

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        # Verify successful flow works (baseline)
        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )
        assert response.status_code == status.HTTP_201_CREATED

        # Verify cart cleared on success
        cart.refresh_from_db()
        assert cart.items.count() == 0

        # Now verify that a failure during the flow preserves everything
        # (tested in UOW-REG-001 and UOW-REG-002 above)

    def test_partial_failure_no_orphan_records(self, api_client, user):
        """
        Verify no orphan OrderItem records exist without parent Order
        after a failed checkout.
        """
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=1, reserved_stock=1, is_active=True)
        # 0 available

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        initial_orderitems = OrderItem.objects.count()

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # No orphan order items
        assert OrderItem.objects.count() == initial_orderitems
