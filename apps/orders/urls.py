from django.urls import path
from .views import (
    OrderListView,
    OrderDetailView,
    OrderCancelView,
    OrderInvoiceView,
)

urlpatterns = [
    path('orders/', OrderListView.as_view(), name='order-list'),
    path('orders/<uuid:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<uuid:pk>/cancel/', OrderCancelView.as_view(), name='order-cancel'),
    path('orders/<uuid:pk>/invoice/', OrderInvoiceView.as_view(), name='order-invoice'),
]
