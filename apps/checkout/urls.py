from django.urls import path
from .views import (
    CheckoutSummaryView,
    PlaceOrderView,
)

urlpatterns = [
    path('checkout/summary/', CheckoutSummaryView.as_view(), name='checkout-summary'),
    path('checkout/place-order/', PlaceOrderView.as_view(), name='checkout-place-order'),
]
