"""API regression tests for Wishlist endpoints.

WISH-REG-001: Wishlist add/remove works
"""
import pytest
from django.urls import reverse
from rest_framework import status

from common.tests.factories import ProductFactory


@pytest.mark.django_db
class TestWishlistRegression:
    """WISH-REG-001"""

    def test_add_and_remove_wishlist_item(self, authenticated_client):
        """WISH-REG-001: Add then remove a wishlist item."""
        product = ProductFactory(is_active=True)

        # Add to wishlist
        add_resp = authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )
        assert add_resp.status_code == 201
        data = add_resp.json()
        assert data['product_id'] == product.id

        # Remove from wishlist
        remove_resp = authenticated_client.delete(
            reverse('wishlist-remove', kwargs={'product_id': product.id}),
        )
        assert remove_resp.status_code == 204

    def test_list_wishlist_returns_items(self, authenticated_client):
        """List wishlist returns user's items."""
        p1 = ProductFactory(is_active=True)
        p2 = ProductFactory(is_active=True)

        authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': p1.id},
            format='json',
        )
        authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': p2.id},
            format='json',
        )

        resp = authenticated_client.get(reverse('wishlist-list'))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_duplicate_wishlist_blocked(self, authenticated_client):
        """Duplicate product in wishlist returns 400."""
        product = ProductFactory(is_active=True)
        authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )
        resp = authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )
        assert resp.status_code == 400

    def test_wishlist_requires_auth(self, api_client):
        """Wishlist endpoints require authentication."""
        resp = api_client.get(reverse('wishlist-list'))
        assert resp.status_code == 401

    def test_remove_nonexistent_wishlist_item(self, authenticated_client):
        """Removing non-existent wishlist item returns 404."""
        resp = authenticated_client.delete(
            reverse('wishlist-remove', kwargs={'product_id': 99999}),
        )
        assert resp.status_code == 404
