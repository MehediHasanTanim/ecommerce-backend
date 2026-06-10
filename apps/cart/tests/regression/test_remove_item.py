"""CART-REG-004 – Remove Cart Item Succeeds

DELETE /api/v1/cart/items/{id}/delete/ → 200 OK with updated cart
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.cart.models import Cart, CartItem
from common.tests.factories import ProductVariantFactory


@pytest.mark.django_db
class TestRemoveCartItemSucceeds:
    """CART-REG-004: Remove cart item succeeds"""

    def test_remove_item_returns_200_with_empty_items(self, api_client):
        """Deleting the only item returns 200 and empty items list."""
        # Arrange – create cart with 1 item
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        guest_token = add_data.get('guest_token', '')
        cart_id = add_data['id']
        headers = {'X-Guest-Token': guest_token} if guest_token else {}

        # Act – remove the item
        delete_url = reverse('cart-remove-item', kwargs={'item_id': item_id})
        response = api_client.delete(delete_url, headers=headers)

        # Assert – HTTP status (API returns 200 with updated cart, not 204)
        assert response.status_code == status.HTTP_200_OK, (
            f"Expected 200 OK, got {response.status_code}"
        )

        # Assert – item removed from response
        data = response.json()
        assert len(data['items']) == 0, "Cart should have zero items after removal"

    def test_remove_item_deletes_from_database(self, api_client):
        """The CartItem is deleted from the database after removal."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        guest_token = add_data.get('guest_token', '')
        headers = {'X-Guest-Token': guest_token} if guest_token else {}

        # Act
        delete_url = reverse('cart-remove-item', kwargs={'item_id': item_id})
        response = api_client.delete(delete_url, headers=headers)

        # Assert – database state
        assert response.status_code == status.HTTP_200_OK
        assert CartItem.objects.count() == 0, "CartItem should be deleted from database"

    def test_remove_item_cart_remains_valid(self, api_client):
        """The Cart itself remains in the database after removing all items."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        cart_id = add_data['id']
        guest_token = add_data.get('guest_token', '')
        headers = {'X-Guest-Token': guest_token} if guest_token else {}

        # Act
        delete_url = reverse('cart-remove-item', kwargs={'item_id': item_id})
        response = api_client.delete(delete_url, headers=headers)

        # Assert – cart still exists
        assert response.status_code == status.HTTP_200_OK
        assert Cart.objects.filter(pk=cart_id).exists(), (
            "Cart should persist after removing its last item"
        )

    def test_remove_item_totals_set_to_zero(self, api_client):
        """After removing the last item, subtotal and grand_total should be 0."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 3},
            format='json',
        )
        add_data = add_resp.json()
        item_id = add_data['items'][0]['id']
        guest_token = add_data.get('guest_token', '')
        headers = {'X-Guest-Token': guest_token} if guest_token else {}

        # Act
        delete_url = reverse('cart-remove-item', kwargs={'item_id': item_id})
        response = api_client.delete(delete_url, headers=headers)

        # Assert – totals zero
        data = response.json()
        assert float(data['subtotal']) == 0.0, (
            f"Subtotal should be 0.00, got {data['subtotal']}"
        )
        assert float(data['grand_total']) == 0.0, (
            f"Grand total should be 0.00, got {data['grand_total']}"
        )

    def test_remove_nonexistent_item_returns_404(self, api_client):
        """Deleting a non-existent item ID returns 404."""
        # Arrange – random UUID that does not exist
        fake_item_id = "00000000-0000-0000-0000-000000000000"

        # Act
        delete_url = reverse('cart-remove-item', kwargs={'item_id': fake_item_id})
        response = api_client.delete(delete_url)

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND, (
            f"Expected 404 for non-existent item, got {response.status_code}"
        )
