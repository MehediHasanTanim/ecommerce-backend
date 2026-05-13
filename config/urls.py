from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(request):
    """REGR-HEALTH-001 – lightweight liveness probe, no auth required."""
    return JsonResponse({"status": "ok", "service": "ecommerce-backend"})

urlpatterns = [
    path('admin/', admin.site.urls),

    # Health / liveness probe  (REGR-HEALTH-001)
    path('api/v1/health/', health_check, name='health'),

    # API endpoints
    path('api/auth/', include('apps.accounts.urls')),
    path('api/users/', include('apps.users.urls')),
    
    # OpenAPI Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
