from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, MeView, MePasswordView, AddressViewSet

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('me/password/', MePasswordView.as_view(), name='me_password'),
    path('', include(router.urls)),
]
