"""CART-REG-001 & CART-REG-002 – Add Item Regression Tests

CART-REG-001: Add item to cart succeeds → 201 Created
CART-REG-002: Add item above stock fails → 400 Bad Request
"""
import pytest
from django.urls import reverse
from rest_framework import status

from common.tests.factories import ProductVariantFactory


@pytest.mark.django_db
class TestAddItemSucceeds:
    """CART-REG-001: Add item to cart succeeds"""

    def test_add_item_returns_201_with_correct_item_data(self, api_client):
        """POST /api/v1/cart/add/ with valid payload returns 201 and cart data."""
        # Arrange – active variant with sufficient stock
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Act
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 2},
            format='json',
        )

        # Assert – HTTP status
        assert response.status_code == status.HTTP_201_CREATED, (
            f"Expected 201 Created, got {response.status_code}"
        )

        # Assert – response body
        data = response.json()
        assert 'items' in data, "Response should contain 'items' array"
        assert len(data['items']) == 1, "Cart should contain exactly 1 item"
        assert data['items'][0]['variant_id'] == variant.id, (
            "Item should reference the correct variant"
        )
        assert data['items'][0]['quantity'] == 2, (
            f"Item quantity should be 2, got {data['items'][0]['quantity']}"
        )

    def test_add_item_creates_cart_in_database(self, api_client):
        """Adding the first item creates a persistent Cart and CartItem in the database."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Act
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 1},
            format='json',
        )

        # Assert – database state
        from apps.cart.models import Cart, CartItem
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        cart_id = data['id']
        assert Cart.objects.filter(pk=cart_id).exists(), "Cart should exist in database"
        assert CartItem.objects.filter(cart_id=cart_id).count() == 1, (
            "Exactly 1 CartItem should exist for the cart"
        )

    def test_add_item_recalculates_totals(self, api_client):
        """Cart totals (subtotal, grand_total) are calculated after adding an item."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=10, is_active=True)

        # Act
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 3},
            format='json',
        )

        # Assert – totals in response
        data = response.json()
        assert 'subtotal' in data, "Response should include subtotal"
        assert 'grand_total' in data, "Response should include grand_total"
        assert float(data['subtotal']) > 0, "Subtotal should be greater than 0"


@pytest.mark.django_db
class TestAddItemAboveStockFails:
    """CART-REG-002: Add item above stock fails"""

    def test_add_item_above_stock_returns_400(self, api_client):
        """POST /api/v1/cart/add/ with quantity > stock returns 400."""
        # Arrange – variant with limited stock
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)

        # Act
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 10},
            format='json',
        )

        # Assert – HTTP status
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400 Bad Request, got {response.status_code}"
        )

    def test_add_item_above_stock_error_contains_stock_message(self, api_client):
        """Error response mentions stock limit."""
        # Arrange
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)

        # Act
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 10},
            format='json',
        )

        # Assert – error message
        data = response.json()
        # Error format is {'detail': '...'} from the view
        error_text = str(data).lower()
        assert 'stock' in error_text or 'exceed' in error_text, (
            f"Error should mention stock limit, got: {data}"
        )

    def test_add_item_above_stock_does_not_modify_database(self, api_client):
        """No CartItem is created when stock validation fails."""
        # Arrange
        from apps.cart.models import CartItem
        variant = ProductVariantFactory(stock_quantity=5, is_active=True)
        initial_count = CartItem.objects.count()

        # Act
        response = api_client.post(
            reverse('cart-add-item'),
            {'variant_id': variant.id, 'quantity': 10},
            format='json',
        )

        # Assert – database unchanged
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert CartItem.objects.count() == initial_count, (
            "No new CartItem should be created on failed add"
        )
