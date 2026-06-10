"""Serializers for Cart, CartItem, Coupon, and related request/response types."""
from decimal import Decimal
from rest_framework import serializers
from django.db.models import Sum

from .models import Cart, CartItem, Coupon
from apps.catalog.models import ProductVariant


# ---------------------------------------------------------------------------
# Coupon Serializers
# ---------------------------------------------------------------------------

class CouponValidateRequestSerializer(serializers.Serializer):
    """Request payload for coupon validation."""
    code = serializers.CharField(max_length=50, trim_whitespace=True)

    def validate_code(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Coupon code cannot be empty.")
        return value.strip().upper()


class CouponValidateResponseSerializer(serializers.Serializer):
    """Response for coupon validation."""
    valid = serializers.BooleanField()
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    discount_type = serializers.CharField(required=False)
    message = serializers.CharField(required=False)


# ---------------------------------------------------------------------------
# Cart Item Serializers
# ---------------------------------------------------------------------------

class CartItemSerializer(serializers.ModelSerializer):
    """Read serializer for a single cart line item."""
    variant_id = serializers.IntegerField(source='product_variant_id', read_only=True)
    variant_name = serializers.CharField(source='product_variant.variant_name', read_only=True)
    product_id = serializers.IntegerField(source='product_variant.product_id', read_only=True)
    product_name = serializers.CharField(source='product_variant.product.name', read_only=True)
    product_slug = serializers.CharField(source='product_variant.product.slug', read_only=True)
    sku = serializers.CharField(source='product_variant.sku', read_only=True)
    attributes = serializers.JSONField(source='product_variant.attributes', read_only=True)
    stock_quantity = serializers.IntegerField(source='product_variant.stock_quantity', read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id', 'variant_id', 'variant_name', 'product_id', 'product_name',
            'product_slug', 'sku', 'attributes', 'quantity',
            'unit_price', 'line_total', 'stock_quantity',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'variant_id', 'variant_name', 'product_id', 'product_name',
            'product_slug', 'sku', 'attributes', 'unit_price', 'line_total',
            'stock_quantity', 'created_at', 'updated_at',
        ]


# ---------------------------------------------------------------------------
# Add Item Request / Response
# ---------------------------------------------------------------------------

class AddItemRequestSerializer(serializers.Serializer):
    """Request payload to add an item to the cart."""
    variant_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_variant_id(self, value: int) -> int:
        try:
            variant = ProductVariant.objects.select_related('product').get(pk=value)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError("Product variant not found.")

        if not variant.is_active:
            raise serializers.ValidationError("This product variant is no longer available.")

        if not variant.product.is_active:
            raise serializers.ValidationError("This product is no longer available.")

        self._validated_variant = variant
        return value

    def validate_quantity(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate(self, data: dict) -> dict:
        variant = getattr(self, '_validated_variant', None)
        quantity = data.get('quantity', 1)
        if variant and quantity > variant.stock_quantity:
            raise serializers.ValidationError({
                'quantity': f"Requested quantity ({quantity}) exceeds available stock ({variant.stock_quantity})."
            })
        return data


class UpdateQuantityRequestSerializer(serializers.Serializer):
    """Request payload to update an item quantity."""
    quantity = serializers.IntegerField(min_value=1)

    def validate_quantity(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


# ---------------------------------------------------------------------------
# Coupon Apply Serializer
# ---------------------------------------------------------------------------

class CouponApplyRequestSerializer(serializers.Serializer):
    """Request payload to apply a coupon to the cart."""
    code = serializers.CharField(max_length=50, trim_whitespace=True)

    def validate_code(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Coupon code cannot be empty.")
        return value.strip().upper()


# ---------------------------------------------------------------------------
# Cart Summary Serializer (full cart response)
# ---------------------------------------------------------------------------

class CartSerializer(serializers.ModelSerializer):
    """Full cart read serializer with items, totals, and coupon info."""
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    discount = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    coupon_code = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id', 'user', 'guest_token', 'coupon', 'coupon_code',
            'items', 'item_count', 'subtotal', 'discount', 'grand_total',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'guest_token', 'coupon', 'coupon_code',
            'items', 'item_count', 'subtotal', 'discount', 'grand_total',
            'created_at', 'updated_at',
        ]

    def get_item_count(self, obj: Cart) -> int:
        items = getattr(obj, 'items', None)
        if items is not None:
            # Prefetched via prefetch_related
            return sum(item.quantity for item in items.all())
        return obj.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def get_subtotal(self, obj: Cart) -> Decimal:
        items = getattr(obj, 'items', None)
        if items is not None:
            return sum((item.unit_price * item.quantity) for item in items.all())
        return Decimal('0.00')

    def get_discount(self, obj: Cart) -> Decimal:
        from .services import CartCalculationService
        subtotal = self.get_subtotal(obj)
        return CartCalculationService.calculate_discount(subtotal, obj.coupon)

    def get_grand_total(self, obj: Cart) -> Decimal:
        subtotal = self.get_subtotal(obj)
        discount = self.get_discount(obj)
        return subtotal - discount

    def get_coupon_code(self, obj: Cart) -> str | None:
        if obj.coupon:
            return obj.coupon.code
        return None
