"""Service layer for Wishlist operations."""
from __future__ import annotations

import logging

from django.db import transaction
from django.db import IntegrityError

from apps.users.services import create_audit_log
from .models import WishlistItem

logger = logging.getLogger(__name__)


class WishlistService:
    """Manages wishlist operations: add, remove, list."""

    @staticmethod
    @transaction.atomic
    def add_product(user, product_id: int) -> WishlistItem:
        """Add a product to user's wishlist. Raises ValueError on duplicate."""
        try:
            item = WishlistItem.objects.create(user=user, product_id=product_id)
        except IntegrityError:
            raise ValueError("This product is already in your wishlist.")

        create_audit_log(
            'WISHLIST_ITEM_ADDED',
            user=user,
            resource_type='WishlistItem',
            resource_id=str(item.id),
            metadata={'product_id': product_id},
        )
        logger.info("Wishlist item added: user=%s product=%s", user.id, product_id)
        return item

    @staticmethod
    @transaction.atomic
    def remove_product(user, product_id: int) -> None:
        """Remove a product from user's wishlist."""
        deleted_count, _ = WishlistItem.objects.filter(
            user=user, product_id=product_id
        ).delete()

        if deleted_count == 0:
            raise ValueError("Product not found in wishlist.")

        create_audit_log(
            'WISHLIST_ITEM_REMOVED',
            user=user,
            resource_type='WishlistItem',
            resource_id=str(product_id),
            metadata={'product_id': product_id},
        )
        logger.info("Wishlist item removed: user=%s product=%s", user.id, product_id)

    @staticmethod
    def list_products(user):
        """Return all wishlist items for a user with product details."""
        return (
            WishlistItem.objects
            .filter(user=user)
            .select_related('product')
            .prefetch_related('product__images', 'product__variants')
            .order_by('-created_at')
        )
