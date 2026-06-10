"""Module 6: Invalid Coupon Rejected – Unit Tests

Covers CouponValidationService.validate_coupon() with AAA pattern.
"""
from decimal import Decimal
import pytest

from apps.cart.services import CouponValidationService
from common.tests.factories import (
    CouponFactory,
    ExpiredCouponFactory,
    InactiveCouponFactory,
    FutureCouponFactory,
)


@pytest.mark.django_db
class TestUnknownCoupon:
    """Test Case 1: Unknown Coupon"""

    def test_unknown_coupon_returns_invalid(self):
        """A non-existent coupon code returns valid=False."""
        # Act
        result = CouponValidationService.validate_coupon('NONEXISTENT')

        # Assert
        assert result['valid'] is False, "Unknown coupon should be invalid"
        assert 'message' in result, "Response should contain an error message"


@pytest.mark.django_db
class TestExpiredCoupon:
    """Test Case 2: Expired Coupon"""

    def test_expired_coupon_returns_invalid(self):
        """An expired coupon returns valid=False."""
        # Arrange
        coupon = ExpiredCouponFactory(code='EXPIRED1')

        # Act
        result = CouponValidationService.validate_coupon(coupon.code)

        # Assert
        assert result['valid'] is False, "Expired coupon should be invalid"
        assert 'expired' in result['message'].lower(), "Message should indicate expiry"


@pytest.mark.django_db
class TestInactiveCoupon:
    """Test Case 3: Inactive Coupon"""

    def test_inactive_coupon_returns_invalid(self):
        """A deactivated coupon returns valid=False."""
        # Arrange
        coupon = InactiveCouponFactory(code='OFF', active=False)

        # Act
        result = CouponValidationService.validate_coupon(coupon.code)

        # Assert
        assert result['valid'] is False, "Inactive coupon should be invalid"


@pytest.mark.django_db
class TestCouponBeforeStartDate:
    """Test Case 4: Coupon Before Start Date"""

    def test_future_coupon_returns_invalid(self):
        """A coupon whose start_date is in the future returns valid=False."""
        # Arrange
        coupon = FutureCouponFactory(code='FUTURE')

        # Act
        result = CouponValidationService.validate_coupon(coupon.code)

        # Assert
        assert result['valid'] is False, "Future-start coupon should be invalid"
        assert 'not yet valid' in result['message'].lower(), (
            "Message should indicate coupon is not yet active"
        )


@pytest.mark.django_db
class TestErrorMessageValidation:
    """Test Case 5: Error Message Validation"""

    def test_unknown_coupon_message_contains_invalid_coupon_text(self):
        """The error message for an unknown coupon contains 'Invalid coupon'."""
        # Act
        result = CouponValidationService.validate_coupon('BADCODE')

        # Assert
        assert 'Invalid coupon' in result['message'], (
            f"Expected 'Invalid coupon' in message, got: {result['message']}"
        )

    def test_valid_coupon_returns_discount_information(self):
        """A valid coupon returns valid=True with discount and discount_type."""
        # Arrange
        coupon = CouponFactory(code='GOOD', active=True, discount_value=Decimal('15.00'))

        # Act
        result = CouponValidationService.validate_coupon(coupon.code, Decimal('100.00'))

        # Assert
        assert result['valid'] is True, "Valid coupon should be accepted"
        assert 'discount' in result, "Response should include discount amount"
        assert result['discount'] == 15.00, f"Discount should be 15.00, got {result['discount']}"
        assert 'discount_type' in result, "Response should include discount_type"
