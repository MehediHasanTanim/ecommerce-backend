"""API views for Checkout: summary & order placement."""
import logging

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from apps.cart.models import Cart
from apps.cart.services import CartService
from apps.checkout.selectors.checkout_selector import CheckoutSelector
from apps.checkout.services.checkout_service import (
    CheckoutService, EmptyCartError, InvalidAddressError,
)
from apps.inventory.services import InsufficientStockError
from apps.checkout.serializers import (
    CheckoutSummaryResponseSerializer,
    PlaceOrderRequestSerializer,
    PlaceOrderResponseSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkout Summary
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Checkout'],
    summary='Get Checkout Summary',
    description=(
        'Calculate and return cart items, product info, subtotal, discount, '
        'shipping fee, tax, and grand total. '
        'User must be authenticated and cart must not be empty.'
    ),
    responses={
        200: CheckoutSummaryResponseSerializer,
        400: OpenApiResponse(description='Cart is empty or invalid'),
        401: OpenApiResponse(description='Authentication required'),
    },
)
class CheckoutSummaryView(views.APIView):
    """GET /api/v1/checkout/summary/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        cart = CartService.get_cart(user=user)

        if cart is None or not cart.items.exists():
            return Response(
                {'detail': 'Cart is empty. Add items before checkout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the default shipping address or first address
        address = user.addresses.filter(is_default=True, type='shipping').first()
        if address is None:
            address = user.addresses.filter(type='shipping').first()

        if address is None:
            return Response(
                {'detail': 'No shipping address found. Please add an address first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon = cart.coupon if hasattr(cart, 'coupon') else None

        try:
            summary = CheckoutSelector.get_checkout_summary(
                cart=cart, address=address, coupon=coupon,
            )
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InsufficientStockError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(summary, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Place Order
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Checkout'],
    summary='Place Order',
    description=(
        'Place an order from the current cart. '
        'Validates cart, address, inventory, calculates totals, '
        'reserves stock, creates order, and clears cart in a single transaction.'
    ),
    request=PlaceOrderRequestSerializer,
    responses={
        201: PlaceOrderResponseSerializer,
        400: OpenApiResponse(description='Validation error / empty cart / insufficient stock'),
        401: OpenApiResponse(description='Authentication required'),
    },
    examples=[
        OpenApiExample(
            'Place COD Order',
            summary='Place a cash-on-delivery order',
            value={'address_id': '550e8400-e29b-41d4-a716-446655440000', 'payment_method': 'cod'},
            request_only=True,
        ),
    ],
)
class PlaceOrderView(views.APIView):
    """POST /api/v1/checkout/place-order/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PlaceOrderRequestSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        address_id = serializer.validated_data['address_id']
        payment_method = serializer.validated_data['payment_method']
        notes = serializer.validated_data.get('notes', '')

        user = request.user
        cart = CartService.get_cart(user=user)

        if cart is None or not cart.items.exists():
            return Response(
                {'detail': 'Cart is empty. Add items before placing an order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon = cart.coupon if hasattr(cart, 'coupon') else None

        try:
            order = CheckoutService.place_order(
                user=user,
                cart=cart,
                address_id=str(address_id),
                payment_method=payment_method,
                coupon=coupon,
                notes=notes,
            )
        except EmptyCartError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidAddressError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InsufficientStockError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'grand_total': str(order.grand_total),
            },
            status=status.HTTP_201_CREATED,
        )
