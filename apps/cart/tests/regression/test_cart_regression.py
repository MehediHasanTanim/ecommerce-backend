"""API regression tests for Cart & Coupon endpoints.

CART-REG-001: Add item to cart succeeds
CART-REG-002: Add item above stock fails
CART-REG-003: Update cart quantity recalculates totals
CART-REG-004: Remove cart item succeeds
CART-REG-005: Guest cart persists by session
CART-REG-006: Guest cart merges after login
COUPON-REG-001: Invalid coupon is rejected
"""
import pytest
from django.urls import reverse
from rest_framework import status
from decimal import Decimal

from common.tests.factories import (
    ProductVariantFactory,
    CouponFactory,
    ExpiredCouponFactory,
    CartItemFactory,
    GuestCartFactory,
)


@pytest.mark.django_db
class TestCartAddItemRegression:
    """CART-REG-001 & CART-REG-002"""

    def test_add_item_succeeds(self, api_client):
        """CART-REG-001: Add item to cart succeeds → 201, cart updated."""
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert 'items' in data
        assert len(data['items']) == 1
        assert data['items'][0]['variant_id'] == variant.id
        assert data['items'][0]['quantity'] == 2

    def test_add_item_above_stock_fails(self, api_client):
        """CART-REG-002: Add item above stock → 400 error."""
        variant = ProductVariantFactory(stock_quantity=3, is_active=True)
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 100},
            format='json',
        )
        assert response.status_code == 400

    def test_add_inactive_variant_fails(self, api_client):
        """Adding inactive variant is rejected."""
        variant = ProductVariantFactory(stock_quantity=5, is_active=False)
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        assert response.status_code == 400

    def test_add_item_creates_guest_token(self, api_client):
        """Guest cart should return a guest_token in response."""
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        assert response.status_code in (200, 201)
        data = response.json()
        # Guest token should be present
        assert 'guest_token' in data


@pytest.mark.django_db
class TestCartUpdateRegression:
    """CART-REG-003"""

    def test_update_quantity_recalculates_totals(self, api_client):
        """CART-REG-003: Update cart quantity → totals recalculated."""
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        # First add an item
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        data = add_resp.json()
        item_id = data['items'][0]['id']
        guest_token = data.get('guest_token', '')

        # Update quantity
        headers = {}
        if guest_token:
            headers['X-Guest-Token'] = guest_token

        update_url = reverse('cart-update-item', kwargs={'item_id': item_id})
        response = api_client.put(
            update_url,
            {'quantity': 5},
            format='json',
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data['items'][0]['quantity'] == 5
        # Totals should be recalculated
        assert 'subtotal' in data
        assert 'grand_total' in data


@pytest.mark.django_db
class TestCartRemoveRegression:
    """CART-REG-004"""

    def test_remove_item_succeeds(self, api_client):
        """CART-REG-004: Remove cart item → item removed."""
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        data = add_resp.json()
        item_id = data['items'][0]['id']
        guest_token = data.get('guest_token', '')

        headers = {}
        if guest_token:
            headers['X-Guest-Token'] = guest_token

        delete_url = reverse('cart-remove-item', kwargs={'item_id': item_id})
        response = api_client.delete(delete_url, headers=headers)
        assert response.status_code == 200
        assert len(response.json()['items']) == 0


@pytest.mark.django_db
class TestGuestCartPersistence:
    """CART-REG-005"""

    def test_guest_cart_persists_by_session(self, api_client):
        """CART-REG-005: Guest cart persists across requests via X-Guest-Token."""
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        # First request – creates guest cart
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )
        data = add_resp.json()
        guest_token = data.get('guest_token')

        assert guest_token is not None, "Guest token should be returned"

        # Second request – use the token
        headers = {'X-Guest-Token': guest_token}
        get_resp = api_client.get(reverse('cart-detail'), headers=headers)
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert len(data['items']) == 1
        assert data['items'][0]['variant_id'] == variant.id
        assert data['items'][0]['quantity'] == 2


@pytest.mark.django_db
class TestGuestCartMergeRegression:
    """CART-REG-006"""

    def test_guest_cart_merges_after_login(self, authenticated_client, api_client, user):
        """CART-REG-006: Guest cart merges into user cart after login."""
        variant_a = ProductVariantFactory(stock_quantity=10, is_active=True)
        variant_b = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Create guest cart
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant_a.id, 'quantity': 2},
            format='json',
        )
        guest_data = add_resp.json()
        guest_token = guest_data.get('guest_token')

        # Simulate the merge by the authenticated client using its cart
        # We add via authenticated client which creates user cart
        auth_resp = authenticated_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant_b.id, 'quantity': 1},
            format='json',
        )
        assert auth_resp.status_code in (200, 201)

        # Now simulate the merge: add guest items to user's cart
        # In production this would happen via CartMergeService on login,
        # but for regression we test the user cart has the right items
        from apps.cart.services import CartMergeService
        from apps.cart.models import Cart

        guest_cart = Cart.objects.get(guest_token=guest_token)
        merged_cart = CartMergeService.merge_guest_cart(user, guest_cart)

        # Verify merged result
        get_resp = authenticated_client.get(reverse('cart-detail'))
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert len(data['items']) == 2

        # Guest cart should be gone
        assert not Cart.objects.filter(guest_token=guest_token).exists()


@pytest.mark.django_db
class TestCouponRegression:
    """COUPON-REG-001"""

    def test_valid_coupon_accepted(self, api_client):
        """Valid coupon returns valid=True."""
        coupon = CouponFactory(code='REGSAVE', active=True)
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': 'REGSAVE'},
            format='json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['valid'] is True

    def test_invalid_coupon_rejected(self, api_client):
        """COUPON-REG-001: Invalid coupon returns validation failure."""
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': 'INVALIDCODE'},
            format='json',
        )
        assert response.status_code == 400
        data = response.json()
        assert data['valid'] is False

    def test_expired_coupon_rejected(self, api_client):
        """Expired coupon is rejected."""
        coupon = ExpiredCouponFactory(code='OLDCODE')
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': 'OLDCODE'},
            format='json',
        )
        assert response.status_code == 400
        assert response.json()['valid'] is False
