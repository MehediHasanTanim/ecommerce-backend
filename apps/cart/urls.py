from django.urls import path
from .views import (
    CartDetailView,
    CartAddItemView,
    CartUpdateItemView,
    CartRemoveItemView,
    CouponValidateView,
    CouponApplyView,
    CouponRemoveView,
)

urlpatterns = [
    # Cart operations
    path('cart/', CartDetailView.as_view(), name='cart-detail'),
    path('cart/add/', CartAddItemView.as_view(), name='cart-add-item'),
    path('cart/items/<uuid:item_id>/', CartUpdateItemView.as_view(), name='cart-update-item'),
    path('cart/items/<uuid:item_id>/delete/', CartRemoveItemView.as_view(), name='cart-remove-item'),

    # Coupon operations
    path('cart/coupons/validate/', CouponValidateView.as_view(), name='coupon-validate'),
    path('cart/coupons/apply/', CouponApplyView.as_view(), name='coupon-apply'),
    path('cart/coupons/remove/', CouponRemoveView.as_view(), name='coupon-remove'),
]
