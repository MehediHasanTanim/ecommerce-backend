"""Order & OrderItem models for the Checkout & Orders module."""
import uuid
import logging
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.catalog.models import Product, ProductVariant

logger = logging.getLogger(__name__)


class Order(models.Model):
    """Core order entity capturing a snapshot of the checkout."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text='e.g. ORD-20260611-000001',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    address_snapshot = models.JSONField(
        help_text='Snapshot of the shipping address at order time.',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    payment_method = models.CharField(
        max_length=30,
        default='cod',
        help_text='e.g. cod, card, wallet, bKash',
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
        ]

    def __str__(self):
        return self.order_number

    @property
    def can_cancel(self):
        """An order can be cancelled only if status is PENDING or CONFIRMED."""
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)


class OrderItem(models.Model):
    """
    Line item within an order. Snapshot of product/variant data at order time
    so order history is independent of future product changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    sku = models.CharField(max_length=100, help_text='Variant SKU at order time.')
    product_name = models.CharField(max_length=500, help_text='Product name at order time.')
    variant_name = models.CharField(max_length=255, help_text='Variant name at order time.')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['product']),
            models.Index(fields=['variant']),
        ]

    def save(self, *args, **kwargs):
        if self.unit_price is not None and self.quantity is not None:
            self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"OrderItem {self.product_name} × {self.quantity}"


class OrderNumberCounter(models.Model):
    """
    Database-backed counter for generating unique daily order numbers.

    One row per date (e.g. '20260611') with an auto-incrementing sequence.
    Used by OrderNumberService with INSERT ... ON CONFLICT for atomicity.
    """
    date_str = models.CharField(
        max_length=8,
        unique=True,
        db_index=True,
        help_text='Date in YYYYMMDD format.',
    )
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Order Number Counter'
        verbose_name_plural = 'Order Number Counters'

    def __str__(self):
        return f"Counter for {self.date_str}: {self.last_sequence}"
