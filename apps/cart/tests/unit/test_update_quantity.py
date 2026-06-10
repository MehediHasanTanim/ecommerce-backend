"""Module 2: Update Quantity Rules – Unit Tests

Covers CartService.update_item() with AAA pattern.
"""
import pytest

from apps.cart.services import CartService
from common.tests.factories import CartItemFactory, ProductVariantFactory


@pytest.mark.django_db
class TestUpdateQuantitySuccessfully:
    """Test Case 1: Update Quantity Successfully"""

    def test_quantity_updated_to_new_value(self, cart, product_variant):
        """Updating quantity from 1 to 4 sets the correct quantity."""
        # Arrange
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=1)

        # Act
        updated = CartService.update_item(item, 4)

        # Assert
        assert updated.quantity == 4, f"Quantity should be 4, got {updated.quantity}"

    def test_unit_price_refreshed_on_update(self, cart):
        """Unit price is refreshed from the variant's current effective_price on update."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True, price=99.99)
        item = CartItemFactory(cart=cart, product_variant=variant, quantity=1, unit_price=50.00)

        # Act
        updated = CartService.update_item(item, 2)

        # Assert
        assert updated.unit_price == variant.effective_price, (
            f"Unit price should refresh to {variant.effective_price}, got {updated.unit_price}"
        )


@pytest.mark.django_db
class TestUpdateQuantityToZero:
    """Test Case 2: Update Quantity To Zero"""

    def test_quantity_zero_raises_value_error(self, cart, product_variant):
        """Setting quantity to 0 raises ValueError."""
        # Arrange
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=3)

        # Act & Assert
        with pytest.raises(ValueError, match='greater than zero'):
            CartService.update_item(item, 0)

        # Assert – original quantity preserved
        item.refresh_from_db()
        assert item.quantity == 3, "Quantity should remain unchanged after failed update"


@pytest.mark.django_db
class TestUpdateQuantityBelowZero:
    """Test Case 3: Update Quantity Below Zero"""

    def test_quantity_negative_raises_value_error(self, cart, product_variant):
        """Setting quantity to a negative value raises ValueError."""
        # Arrange
        item = CartItemFactory(cart=cart, product_variant=product_variant, quantity=2)
        original_qty = item.quantity

        # Act & Assert
        with pytest.raises(ValueError):
            CartService.update_item(item, -1)

        # Assert – original quantity preserved
        item.refresh_from_db()
        assert item.quantity == original_qty, "Quantity should remain unchanged after failed update"


@pytest.mark.django_db
class TestUpdateQuantityAboveStock:
    """Test Case 4: Update Quantity Above Available Stock"""

    def test_quantity_above_stock_raises_value_error(self, cart):
        """Requesting more than available stock raises ValueError and quantity unchanged."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=3, is_active=True)
        item = CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        # Act & Assert
        with pytest.raises(ValueError, match='exceeds available stock'):
            CartService.update_item(item, 10)

        # Assert – original quantity preserved
        item.refresh_from_db()
        assert item.quantity == 1, "Quantity should remain unchanged after rejected update"


@pytest.mark.django_db
class TestUpdateQuantityToStockBoundary:
    """Test Case 5: Update Quantity To Stock Boundary"""

    def test_quantity_at_stock_boundary_accepted(self, cart):
        """Setting quantity exactly equal to stock_quantity is accepted."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        item = CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        # Act
        updated = CartService.update_item(item, 10)

        # Assert
        assert updated.quantity == 10, (
            f"Quantity at stock boundary (10) should be accepted, got {updated.quantity}"
        )
