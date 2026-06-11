"""API regression tests for Inventory – stock reservation & order item creation.

INV-REG-001: Stock reserved correctly after order placement
INV-REG-002: Order items created correctly with snapshot data
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.orders.models import Order
from common.tests.factories import (
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
# INV-REG-001: Stock Reserved Correctly
# =============================================================================

@pytest.mark.django_db
class TestStockReservationRegression:

    def test_reserved_stock_increments_after_order(self, api_client, user):
        """
        INV-REG-001: Variant stock=10, reserved=0. Order quantity=3.
        After order: reserved_stock == 3.
        """
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=3)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        variant.refresh_from_db()
        assert variant.reserved_stock == 3
        assert variant.available_stock == 7

    def test_reserved_stock_accumulates_across_orders(self, api_client, user):
        """Multiple orders accumulate reserved stock correctly."""
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=50, reserved_stock=0, is_active=True)

        # First order: reserve 5
        cart1 = CartFactory(user=user)
        CartItemFactory(cart=cart1, product_variant=variant, quantity=5)

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        r1 = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )
        assert r1.status_code == status.HTTP_201_CREATED

        variant.refresh_from_db()
        assert variant.reserved_stock == 5

        # Second order: reserve 3 more (need new cart since old was cleared)
        cart2 = CartFactory(user=user)
        CartItemFactory(cart=cart2, product_variant=variant, quantity=3)

        r2 = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )
        assert r2.status_code == status.HTTP_201_CREATED

        variant.refresh_from_db()
        assert variant.reserved_stock == 8

    def test_reserved_stock_does_not_exceed_total_stock(self, api_client, user):
        """Reservation is blocked before exceeding stock."""
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=8, is_active=True)

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=5)  # needs 5, but only 2 available

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        variant.refresh_from_db()
        assert variant.reserved_stock == 8  # unchanged


# =============================================================================
# INV-REG-002: Order Items Created Correctly
# =============================================================================

@pytest.mark.django_db
class TestOrderItemsRegression:

    def test_order_items_snapshot_preserved(self, api_client, user):
        """
        INV-REG-002: 2 products in cart → 2 order items.
        Each has product_name, sku, quantity, unit_price, line_total.
        """
        client = _auth(api_client, user)

        v1 = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        v1.price = Decimal('200.00')
        v1.save()

        v2 = ProductVariantFactory(stock_quantity=5, reserved_stock=0, is_active=True)
        v2.price = Decimal('50.00')
        v2.save()

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=v1, quantity=1, unit_price=Decimal('200.00'))
        CartItemFactory(cart=cart, product_variant=v2, quantity=3, unit_price=Decimal('50.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        response = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        order = Order.objects.get(id=response.json()['order_id'])

        assert order.items.count() == 2

        # Verify each item has snapshot data
        for item in order.items.all():
            assert item.product_name
            assert item.variant_name
            assert item.sku
            assert item.quantity > 0
            assert item.unit_price > 0
            assert item.line_total == item.unit_price * item.quantity

    def test_order_items_via_detail_api(self, api_client, user):
        """Order detail API returns items with correct snapshot data."""
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        variant.price = Decimal('75.00')
        variant.save()

        original_name = variant.product.name
        original_sku = variant.sku

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=2, unit_price=Decimal('75.00'))

        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        place_resp = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )
        assert place_resp.status_code == status.HTTP_201_CREATED
        order_id = place_resp.json()['order_id']

        # Change product name/sku after order (should NOT affect snapshot)
        variant.product.name = 'CHANGED NAME'
        variant.product.save()
        variant.sku = 'CHANGED-SKU'
        variant.save()

        # Get order detail
        detail_resp = client.get(reverse('order-detail', kwargs={'pk': order_id}))
        assert detail_resp.status_code == status.HTTP_200_OK
        detail = detail_resp.json()
        assert len(detail['items']) == 1
        item = detail['items'][0]

        # Snapshot preserved — not affected by product changes
        assert item['product_name'] == original_name
        assert item['sku'] == original_sku
        assert item['quantity'] == 2

    def test_order_detail_includes_all_fields(self, api_client, user):
        """Order detail response includes address snapshot, payment info, totals."""
        client = _auth(api_client, user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)

        cart = CartFactory(user=user)
        CartItemFactory(cart=cart, product_variant=variant, quantity=2)

        address = AddressFactory(
            user=user, name='Ship Home', city='Dhaka',
            country='Bangladesh', type='shipping',
        )

        place_resp = client.post(
            reverse('checkout-place-order'),
            {'address_id': str(address.id), 'payment_method': 'cod'},
            format='json',
        )
        assert place_resp.status_code == status.HTTP_201_CREATED
        order_id = place_resp.json()['order_id']

        detail_resp = client.get(reverse('order-detail', kwargs={'pk': order_id}))
        assert detail_resp.status_code == status.HTTP_200_OK
        data = detail_resp.json()

        # Verify all expected fields
        assert 'order_number' in data
        assert 'status' in data
        assert 'payment_status' in data
        assert 'payment_method' in data
        assert 'subtotal' in data
        assert 'discount' in data
        assert 'shipping_fee' in data
        assert 'tax' in data
        assert 'grand_total' in data
        assert 'address_snapshot' in data
        assert 'items' in data
        assert 'can_cancel' in data
        assert data['address_snapshot']['name'] == 'Ship Home'
