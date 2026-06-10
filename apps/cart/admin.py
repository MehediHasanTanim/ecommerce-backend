from django.contrib import admin
from .models import Cart, CartItem, Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'active', 'start_date', 'end_date', 'usage_count']
    list_filter = ['active', 'discount_type']
    search_fields = ['code']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'guest_token', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'guest_token']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'cart', 'product_variant', 'quantity', 'unit_price', 'line_total']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
