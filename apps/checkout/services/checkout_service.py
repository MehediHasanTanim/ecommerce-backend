"""CheckoutService – order placement with full transactional integrity.

Orchestrates the complete order placement flow using UnitOfWork:
1. Validate user, address, cart
2. Validate inventory
3. Calculate totals
4. Reserve stock
5. Create order + order items
6. Create payment record
7. Clear cart
8. Commit (or rollback on any failure)
"""
import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction

from common.uow import UnitOfWork
from apps.users.models import Address, User
from apps.users.services import create_audit_log
from apps.cart.models import Cart, CartItem, Coupon
from apps.cart.services import CartCalculationService, CartService
from apps.orders.models import Order, OrderItem
from apps.orders.services.order_number_service import OrderNumberService
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.checkout.services.shipping_service import ShippingService
from apps.checkout.selectors.checkout_selector import CheckoutSelector, _DEFAULT_TAX_RATE

logger = logging.getLogger(__name__)


class EmptyCartError(Exception):
    """Raised when attempting to checkout with an empty cart."""


class InvalidAddressError(Exception):
    """Raised when the address does not belong to the user."""


class CheckoutService:
    """Handles the complete order placement flow."""

    @staticmethod
    def validate_checkout(
        user: User,
        cart: Cart,
        address_id: str,
    ) -> tuple[Address, list]:
        """Validate prerequisites for order placement.

        Returns:
            Tuple of (address, validated_items_list).

        Raises:
            EmptyCartError: Cart has no items.
            InvalidAddressError: Address doesn't belong to user.
            ValueError: Product/variant inactive.
            InsufficientStockError: Stock insufficient.
        """
        # Validate address ownership
        try:
            address = Address.objects.get(id=address_id, user=user)
        except Address.DoesNotExist:
            raise InvalidAddressError(
                f"Address {address_id} not found or does not belong to user."
            )

        # Validate cart is not empty
        cart_items = cart.items.all()
        if not cart_items.exists():
            raise EmptyCartError("Cannot checkout with an empty cart.")

        # Validate inventory for all items
        validated = InventoryService.validate_cart_items(cart_items)

        return address, validated

    @staticmethod
    def calculate_order_totals(
        cart: Cart,
        address: Address,
        coupon: Optional[Coupon] = None,
        tax_rate: Optional[Decimal] = None,
    ) -> dict:
        """Calculate all order totals server-side (never trust client).

        Returns:
            dict with subtotal, discount, shipping_fee, tax, grand_total.
        """
        items = cart.items.all()
        subtotal = sum(
            (item.unit_price * item.quantity) for item in items
        )

        discount = Decimal('0.00')
        if coupon:
            discount = CartCalculationService.calculate_discount(subtotal, coupon)

        shipping_fee = ShippingService.calculate(address=address, subtotal=subtotal)

        rate = tax_rate if tax_rate is not None else _DEFAULT_TAX_RATE
        taxable_amount = subtotal - discount
        tax = (taxable_amount * rate).quantize(Decimal('0.01'))

        grand_total = taxable_amount + shipping_fee + tax

        return {
            'subtotal': subtotal,
            'discount': discount,
            'shipping_fee': shipping_fee,
            'tax': tax,
            'grand_total': grand_total,
        }

    @staticmethod
    def place_order(
        user: User,
        cart: Cart,
        address_id: str,
        payment_method: str = 'cod',
        coupon: Optional[Coupon] = None,
        notes: str = '',
    ) -> Order:
        """Place an order with full transactional integrity via UnitOfWork.

        Args:
            user: Authenticated user.
            cart: User's cart with prefetched items.
            address_id: UUID of the shipping address.
            payment_method: Payment method (default: cod).
            coupon: Optional applied coupon.
            notes: Optional order notes.

        Returns:
            The created Order instance.

        Raises:
            EmptyCartError, InvalidAddressError, InsufficientStockError, ValueError.
        """
        # Validate prerequisites
        address, validated_items = CheckoutService.validate_checkout(
            user=user, cart=cart, address_id=address_id,
        )

        # Calculate totals server-side
        totals = CheckoutService.calculate_order_totals(
            cart=cart, address=address, coupon=coupon,
        )

        with UnitOfWork(action_name="place_order"):
            # 1. Reserve stock for all items (select_for_update inside)
            for variant_id, quantity in validated_items:
                InventoryService.reserve_stock(variant_id, quantity)

            # 2. Generate unique order number
            order_number = OrderNumberService.generate()

            # 3. Create order
            order = Order.objects.create(
                order_number=order_number,
                user=user,
                address_snapshot={
                    'id': str(address.id),
                    'name': address.name,
                    'phone': address.phone,
                    'country': address.country,
                    'city': address.city,
                    'area': address.area,
                    'postal_code': address.postal_code,
                    'address_line': address.address_line,
                    'type': address.type,
                },
                status=Order.Status.PENDING,
                payment_status=Order.PaymentStatus.PENDING,
                payment_method=payment_method,
                subtotal=totals['subtotal'],
                discount=totals['discount'],
                shipping_fee=totals['shipping_fee'],
                tax=totals['tax'],
                grand_total=totals['grand_total'],
                notes=notes,
            )

            # 4. Create order items (snapshot product data)
            for item in cart.items.all():
                variant = item.product_variant
                product = variant.product
                unit_price = item.unit_price or variant.effective_price

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    variant=variant,
                    sku=variant.sku,
                    product_name=product.name,
                    variant_name=variant.variant_name,
                    unit_price=unit_price,
                    quantity=item.quantity,
                )

            # 5. Clear the cart
            cart.items.all().delete()
            cart.coupon = None
            cart.save(update_fields=['coupon', 'updated_at'])

            # 6. Audit log
            create_audit_log(
                action='ORDER_CREATED',
                user=user,
                resource_type='Order',
                resource_id=str(order.id),
                metadata={
                    'order_number': order_number,
                    'grand_total': str(totals['grand_total']),
                    'payment_method': payment_method,
                    'item_count': len(validated_items),
                },
            )

            logger.info(
                "Order placed successfully: %s, user=%s, total=%s, items=%s",
                order_number, user.id, totals['grand_total'], len(validated_items),
                extra={
                    'order_number': order_number,
                    'user_id': str(user.id),
                    'event': 'ORDER_CREATED',
                    'status': 'success',
                },
            )

        return order
