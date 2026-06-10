"""Module 3: Remove Item – Unit Tests

Covers CartService.remove_item() with AAA pattern.
"""
from decimal import Decimal
import pytest

from apps.cart.models import CartItem
from apps.cart.services import CartService, CartCalculationService
from common.tests.factories import CartItemFactory, ProductVariantFactory


@pytest.mark.django_db
class TestRemoveExistingItem:
    """Test Case 1: Remove Existing Item"""

    def test_remove_item_deletes_cart_item(self, cart, product_variant):
        """Removing an existing item deletes it from the database."""
        # Arrange
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=2)

        # Act
        CartService.remove_item(item)

        # Assert
        assert CartItem.objects.count() == 0, "CartItem should be deleted from database"
        assert cart.items.count() == 0, "Cart should have zero items after removal"

    def test_remove_item_reduces_cart_count(self, cart):
        """Removing one item reduces total count but other items remain."""
        # Arrange
        v1 = ProductVariantFactory(stock_quantity=10)
        v2 = ProductVariantFactory(stock_quantity=10)
        item1 = CartItemFactory(cart=cart, product_variant=v1, quantity=1)
        CartItemFactory(cart=cart, product_variant=v2, quantity=3)

        # Act
        CartService.remove_item(item1)

        # Assert
        assert cart.items.count() == 1, "Cart should have 1 remaining item"
        assert cart.items.first().product_variant_id == v2.id, "Remaining item should be v2"


@pytest.mark.django_db
class TestRemoveInvalidItem:
    """Test Case 2: Remove Invalid Item"""

    def test_remove_nonexistent_item_raises_not_found(self):
        """Attempting to get a non-existent CartItem raises DoesNotExist."""
        # Arrange – use a UUID that does not exist
        nonexistent_id = "00000000-0000-0000-0000-000000000000"

        # Act & Assert
        with pytest.raises(CartItem.DoesNotExist):
            CartItem.objects.get(pk=nonexistent_id)


@pytest.mark.django_db
class TestRemoveLastItem:
    """Test Case 3: Remove Last Item From Cart"""

    def test_remove_last_item_makes_cart_empty(self, cart, product_variant):
        """Removing the last item results in an empty cart with zero totals."""
        # Arrange
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=5)

        # Act
        CartService.remove_item(item)

        # Assert
        cart.refresh_from_db()
        subtotal = CartCalculationService.calculate_subtotal(cart.items.all())
        assert subtotal == Decimal('0.00'), (
            f"Subtotal should be 0.00 after removing last item, got {subtotal}"
        )
        assert cart.items.count() == 0, "Cart should have zero items"
