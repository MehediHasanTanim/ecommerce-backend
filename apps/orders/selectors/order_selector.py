"""OrderSelector – read-side queries for orders."""
import logging
from typing import Optional

from django.db.models import QuerySet

from apps.orders.models import Order

logger = logging.getLogger(__name__)


class OrderSelector:
    """Read-only order queries."""

    @staticmethod
    def list_orders(
        user,
        status: Optional[str] = None,
        ordering: str = '-created_at',
    ) -> QuerySet:
        """Return a queryset of orders for the given user, with optional status filter.

        Args:
            user: The authenticated user.
            status: Optional status filter value.
            ordering: Field to order by (default: newest first).

        Returns:
            Filtered QuerySet of orders.
        """
        qs = (
            Order.objects
            .filter(user=user)
            .prefetch_related('items__product', 'items__variant')
            .order_by(ordering)
        )

        if status:
            qs = qs.filter(status=status)

        logger.info(
            "Orders listed for user=%s, status=%s, count=%s",
            user.id, status or 'all', qs.count(),
        )
        return qs

    @staticmethod
    def get_order_detail(order_id, user) -> Order:
        """Get a single order with all related data for the given user.

        Args:
            order_id: UUID of the order.
            user: The authenticated user (for ownership check).

        Returns:
            Order instance.

        Raises:
            Order.DoesNotExist: If order not found or not owned by user.
        """
        return (
            Order.objects
            .filter(id=order_id, user=user)
            .prefetch_related('items__product', 'items__variant')
            .get()
        )
