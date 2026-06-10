"""WISH-REG-001 – Wishlist Add/Remove Works

POST /api/v1/wishlist/add/ → 201 Created
DELETE /api/v1/wishlist/{product_id}/ → 204 No Content
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.wishlist.models import WishlistItem
from common.tests.factories import ProductFactory, UserFactory


@pytest.mark.django_db
class TestWishlistAddWorks:
    """WISH-REG-001 – Add to wishlist"""

    def test_add_to_wishlist_returns_201(self, authenticated_client):
        """Adding a product to wishlist returns 201 Created with item data."""
        # Arrange
        product = ProductFactory(is_active=True)

        # Act
        response = authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )

        # Assert – HTTP status
        assert response.status_code == status.HTTP_201_CREATED, (
            f"Expected 201 Created, got {response.status_code}"
        )

        # Assert – response body
        data = response.json()
        assert data['product_id'] == product.id, (
            f"Response should reference product {product.id}"
        )

    def test_add_to_wishlist_creates_database_record(self, authenticated_client):
        """WishlistItem record is created in the database."""
        # Arrange
        product = ProductFactory(is_active=True)

        # Act
        response = authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )

        # Assert – database
        assert response.status_code == status.HTTP_201_CREATED
        assert WishlistItem.objects.count() == 1, (
            "Exactly 1 WishlistItem should exist"
        )
        item = WishlistItem.objects.first()
        assert item.product_id == product.id
        assert item.user == authenticated_client.handler._force_user

    def test_duplicate_wishlist_blocked_returns_400(self, authenticated_client):
        """Adding the same product twice returns 400."""
        # Arrange
        product = ProductFactory(is_active=True)
        authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )

        # Act
        response = authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400 for duplicate, got {response.status_code}"
        )

    def test_wishlist_requires_authentication(self, api_client):
        """Wishlist add endpoint returns 401 without authentication."""
        # Arrange
        product = ProductFactory(is_active=True)

        # Act
        response = api_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Expected 401 Unauthorized, got {response.status_code}"
        )


@pytest.mark.django_db
class TestWishlistRemoveWorks:
    """WISH-REG-001 – Remove from wishlist"""

    def test_remove_from_wishlist_returns_204(self, authenticated_client):
        """Removing a wishlist item returns 204 No Content."""
        # Arrange – add item first
        product = ProductFactory(is_active=True)
        authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )
        assert WishlistItem.objects.count() == 1  # precondition

        # Act
        response = authenticated_client.delete(
            reverse('wishlist-remove', kwargs={'product_id': product.id}),
        )

        # Assert – HTTP status
        assert response.status_code == status.HTTP_204_NO_CONTENT, (
            f"Expected 204 No Content, got {response.status_code}"
        )

    def test_remove_from_wishlist_deletes_database_record(self, authenticated_client):
        """WishlistItem is deleted from the database after removal."""
        # Arrange
        product = ProductFactory(is_active=True)
        authenticated_client.post(
            reverse('wishlist-add'),
            {'product_id': product.id},
            format='json',
        )

        # Act
        response = authenticated_client.delete(
            reverse('wishlist-remove', kwargs={'product_id': product.id}),
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert WishlistItem.objects.count() == 0, (
            "WishlistItem should be deleted from database"
        )

    def test_user_cannot_remove_other_users_wishlist_item(self, authenticated_client):
        """User A cannot remove a wishlist item owned by User B."""
        # Arrange – User B's item
        other_user = UserFactory()
        product = ProductFactory(is_active=True)
        from common.tests.factories import WishlistItemFactory
        WishlistItemFactory(user=other_user, product=product)

        # Act – User A tries to remove it
        response = authenticated_client.delete(
            reverse('wishlist-remove', kwargs={'product_id': product.id}),
        )

        # Assert – should return 404 (not found for this user)
        assert response.status_code == status.HTTP_404_NOT_FOUND, (
            f"Expected 404 when removing another user's item, got {response.status_code}"
        )
        # User B's item still exists
        assert WishlistItem.objects.filter(user=other_user, product=product).exists()

    def test_remove_nonexistent_wishlist_returns_404(self, authenticated_client):
        """Removing a product not in wishlist returns 404."""
        # Arrange – product was never added
        product = ProductFactory(is_active=True)

        # Act
        response = authenticated_client.delete(
            reverse('wishlist-remove', kwargs={'product_id': product.id}),
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND, (
            f"Expected 404 for non-existent wishlist item, got {response.status_code}"
        )


@pytest.mark.django_db
class TestWishlistListWorks:
    """WISH-REG-001 – List wishlist"""

    def test_list_wishlist_returns_user_items(self, authenticated_client):
        """Listing wishlist returns only the authenticated user's items."""
        # Arrange – add 2 items for current user
        p1 = ProductFactory(is_active=True)
        p2 = ProductFactory(is_active=True)
        authenticated_client.post(reverse('wishlist-add'), {'product_id': p1.id}, format='json')
        authenticated_client.post(reverse('wishlist-add'), {'product_id': p2.id}, format='json')

        # Add 1 item for another user
        other_user = UserFactory()
        from common.tests.factories import WishlistItemFactory
        WishlistItemFactory(user=other_user, product=ProductFactory(is_active=True))

        # Act
        response = authenticated_client.get(reverse('wishlist-list'))

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2, f"Should return only own 2 items, got {len(data)}"
        returned_ids = {item['product_id'] for item in data}
        assert returned_ids == {p1.id, p2.id}, "Should return correct product IDs"
