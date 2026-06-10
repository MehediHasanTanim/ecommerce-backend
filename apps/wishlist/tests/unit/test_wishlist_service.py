"""Module 5: Wishlist Add / Remove – Unit Tests

Covers WishlistService with AAA pattern.
"""
import pytest

from apps.wishlist.models import WishlistItem
from apps.wishlist.services import WishlistService
from common.tests.factories import ProductFactory, WishlistItemFactory, UserFactory


@pytest.mark.django_db
class TestAddProductToWishlist:
    """Test Case 1: Add Product To Wishlist"""

    def test_add_product_creates_wishlist_record(self, user):
        """Adding a product creates exactly one WishlistItem record."""
        # Arrange
        product = ProductFactory(is_active=True)

        # Act
        item = WishlistService.add_product(user, product.id)

        # Assert
        assert WishlistItem.objects.count() == 1, "Should create exactly 1 wishlist record"
        assert item.product_id == product.id, "Record should reference the correct product"
        assert item.user_id == user.id, "Record should be owned by the correct user"

    def test_add_product_appears_in_user_wishlist_list(self, user):
        """Added product is returned when listing the user's wishlist."""
        # Arrange
        product = ProductFactory(is_active=True)

        # Act
        WishlistService.add_product(user, product.id)

        # Assert
        items = WishlistService.list_products(user)
        assert items.count() == 1, "User's wishlist should contain the added product"


@pytest.mark.django_db
class TestAddDuplicateProduct:
    """Test Case 2: Add Duplicate Product"""

    def test_duplicate_product_blocked_and_record_count_unchanged(self, user):
        """Adding the same product twice raises ValueError; only 1 record exists."""
        # Arrange
        product = ProductFactory(is_active=True)
        WishlistService.add_product(user, product.id)

        # Act & Assert
        with pytest.raises(ValueError, match='already in your wishlist'):
            WishlistService.add_product(user, product.id)

        # Assert – count still 1
        assert WishlistItem.objects.count() == 1, "Duplicate should not create a second record"


@pytest.mark.django_db
class TestRemoveWishlistProduct:
    """Test Case 3: Remove Wishlist Product"""

    def test_remove_product_deletes_wishlist_record(self, user):
        """Removing a wishlisted product deletes the record."""
        # Arrange
        product = ProductFactory(is_active=True)
        WishlistService.add_product(user, product.id)
        assert WishlistItem.objects.count() == 1  # precondition

        # Act
        WishlistService.remove_product(user, product.id)

        # Assert
        assert WishlistItem.objects.count() == 0, "Wishlist record should be deleted"


@pytest.mark.django_db
class TestRemoveNonExistingWishlistItem:
    """Test Case 4: Remove Non-Existing Wishlist Item"""

    def test_remove_nonexistent_product_raises_value_error(self, user):
        """Attempting to remove a product not in the wishlist raises ValueError."""
        # Arrange
        product = ProductFactory(is_active=True)
        # Product was never added to wishlist

        # Act & Assert
        with pytest.raises(ValueError, match='not found'):
            WishlistService.remove_product(user, product.id)

    def test_remove_another_users_wishlist_item_does_not_affect_my_count(self, user):
        """Removing a product from another user's wishlist should not affect mine (or fail cleanly)."""
        # Arrange
        other_user = UserFactory()
        product = ProductFactory(is_active=True)
        WishlistItemFactory(user=other_user, product=product)
        WishlistService.add_product(user, ProductFactory(is_active=True))

        # Act & Assert – my product not in other user's wishlist
        with pytest.raises(ValueError, match='not found'):
            WishlistService.remove_product(user, product.id)

        # Assert – my wishlist count unchanged
        assert WishlistItem.objects.filter(user=user).count() == 1
