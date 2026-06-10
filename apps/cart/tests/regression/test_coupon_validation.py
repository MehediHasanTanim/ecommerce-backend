"""COUPON-REG-001 – Invalid Coupon Is Rejected

POST /api/v1/cart/coupons/validate/ → 400 Bad Request for invalid coupons
POST /api/v1/cart/coupons/apply/ → 400 Bad Request for invalid coupons
"""
import pytest
from django.urls import reverse
from rest_framework import status

from common.tests.factories import (
    CouponFactory,
    ExpiredCouponFactory,
    InactiveCouponFactory,
    FutureCouponFactory,
    ProductVariantFactory,
)


@pytest.mark.django_db
class TestInvalidCouponRejected:
    """COUPON-REG-001: Invalid coupon is rejected"""

    # ── Validate endpoint ────────────────────────────────────────────────────

    def test_validate_nonexistent_coupon_returns_400(self, api_client):
        """POST /api/v1/cart/coupons/validate/ with unknown code returns 400."""
        # Act
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': 'NONEXISTENT'},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400 for unknown coupon, got {response.status_code}"
        )
        data = response.json()
        assert data['valid'] is False, "valid should be False for unknown coupon"
        assert 'Invalid coupon' in data.get('message', ''), (
            f"Message should contain 'Invalid coupon', got: {data.get('message')}"
        )

    def test_validate_expired_coupon_returns_400(self, api_client):
        """Expired coupon returns 400 with valid=False."""
        # Arrange
        coupon = ExpiredCouponFactory(code='OLD')

        # Act
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': coupon.code},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['valid'] is False, "Expired coupon should be invalid"

    def test_validate_inactive_coupon_returns_400(self, api_client):
        """Deactivated coupon returns 400 with valid=False."""
        # Arrange
        coupon = InactiveCouponFactory(code='DEACTIVATED', active=False)

        # Act
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': coupon.code},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['valid'] is False, "Inactive coupon should be invalid"

    def test_validate_future_coupon_returns_400(self, api_client):
        """Coupon with future start_date returns 400."""
        # Arrange
        coupon = FutureCouponFactory(code='FUTURE')

        # Act
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': coupon.code},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['valid'] is False, "Future-started coupon should be invalid"

    # ── Apply endpoint ───────────────────────────────────────────────────────

    def test_apply_invalid_coupon_to_cart_returns_400(self, api_client):
        """POST /api/v1/cart/coupons/apply/ with invalid code returns 400."""
        # Arrange – create a cart first (coupon apply requires an existing cart)
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        guest_token = add_resp.json().get('guest_token', '')

        # Act – try to apply invalid coupon
        headers = {'X-Guest-Token': guest_token} if guest_token else {}
        response = api_client.post(
            reverse('coupon-apply'),
            {'code': 'BADCODE'},
            format='json',
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400 for invalid coupon apply, got {response.status_code}"
        )
        data = response.json()
        assert data['valid'] is False, "valid should be False"

    def test_apply_invalid_coupon_does_not_change_cart_total(self, api_client):
        """Cart subtotal and grand total remain unchanged after failed coupon apply."""
        # Arrange – cart with item
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )
        add_data = add_resp.json()
        guest_token = add_data.get('guest_token', '')
        original_subtotal = float(add_data['subtotal'])
        original_grand_total = float(add_data['grand_total'])

        # Act – try to apply bad coupon
        headers = {'X-Guest-Token': guest_token} if guest_token else {}
        api_client.post(
            reverse('coupon-apply'),
            {'code': 'BADCODE'},
            format='json',
            headers=headers,
        )

        # Assert – cart totals unchanged
        get_resp = api_client.get(reverse('cart-detail'), headers=headers)
        get_data = get_resp.json()
        assert float(get_data['subtotal']) == original_subtotal, (
            "Subtotal should not change after failed coupon apply"
        )
        assert float(get_data['grand_total']) == original_grand_total, (
            "Grand total should not change after failed coupon apply"
        )

    # ── Valid coupon for contrast ─────────────────────────────────────────────

    def test_valid_coupon_returns_200(self, api_client):
        """A valid coupon returns 200 OK from validate endpoint."""
        # Arrange
        coupon = CouponFactory(code='GOOD', active=True)

        # Act
        response = api_client.post(
            reverse('coupon-validate'),
            {'code': coupon.code},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK, (
            f"Expected 200 for valid coupon, got {response.status_code}"
        )
        data = response.json()
        assert data['valid'] is True, "Valid coupon should have valid=True"
