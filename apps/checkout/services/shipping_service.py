"""ShippingService – zone-based shipping fee calculation.

Supports:
- Zone-based: Inside Dhaka = 60, Outside Dhaka = 120
- Extensible for weight-based, courier integration, multiple methods.
"""
import logging
from decimal import Decimal
from typing import Optional

from apps.users.models import Address
from apps.cart.models import Cart

logger = logging.getLogger(__name__)

# Dhaka city aliases (case-insensitive matching)
_DHAKA_ALIASES = {
    'dhaka', 'dhaka city', 'dhaka city corporation',
    'dhaka north', 'dhaka south', 'dhanmondi', 'gulshan',
    'banani', 'mirpur', 'uttara', 'motijheel', 'mohammadpur',
    'bashundhara', 'baridhara', 'tejgaon', 'khilgaon',
    'shyamoli', 'jatrabari', 'savar', 'keraniganj',
    'old dhaka', 'puran dhaka',
}


class ShippingService:
    """Calculate shipping fees based on delivery zone."""

    INSIDE_DHAKA_FEE = Decimal('60.00')
    OUTSIDE_DHAKA_FEE = Decimal('120.00')
    FREE_SHIPPING_THRESHOLD = Decimal('0.00')  # Set > 0 to enable free shipping

    @classmethod
    def is_dhaka(cls, city: str) -> bool:
        """Check if the given city string matches Dhaka."""
        if not city:
            return False
        return city.strip().lower() in _DHAKA_ALIASES

    @classmethod
    def calculate(
        cls,
        address: Address,
        cart: Optional[Cart] = None,
        subtotal: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate shipping fee based on delivery address.

        Args:
            address: Delivery address object.
            cart: Optional cart (for future weight-based logic).
            subtotal: Optional subtotal (for free-shipping threshold).

        Returns:
            Decimal shipping fee.
        """
        # Future: implement free shipping above threshold
        if subtotal is not None and cls.FREE_SHIPPING_THRESHOLD > 0:
            if subtotal >= cls.FREE_SHIPPING_THRESHOLD:
                logger.info("Free shipping applied: subtotal %s >= threshold %s",
                            subtotal, cls.FREE_SHIPPING_THRESHOLD)
                return Decimal('0.00')

        city = getattr(address, 'city', '') or ''
        is_dhaka = cls.is_dhaka(city)
        fee = cls.INSIDE_DHAKA_FEE if is_dhaka else cls.OUTSIDE_DHAKA_FEE

        logger.info(
            "Shipping fee calculated: %s for city=%s (dhaka=%s)",
            fee, city, is_dhaka,
        )
        return fee
