"""Unit tests for OrderService – cancel, restore stock, audit log.

Covers:
- Cancel PENDING order → stock restored
- Cancel CONFIRMED order → stock restored
- Cancel SHIPPED order → blocked
- Cancel DELIVERED order → blocked
- Cancel already CANCELLED order → blocked
- Ownership validation
- Audit log creation
- Order retrieval
"""
from decimal import Decimal

import pytest

from apps.orders.models import Order, OrderItem
from apps.orders.services.order_service import OrderService, OrderCancellationError
from apps.users.models import AuditLog
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
    CartFactory,
    CartItemFactory,
    OrderFactory,
    OrderItemFactory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order(user, variant, status=Order.Status.PENDING, reserved_stock=5):
    """Create a real order with one item, setting variant reserved_stock."""
    variant.reserved_stock = reserved_stock
    variant.save()

    address = AddressFactory(user=user, city='Dhaka', type='shipping')

    order = Order.objects.create(
        order_number=f'ORD-20260611-{Order.objects.count() + 1000:06d}',
        user=user,
        address_snapshot={
            'id': str(address.id), 'name': address.name,
            'phone': address.phone, 'city': address.city,
            'country': address.country, 'area': address.area,
            'postal_code': address.postal_code,
            'address_line': address.address_line,
            'type': address.type,
        },
        status=status,
        payment_status=Order.PaymentStatus.PENDING,
        payment_method='cod',
        subtotal=Decimal('200.00'), discount=Decimal('0.00'),
        shipping_fee=Decimal('60.00'), tax=Decimal('0.00'),
        grand_total=Decimal('260.00'),
    )

    OrderItem.objects.create(
        order=order,
        product=variant.product,
        variant=variant,
        sku=variant.sku,
        product_name=variant.product.name,
        variant_name=variant.variant_name,
        unit_price=Decimal('100.00'),
        quantity=2,
    )

    return order


# ---------------------------------------------------------------------------
# Cancel – Success Cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancelOrderSuccess:

    def test_cancel_pending_order_restores_stock(self):
        """Cancel PENDING → stock restored, status = CANCELLED."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.PENDING, reserved_stock=5)

        cancelled = OrderService.cancel_order(order.id, user)

        assert cancelled.status == Order.Status.CANCELLED
        variant.refresh_from_db()
        assert variant.reserved_stock == 3  # was 5, released 2

    def test_cancel_confirmed_order_restores_stock(self):
        """Cancel CONFIRMED → stock restored."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.CONFIRMED, reserved_stock=10)

        cancelled = OrderService.cancel_order(order.id, user)

        assert cancelled.status == Order.Status.CANCELLED
        variant.refresh_from_db()
        assert variant.reserved_stock == 8  # was 10, released 2

    def test_cancel_creates_audit_log(self):
        """Cancel generates ORDER_CANCELLED audit log."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.PENDING, reserved_stock=5)

        initial_audit_count = AuditLog.objects.filter(action='ORDER_CANCELLED').count()

        OrderService.cancel_order(order.id, user)

        assert AuditLog.objects.filter(action='ORDER_CANCELLED').count() == initial_audit_count + 1

    def test_cancel_full_stock_release(self):
        """All reserved stock for the order is released."""
        variant = ProductVariantFactory(stock_quantity=50, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.PENDING, reserved_stock=2)

        OrderService.cancel_order(order.id, user)

        variant.refresh_from_db()
        assert variant.reserved_stock == 0  # was 2, released exactly 2


# ---------------------------------------------------------------------------
# Cancel – Blocked Cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancelOrderBlocked:

    def test_cancel_shipped_order_blocked(self):
        """SHIPPED orders cannot be cancelled."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.SHIPPED, reserved_stock=5)

        with pytest.raises(OrderCancellationError, match='cannot be cancelled'):
            OrderService.cancel_order(order.id, user)

        # Status unchanged
        order.refresh_from_db()
        assert order.status == Order.Status.SHIPPED

    def test_cancel_delivered_order_blocked(self):
        """DELIVERED orders cannot be cancelled."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.DELIVERED, reserved_stock=5)

        with pytest.raises(OrderCancellationError):
            OrderService.cancel_order(order.id, user)

    def test_cancel_already_cancelled_order_blocked(self):
        """CANCELLED orders cannot be cancelled again."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.CANCELLED, reserved_stock=0)

        with pytest.raises(OrderCancellationError):
            OrderService.cancel_order(order.id, user)

    def test_cancel_processing_order_blocked(self):
        """PROCESSING orders cannot be cancelled."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.PROCESSING, reserved_stock=5)

        with pytest.raises(OrderCancellationError):
            OrderService.cancel_order(order.id, user)

    def test_cancel_order_not_owned(self):
        """Another user cannot cancel someone else's order."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        owner = UserFactory()
        order = _make_order(owner, variant, status=Order.Status.PENDING, reserved_stock=5)

        other_user = UserFactory()
        with pytest.raises(Order.DoesNotExist):
            OrderService.cancel_order(order.id, other_user)


