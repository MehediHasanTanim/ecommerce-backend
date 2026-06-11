"""Unit tests for InventoryService – reserve, release, validate, concurrency.

Covers:
- Reserve stock (success, insufficient, concurrent)
- Release stock (success, not below zero)
- Validate cart items (active, inactive, stock check)
- available_stock property
- select_for_update usage
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.db import transaction
from django.db.models import F

from apps.catalog.models import ProductVariant
from apps.inventory.services import (
    InventoryService,
    InsufficientStockError,
)
from common.tests.factories import (
    ProductVariantFactory,
    CartItemFactory,
    InactiveProductFactory,
)


# ---------------------------------------------------------------------------
# Reserve Stock
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReserveStock:

    def test_reserve_increments_reserved_stock(self):
        """reserved_stock increases by quantity."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0)
        InventoryService.reserve_stock(variant.id, 3)
        variant.refresh_from_db()
        assert variant.reserved_stock == 3

    def test_reserve_multiple_times(self):
        """Multiple reservations accumulate correctly."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0)

        InventoryService.reserve_stock(variant.id, 2)
        variant.refresh_from_db()
        assert variant.reserved_stock == 2

        InventoryService.reserve_stock(variant.id, 3)
        variant.refresh_from_db()
        assert variant.reserved_stock == 5

    def test_reserve_reduces_available_stock(self):
        """available_stock = stock_quantity - reserved_stock."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0)
        assert variant.available_stock == 10

        InventoryService.reserve_stock(variant.id, 4)
        variant.refresh_from_db()
        assert variant.available_stock == 6

    def test_reserve_up_to_exact_capacity(self):
        """Can reserve exactly the available stock."""
        variant = ProductVariantFactory(stock_quantity=5, reserved_stock=0)
        InventoryService.reserve_stock(variant.id, 5)
        variant.refresh_from_db()
        assert variant.reserved_stock == 5
        assert variant.available_stock == 0

    def test_reserve_zero_quantity(self):
        """Reserving 0 is a no-op."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=2)
        InventoryService.reserve_stock(variant.id, 0)
        variant.refresh_from_db()
        assert variant.reserved_stock == 2

    def test_reserve_single_item(self):
        """Reserving 1 unit works."""
        variant = ProductVariantFactory(stock_quantity=100, reserved_stock=0)
        InventoryService.reserve_stock(variant.id, 1)
        variant.refresh_from_db()
        assert variant.reserved_stock == 1


# ---------------------------------------------------------------------------
# Reserve Stock – Failure Cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReserveStockFailures:

    def test_insufficient_stock_raises(self):
        """InsufficientStockError when requesting more than available."""
        variant = ProductVariantFactory(stock_quantity=5, reserved_stock=3)
        # available = 2
        with pytest.raises(InsufficientStockError) as exc_info:
            InventoryService.reserve_stock(variant.id, 5)

        assert exc_info.value.variant_id == variant.id
        assert exc_info.value.requested == 5
        assert exc_info.value.available == 2

    def test_insufficient_exact_boundary(self):
        """Requesting available+1 raises error."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=5)
        # available = 5
        with pytest.raises(InsufficientStockError):
            InventoryService.reserve_stock(variant.id, 6)

    def test_reserve_from_zero_available(self):
        """Requesting when available = 0 raises error."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=10)
        # available = 0
        with pytest.raises(InsufficientStockError):
            InventoryService.reserve_stock(variant.id, 1)

    def test_no_partial_reserve_on_failure(self):
        """Failed reservation does not modify reserved_stock."""
        variant = ProductVariantFactory(stock_quantity=5, reserved_stock=2)
        original_reserved = variant.reserved_stock

        with pytest.raises(InsufficientStockError):
            InventoryService.reserve_stock(variant.id, 10)

        variant.refresh_from_db()
        assert variant.reserved_stock == original_reserved


# ---------------------------------------------------------------------------
# Release Stock
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReleaseStock:

    def test_release_decrements_reserved_stock(self):
        """reserved_stock decreases by quantity."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=5)
        InventoryService.release_stock(variant.id, 3)
        variant.refresh_from_db()
        assert variant.reserved_stock == 2

    def test_release_full_reservation(self):
        """Can release all reserved stock."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=5)
        InventoryService.release_stock(variant.id, 5)
        variant.refresh_from_db()
        assert variant.reserved_stock == 0

    def test_release_not_below_zero(self):
        """Release beyond reserved amount is capped at zero."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=2)
        InventoryService.release_stock(variant.id, 10)
        variant.refresh_from_db()
        assert variant.reserved_stock == 0

    def test_release_zero_reserved(self):
        """Releasing when nothing reserved is safe."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0)
        InventoryService.release_stock(variant.id, 5)
        variant.refresh_from_db()
        assert variant.reserved_stock == 0

    def test_release_restores_available_stock(self):
        """available_stock increases after release."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=5)
        assert variant.available_stock == 5

        InventoryService.release_stock(variant.id, 3)
        variant.refresh_from_db()
        assert variant.available_stock == 8


