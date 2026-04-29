from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from .models import User
from .serializers import UserSerializer

class UserViewSet(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own profile, unless they are staff/admin
        user = self.request.user
        if user.is_staff or user.role == 'admin':
            return super().get_queryset()
        return super().get_queryset().filter(id=user.id)