# ---------------------------------------------------------------------------
# Cancel – Stock Integrity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancelStockIntegrity:

    def test_stock_not_double_released(self):
        """Cancelling twice should not work (second call blocked)."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.PENDING, reserved_stock=5)

        # First cancel
        OrderService.cancel_order(order.id, user)
        variant.refresh_from_db()
        reserved_after_first = variant.reserved_stock

        # Second cancel should fail (already CANCELLED)
        with pytest.raises(OrderCancellationError):
            OrderService.cancel_order(order.id, user)

        variant.refresh_from_db()
        assert variant.reserved_stock == reserved_after_first

    def test_multi_item_order_full_release(self):
        """All items in a multi-item order are released."""
        v1 = ProductVariantFactory(stock_quantity=30, reserved_stock=10)
        v2 = ProductVariantFactory(stock_quantity=30, reserved_stock=8)

        user = UserFactory()
        address = AddressFactory(user=user, city='Dhaka', type='shipping')

        order = Order.objects.create(
            order_number='ORD-20260611-009999',
            user=user,
            address_snapshot={
                'id': str(address.id), 'name': address.name,
                'city': address.city, 'country': address.country,
                'address_line': address.address_line, 'type': address.type,
            },
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.PENDING,
            payment_method='cod',
            subtotal=Decimal('500.00'), discount=Decimal('0.00'),
            shipping_fee=Decimal('60.00'), tax=Decimal('0.00'),
            grand_total=Decimal('560.00'),
        )

        OrderItem.objects.create(
            order=order, product=v1.product, variant=v1,
            sku=v1.sku, product_name=v1.product.name,
            variant_name=v1.variant_name,
            unit_price=Decimal('100.00'), quantity=3,
        )
        OrderItem.objects.create(
            order=order, product=v2.product, variant=v2,
            sku=v2.sku, product_name=v2.product.name,
            variant_name=v2.variant_name,
            unit_price=Decimal('100.00'), quantity=2,
        )

        OrderService.cancel_order(order.id, user)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.reserved_stock == 7   # 10 - 3
        assert v2.reserved_stock == 6   # 8 - 2


# ---------------------------------------------------------------------------
# Order Detail Retrieval
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderRetrieval:

    def test_get_order_with_items(self):
        """get_order returns order with prefetched items."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        user = UserFactory()
        order = _make_order(user, variant, status=Order.Status.PENDING, reserved_stock=3)

        retrieved = OrderService.get_order(order.id, user)
        assert retrieved.id == order.id
        assert retrieved.items.count() == 1

    def test_get_order_not_found(self):
        """Nonexistent order raises DoesNotExist."""
        user = UserFactory()
        with pytest.raises(Order.DoesNotExist):
            OrderService.get_order('00000000-0000-0000-0000-000000000000', user)

    def test_get_order_wrong_owner(self):
        """Order not visible to another user."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0, is_active=True)
        owner = UserFactory()
        order = _make_order(owner, variant, status=Order.Status.PENDING, reserved_stock=3)

        other_user = UserFactory()
        with pytest.raises(Order.DoesNotExist):
            OrderService.get_order(order.id, other_user)
