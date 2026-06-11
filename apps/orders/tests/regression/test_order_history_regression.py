"""API regression tests for Order History – user isolation, filtering, pagination.

ORD-REG-001: Order history returns only current user's orders
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.orders.models import Order, OrderItem
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
)


def _auth(api_client, user):
    """Authenticate an API client with the given user."""
    api_client.force_authenticate(user=user)
    return api_client


def _create_order(user, order_number, status=Order.Status.PENDING, city='Dhaka'):
    """Helper: create an Order with 1 OrderItem for a user."""
    variant = ProductVariantFactory(stock_quantity=10, reserved_stock=1, is_active=True)
    address = AddressFactory(user=user, city=city, type='shipping')

    order = Order.objects.create(
        order_number=order_number,
        user=user,
        address_snapshot={'id': str(address.id), 'city': city, 'name': address.name,
                          'country': address.country, 'address_line': address.address_line,
                          'type': address.type},
        status=status,
        payment_status=Order.PaymentStatus.PENDING if status in ('pending', 'confirmed')
                        else Order.PaymentStatus.PAID,
        payment_method='cod',
        subtotal=Decimal('100.00'), discount=Decimal('0.00'),
        shipping_fee=Decimal('60.00'), tax=Decimal('0.00'),
        grand_total=Decimal('160.00'),
    )

    OrderItem.objects.create(
        order=order, product=variant.product, variant=variant,
        sku=variant.sku, product_name=variant.product.name,
        variant_name=variant.variant_name,
        unit_price=Decimal('50.00'), quantity=2,
    )

    return order


# =============================================================================
# ORD-REG-001: Order History Returns Only Current User's Orders
# =============================================================================

@pytest.mark.django_db
class TestOrderHistoryRegression:

    def test_user_sees_only_own_orders(self, api_client, user):
        """
        ORD-REG-001: User A has 3 orders, User B has 2 orders.
        Authenticated as User A → sees exactly 3 orders, none from User B.
        """
        client = _auth(api_client, user)

        # User A: 3 orders
        _create_order(user, 'ORD-20260611-000001')
        _create_order(user, 'ORD-20260611-000002')
        _create_order(user, 'ORD-20260611-000003')

        # User B: 2 orders
        other_user = UserFactory()
        _create_order(other_user, 'ORD-20260611-000004')
        _create_order(other_user, 'ORD-20260611-000005')

        response = client.get(reverse('order-list'))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 3
        assert len(data['results']) == 3

        # Verify all returned orders belong to user
        for order_data in data['results']:
            order = Order.objects.get(id=order_data['id'])
            assert order.user == user

    def test_status_filter_works(self, api_client, user):
        """Filter by status returns only matching orders."""
        client = _auth(api_client, user)

        _create_order(user, 'ORD-20260611-001001', status=Order.Status.PENDING)
        _create_order(user, 'ORD-20260611-001002', status=Order.Status.PENDING)
        _create_order(user, 'ORD-20260611-001003', status=Order.Status.DELIVERED)

        # Filter by pending
        response = client.get(reverse('order-list') + '?status=pending')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 2

        # Filter by delivered
        response = client.get(reverse('order-list') + '?status=delivered')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 1

    def test_empty_history(self, api_client, user):
        """User with no orders gets empty list."""
        client = _auth(api_client, user)

        response = client.get(reverse('order-list'))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 0
        assert len(data['results']) == 0

    def test_order_list_pagination(self, api_client, user):
        """Pagination works for order list."""
        client = _auth(api_client, user)

        # Create 5 orders
        for i in range(5):
            _create_order(user, f'ORD-20260611-{100 + i:06d}')

        response = client.get(reverse('order-list') + '?page_size=2&page=1')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['count'] == 5
        assert len(data['results']) == 2
        assert data['page'] == 1

        response = client.get(reverse('order-list') + '?page_size=2&page=3')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['results']) == 1

    def test_order_list_requires_authentication(self, api_client):
        """Unauthenticated user → 401."""
        response = api_client.get(reverse('order-list'))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_order_detail_requires_authentication(self, api_client, user):
        """Order detail blocked for unauthenticated user."""
        order = _create_order(user, 'ORD-20260611-000099')
        response = api_client.get(reverse('order-detail', kwargs={'pk': str(order.id)}))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_order_detail_not_visible_to_other_user(self, api_client, user):
        """User B cannot see User A's order detail."""
        order = _create_order(user, 'ORD-20260611-000100')

        other_user = UserFactory()
        client = _auth(api_client, other_user)

        response = client.get(reverse('order-detail', kwargs={'pk': str(order.id)}))
        assert response.status_code == status.HTTP_404_NOT_FOUND
