import logging
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.catalog.models import ProductVariant

logger = logging.getLogger(__name__)


class Coupon(models.Model):
    """Discount coupon for cart-level application."""
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED = 'fixed', 'Fixed Amount'

    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.FIXED,
    )
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    active = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    max_usage = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    usage_count = models.PositiveIntegerField(default=0)
    min_cart_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['active', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f"Coupon {self.code} ({self.discount_type})"


class Cart(models.Model):
    """Shopping cart – one per authenticated user or one per guest token."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
    )
    guest_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['guest_token']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False) |
                    models.Q(guest_token__isnull=False)
                ),
                name='cart_user_or_guest_required',
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"Cart for user {self.user_id}"
        return f"Guest cart {self.guest_token}"


class CartItem(models.Model):
    """Line item within a cart."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product_variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Snapshot of variant effective_price at add time.',
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='unit_price × quantity, denormalized for fast reads.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'product_variant'],
                name='unique_cart_variant',
            ),
        ]
        indexes = [
            models.Index(fields=['cart']),
            models.Index(fields=['product_variant']),
        ]

    def save(self, *args, **kwargs):
        if self.unit_price is not None and self.quantity is not None:
            self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"CartItem {self.product_variant_id} × {self.quantity}"
