"""CheckoutSelector – read-side queries for the checkout flow."""
import logging
from decimal import Decimal
from typing import Optional

from apps.cart.models import Cart, CartItem, Coupon
from apps.cart.services import CartCalculationService
from apps.users.models import Address
from apps.checkout.services.shipping_service import ShippingService

logger = logging.getLogger(__name__)

# Tax rate (configurable; in production, this would come from settings or a tax service)
_DEFAULT_TAX_RATE = Decimal('0.00')  # 0% tax; set to e.g. 0.15 for 15%


class CheckoutSelector:
    """Read-only operations for the checkout summary."""

    @staticmethod
    def get_checkout_summary(
        cart: Cart,
        address: Address,
        coupon: Optional[Coupon] = None,
        tax_rate: Optional[Decimal] = None,
    ) -> dict:
        """Build the checkout summary response.

        Args:
            cart: The user's cart with prefetched items.
            address: The delivery address.
            coupon: Optional applied coupon.
            tax_rate: Tax rate as decimal (0.15 = 15%). Defaults to 0.00.

        Returns:
            dict with items, subtotal, discount, shipping_fee, tax, grand_total.
        """
        items = cart.items.all() if hasattr(cart.items, 'all') else cart.items

        # Build line items
        line_items = []
        subtotal = Decimal('0.00')

        for item in items:
            variant = item.product_variant
            product = variant.product
            unit_price = item.unit_price or variant.effective_price
            line_total = unit_price * item.quantity
            subtotal += line_total

            line_items.append({
                'product_id': str(product.id),
                'product_name': product.name,
                'variant_id': str(variant.id),
                'variant_name': variant.variant_name,
                'sku': variant.sku,
                'quantity': item.quantity,
                'unit_price': str(unit_price),
                'line_total': str(line_total),
                'stock_available': variant.available_stock,
            })

        # Discount from coupon
        discount = Decimal('0.00')
        if coupon:
            discount = CartCalculationService.calculate_discount(subtotal, coupon)

        # Shipping
        shipping_fee = ShippingService.calculate(address=address, subtotal=subtotal)

        # Tax (on subtotal after discount)
        rate = tax_rate if tax_rate is not None else _DEFAULT_TAX_RATE
        taxable_amount = subtotal - discount
        tax = (taxable_amount * rate).quantize(Decimal('0.01'))

        # Grand total
        grand_total = taxable_amount + shipping_fee + tax

        logger.info(
            "Checkout summary: subtotal=%s, discount=%s, shipping=%s, tax=%s, grand_total=%s",
            subtotal, discount, shipping_fee, tax, grand_total,
        )

        return {
            'items': line_items,
            'subtotal': str(subtotal),
            'discount': str(discount),
            'shipping_fee': str(shipping_fee),
            'tax': str(tax),
            'grand_total': str(grand_total),
        }
