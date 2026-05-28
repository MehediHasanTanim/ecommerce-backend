import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status

from common.tests.factories import ProductFactory, ProductVariantFactory


@pytest.mark.django_db
class TestProductListApi:
    def test_list_returns_pagination_metadata(self, api_client, settings):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'PAGE_SIZE': 2}
        for index in range(3):
            ProductFactory(name=f'Paged Product {index}')

        response = api_client.get(reverse('product-list'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 3
        assert response.data['next'] is not None
        assert response.data['previous'] is None
        assert len(response.data['results']) == 2

    def test_list_pagination_with_filters_and_sorting(self, api_client, category, brand, settings):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'PAGE_SIZE': 1}
        low = ProductFactory(category=category, brand=brand, base_price=Decimal('10.00'))
        high = ProductFactory(category=category, brand=brand, base_price=Decimal('20.00'))
        ProductFactory(base_price=Decimal('30.00'))

        response = api_client.get(reverse('product-list'), {
            'category': category.slug,
            'brand': brand.slug,
            'price_min': '5',
            'price_max': '25',
            'sort': 'price_desc',
        })

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert response.data['results'][0]['id'] == high.id
        assert low.id != response.data['results'][0]['id']

    def test_list_filters_by_availability(self, api_client):
        in_stock = ProductFactory()
        out_of_stock = ProductFactory()
        ProductVariantFactory(product=in_stock, stock_quantity=4, is_active=True)
        ProductVariantFactory(product=out_of_stock, stock_quantity=0, is_active=True)

        response = api_client.get(reverse('product-list'), {'in_stock': 'true'})

        assert response.status_code == status.HTTP_200_OK
        returned_ids = {item['id'] for item in response.data['results']}
        assert in_stock.id in returned_ids
        assert out_of_stock.id not in returned_ids


@pytest.mark.django_db
class TestProductSearchApi:
    def test_search_requires_non_empty_query(self, api_client):
        response = api_client.get(reverse('product-search'), {'q': ''})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'detail' in response.data

    def test_search_returns_paginated_results(self, api_client, settings):
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'PAGE_SIZE': 1}
        first = ProductFactory(name='Searchable Phone One')
        second = ProductFactory(name='Searchable Phone Two')

        response = api_client.get(reverse('product-search'), {'q': 'Searchable Phone'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
        assert response.data['next'] is not None
        assert response.data['results'][0]['id'] in {first.id, second.id}

    def test_search_sql_injection_payload_is_safe(self, api_client):
        ProductFactory(name='Normal Product')
        response = api_client.get(reverse('product-search'), {'q': "'; DROP TABLE catalog_product; --"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 0
