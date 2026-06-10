"""Module 4: Guest Cart Merge After Login – Unit Tests

Covers CartMergeService.merge_guest_cart() with AAA pattern.
"""
import pytest

from apps.cart.models import Cart
from apps.cart.services import CartMergeService
from common.tests.factories import (
    CartFactory,
    GuestCartFactory,
    CartItemFactory,
    ProductVariantFactory,
)


@pytest.mark.django_db
class TestMergeIntoEmptyUserCart:
    """Test Case 1: Merge Into Empty User Cart"""

    def test_merge_populates_user_cart_with_all_guest_items(self, user):
        """Merging into empty user cart copies all guest cart items."""
        # Arrange
        variant_a = ProductVariantFactory(stock_quantity=10, is_active=True)
        variant_b = ProductVariantFactory(stock_quantity=10, is_active=True)
        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant_a, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=variant_b, quantity=1)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert
        assert merged.items.count() == 2, f"User cart should have 2 items, got {merged.items.count()}"


@pytest.mark.django_db
class TestMergeWithExistingUserCart:
    """Test Case 2: Merge With Existing User Cart"""

    def test_merge_sums_quantities_for_same_variant(self, user):
        """When guest and user have the same variant, quantities are summed."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=variant, quantity=1)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant, quantity=2)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert
        merged_item = merged.items.get(product_variant=variant)
        assert merged_item.quantity == 3, (
            f"Merged quantity should be 3 (1+2), got {merged_item.quantity}"
        )

    def test_merge_preserves_unique_items_from_both_carts(self, user):
        """Items unique to each cart are all present after merge."""
        # Arrange
        v_a = ProductVariantFactory(stock_quantity=10, is_active=True)  # both carts
        v_b = ProductVariantFactory(stock_quantity=10, is_active=True)  # guest only
        v_c = ProductVariantFactory(stock_quantity=10, is_active=True)  # user only

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=v_a, quantity=1)
        CartItemFactory(cart=user_cart, product_variant=v_c, quantity=3)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=v_a, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=v_b, quantity=1)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert
        assert merged.items.count() == 3, "Should have 3 unique variants after merge"
        assert merged.items.get(product_variant=v_a).quantity == 3  # 1+2
        assert merged.items.get(product_variant=v_b).quantity == 1
        assert merged.items.get(product_variant=v_c).quantity == 3


@pytest.mark.django_db
class TestMergeRespectsStockLimit:
    """Test Case 3: Merge Respects Stock Limit"""

    def test_merge_caps_quantity_at_stock_limit(self, user):
        """When combined quantity exceeds stock, it is capped at stock_quantity."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=variant, quantity=3)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant, quantity=4)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert
        merged_item = merged.items.get(product_variant=variant)
        assert merged_item.quantity == 5, (
            f"Expected quantity capped at 5 (stock limit), got {merged_item.quantity}"
        )


@pytest.mark.django_db
class TestGuestCartDeletedAfterMerge:
    """Test Case 4: Guest Cart Deleted After Merge"""

    def test_guest_cart_does_not_exist_after_merge(self, user):
        """The guest cart and its items are fully cleaned up after merge."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant, quantity=1)
        guest_cart_id = guest_cart.id

        # Act
        CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert
        assert not Cart.objects.filter(id=guest_cart_id).exists(), (
            "Guest cart should be deleted after merge"
        )
