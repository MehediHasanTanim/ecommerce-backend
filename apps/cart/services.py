"""Service layer for Cart, Coupon, CartMerge, and Wishlist operations."""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.users.services import create_audit_log
from .models import Cart, CartItem, Coupon

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cart Calculation Service
# ---------------------------------------------------------------------------


class CartCalculationService:
    """Reusable cart total calculations."""

    @staticmethod
    def calculate_subtotal(items) -> Decimal:
        """Sum of (unit_price × quantity) across all items."""
        if hasattr(items, 'all'):
            # Queryset / prefetched manager
            return sum(
                (item.unit_price * item.quantity)
                for item in items.all()
            )
        total = Decimal('0.00')
        for item in items:
            total += (item.unit_price or Decimal('0')) * (item.quantity or 0)
        return total

    @staticmethod
    def calculate_discount(subtotal: Decimal, coupon: Optional[Coupon] = None) -> Decimal:
        """Compute discount amount from an applied coupon."""
        if coupon is None:
            return Decimal('0.00')
        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            discount = (subtotal * coupon.discount_value / 100).quantize(Decimal('0.01'))
            return min(discount, subtotal)
        # Fixed amount
        return min(coupon.discount_value, subtotal)

    @staticmethod
    def calculate_total(subtotal: Decimal, discount: Decimal) -> Decimal:
        """Grand total = subtotal – discount."""
        return (subtotal - discount).quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# Cart Service
# ---------------------------------------------------------------------------


class CartService:
    """Manages cart lifecycle: get, add, update, remove, clear."""

    @staticmethod
    def _get_or_create_cart(
        *,
        user=None,
        guest_token: str | None = None,
    ) -> Cart:
        """Retrieve existing cart or create a new one."""
        if user and user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=user)
            if created:
                logger.info("Cart created for user %s (cart_id=%s)", user.id, cart.id)
            return cart

        if guest_token:
            cart, created = Cart.objects.get_or_create(guest_token=guest_token)
            if created:
                logger.info("Guest cart created with token %s (cart_id=%s)", guest_token, cart.id)
            return cart

        # Generate a new guest token
        guest_token = uuid.uuid4().hex
        cart = Cart.objects.create(guest_token=guest_token)
        logger.info("Guest cart created with new token %s (cart_id=%s)", guest_token, cart.id)
        return cart

    @staticmethod
    def get_cart(*, user=None, guest_token: str | None = None) -> Cart:
        """Get existing cart for user or guest, or return None."""
        if user and user.is_authenticated:
            try:
                return (
                    Cart.objects
                    .filter(user=user)
                    .prefetch_related('items__product_variant__product')
                    .first()
                )
            except Cart.DoesNotExist:
                return None

        if guest_token:
            try:
                return (
                    Cart.objects
                    .filter(guest_token=guest_token)
                    .prefetch_related('items__product_variant__product')
                    .first()
                )
            except Cart.DoesNotExist:
                return None

        return None

    @staticmethod
    def _get_cart_subtotal(cart: Cart) -> Decimal:
        """Calculate cart subtotal from items."""
        items = getattr(cart, 'items', None)
        if items is not None:
            return sum(
                (item.unit_price or Decimal('0')) * (item.quantity or 0)
                for item in items.all()
            )
        return Decimal('0.00')

    @staticmethod
    @transaction.atomic
    def add_item(
        cart: Cart,
        variant_id: int,
        quantity: int = 1,
        actor=None,
    ) -> CartItem:
        """Add an item to the cart, merging duplicates."""
        variant = ProductVariant.objects.select_related('product').get(pk=variant_id)

        # Validation
        if not variant.is_active:
            raise ValueError("This product variant is no longer available.")
        if not variant.product.is_active:
            raise ValueError("This product is no longer available.")
        if quantity > variant.stock_quantity:
            raise ValueError(
                f"Requested quantity ({quantity}) exceeds available stock ({variant.stock_quantity})."
            )

        unit_price = variant.effective_price

        # Merge duplicate items
        existing = cart.items.filter(product_variant=variant).first()
        if existing:
            new_qty = existing.quantity + quantity
            if new_qty > variant.stock_quantity:
                raise ValueError(
                    f"Total quantity ({new_qty}) would exceed available stock ({variant.stock_quantity})."
                )
            existing.quantity = new_qty
            existing.unit_price = unit_price
            existing.save()
            cart.save()  # bump updated_at
            logger.info(
                "Cart item merged: cart=%s variant=%s qty=%d",
                cart.id, variant.sku, new_qty,
            )
            return existing

        cart_item = CartItem.objects.create(
            cart=cart,
            product_variant=variant,
            quantity=quantity,
            unit_price=unit_price,
        )
        cart.save()  # bump updated_at

        create_audit_log(
            'CART_ITEM_ADDED',
            user=actor,
            resource_type='CartItem',
            resource_id=str(cart_item.id),
            metadata={
                'cart_id': str(cart.id),
                'variant_id': variant_id,
                'sku': variant.sku,
                'quantity': quantity,
                'unit_price': str(unit_price),
            },
        )
        logger.info(
            "Cart item added: cart=%s variant=%s qty=%d",
            cart.id, variant.sku, quantity,
        )
        return cart_item

    @staticmethod
    @transaction.atomic
    def update_item(
        cart_item: CartItem,
        quantity: int,
        actor=None,
    ) -> CartItem:
        """Update quantity of an existing cart item."""
        variant = cart_item.product_variant

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if quantity > variant.stock_quantity:
            raise ValueError(
                f"Requested quantity ({quantity}) exceeds available stock ({variant.stock_quantity})."
            )

        cart_item.quantity = quantity
        cart_item.unit_price = variant.effective_price
        cart_item.save()
        cart_item.cart.save()

        create_audit_log(
            'CART_ITEM_UPDATED',
            user=actor,
            resource_type='CartItem',
            resource_id=str(cart_item.id),
            metadata={
                'cart_id': str(cart_item.cart_id),
                'variant_id': variant.id,
                'new_quantity': quantity,
            },
        )
        logger.info(
            "Cart item updated: item=%s qty=%d",
            cart_item.id, quantity,
        )
        return cart_item

    @staticmethod
    @transaction.atomic
    def remove_item(cart_item: CartItem, actor=None) -> None:
        """Remove an item from the cart."""
        cart = cart_item.cart
        item_id = str(cart_item.id)
        variant_id = cart_item.product_variant_id

        cart_item.delete()
        cart.save()  # bump updated_at

        create_audit_log(
            'CART_ITEM_REMOVED',
            user=actor,
            resource_type='CartItem',
            resource_id=item_id,
            metadata={
                'cart_id': str(cart.id),
                'variant_id': variant_id,
            },
        )
        logger.info("Cart item removed: item=%s cart=%s", item_id, cart.id)

    @staticmethod
    @transaction.atomic
    def clear_cart(cart: Cart, actor=None) -> None:
        """Remove all items from the cart."""
        cart.items.all().delete()
        cart.coupon = None
        cart.save()

        create_audit_log(
            'CART_CLEARED',
            user=actor,
            resource_type='Cart',
            resource_id=str(cart.id),
        )
        logger.info("Cart cleared: cart=%s", cart.id)

    @staticmethod
    @transaction.atomic
    def apply_coupon(cart: Cart, coupon: Coupon, actor=None) -> Cart:
        """Apply a validated coupon to the cart."""
        cart.coupon = coupon
        cart.save()

        create_audit_log(
            'CART_COUPON_APPLIED',
            user=actor,
            resource_type='Cart',
            resource_id=str(cart.id),
            metadata={'coupon_code': coupon.code},
        )
        logger.info("Coupon %s applied to cart %s", coupon.code, cart.id)
        return cart

    @staticmethod
    @transaction.atomic
    def remove_coupon(cart: Cart, actor=None) -> Cart:
        """Remove applied coupon from cart."""
        old_code = cart.coupon.code if cart.coupon else None
        cart.coupon = None
        cart.save()

        create_audit_log(
            'CART_COUPON_REMOVED',
            user=actor,
            resource_type='Cart',
            resource_id=str(cart.id),
            metadata={'old_coupon': old_code},
        )
        logger.info("Coupon removed from cart %s", cart.id)
        return cart


