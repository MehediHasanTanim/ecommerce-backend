"""CART-REG-005 – Guest Cart Persists by Session

Verifies that a guest cart survives across multiple HTTP requests
using the X-Guest-Token header for session continuity.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from common.tests.factories import ProductVariantFactory


@pytest.mark.django_db
class TestGuestCartPersistenceBySession:
    """CART-REG-005: Guest cart persists by session"""

    def test_guest_cart_same_across_requests(self, api_client):
        """Cart ID and items are the same when retrieved with the same guest token."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Step 1 – Guest adds an item
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )
        add_data = add_resp.json()
        first_cart_id = add_data['id']
        guest_token = add_data['guest_token']
        assert guest_token is not None, "Guest token must be returned on first request"

        # Step 2 – Retrieve cart with guest token
        get_resp_1 = api_client.get(
            reverse('cart-detail'),
            headers={'X-Guest-Token': guest_token},
        )
        assert get_resp_1.status_code == status.HTTP_200_OK

        # Step 3 – Retrieve cart again (simulate new request with same session)
        get_resp_2 = api_client.get(
            reverse('cart-detail'),
            headers={'X-Guest-Token': guest_token},
        )
        assert get_resp_2.status_code == status.HTTP_200_OK

        # Assert – same cart ID across requests
        second_cart_id = get_resp_1.json()['id']
        third_cart_id = get_resp_2.json()['id']
        assert first_cart_id == second_cart_id == third_cart_id, (
            f"Cart ID should be consistent across requests: "
            f"{first_cart_id} / {second_cart_id} / {third_cart_id}"
        )

        # Assert – item count and data preserved
        get_data = get_resp_2.json()
        assert len(get_data['items']) == 1, "Cart should still have 1 item"
        assert get_data['items'][0]['quantity'] == 2, "Item quantity should be 2"

    def test_guest_cart_persists_item_data_unchanged(self, api_client):
        """Item data (variant, quantity, price) is unchanged across GET requests."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)
        add_resp = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 3},
            format='json',
        )
        add_data = add_resp.json()
        guest_token = add_data['guest_token']
        original_item = add_data['items'][0]

        # Act – retrieve multiple times
        for _ in range(3):
            resp = api_client.get(
                reverse('cart-detail'),
                headers={'X-Guest-Token': guest_token},
            )
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()

            # Assert – same item data
            assert len(data['items']) == 1
            item = data['items'][0]
            assert item['variant_id'] == original_item['variant_id'], (
                "Variant ID should be unchanged"
            )
            assert item['quantity'] == original_item['quantity'], (
                "Quantity should be unchanged"
            )
            assert float(item['unit_price']) == float(original_item['unit_price']), (
                "Unit price should be unchanged"
            )

    def test_different_guest_tokens_isolated(self, api_client):
        """Two different guest tokens get completely separate carts."""
        # Arrange – create two guest carts
        v1 = ProductVariantFactory(stock_quantity=10, is_active=True)
        v2 = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Guest 1
        resp1 = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': v1.id, 'quantity': 1},
            format='json',
        )
        token1 = resp1.json()['guest_token']
        cart1_id = resp1.json()['id']

        # Guest 2
        resp2 = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': v2.id, 'quantity': 1},
            format='json',
        )
        token2 = resp2.json()['guest_token']
        cart2_id = resp2.json()['id']

        # Assert – different carts
        assert cart1_id != cart2_id, "Each guest should get a unique cart"
        assert token1 != token2, "Each guest should get a unique token"

        # Assert – each cart has only its own items
        cart1_data = api_client.get(
            reverse('cart-detail'),
            headers={'X-Guest-Token': token1},
        ).json()
        cart2_data = api_client.get(
            reverse('cart-detail'),
            headers={'X-Guest-Token': token2},
        ).json()

        assert cart1_data['items'][0]['variant_id'] == v1.id
        assert cart2_data['items'][0]['variant_id'] == v2.id
