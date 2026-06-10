"""CART-REG-006 – Guest Cart Merges After Login

Verifies that a guest cart is correctly merged into the authenticated
user's cart upon login, with quantities combined, stock respected,
and the guest cart deleted.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.cart.models import Cart
from apps.cart.services import CartMergeService
from common.tests.factories import (
    ProductVariantFactory,
    CartFactory,
    GuestCartFactory,
    CartItemFactory,
)


@pytest.mark.django_db
class TestGuestCartMergeAfterLogin:
    """CART-REG-006: Guest cart merges after login"""

    def test_merge_combines_quantities_correctly(self, user):
        """Merged cart has correct summed quantities across all variants."""
        # Arrange
        v_a = ProductVariantFactory(stock_quantity=10, is_active=True)
        v_b = ProductVariantFactory(stock_quantity=10, is_active=True)
        v_c = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Guest cart: A x2, B x1
        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=v_a, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=v_b, quantity=1)

        # User cart: A x1, C x3
        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=v_a, quantity=1)
        CartItemFactory(cart=user_cart, product_variant=v_c, quantity=3)

        # Act – merge
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert – merged quantities
        item_a = merged.items.get(product_variant=v_a)
        item_b = merged.items.get(product_variant=v_b)
        item_c = merged.items.get(product_variant=v_c)

        assert item_a.quantity == 3, f"Product A: expected 3 (1+2), got {item_a.quantity}"
        assert item_b.quantity == 1, f"Product B: expected 1, got {item_b.quantity}"
        assert item_c.quantity == 3, f"Product C: expected 3, got {item_c.quantity}"

    def test_merge_guest_cart_deleted_after_merge(self, user):
        """Guest cart and its ID are gone from the database after merge."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant, quantity=1)
        guest_cart_id = guest_cart.id

        # Act
        CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert – guest cart deleted
        assert not Cart.objects.filter(id=guest_cart_id).exists(), (
            f"Guest cart {guest_cart_id} should not exist after merge"
        )

    def test_merge_no_duplicate_records(self, user):
        """After merge, there is exactly one CartItem per variant in the user cart."""
        # Arrange
        v_a = ProductVariantFactory(stock_quantity=10, is_active=True)
        v_b = ProductVariantFactory(stock_quantity=10, is_active=True)

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=v_a, quantity=1)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=v_a, quantity=2)
        CartItemFactory(cart=guest_cart, product_variant=v_b, quantity=1)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert – no duplicates
        item_count_by_variant = {}
        for item in merged.items.all():
            vid = item.product_variant_id
            item_count_by_variant[vid] = item_count_by_variant.get(vid, 0) + 1

        assert all(count == 1 for count in item_count_by_variant.values()), (
            f"Each variant should appear exactly once, got: {item_count_by_variant}"
        )
        assert merged.items.count() == 2, "Should have 2 unique items, not 3"

    def test_merge_respects_stock_limits(self, user):
        """Combined quantity is capped at available stock."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)

        user_cart = CartFactory(user=user)
        CartItemFactory(cart=user_cart, product_variant=variant, quantity=3)

        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant, quantity=4)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert – capped at stock limit
        item = merged.items.get(product_variant=variant)
        assert item.quantity == 5, (
            f"Quantity should be capped at stock limit 5, got {item.quantity}"
        )

    def test_merge_into_empty_user_cart_creates_new_cart(self, user):
        """When user has no cart, merge creates one with guest items."""
        # Arrange – no user cart exists
        assert not Cart.objects.filter(user=user).exists()

        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        guest_cart = GuestCartFactory()
        CartItemFactory(cart=guest_cart, product_variant=variant, quantity=2)

        # Act
        merged = CartMergeService.merge_guest_cart(user, guest_cart)

        # Assert
        assert merged.user == user, "Merged cart should belong to the user"
        assert merged.items.count() == 1, "Should have the guest's items"
        assert merged.items.first().quantity == 2
