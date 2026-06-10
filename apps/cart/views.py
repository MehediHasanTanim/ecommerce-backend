"""API views for Cart and Coupon operations."""
from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, views
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from .models import Cart, CartItem
from .serializers import (
    AddItemRequestSerializer,
    UpdateQuantityRequestSerializer,
    CartSerializer,
    CartItemSerializer,
    CouponValidateRequestSerializer,
    CouponValidateResponseSerializer,
    CouponApplyRequestSerializer,
)
from .services import CartService, CouponValidationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Get Cart
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart'],
    summary='View Cart',
    description='Retrieve the current cart (authenticated user or guest via X-Guest-Token header).',
    responses={
        200: CartSerializer,
        404: OpenApiResponse(description='Cart not found'),
    },
)
class CartDetailView(views.APIView):
    """GET /api/v1/cart/ – View cart."""
    permission_classes = [AllowAny]

    def get(self, request):
        cart = self._resolve_cart(request)
        if cart is None:
            return Response(
                {'detail': 'Cart not found. Add an item to create one.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data)

    @staticmethod
    def _resolve_cart(request):
        """Resolve cart from authenticated user or guest token header."""
        user = request.user if request.user.is_authenticated else None
        guest_token = request.headers.get('X-Guest-Token')
        return CartService.get_cart(user=user, guest_token=guest_token)


# ---------------------------------------------------------------------------
# Add Item
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart'],
    summary='Add Item to Cart',
    description='Add a product variant to the cart. Creates cart if it does not exist.',
    request=AddItemRequestSerializer,
    responses={
        200: CartSerializer,
        201: CartSerializer,
        400: OpenApiResponse(description='Validation error'),
    },
    examples=[
        OpenApiExample(
            'Valid Add',
            summary='Add item to cart',
            value={'variant_id': 101, 'quantity': 2},
            request_only=True,
        ),
    ],
)
class CartAddItemView(views.APIView):
    """POST /api/v1/cart/add/ – Add item to cart."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AddItemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variant_id = serializer.validated_data['variant_id']
        quantity = serializer.validated_data['quantity']

        user = request.user if request.user.is_authenticated else None
        guest_token = request.headers.get('X-Guest-Token')

        cart = CartService._get_or_create_cart(user=user, guest_token=guest_token)

        try:
            CartService.add_item(cart, variant_id, quantity, actor=user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        cart.refresh_from_db()
        cart = (
            Cart.objects
            .filter(pk=cart.pk)
            .prefetch_related('items__product_variant__product')
            .first()
        )
        response_serializer = CartSerializer(cart, context={'request': request})

        # If new guest token was generated, include it
        response_data = response_serializer.data
        if not user and not guest_token:
            response_data['guest_token'] = cart.guest_token

        return Response(response_data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Update Quantity
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart'],
    summary='Update Item Quantity',
    description='Update the quantity of an existing cart item.',
    request=UpdateQuantityRequestSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(description='Validation error'),
        404: OpenApiResponse(description='Cart item not found'),
    },
    examples=[
        OpenApiExample(
            'Update Quantity',
            summary='Set quantity to 5',
            value={'quantity': 5},
            request_only=True,
        ),
    ],
)
class CartUpdateItemView(views.APIView):
    """PUT /api/v1/cart/items/{id}/ – Update item quantity."""
    permission_classes = [AllowAny]

    def put(self, request, item_id):
        cart_item = self._get_cart_item(request, item_id)
        if cart_item is None:
            return Response(
                {'detail': 'Cart item not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UpdateQuantityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data['quantity']

        user = request.user if request.user.is_authenticated else None

        try:
            CartService.update_item(cart_item, quantity, actor=user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        cart_item.cart.refresh_from_db()
        cart = (
            Cart.objects
            .filter(pk=cart_item.cart_id)
            .prefetch_related('items__product_variant__product')
            .first()
        )
        response_serializer = CartSerializer(cart, context={'request': request})
        return Response(response_serializer.data)

    def _get_cart_item(self, request, item_id):
        """Retrieve cart item ensuring ownership."""
        user = request.user if request.user.is_authenticated else None
        guest_token = request.headers.get('X-Guest-Token')

        try:
            cart_item = CartItem.objects.select_related('cart').get(pk=item_id)
        except CartItem.DoesNotExist:
            return None

        if user and cart_item.cart.user_id == user.id:
            return cart_item
        if guest_token and cart_item.cart.guest_token == guest_token:
            return cart_item
        return None


# ---------------------------------------------------------------------------
# Remove Item
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart'],
    summary='Remove Item from Cart',
    description='Remove an item from the cart. Recalculates totals.',
    responses={
        200: CartSerializer,
        404: OpenApiResponse(description='Cart item not found'),
    },
)
class CartRemoveItemView(views.APIView):
    """DELETE /api/v1/cart/items/{id}/delete/ – Remove item from cart."""
    permission_classes = [AllowAny]

    def delete(self, request, item_id):
        cart_item = self._get_cart_item(request, item_id)
        if cart_item is None:
            return Response(
                {'detail': 'Cart item not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        cart_id = cart_item.cart_id
        user = request.user if request.user.is_authenticated else None

        CartService.remove_item(cart_item, actor=user)

        # Return updated cart
        try:
            cart = (
                Cart.objects
                .filter(pk=cart_id)
                .prefetch_related('items__product_variant__product')
                .first()
            )
        except Cart.DoesNotExist:
            return Response(
                {'detail': 'Cart has been removed.'},
                status=status.HTTP_200_OK,
            )

        response_serializer = CartSerializer(cart, context={'request': request})
        return Response(response_serializer.data)

    def _get_cart_item(self, request, item_id):
        user = request.user if request.user.is_authenticated else None
        guest_token = request.headers.get('X-Guest-Token')

        try:
            cart_item = CartItem.objects.select_related('cart').get(pk=item_id)
        except CartItem.DoesNotExist:
            return None

        if user and cart_item.cart.user_id == user.id:
            return cart_item
        if guest_token and cart_item.cart.guest_token == guest_token:
            return cart_item
        return None


# ---------------------------------------------------------------------------
# Coupon Validate
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart – Coupons'],
    summary='Validate Coupon',
    description='Validate a coupon code without applying it to the cart.',
    request=CouponValidateRequestSerializer,
    responses={
        200: CouponValidateResponseSerializer,
        400: OpenApiResponse(description='Invalid coupon'),
    },
    examples=[
        OpenApiExample(
            'Valid Coupon',
            summary='Validate a coupon',
            value={'code': 'SAVE10'},
            request_only=True,
        ),
    ],
)
class CouponValidateView(views.APIView):
    """POST /api/v1/cart/coupons/validate/ – Validate coupon."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CouponValidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code']
        result = CouponValidationService.validate_coupon(code)

        if not result['valid']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Apply Coupon
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart – Coupons'],
    summary='Apply Coupon to Cart',
    description='Apply a validated coupon to the current cart.',
    request=CouponApplyRequestSerializer,
    responses={
        200: CartSerializer,
        400: OpenApiResponse(description='Coupon invalid or cart not found'),
    },
)
class CouponApplyView(views.APIView):
    """POST /api/v1/cart/coupons/apply/ – Apply coupon to cart."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CouponApplyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data['code']

        user = request.user if request.user.is_authenticated else None
        guest_token = request.headers.get('X-Guest-Token')
        cart = CartService.get_cart(user=user, guest_token=guest_token)

        if cart is None:
            return Response(
                {'detail': 'Cart not found. Add an item first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Calculate subtotal for validation
        subtotal = CartService._get_cart_subtotal(cart)
        result = CouponValidationService.validate_coupon(code, subtotal)

        if not result['valid']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        from .models import Coupon
        coupon = Coupon.objects.get(code=code)
        CartService.apply_coupon(cart, coupon, actor=user)

        cart.refresh_from_db()
        cart = (
            Cart.objects
            .filter(pk=cart.pk)
            .prefetch_related('items__product_variant__product')
            .first()
        )
        response_serializer = CartSerializer(cart, context={'request': request})
        return Response(response_serializer.data)


# ---------------------------------------------------------------------------
# Remove Coupon
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Cart – Coupons'],
    summary='Remove Coupon from Cart',
    description='Remove the applied coupon from the cart.',
    responses={
        200: CartSerializer,
        404: OpenApiResponse(description='Cart not found'),
    },
)
class CouponRemoveView(views.APIView):
    """DELETE /api/v1/cart/coupons/ – Remove coupon from cart."""
    permission_classes = [AllowAny]

    def delete(self, request):
        user = request.user if request.user.is_authenticated else None
        guest_token = request.headers.get('X-Guest-Token')
        cart = CartService.get_cart(user=user, guest_token=guest_token)

        if cart is None:
            return Response(
                {'detail': 'Cart not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        CartService.remove_coupon(cart, actor=user)
        cart.refresh_from_db()
        cart = (
            Cart.objects
            .filter(pk=cart.pk)
            .prefetch_related('items__product_variant__product')
            .first()
        )
        response_serializer = CartSerializer(cart, context={'request': request})
        return Response(response_serializer.data)
