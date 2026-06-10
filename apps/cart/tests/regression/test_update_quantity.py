"""CART-REG-003 – Update Cart Quantity Recalculates Totals

PUT /api/v1/cart/items/{id}/ → 200 OK with recalculated totals
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from rest_framework import status

from common.tests.factories import ProductVariantFactory


@pytest.mark.django_db
class TestUpdateQuantityRecalculatesTotals:
    """CART-REG-003: Update cart quantity recalculates totals"""

    def test_update_quantity_updates_item_and_totals(self, api_client):
        """Updating quantity from 1 to 3 recalculates line_total, subtotal, grand_total."""
        # Arrange – create cart with 1 item
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        guest_token = add_data.get('guest_token', '')
        original_subtotal = float(add_data['subtotal'])

        headers = {'X-Guest-Token': guest_token} if guest_token else {}

        # Act – update quantity to 3
        update_url = reverse('cart-update-item', kwargs={'item_id': item_id})
        response = api_client.put(
            update_url,
            {'quantity': 3},
            format='json',
            headers=headers,
        )

        # Assert – HTTP status
        assert response.status_code == status.HTTP_200_OK, (
            f"Expected 200 OK, got {response.status_code}"
        )

        # Assert – item quantity updated
        data = response.json()
        updated_item = data['items'][0]
        assert updated_item['quantity'] == 3, (
            f"Expected quantity 3, got {updated_item['quantity']}"
        )

        # Assert – line total updated (unit_price × quantity)
        expected_line_total = float(updated_item['unit_price']) * 3
        assert abs(float(updated_item['line_total']) - expected_line_total) < 0.01, (
            f"Line total should be {expected_line_total}, got {updated_item['line_total']}"
        )

        # Assert – cart subtotal updated
        new_subtotal = float(data['subtotal'])
        assert new_subtotal > original_subtotal, (
            "Subtotal should increase when quantity increases"
        )

        # Assert – grand total present and consistent
        assert 'grand_total' in data, "Response should include grand_total"
        assert float(data['grand_total']) == float(data['subtotal']), (
            "Grand total should equal subtotal when no coupon applied"
        )

    def test_update_quantity_preserves_guest_token(self, api_client):
        """The guest token is preserved after updating quantity."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        guest_token = add_data['guest_token']

        # Act
        update_url = reverse('cart-update-item', kwargs={'item_id': item_id})
        response = api_client.put(
            update_url,
            {'quantity': 2},
            format='json',
            headers={'X-Guest-Token': guest_token},
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['guest_token'] == guest_token, "Guest token should be preserved"

    def test_update_quantity_below_one_returns_400(self, api_client):
        """Quantity of 0 or less is rejected with 400."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        guest_token = add_data.get('guest_token', '')
        headers = {'X-Guest-Token': guest_token} if guest_token else {}

        # Act
        update_url = reverse('cart-update-item', kwargs={'item_id': item_id})
        response = api_client.put(
            update_url,
            {'quantity': 0},
            format='json',
            headers=headers,
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400 for quantity 0, got {response.status_code}"
        )
