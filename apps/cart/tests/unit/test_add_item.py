"""Module 1: Add Item To Cart – Unit Tests

Covers CartService.add_item() with AAA pattern.
"""
from decimal import Decimal
import pytest

from apps.cart.models import CartItem
from apps.cart.services import CartService, CartCalculationService
from common.tests.factories import (
    ProductVariantFactory,
    ProductFactory,
    CartFactory,
)


@pytest.mark.django_db
class TestAddValidItem:
    """Test Case 1: Add Valid Item"""

    def test_cart_item_created_with_correct_quantity(self, cart):
        """Adding a valid variant creates exactly 1 cart item with correct quantity."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Act
        item = CartService.add_item(cart, variant.id, quantity=2)

        # Assert
        assert cart.items.count() == 1, "Cart should contain exactly 1 item"
        assert item.quantity == 2, "Item quantity should match requested amount"
        assert item.product_variant_id == variant.id, "Item should reference correct variant"

    def test_cart_item_stores_unit_price_from_variant(self, cart):
        """Unit price is snapshotted from the variant's effective_price at add time."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True, price=Decimal('49.99'))
        expected_price = variant.effective_price

        # Act
        item = CartService.add_item(cart, variant.id, quantity=1)

        # Assert
        assert item.unit_price == expected_price, (
            f"Unit price {item.unit_price} should equal variant effective_price {expected_price}"
        )

    def test_totals_recalculated_after_add(self, cart):
        """Cart subtotal and grand total reflect the new item."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True, price=Decimal('25.00'))

        # Act
        CartService.add_item(cart, variant.id, quantity=3)

        # Assert
        subtotal = CartCalculationService.calculate_subtotal(cart.items.all())
        expected = Decimal('25.00') * 3
        assert subtotal == expected, f"Subtotal {subtotal} should equal {expected}"


@pytest.mark.django_db
class TestAddExistingItemAgain:
    """Test Case 2: Add Existing Item Again (merge)"""

    def test_duplicate_merges_quantity_into_single_item(self, cart):
        """Adding the same variant twice merges into a single CartItem with summed quantity."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        CartService.add_item(cart, variant.id, quantity=2)

        # Act
        CartService.add_item(cart, variant.id, quantity=3)

        # Assert
        assert cart.items.count() == 1, "Duplicate variants should merge into a single CartItem"
        item = cart.items.first()
        assert item.quantity == 5, f"Merged quantity should be 5, got {item.quantity}"


@pytest.mark.django_db
class TestAddInactiveVariant:
    """Test Case 3: Add Inactive Variant"""

    def test_inactive_variant_raises_value_error(self, cart):
        """Adding an inactive variant raises ValueError and cart is unchanged."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=False)
        initial_count = cart.items.count()

        # Act & Assert
        with pytest.raises(ValueError, match='no longer available'):
            CartService.add_item(cart, variant.id, quantity=1)

        assert cart.items.count() == initial_count, "Cart should be unchanged after failed add"

    def test_inactive_product_variant_raises_value_error(self, cart):
        """Adding a variant of an inactive product raises ValueError."""
        # Arrange
        product = ProductFactory(is_active=False)
        variant = ProductVariantFactory(product=product, stock_quantity=10, is_active=True)

        # Act & Assert
        with pytest.raises(ValueError, match='no longer available'):
            CartService.add_item(cart, variant.id, quantity=1)


@pytest.mark.django_db
class TestAddQuantityAboveStock:
    """Test Case 4: Add Quantity Above Available Stock"""

    def test_quantity_exceeding_stock_raises_value_error(self, cart):
        """Requesting more than available stock raises ValueError."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)
        initial_count = cart.items.count()

        # Act & Assert
        with pytest.raises(ValueError, match='exceeds available stock'):
            CartService.add_item(cart, variant.id, quantity=10)

        # Assert – cart unchanged
        assert cart.items.count() == initial_count, "Cart should be unchanged after rejected add"

    def test_duplicate_merging_exceeding_stock_raises_value_error(self, cart):
        """When merge would exceed stock, ValueError is raised and original quantity preserved."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)
        CartService.add_item(cart, variant.id, quantity=3)
        initial_qty = cart.items.first().quantity

        # Act & Assert
        with pytest.raises(ValueError, match='exceeds available stock'):
            CartService.add_item(cart, variant.id, quantity=3)  # 3+3=6 > 5

        # Assert – original quantity unchanged
        cart.items.first().refresh_from_db()
        assert cart.items.first().quantity == initial_qty, (
            f"Quantity should remain {initial_qty} after failed merge"
        )
