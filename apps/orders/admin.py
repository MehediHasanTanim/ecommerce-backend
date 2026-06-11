from django.contrib import admin
from .models import Order, OrderItem, OrderNumberCounter


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['sku', 'product_name', 'variant_name', 'unit_price', 'quantity', 'line_total']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user_email', 'status', 'payment_status',
        'payment_method', 'grand_total', 'created_at',
    ]
    list_filter = ['status', 'payment_status', 'payment_method', 'created_at']
    search_fields = ['order_number', 'user__email']
    readonly_fields = [
        'order_number', 'address_snapshot', 'subtotal', 'discount',
        'shipping_fee', 'tax', 'grand_total', 'created_at', 'updated_at',
    ]
    inlines = [OrderItemInline]
    ordering = ['-created_at']

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email


@admin.register(OrderNumberCounter)
class OrderNumberCounterAdmin(admin.ModelAdmin):
    list_display = ['date_str', 'last_sequence']
    readonly_fields = ['date_str', 'last_sequence']
