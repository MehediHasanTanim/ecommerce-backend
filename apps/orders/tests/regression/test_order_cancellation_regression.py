"""API regression tests for Order Cancellation – policy enforcement & stock restore.

ORD-REG-002: Cancel eligible order works (PENDING/CONFIRMED → CANCELLED, stock restored)
ORD-REG-003: Cancel shipped order blocked
ORD-REG-004: Cancel delivered order blocked
Security: User cannot cancel another user's order
Security: Unauthenticated user cannot cancel
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.orders.models import Order, OrderItem
from apps.users.models import AuditLog
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
)


def _auth(api_client, user):
    """Authenticate an API client with the given user."""
    api_client.force_authenticate(user=user)
    return api_client


def _create_order(user, status=Order.Status.PENDING, reserved_stock=5):
    """Helper: create an Order with 1 OrderItem. Sets variant.reserved_stock."""
    variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
    variant.reserved_stock = reserved_stock
    variant.save()

    address = AddressFactory(user=user, city='Dhaka', type='shipping')

    order = Order.objects.create(
        order_number=f'ORD-20260611-{Order.objects.count() + 2000:06d}',
        user=user,
        address_snapshot={
            'id': str(address.id), 'name': address.name,
            'phone': address.phone, 'city': address.city,
            'country': address.country, 'area': address.area or '',
            'postal_code': address.postal_code,
            'address_line': address.address_line,
            'type': address.type,
        },
        status=status,
        payment_status=Order.PaymentStatus.PENDING,
        payment_method='cod',
        subtotal=Decimal('200.00'), discount=Decimal('0.00'),
        shipping_fee=Decimal('60.00'), tax=Decimal('0.00'),
        grand_total=Decimal('260.00'),
    )

    OrderItem.objects.create(
        order=order, product=variant.product, variant=variant,
        sku=variant.sku, product_name=variant.product.name,
        variant_name=variant.variant_name,
        unit_price=Decimal('100.00'), quantity=2,
    )

    return order, variant


# =============================================================================
# ORD-REG-002: Cancel Eligible Order Works
# =============================================================================

@pytest.mark.django_db
class TestCancelEligibleOrderRegression:

    def test_cancel_pending_order(self, api_client, user):
        """
        ORD-REG-002: Order status=PENDING → cancel succeeds.
        Stock restored. Audit log created.
        """
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.PENDING, reserved_stock=5)

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'cancelled'

        # Stock restored
        variant.refresh_from_db()
        assert variant.reserved_stock == 3  # was 5, released 2

        # Audit log created
        assert AuditLog.objects.filter(
            action='ORDER_CANCELLED',
            resource_id=str(order.id),
        ).exists()

    def test_cancel_confirmed_order(self, api_client, user):
        """Order status=CONFIRMED → cancel succeeds, stock restored."""
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.CONFIRMED, reserved_stock=10)

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'cancelled'

        variant.refresh_from_db()
        assert variant.reserved_stock == 8  # was 10, released 2

    def test_cancel_full_stock_restore(self, api_client, user):
        """When reserved_stock equals order quantity, cancel restores to 0."""
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.PENDING, reserved_stock=2)

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_200_OK
        variant.refresh_from_db()
        assert variant.reserved_stock == 0

    def test_cancel_available_stock_increases(self, api_client, user):
        """After cancel, available_stock = stock - new_reserved_stock."""
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.PENDING, reserved_stock=5)

        assert variant.available_stock == 15  # 20 - 5

        client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        variant.refresh_from_db()
        assert variant.available_stock == 17  # 20 - 3


# =============================================================================
# ORD-REG-003: Cancel Shipped Order Blocked
# =============================================================================

@pytest.mark.django_db
class TestCancelShippedOrderBlockedRegression:

    def test_cancel_shipped_order_blocked(self, api_client, user):
        """
        ORD-REG-003: Order status=SHIPPED → 400 BAD REQUEST.
        Status unchanged. Inventory unchanged.
        """
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.SHIPPED, reserved_stock=5)

        initial_reserved = variant.reserved_stock

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Status unchanged
        order.refresh_from_db()
        assert order.status == Order.Status.SHIPPED

        # Inventory unchanged
        variant.refresh_from_db()
        assert variant.reserved_stock == initial_reserved


# =============================================================================
# ORD-REG-004: Cancel Delivered Order Blocked
# =============================================================================

@pytest.mark.django_db
class TestCancelDeliveredOrderBlockedRegression:

    def test_cancel_delivered_order_blocked(self, api_client, user):
        """
        ORD-REG-004: Order status=DELIVERED → 400 BAD REQUEST.
        Status unchanged. Inventory unchanged.
        """
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.DELIVERED, reserved_stock=2)

        initial_reserved = variant.reserved_stock

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

        order.refresh_from_db()
        assert order.status == Order.Status.DELIVERED

        variant.refresh_from_db()
        assert variant.reserved_stock == initial_reserved

    def test_cancel_processing_order_blocked(self, api_client, user):
        """PROCESSING order cannot be cancelled."""
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.PROCESSING, reserved_stock=5)

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        order.refresh_from_db()
        assert order.status == Order.Status.PROCESSING

    def test_cancel_already_cancelled_blocked(self, api_client, user):
        """Already CANCELLED order cannot be cancelled again."""
        client = _auth(api_client, user)
        order, variant = _create_order(user, status=Order.Status.CANCELLED, reserved_stock=0)

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Security: Ownership & Authentication
# =============================================================================

@pytest.mark.django_db
class TestCancelSecurityRegression:

    def test_user_cannot_cancel_other_user_order(self, api_client, user):
        """User A cannot cancel User B's order → 404 NOT FOUND."""
        order, variant = _create_order(user, status=Order.Status.PENDING, reserved_stock=5)

        other_user = UserFactory()
        client = _auth(api_client, other_user)

        response = client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Order unchanged
        order.refresh_from_db()
        assert order.status == Order.Status.PENDING

    def test_unauthenticated_cannot_cancel(self, api_client, user):
        """Unauthenticated user → 401."""
        order, variant = _create_order(user, status=Order.Status.PENDING, reserved_stock=5)

        response = api_client.post(reverse('order-cancel', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_access_invoice(self, api_client, user):
        """Unauthenticated user → 401 on invoice endpoint."""
        order, variant = _create_order(user, status=Order.Status.PENDING, reserved_stock=5)

        response = api_client.get(reverse('order-invoice', kwargs={'pk': str(order.id)}))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
