"""OrderService – order lifecycle operations: cancel, list, detail."""
import logging

from django.db import transaction

from apps.users.services import create_audit_log
from apps.orders.models import Order
from apps.orders.selectors.order_selector import OrderSelector
from apps.inventory.services import InventoryService

logger = logging.getLogger(__name__)


class OrderCancellationError(Exception):
    """Raised when an order cannot be cancelled."""


class OrderService:
    """Handles order lifecycle operations."""

    @staticmethod
    def cancel_order(order_id, user) -> Order:
        """Cancel an eligible order and restore reserved stock.

        Allowed statuses: PENDING, CONFIRMED.
        Blocked statuses: SHIPPED, DELIVERED, CANCELLED.

        Args:
            order_id: UUID of the order.
            user: The authenticated user.

        Returns:
            The cancelled Order.

        Raises:
            OrderCancellationError: If order cannot be cancelled.
            Order.DoesNotExist: If order not found.
        """
        # Fetch with ownership check
        order = OrderSelector.get_order_detail(order_id, user)

        if not order.can_cancel:
            raise OrderCancellationError(
                f"Order {order.order_number} cannot be cancelled. "
                f"Current status: {order.status}."
            )

        with transaction.atomic():
            # Restore inventory
            InventoryService.release_order_stock(order)

            # Update order status
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status', 'updated_at'])

            # Audit log
            create_audit_log(
                action='ORDER_CANCELLED',
                user=user,
                resource_type='Order',
                resource_id=str(order.id),
                metadata={
                    'order_number': order.order_number,
                    'previous_status': order.status,
                },
            )

            logger.info(
                "Order cancelled: %s, user=%s",
                order.order_number, user.id,
                extra={
                    'order_number': order.order_number,
                    'user_id': str(user.id),
                    'event': 'ORDER_CANCELLED',
                    'status': 'success',
                },
            )

        return order

    @staticmethod
    def get_order(order_id, user) -> Order:
        """Get order detail with ownership check.

        Returns:
            Order instance with prefetched items.

        Raises:
            Order.DoesNotExist: If not found or not owned by user.
        """
        return OrderSelector.get_order_detail(order_id, user)
