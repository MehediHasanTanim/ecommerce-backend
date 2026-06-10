"""API views for Wishlist operations."""
from __future__ import annotations

import logging

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from .models import WishlistItem
from .serializers import WishlistAddRequestSerializer, WishlistItemSerializer
from .services import WishlistService

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Wishlist'],
    summary='List Wishlist',
    description='Retrieve all wishlist items for the authenticated user.',
    responses={200: WishlistItemSerializer(many=True)},
)
class WishlistListView(views.APIView):
    """GET /api/v1/wishlist/ – List wishlist."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = WishlistService.list_products(request.user)
        serializer = WishlistItemSerializer(
            items, many=True, context={'request': request}
        )
        return Response(serializer.data)


@extend_schema(
    tags=['Wishlist'],
    summary='Add to Wishlist',
    description='Add a product to the authenticated user\'s wishlist.',
    request=WishlistAddRequestSerializer,
    responses={
        201: WishlistItemSerializer,
        400: OpenApiResponse(description='Validation error or duplicate'),
    },
    examples=[
        OpenApiExample(
            'Add to wishlist',
            summary='Add product',
            value={'product_id': 1001},
            request_only=True,
        ),
    ],
)
class WishlistAddView(views.APIView):
    """POST /api/v1/wishlist/ – Add item to wishlist."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WishlistAddRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']

        try:
            item = WishlistService.add_product(request.user, product_id)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_serializer = WishlistItemSerializer(
            item, context={'request': request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Wishlist'],
    summary='Remove from Wishlist',
    description='Remove a product from the authenticated user\'s wishlist by product ID.',
    responses={
        204: None,
        404: OpenApiResponse(description='Product not in wishlist'),
    },
)
class WishlistRemoveView(views.APIView):
    """DELETE /api/v1/wishlist/{product_id}/ – Remove item from wishlist."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        try:
            WishlistService.remove_product(request.user, product_id)
        except ValueError:
            return Response(
                {'detail': 'Product not found in wishlist.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
