from rest_framework import viewsets, permissions, status, views
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import User, Address
from .serializers import (
    UserSerializer, UserProfileSerializer, ProfileUpdateSerializer, 
    ChangePasswordSerializer, AddressSerializer, AddressCreateUpdateSerializer
)
from .services import update_profile, change_password, create_address, set_default_address
from .permissions import IsOwnerOrAdmin
from drf_spectacular.utils import extend_schema

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserProfileSerializer})
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(request=ProfileUpdateSerializer, responses={200: UserProfileSerializer})
    def put(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        user = update_profile(request.user, serializer.validated_data)
        return Response(UserProfileSerializer(user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses={200: UserProfileSerializer})
    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = update_profile(request.user, serializer.validated_data)
        return Response(UserProfileSerializer(user).data)

class MePasswordView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer)
    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        success = change_password(
            request.user, 
            serializer.validated_data['old_password'], 
            serializer.validated_data['new_password']
        )
        if not success:
            return Response({'detail': 'Invalid old password.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AddressCreateUpdateSerializer
        return AddressSerializer

    def perform_create(self, serializer):
        self.instance = create_address(self.request.user, serializer.validated_data)

    @action(detail=True, methods=['patch'], url_path='default')
    def set_default(self, request, pk=None):
        set_default_address(request.user, pk)
        return Response({'detail': 'Default address updated.'}, status=status.HTTP_200_OK)
