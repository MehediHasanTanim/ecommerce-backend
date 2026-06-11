"""API views for Orders: list, detail, cancel, invoice."""
import logging
from io import BytesIO

from django.http import HttpResponse
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from apps.orders.models import Order
from apps.orders.selectors.order_selector import OrderSelector
from apps.orders.services.order_service import OrderService, OrderCancellationError
from apps.orders.services.invoice_service import InvoiceService
from apps.checkout.serializers import (
    OrderListSerializer,
    OrderDetailSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Order List
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Orders'],
    summary='List Orders',
    description=(
        'Return paginated list of orders for the authenticated user. '
        'Supports status filtering and sorting.'
    ),
    parameters=[
        OpenApiParameter(
            name='status',
            description='Filter by order status (pending, confirmed, processing, shipped, delivered, cancelled)',
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name='ordering',
            description='Sort order (default: -created_at)',
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name='page',
            description='Page number for pagination',
            required=False,
            type=int,
        ),
        OpenApiParameter(
            name='page_size',
            description='Number of items per page (default: 20)',
            required=False,
            type=int,
        ),
    ],
    responses={
        200: OrderListSerializer(many=True),
        401: OpenApiResponse(description='Authentication required'),
    },
)
class OrderListView(views.APIView):
    """GET /api/v1/orders/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status')
        ordering = request.query_params.get('ordering', '-created_at')
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))

        qs = OrderSelector.list_orders(
            user=request.user,
            status=status_filter,
            ordering=ordering,
        )

        # Manual pagination
        total = qs.count()
        offset = (page - 1) * page_size
        orders = qs[offset:offset + page_size]

        serializer = OrderListSerializer(orders, many=True)

        return Response({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': serializer.data,
        })


# ---------------------------------------------------------------------------
# Order Detail
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Orders'],
    summary='Get Order Detail',
    description=(
        'Return full order details including items, address snapshot, payment status.'
    ),
    responses={
        200: OrderDetailSerializer,
        401: OpenApiResponse(description='Authentication required'),
        404: OpenApiResponse(description='Order not found'),
    },
)
class OrderDetailView(views.APIView):
    """GET /api/v1/orders/{id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = OrderService.get_order(pk, request.user)
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Cancel Order
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Orders'],
    summary='Cancel Order',
    description=(
        'Cancel an eligible order (status PENDING or CONFIRMED). '
        'Restores reserved stock. Orders with status SHIPPED or DELIVERED cannot be cancelled.'
    ),
    responses={
        200: OrderDetailSerializer,
        400: OpenApiResponse(description='Order cannot be cancelled'),
        401: OpenApiResponse(description='Authentication required'),
        404: OpenApiResponse(description='Order not found'),
    },
)
class OrderCancelView(views.APIView):
    """POST /api/v1/orders/{id}/cancel/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            order = OrderService.cancel_order(pk, request.user)
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OrderCancellationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Invoice Download
# ---------------------------------------------------------------------------

@extend_schema(
    tags=['Orders'],
    summary='Download Invoice',
    description=(
        'Generate and download a PDF invoice for the order. '
        'Cached after first generation.'
    ),
    responses={
        200: OpenApiResponse(description='PDF invoice file', response=None),
        401: OpenApiResponse(description='Authentication required'),
        404: OpenApiResponse(description='Order not found'),
        500: OpenApiResponse(description='Invoice generation failed'),
    },
)
class OrderInvoiceView(views.APIView):
    """GET /api/v1/orders/{id}/invoice/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            order = OrderService.get_order(pk, request.user)
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            pdf_bytes, is_cached = InvoiceService.get_or_generate_invoice(
                order, user=request.user,
            )
        except ImportError as e:
            logger.error("Invoice generation failed: %s", str(e))
            return Response(
                {'detail': 'Invoice generation is not available. Please contact support.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error("Invoice generation error: %s", str(e), exc_info=True)
            return Response(
                {'detail': 'Failed to generate invoice.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="invoice-{order.order_number}.pdf"'
        )
        return response
