from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, MeView, MePasswordView, AddressViewSet

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('change-password/', MePasswordView.as_view(), name='change_password'),
    path('', include(router.urls)),
]
