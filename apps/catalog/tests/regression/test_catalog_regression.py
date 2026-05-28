from decimal import Decimal
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.catalog.models import Product
from common.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ProductFactory,
    ProductImageFactory,
    ProductVariantFactory,
)


@pytest.mark.django_db
class TestProductListingRegression:
    def test_public_listing_returns_only_active_products(self, api_client):
        # Arrange
        active = ProductFactory(name='Active Product', is_active=True)
        ProductFactory(name='Inactive Product', is_active=False)
        ProductFactory(name='Draft Product', is_active=False)

        deleted = ProductFactory(name='Deleted Product', is_active=True)
        deleted_id = deleted.id
        deleted.delete()

        # Act
        response = api_client.get(reverse('product-list'))

        # Assert
        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data['results']}
        assert returned_ids == {active.id}
        assert deleted_id not in returned_ids

    def test_public_listing_returns_pagination_metadata(self, api_client, settings):
        # Arrange
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'PAGE_SIZE': 2}
        for index in range(3):
            ProductFactory(name=f'Paged Product {index}')

        # Act
        response = api_client.get(reverse('product-list'))

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3
        assert response.data['next'] is not None
        assert response.data['previous'] is None
        assert len(response.data['results']) == 2


@pytest.mark.django_db
class TestProductDetailRegression:
    def test_product_detail_returns_correct_product_by_slug(self, api_client):
        # Arrange
        product = ProductFactory(name='Detail Product', slug='detail-product')
        ProductFactory(name='Other Product', slug='other-product')

        # Act
        response = api_client.get(reverse('product-detail', kwargs={'slug': product.slug}))

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == product.id
        assert response.data['slug'] == 'detail-product'

    def test_invalid_product_slug_returns_404(self, api_client):
        # Arrange / Act
        response = api_client.get(reverse('product-detail', kwargs={'slug': 'missing-slug'}))

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_product_slug_is_hidden_from_public_api(self, api_client):
        # Arrange
        product = ProductFactory(slug='hidden-product', is_active=False)

        # Act
        response = api_client.get(reverse('product-detail', kwargs={'slug': product.slug}))

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProductFilterRegression:
    @pytest.fixture(autouse=True)
    def setup_products(self):
        self.category = CategoryFactory(slug='phones', name='Phones')
        self.other_category = CategoryFactory(slug='laptops', name='Laptops')
        self.brand = BrandFactory(slug='acme', name='Acme')
        self.other_brand = BrandFactory(slug='globex', name='Globex')
        self.match = ProductFactory(
            name='Matched Phone',
            category=self.category,
            brand=self.brand,
            base_price=Decimal('500.00'),
        )
        self.other_category_product = ProductFactory(
            name='Laptop Product',
            category=self.other_category,
            brand=self.brand,
            base_price=Decimal('500.00'),
        )
        self.other_brand_product = ProductFactory(
            name='Other Brand Phone',
            category=self.category,
            brand=self.other_brand,
            base_price=Decimal('500.00'),
        )
        self.expensive_product = ProductFactory(
            name='Expensive Phone',
            category=self.category,
            brand=self.brand,
            base_price=Decimal('1500.00'),
        )

    def test_category_filter_returns_matching_products(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'category': self.category.slug})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data['results']}
        assert self.match.id in returned_ids
        assert self.other_category_product.id not in returned_ids

    def test_brand_filter_returns_matching_products(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'brand': self.brand.slug})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data['results']}
        assert self.match.id in returned_ids
        assert self.other_brand_product.id not in returned_ids

    def test_price_min_max_filter_returns_matching_products(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'price_min': '400', 'price_max': '600'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data['results']}
        assert self.match.id in returned_ids
        assert self.expensive_product.id not in returned_ids

    def test_combined_category_brand_price_filters_return_precise_match(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {
            'category': self.category.slug,
            'brand': self.brand.slug,
            'price_min': '400',
            'price_max': '600',
        })

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [self.match.id]

    def test_invalid_price_filter_returns_validation_error(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'price_min': 'not-a-number'})

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'price_min' in response.data


