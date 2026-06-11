from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(request):
    """REGR-HEALTH-001 – lightweight liveness probe, no auth required."""
    return JsonResponse({"status": "ok", "service": "ecommerce-backend"})

urlpatterns = [
    path('admin/', admin.site.urls),

    # Health / liveness probe  (REGR-HEALTH-001)
    path('api/v1/health/', health_check, name='health'),

    # API endpoints
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/users/', include('apps.users.urls')),

    # Phase 3: Catalog & Search
    path('api/v1/', include('apps.catalog.urls')),

    # Phase 4: Cart & Wishlist
    path('api/v1/', include('apps.cart.urls')),
    path('api/v1/', include('apps.wishlist.urls')),

    # Phase 5: Checkout & Orders
    path('api/v1/', include('apps.checkout.urls')),
    path('api/v1/', include('apps.orders.urls')),

    # OpenAPI Docs
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
