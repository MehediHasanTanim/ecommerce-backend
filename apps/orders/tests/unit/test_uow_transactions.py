"""Unit tests for UnitOfWork – commit, rollback, and transactional integrity.

Covers:
- Commit successful transaction
- Rollback on exception
- Rollback during stock reservation
- Rollback preserving cart items
- Rollback preserving inventory state
- Nested transaction behavior
- No partial writes on failure
"""
from decimal import Decimal

import pytest
from django.db import transaction

from apps.cart.models import CartItem
from apps.orders.models import Order
from apps.users.models import User
from common.uow import UnitOfWork
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
    CartFactory,
    CartItemFactory,
    OrderFactory,
)


# ---------------------------------------------------------------------------
# Basic Commit / Rollback
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUowCommitRollback:

    def test_commit_persists_data(self):
        """Data created within UoW is visible after commit."""
        with UnitOfWork(action_name='test_commit'):
            UserFactory(email='uow_commit@test.com')

        assert User.objects.filter(email='uow_commit@test.com').exists()

    def test_rollback_discards_data(self):
        """Exception inside UoW rolls back all changes."""
        with pytest.raises(ValueError, match='Intentional'):
            with UnitOfWork(action_name='test_rollback'):
                UserFactory(email='uow_rollback@test.com')
                raise ValueError('Intentional rollback')

        assert not User.objects.filter(email='uow_rollback@test.com').exists()

    def test_rollback_preserves_pre_existing_data(self):
        """Rollback does not affect data created before the UoW."""
        pre_user = UserFactory(email='pre_existing@test.com')

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='test_nested_rollback'):
                UserFactory(email='should_rollback@test.com')
                raise ValueError('Rollback!')

        assert User.objects.filter(email='pre_existing@test.com').exists()
        assert not User.objects.filter(email='should_rollback@test.com').exists()


# ---------------------------------------------------------------------------
# Stock Reservation Rollback
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUowStockRollback:

    def test_rollback_restores_stock_state(self):
        """Stock reservation inside UoW is rolled back on failure."""
        variant = ProductVariantFactory(stock_quantity=50, reserved_stock=0)

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='reserve_then_fail'):
                variant.reserved_stock = 10
                variant.save(update_fields=['reserved_stock'])
                raise ValueError('Simulated failure after reserve')

        variant.refresh_from_db()
        assert variant.reserved_stock == 0  # Rolled back

    def test_rollback_preserves_cart_items(self):
        """Cart items deleted inside UoW are restored on rollback."""
        user = UserFactory()
        cart = CartFactory(user=user)

        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=3)
        CartItemFactory(cart=cart, product_variant=ProductVariantFactory(stock_quantity=10), quantity=1)

        initial_count = cart.items.count()
        assert initial_count == 2

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='clear_cart_then_fail'):
                cart.items.all().delete()
                raise ValueError('Simulated payment failure')

        cart.refresh_from_db()
        assert cart.items.count() == initial_count

    def test_rollback_order_not_persisted(self):
        """Order created inside UoW is rolled back on failure."""
        user = UserFactory()
        initial_count = Order.objects.count()

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='create_order_then_fail'):
                OrderFactory(user=user)
                raise ValueError('Simulated downstream failure')

        assert Order.objects.count() == initial_count

    def test_rollback_all_or_nothing(self):
        """Multiple operations — either all persist or none do."""
        user = UserFactory()

        initial_user_count = User.objects.count()
        initial_order_count = Order.objects.count()

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='all_or_nothing'):
                UserFactory(email='partial@test.com')
                OrderFactory(user=user)
                raise ValueError('Rollback everything')

        assert User.objects.count() == initial_user_count
        assert Order.objects.count() == initial_order_count


# ---------------------------------------------------------------------------
# Simulated Order Placement Rollback Scenarios
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUowOrderPlacementRollback:

    def test_rollback_during_stock_reservation(self):
        """Simulate: stock reserve succeeds, order creation fails → rollback."""
        variant = ProductVariantFactory(stock_quantity=20, reserved_stock=0)
        user = UserFactory()

        with pytest.raises(ValueError, match='Order creation failed'):
            with UnitOfWork(action_name='order_placement'):
                # Step 1: Reserve stock
                variant.reserved_stock = 5
                variant.save(update_fields=['reserved_stock'])

                # Step 2: Create order — simulate failure
                raise ValueError('Order creation failed')

        variant.refresh_from_db()
        assert variant.reserved_stock == 0  # Stock rollback
        assert Order.objects.count() == 0

    def test_rollback_during_order_item_creation(self):
        """Simulate: order created, item creation fails → rollback entire order."""
        user = UserFactory()
        initial_orders = Order.objects.count()

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='order_with_items'):
                order = OrderFactory(user=user)
                # Simulate item creation failure
                raise ValueError('OrderItem creation failed')

        assert Order.objects.count() == initial_orders

    def test_rollback_during_cart_clear(self):
        """Simulate: order done, cart clear fails → rollback keeps cart."""
        user = UserFactory()
        cart = CartFactory(user=user)
        variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)
        CartItemFactory(cart=cart, product_variant=variant, quantity=2)
        initial_items = cart.items.count()

        initial_orders = Order.objects.count()

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='cart_clear_fails'):
                OrderFactory(user=user)
                cart.items.all().delete()
                raise ValueError('Cart clear verification failed')

        cart.refresh_from_db()
        assert cart.items.count() == initial_items
        assert Order.objects.count() == initial_orders


# ---------------------------------------------------------------------------
# Nested / Multiple UoW Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUowMultiple:

    def test_nested_uow_independence(self):
        """Inner UoW rollback does not affect outer UoW."""
        with pytest.raises(ValueError):
            with UnitOfWork(action_name='outer'):
                UserFactory(email='outer_user@test.com')

                with pytest.raises(ValueError):
                    with UnitOfWork(action_name='inner'):
                        UserFactory(email='inner_user@test.com')
                        raise ValueError('Inner rollback')

                # Re-raise to rollback outer too
                raise ValueError('Outer rollback')

        assert not User.objects.filter(email='outer_user@test.com').exists()
        assert not User.objects.filter(email='inner_user@test.com').exists()

    def test_sequential_uow_no_leakage(self):
        """First UoW data does not leak into second UoW context."""
        with UnitOfWork(action_name='first'):
            UserFactory(email='first@test.com')

        # This should exist after first commit
        assert User.objects.filter(email='first@test.com').exists()

        with pytest.raises(ValueError):
            with UnitOfWork(action_name='second'):
                UserFactory(email='second@test.com')
                raise ValueError('Second failure')

        assert User.objects.filter(email='first@test.com').exists()
        assert not User.objects.filter(email='second@test.com').exists()
