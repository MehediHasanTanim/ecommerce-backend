"""InventoryService – stock reservation, release, and validation.

Uses select_for_update() for concurrency-safe stock operations.
"""
import logging
from typing import List, Tuple

from django.db.models import F

from apps.catalog.models import ProductVariant

logger = logging.getLogger(__name__)


class InsufficientStockError(Exception):
    """Raised when requested quantity exceeds available stock."""

    def __init__(self, variant_id, requested, available):
        self.variant_id = variant_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for variant {variant_id}: "
            f"requested {requested}, available {available}"
        )


class InventoryService:
    """Handles stock validation, reservation, and release."""

    @staticmethod
    def validate_cart_items(cart_items) -> List[Tuple[int, int]]:
        """Validate that all cart items have sufficient available stock.

        Returns:
            List of (variant_id, quantity) tuples for valid items.

        Raises:
            InsufficientStockError: If any item exceeds available stock.
            ValueError: If any variant or product is inactive.
        """
        validated = []
        for item in cart_items:
            variant = item.product_variant

            # Re-check active status
            if not variant.is_active:
                raise ValueError(f"Product variant '{variant.variant_name}' is no longer available.")
            if not variant.product.is_active:
                raise ValueError(f"Product '{variant.product.name}' is no longer available.")

            available = variant.available_stock
            if item.quantity > available:
                raise InsufficientStockError(
                    variant_id=variant.id,
                    requested=item.quantity,
                    available=available,
                )

            validated.append((variant.id, item.quantity))

        return validated

    @staticmethod
    def reserve_stock(variant_id: int, quantity: int) -> None:
        """Atomically increment reserved_stock for a variant.

        Uses select_for_update() within an active transaction to prevent
        race conditions (overselling).
        """
        variant = (
            ProductVariant.objects
            .select_for_update()
            .get(pk=variant_id)
        )

        available = variant.available_stock
        if quantity > available:
            raise InsufficientStockError(
                variant_id=variant_id,
                requested=quantity,
                available=available,
            )

        variant.reserved_stock = F('reserved_stock') + quantity
        variant.save(update_fields=['reserved_stock'])

        # Refresh to get the actual updated value
        variant.refresh_from_db(fields=['reserved_stock'])

        logger.info(
            "Stock reserved: variant_id=%s, quantity=%s, "
            "new_reserved=%s, stock=%s",
            variant_id, quantity,
            variant.reserved_stock, variant.stock_quantity,
        )

    @staticmethod
    def release_stock(variant_id: int, quantity: int) -> None:
        """Atomically decrement reserved_stock for a variant.

        Used when cancelling an order to restore available stock.
        """
        variant = (
            ProductVariant.objects
            .select_for_update()
            .get(pk=variant_id)
        )

        release_qty = min(quantity, variant.reserved_stock)
        variant.reserved_stock = F('reserved_stock') - release_qty
        variant.save(update_fields=['reserved_stock'])

        variant.refresh_from_db(fields=['reserved_stock'])

        logger.info(
            "Stock released: variant_id=%s, quantity=%s, "
            "new_reserved=%s",
            variant_id, release_qty, variant.reserved_stock,
        )

    @staticmethod
    def release_order_stock(order) -> None:
        """Release all reserved stock for an order's items."""
        for item in order.items.all():
            InventoryService.release_stock(item.variant_id, item.quantity)