# ---------------------------------------------------------------------------
# Cart Merge Service
# ---------------------------------------------------------------------------


class CartMergeService:
    """Merges a guest cart into an authenticated user's cart after login."""

    @staticmethod
    @transaction.atomic
    def merge_guest_cart(user, guest_cart: Cart) -> Cart:
        """
        Merge guest_cart items into the user's cart.
        Rules:
          - Combine quantities for same variants.
          - Respect stock limits.
          - Keep newest cart metadata.
          - Clear guest cart after merge.
        """
        user_cart, _ = Cart.objects.get_or_create(user=user)

        for guest_item in guest_cart.items.select_related('product_variant__product').all():
            variant = guest_item.product_variant

            # Skip inactive variants/products
            if not variant.is_active or not variant.product.is_active:
                logger.info(
                    "Skipping inactive variant %s during merge", variant.sku,
                )
                continue

            existing = user_cart.items.filter(product_variant=variant).first()
            merged_qty = guest_item.quantity + (existing.quantity if existing else 0)

            # Cap at available stock
            capped_qty = min(merged_qty, variant.stock_quantity)

            if capped_qty <= 0:
                if existing:
                    existing.delete()
                continue

            unit_price = variant.effective_price

            if existing:
                existing.quantity = capped_qty
                existing.unit_price = unit_price
                existing.save()
            else:
                CartItem.objects.create(
                    cart=user_cart,
                    product_variant=variant,
                    quantity=capped_qty,
                    unit_price=unit_price,
                )

        # Clear guest cart
        guest_cart.items.all().delete()
        guest_cart.delete()

        user_cart.save()
        logger.info(
            "Guest cart %s merged into user cart %s (user=%s)",
            guest_cart.id, user_cart.id, user.id,
        )
        return user_cart


# ---------------------------------------------------------------------------
# Coupon Validation Service
# ---------------------------------------------------------------------------


class CouponValidationService:
    """Validates coupon codes against business rules."""

    @staticmethod
    def validate_coupon(code: str, cart_subtotal: Decimal = Decimal('0.00')) -> dict:
        """
        Validate a coupon code.
        Returns dict with 'valid', 'discount', 'discount_type', 'message'.
        """
        code = code.strip().upper()

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return {'valid': False, 'message': 'Invalid coupon code.'}

        now = timezone.now()

        if not coupon.active:
            return {'valid': False, 'message': 'This coupon is no longer active.'}

        if coupon.start_date > now:
            return {'valid': False, 'message': 'This coupon is not yet valid.'}

        if coupon.end_date < now:
            return {'valid': False, 'message': 'This coupon has expired.'}

        if coupon.max_usage > 0 and coupon.usage_count >= coupon.max_usage:
            return {'valid': False, 'message': 'This coupon has reached its usage limit.'}

        if cart_subtotal < coupon.min_cart_amount:
            return {
                'valid': False,
                'message': f'Minimum cart amount of {coupon.min_cart_amount} required.',
            }

        # Calculate discount
        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            discount = (cart_subtotal * coupon.discount_value / 100).quantize(Decimal('0.01'))
        else:
            discount = min(coupon.discount_value, cart_subtotal)

        return {
            'valid': True,
            'discount': float(discount),
            'discount_type': coupon.discount_type,
        }
