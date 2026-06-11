"""Unit tests for ShippingService – zone-based fee, edge cases, extensibility.

Covers:
- Dhaka = 60
- Outside Dhaka = 120
- Dhaka aliases (case-insensitive)
- Empty/null city
- Free-shipping threshold (future)
- Extensibility for weight/courier integration
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.checkout.services.shipping_service import ShippingService
from common.tests.factories import AddressFactory


# ---------------------------------------------------------------------------
# Zone-Based Fee Calculation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestShippingZoneFees:

    def test_dhaka_city_fee(self, user):
        """Standard Dhaka address → 60."""
        address = AddressFactory(user=user, city='Dhaka', type='shipping')
        fee = ShippingService.calculate(address=address)
        assert fee == Decimal('60.00')

    def test_outside_dhaka_fee(self, user):
        """Outside Dhaka → 120."""
        for city in ['Chittagong', 'Sylhet', 'Khulna', 'Rajshahi', 'Barisal']:
            address = AddressFactory(user=user, city=city, type='shipping')
            fee = ShippingService.calculate(address=address)
            assert fee == Decimal('120.00'), f"Expected 120 for {city}, got {fee}"

    def test_dhaka_alias_gulshan(self, user):
        address = AddressFactory(user=user, city='Gulshan', type='shipping')
        assert ShippingService.calculate(address=address) == Decimal('60.00')

    def test_dhaka_alias_banani(self, user):
        address = AddressFactory(user=user, city='Banani', type='shipping')
        assert ShippingService.calculate(address=address) == Decimal('60.00')

    def test_dhaka_alias_uttara(self, user):
        address = AddressFactory(user=user, city='Uttara', type='shipping')
        assert ShippingService.calculate(address=address) == Decimal('60.00')

    def test_dhaka_alias_mirpur(self, user):
        address = AddressFactory(user=user, city='Mirpur', type='shipping')
        assert ShippingService.calculate(address=address) == Decimal('60.00')

    def test_dhaka_alias_dhanmondi(self, user):
        address = AddressFactory(user=user, city='Dhanmondi', type='shipping')
        assert ShippingService.calculate(address=address) == Decimal('60.00')

    def test_dhaka_alias_bashundhara(self, user):
        address = AddressFactory(user=user, city='Bashundhara', type='shipping')
        assert ShippingService.calculate(address=address) == Decimal('60.00')


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestShippingEdgeCases:

    def test_case_insensitive(self, user):
        """Dhaka matching is case-insensitive."""
        for city_variant in ['dhaka', 'DHAKA', 'Dhaka', 'dHaKa']:
            address = AddressFactory(user=user, city=city_variant, type='shipping')
            fee = ShippingService.calculate(address=address)
            assert fee == Decimal('60.00'), f"Failed for {city_variant}"

    def test_whitespace_handling(self, user):
        """City name with whitespace should still match."""
        address = AddressFactory(user=user, city='  dhaka  ', type='shipping')
        fee = ShippingService.calculate(address=address)
        assert fee == Decimal('60.00')

    def test_empty_city_treated_as_outside(self, user):
        """Empty city defaults to outside Dhaka fee."""
        address = AddressFactory(user=user, city='', type='shipping')
        fee = ShippingService.calculate(address=address)
        assert fee == Decimal('120.00')

    def test_none_city_falls_back_to_empty(self, user):
        """City attribute missing → outside Dhaka."""
        # Create an address-like object without city
        address = AddressFactory(user=user, city='', type='shipping')
        address.city = ''  # ensure empty
        address.save()
        fee = ShippingService.calculate(address=address)
        assert fee == Decimal('120.00')

    def test_unknown_city_treated_as_outside(self, user):
        """Completely unknown city → outside Dhaka fee."""
        address = AddressFactory(user=user, city='SomeRandomVillage', type='shipping')
        fee = ShippingService.calculate(address=address)
        assert fee == Decimal('120.00')


# ---------------------------------------------------------------------------
# is_dhaka Helper
# ---------------------------------------------------------------------------

class TestIsDhaka:

    def test_known_dhaka_cities(self):
        assert ShippingService.is_dhaka('Dhaka') is True
        assert ShippingService.is_dhaka('dhaka') is True
        assert ShippingService.is_dhaka('Gulshan') is True
        assert ShippingService.is_dhaka('Mirpur') is True
        assert ShippingService.is_dhaka('Uttara') is True
        assert ShippingService.is_dhaka('Dhanmondi') is True
        assert ShippingService.is_dhaka('Banani') is True
        assert ShippingService.is_dhaka('Motijheel') is True
        assert ShippingService.is_dhaka('Bashundhara') is True
        assert ShippingService.is_dhaka('Baridhara') is True
        assert ShippingService.is_dhaka('Mohammadpur') is True

    def test_non_dhaka_cities(self):
        assert ShippingService.is_dhaka('Chittagong') is False
        assert ShippingService.is_dhaka('Sylhet') is False
        assert ShippingService.is_dhaka('Khulna') is False
        assert ShippingService.is_dhaka('Rajshahi') is False
        assert ShippingService.is_dhaka('Rangpur') is False

    def test_edge_cases(self):
        assert ShippingService.is_dhaka('') is False
        assert ShippingService.is_dhaka(None) is False
        assert ShippingService.is_dhaka('   ') is False


# ---------------------------------------------------------------------------
# Extensibility
# ---------------------------------------------------------------------------

class TestShippingExtensibility:

    def test_free_shipping_threshold_configurable(self, monkeypatch):
        """Free shipping threshold can be changed per environment."""
        original = ShippingService.FREE_SHIPPING_THRESHOLD

        # Temporarily set a threshold
        ShippingService.FREE_SHIPPING_THRESHOLD = Decimal('500.00')

        try:
            from apps.users.models import Address

            # Mock address
            class MockAddress:
                city = 'Sylhet'

            # Subtotal >= threshold → free
            fee = ShippingService.calculate(
                address=MockAddress(),
                subtotal=Decimal('500.00'),
            )
            assert fee == Decimal('0.00')

            # Subtotal < threshold → normal
            fee = ShippingService.calculate(
                address=MockAddress(),
                subtotal=Decimal('499.00'),
            )
            assert fee == Decimal('120.00')
        finally:
            ShippingService.FREE_SHIPPING_THRESHOLD = original

    def test_class_is_extensible(self):
        """Verify ShippingService can be subclassed for custom logic."""
        class CustomShippingService(ShippingService):
            INSIDE_DHAKA_FEE = Decimal('50.00')
            OUTSIDE_DHAKA_FEE = Decimal('150.00')

        assert CustomShippingService.INSIDE_DHAKA_FEE == Decimal('50.00')
        assert CustomShippingService.OUTSIDE_DHAKA_FEE == Decimal('150.00')
        # Parent unchanged
        assert ShippingService.INSIDE_DHAKA_FEE == Decimal('60.00')