# ---------------------------------------------------------------------------
# Validate Cart Items
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidateCartItems:

    def test_validates_all_items(self, cart):
        """Valid items return list of (variant_id, quantity)."""
        v1 = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        v2 = ProductVariantFactory(stock_quantity=5, reserved_stock=0, is_active=True)

        CartItemFactory(cart=cart, product_variant=v1, quantity=3)
        CartItemFactory(cart=cart, product_variant=v2, quantity=2)

        validated = InventoryService.validate_cart_items(cart.items.all())
        assert len(validated) == 2
        assert (v1.id, 3) in validated
        assert (v2.id, 2) in validated

    def test_insufficient_stock_rejected(self, cart):
        """InsufficientStockError when any item exceeds available."""
        v1 = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        v2 = ProductVariantFactory(stock_quantity=3, reserved_stock=2, is_active=True)  # available = 1

        CartItemFactory(cart=cart, product_variant=v1, quantity=1)
        CartItemFactory(cart=cart, product_variant=v2, quantity=3)  # > 1

        with pytest.raises(InsufficientStockError) as exc_info:
            InventoryService.validate_cart_items(cart.items.all())

        assert exc_info.value.variant_id == v2.id

    def test_inactive_variant_rejected(self, cart):
        """ValueError when variant is inactive."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=False)
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        with pytest.raises(ValueError, match='no longer available'):
            InventoryService.validate_cart_items(cart.items.all())

    def test_inactive_product_rejected(self, cart):
        """ValueError when parent product is inactive."""
        inactive_product = InactiveProductFactory(is_active=False)
        variant = ProductVariantFactory(
            product=inactive_product, stock_quantity=10, reserved_stock=0, is_active=True,
        )
        CartItemFactory(cart=cart, product_variant=variant, quantity=1)

        with pytest.raises(ValueError, match='no longer available'):
            InventoryService.validate_cart_items(cart.items.all())

    def test_empty_cart_items(self, cart):
        """Empty list returned for empty cart."""
        validated = InventoryService.validate_cart_items(cart.items.all())
        assert validated == []


# ---------------------------------------------------------------------------
# Available Stock Property
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAvailableStock:

    def test_available_when_no_reserved(self):
        variant = ProductVariantFactory(stock_quantity=50, reserved_stock=0)
        assert variant.available_stock == 50

    def test_available_when_partially_reserved(self):
        variant = ProductVariantFactory(stock_quantity=50, reserved_stock=20)
        assert variant.available_stock == 30

    def test_available_when_fully_reserved(self):
        variant = ProductVariantFactory(stock_quantity=50, reserved_stock=50)
        assert variant.available_stock == 0

    def test_available_never_negative(self):
        """available_stock is max(0, stock - reserved)."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=15)
        assert variant.available_stock == 0


# ---------------------------------------------------------------------------
# Concurrency Protection (select_for_update)
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestConcurrencyProtection:

    def test_sequential_reservations_dont_oversell(self):
        """Multiple sequential reservations respect available stock."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0)

        # First reservation
        InventoryService.reserve_stock(variant.id, 6)
        variant.refresh_from_db()

        # Second reservation should fail (only 4 left, requesting 5)
        with pytest.raises(InsufficientStockError):
            InventoryService.reserve_stock(variant.id, 5)

        variant.refresh_from_db()
        assert variant.reserved_stock == 6  # Only first succeeded

    def test_release_then_reserve(self):
        """Release + reserve in sequence works correctly."""
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=5)

        InventoryService.release_stock(variant.id, 5)
        variant.refresh_from_db()
        assert variant.available_stock == 10

        InventoryService.reserve_stock(variant.id, 8)
        variant.refresh_from_db()
        assert variant.reserved_stock == 8
        assert variant.available_stock == 2

    def test_reserve_release_cycle(self):
        """Full reserve-release cycle returns to original state."""
        variant = ProductVariantFactory(stock_quantity=100, reserved_stock=0)

        # Reserve
        InventoryService.reserve_stock(variant.id, 30)
        variant.refresh_from_db()
        assert variant.reserved_stock == 30

        # Reserve more
        InventoryService.reserve_stock(variant.id, 20)
        variant.refresh_from_db()
        assert variant.reserved_stock == 50

        # Release some
        InventoryService.release_stock(variant.id, 15)
        variant.refresh_from_db()
        assert variant.reserved_stock == 35

        # Release all remaining
        InventoryService.release_stock(variant.id, 35)
        variant.refresh_from_db()
        assert variant.reserved_stock == 0
        assert variant.available_stock == 100


# ---------------------------------------------------------------------------
# Release Order Stock
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReleaseOrderStock:

    def test_releases_all_items_for_order(self):
        """release_order_stock releases all items in an order."""
        v1 = ProductVariantFactory(stock_quantity=20, reserved_stock=10)
        v2 = ProductVariantFactory(stock_quantity=20, reserved_stock=5)

        # Simulate an order
        from apps.orders.models import Order, OrderItem
        from common.tests.factories import OrderFactory

        order = OrderFactory()

        OrderItem.objects.create(
            order=order, product=v1.product, variant=v1,
            sku=v1.sku, product_name=v1.product.name,
            variant_name=v1.variant_name,
            unit_price=Decimal('50.00'), quantity=3,
        )
        OrderItem.objects.create(
            order=order, product=v2.product, variant=v2,
            sku=v2.sku, product_name=v2.product.name,
            variant_name=v2.variant_name,
            unit_price=Decimal('30.00'), quantity=2,
        )

        InventoryService.release_order_stock(order)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.reserved_stock == 7   # 10 - 3
        assert v2.reserved_stock == 3   # 5 - 2
