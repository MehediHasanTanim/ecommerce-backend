"""Unit tests for Wishlist service."""
import pytest
from apps.wishlist.models import WishlistItem
from apps.wishlist.services import WishlistService
from common.tests.factories import ProductFactory, WishlistItemFactory


@pytest.mark.django_db
class TestWishlistService:

    def test_add_wishlist_item(self, user):
        product = ProductFactory(is_active=True)
        item = WishlistService.add_product(user, product.id)
        assert item.product == product
        assert item.user == user
        assert WishlistItem.objects.filter(user=user, product=product).exists()

    def test_duplicate_wishlist_item_blocked(self, user):
        product = ProductFactory(is_active=True)
        WishlistService.add_product(user, product.id)
        with pytest.raises(ValueError, match='already in your wishlist'):
            WishlistService.add_product(user, product.id)

    def test_remove_wishlist_item(self, user):
        product = ProductFactory(is_active=True)
        WishlistService.add_product(user, product.id)
        WishlistService.remove_product(user, product.id)
        assert not WishlistItem.objects.filter(user=user, product=product).exists()

    def test_remove_nonexistent_item_raises(self, user):
        product = ProductFactory(is_active=True)
        with pytest.raises(ValueError, match='not found'):
            WishlistService.remove_product(user, product.id)

    def test_list_wishlist_items(self, user):
        p1 = ProductFactory(is_active=True)
        p2 = ProductFactory(is_active=True)
        WishlistService.add_product(user, p1.id)
        WishlistService.add_product(user, p2.id)

        items = WishlistService.list_products(user)
        assert items.count() == 2

    def test_list_wishlist_only_returns_own(self, user):
        p1 = ProductFactory(is_active=True)
        WishlistService.add_product(user, p1.id)

        # Another user's wishlist item
        from common.tests.factories import UserFactory
        other_user = UserFactory()
        WishlistItemFactory(user=other_user, product=ProductFactory(is_active=True))

        items = WishlistService.list_products(user)
        assert items.count() == 1
