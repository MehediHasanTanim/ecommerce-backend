from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'full_name', 'role', 'is_verified', 'created_at']
        read_only_fields = ['id', 'role', 'is_verified', 'created_at']
