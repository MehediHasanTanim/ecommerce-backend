"""Serializers for Checkout & Orders module."""
from rest_framework import serializers

from apps.users.models import Address
from apps.orders.models import Order, OrderItem


# ---------------------------------------------------------------------------
# Checkout Serializers
# ---------------------------------------------------------------------------

class CheckoutSummaryItemSerializer(serializers.Serializer):
    """Line item in checkout summary response."""
    product_id = serializers.CharField()
    product_name = serializers.CharField()
    variant_id = serializers.CharField()
    variant_name = serializers.CharField()
    sku = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.CharField()
    line_total = serializers.CharField()
    stock_available = serializers.IntegerField()


class CheckoutSummaryResponseSerializer(serializers.Serializer):
    """Response for GET /checkout/summary/"""
    items = CheckoutSummaryItemSerializer(many=True)
    subtotal = serializers.CharField()
    discount = serializers.CharField()
    shipping_fee = serializers.CharField()
    tax = serializers.CharField()
    grand_total = serializers.CharField()


class PlaceOrderRequestSerializer(serializers.Serializer):
    """Request payload for POST /checkout/place-order/"""
    address_id = serializers.UUIDField()
    payment_method = serializers.CharField(default='cod', max_length=30)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_address_id(self, value):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if not Address.objects.filter(id=value, user=request.user).exists():
                raise serializers.ValidationError("Address not found or does not belong to you.")
        return value

    def validate_payment_method(self, value):
        allowed = {'cod', 'card', 'wallet', 'bKash'}
        if value not in allowed:
            raise serializers.ValidationError(
                f"Invalid payment method. Allowed: {', '.join(allowed)}."
            )
        return value


class PlaceOrderResponseSerializer(serializers.Serializer):
    """Response for POST /checkout/place-order/"""
    order_id = serializers.CharField()
    order_number = serializers.CharField()
    status = serializers.CharField()
    grand_total = serializers.CharField()


# ---------------------------------------------------------------------------
# Order Serializers
# ---------------------------------------------------------------------------

class OrderItemSerializer(serializers.ModelSerializer):
    """Read serializer for order line items."""
    product_id = serializers.CharField(source='product_id', read_only=True)
    variant_id = serializers.CharField(source='variant_id', read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_id', 'variant_id', 'sku',
            'product_name', 'variant_name',
            'unit_price', 'quantity', 'line_total',
        ]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for order list (summary view)."""
    item_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'status_display',
            'payment_status', 'payment_status_display',
            'payment_method', 'grand_total', 'item_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_item_count(self, obj) -> int:
        if hasattr(obj, 'items'):
            items = obj.items.all() if callable(getattr(obj.items, 'all', None)) else obj.items
            return len(list(items))
        return 0


class OrderDetailSerializer(serializers.ModelSerializer):
    """Full order detail with items and address snapshot."""
    items = OrderItemSerializer(many=True, read_only=True)
    address_snapshot = serializers.JSONField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user_id',
            'status', 'status_display',
            'payment_status', 'payment_status_display',
            'payment_method',
            'subtotal', 'discount', 'shipping_fee', 'tax', 'grand_total',
            'address_snapshot', 'items', 'notes',
            'can_cancel', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