@pytest.mark.django_db
class TestProductSortingRegression:
    @pytest.fixture(autouse=True)
    def setup_products(self):
        base_time = timezone.now()
        self.cheap = ProductFactory(name='Zebra Phone', base_price=Decimal('100.00'))
        self.middle = ProductFactory(name='Monkey Phone', base_price=Decimal('500.00'))
        self.expensive = ProductFactory(name='Aardvark Phone', base_price=Decimal('900.00'))
        Product.objects.filter(pk=self.cheap.pk).update(created_at=base_time - timedelta(days=3))
        Product.objects.filter(pk=self.middle.pk).update(created_at=base_time - timedelta(days=2))
        Product.objects.filter(pk=self.expensive.pk).update(created_at=base_time - timedelta(days=1))

    def test_sort_by_price_ascending(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'sort': 'price_asc'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [self.cheap.id, self.middle.id, self.expensive.id]

    def test_sort_by_price_descending(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'sort': 'price_desc'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [self.expensive.id, self.middle.id, self.cheap.id]

    def test_sort_by_name_ascending(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'sort': 'name_asc'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [self.expensive.id, self.middle.id, self.cheap.id]

    def test_sort_by_newest_and_oldest(self, api_client):
        # Act
        newest_response = api_client.get(reverse('product-list'), {'sort': 'newest'})
        oldest_response = api_client.get(reverse('product-list'), {'sort': 'oldest'})

        # Assert
        assert newest_response.status_code == status.HTTP_200_OK
        assert oldest_response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in newest_response.data['results']] == [self.expensive.id, self.middle.id, self.cheap.id]
        assert [item['id'] for item in oldest_response.data['results']] == [self.cheap.id, self.middle.id, self.expensive.id]

    def test_invalid_sort_value_is_rejected(self, api_client):
        # Act
        response = api_client.get(reverse('product-list'), {'sort': 'unsupported'})

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'sort' in response.data


@pytest.mark.django_db
class TestProductSearchRegression:
    @pytest.fixture(autouse=True)
    def setup_products(self):
        self.category = CategoryFactory(name='Smartphones')
        self.brand = BrandFactory(name='Acme Search')
        self.product = ProductFactory(
            name='Galaxy Search Phone',
            sku='SEARCH-SKU-001',
            category=self.category,
            brand=self.brand,
            description='Flagship Android phone',
        )
        ProductFactory(name='Unrelated Product', sku='UNRELATED-001')

    def test_search_returns_relevant_product_by_name(self, api_client):
        # Act
        response = api_client.get(reverse('product-search'), {'q': 'Galaxy Search'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data['results']}
        assert self.product.id in returned_ids

    def test_search_works_by_sku_brand_and_category(self, api_client):
        # Act
        sku_response = api_client.get(reverse('product-search'), {'q': 'SEARCH-SKU-001'})
        brand_response = api_client.get(reverse('product-search'), {'q': 'Acme Search'})
        category_response = api_client.get(reverse('product-search'), {'q': 'Smartphones'})

        # Assert
        for response in [sku_response, brand_response, category_response]:
            assert response.status_code == status.HTTP_200_OK
            assert self.product.id in {item['id'] for item in response.data['results']}

    def test_search_is_partial_and_case_insensitive(self, api_client):
        # Act
        response = api_client.get(reverse('product-search'), {'q': 'galaxy'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert self.product.id in {item['id'] for item in response.data['results']}

    def test_search_no_result_response_is_empty_paginated_payload(self, api_client):
        # Act
        response = api_client.get(reverse('product-search'), {'q': 'no-matching-product'})

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
        assert response.data['results'] == []


@pytest.mark.django_db
class TestProductImageUrlRegression:
    def test_product_listing_includes_absolute_primary_image_url(self, api_client):
        # Arrange
        product = ProductFactory()
        ProductImageFactory(product=product, is_primary=True)

        # Act
        response = api_client.get(reverse('product-list'))

        # Assert
        assert response.status_code == status.HTTP_200_OK
        result = response.data['results'][0]
        assert result['id'] == product.id
        assert result['primary_image'].startswith('http://testserver/media/')

    def test_product_detail_includes_absolute_image_url(self, api_client):
        # Arrange
        product = ProductFactory(slug='image-detail-product')
        image = ProductImageFactory(product=product, is_primary=True)

        # Act
        response = api_client.get(reverse('product-detail', kwargs={'slug': product.slug}))

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data['images'][0]['id'] == image.id
        assert response.data['images'][0]['image_url'].startswith('http://testserver/media/')

    def test_product_without_image_returns_null_listing_image_and_empty_detail_images(self, api_client):
        # Arrange
        product = ProductFactory(slug='no-image-product')

        # Act
        list_response = api_client.get(reverse('product-list'))
        detail_response = api_client.get(reverse('product-detail', kwargs={'slug': product.slug}))

        # Assert
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['primary_image'] is None
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['images'] == []
