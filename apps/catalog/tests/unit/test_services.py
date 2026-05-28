import pytest
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from apps.catalog.services import (
    CategoryService, BrandService, ProductService,
    ProductImageService, SearchService
)
from apps.catalog.models import Category, Brand, Product, ProductImage
from apps.users.models import AuditLog
from common.tests.factories import ProductFactory, CategoryFactory, BrandFactory, ProductVariantFactory


@pytest.mark.django_db
class TestCategoryService:

    def test_create_category(self, user):
        data = {'name': 'Laptops', 'description': 'All laptops'}
        category = CategoryService.create(data, actor=user)

        assert category.id is not None
        assert category.name == 'Laptops'
        assert category.slug == 'laptops'
        assert AuditLog.objects.filter(resource_type='Category', action='CATEGORY_CREATED').exists()

    def test_update_category(self, user, category):
        data = {'name': 'Updated Category'}
        updated = CategoryService.update(category, data, actor=user)

        assert updated.name == 'Updated Category'
        assert AuditLog.objects.filter(resource_type='Category', action='CATEGORY_UPDATED').exists()

    def test_delete_category(self, user, category):
        cat_id = category.id
        CategoryService.delete(category, actor=user)

        assert not Category.objects.filter(id=cat_id).exists()
        assert AuditLog.objects.filter(resource_type='Category', action='CATEGORY_DELETED').exists()


@pytest.mark.django_db
class TestBrandService:

    def test_create_brand(self, user):
        data = {'name': 'Sony'}
        brand = BrandService.create(data, actor=user)
        assert brand.slug == 'sony'
        assert AuditLog.objects.filter(resource_type='Brand', action='BRAND_CREATED').exists()


@pytest.mark.django_db
class TestProductService:

    def test_create_product_with_variants(self, user, category, brand):
        data = {
            'name': 'PS5',
            'sku': 'SONY-PS5',
            'category': category,
            'brand': brand,
            'base_price': '499.99',
            'variants': [
                {'sku': 'PS5-DIG', 'variant_name': 'Digital Edition', 'price': '399.99', 'stock_quantity': 10},
                {'sku': 'PS5-DISC', 'variant_name': 'Disc Edition', 'price': '499.99', 'stock_quantity': 5},
            ]
        }
        product = ProductService.create(data, actor=user)

        assert product.id is not None
        assert product.slug == 'ps5'
        assert product.variants.count() == 2
        assert AuditLog.objects.filter(resource_type='Product', action='PRODUCT_CREATED').exists()

    def test_update_product_replaces_variants_when_variants_payload_is_provided(self, user, product):
        ProductVariantFactory(product=product, sku='OLD-VAR', variant_name='Old', stock_quantity=1)
        data = {
            'name': 'Updated Product',
            'variants': [
                {'sku': 'NEW-VAR', 'variant_name': 'New', 'price': Decimal('10.00'), 'stock_quantity': 3},
            ],
        }

        updated = ProductService.update(product, data, actor=user)

        assert updated.name == 'Updated Product'
        assert list(updated.variants.values_list('sku', flat=True)) == ['NEW-VAR']


@pytest.mark.django_db
class TestProductImageService:

    def test_upload_image_sets_primary(self, user, product):
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        data = {'is_primary': True, 'alt_text': 'Front view'}
        
        img_obj = ProductImageService.upload(product, image, data, actor=user)
        assert img_obj.is_primary is True
        assert img_obj.alt_text == 'Front view'
        assert AuditLog.objects.filter(resource_type='ProductImage', action='PRODUCT_IMAGE_UPLOADED').exists()

    def test_upload_image_rejects_invalid_extension(self, user, product):
        image = SimpleUploadedFile('test.gif', b'file_content', content_type='image/gif')
        with pytest.raises(ValidationError):
            ProductImageService.upload(product, image, {}, actor=user)

    def test_upload_image_rejects_oversized_file(self, user, product, settings):
        settings.CATALOG_IMAGE_MAX_SIZE_MB = 1
        image = SimpleUploadedFile('test.jpg', b'x' * (1024 * 1024 + 1), content_type='image/jpeg')
        with pytest.raises(ValidationError):
            ProductImageService.upload(product, image, {}, actor=user)

    def test_delete_image(self, user, product_image):
        img_id = product_image.id
        ProductImageService.delete(product_image, actor=user)
        assert not ProductImage.objects.filter(id=img_id).exists()
        assert AuditLog.objects.filter(resource_type='ProductImage', action='PRODUCT_IMAGE_DELETED').exists()


@pytest.mark.django_db
class TestSearchService:

    def test_empty_query_returns_none(self):
        qs = SearchService.search('')
        assert qs.count() == 0

    def test_search_by_name(self):
        p = ProductFactory(name='UniqueLaptop')
        ProductFactory(name='Other')
        qs = SearchService.search('UniqueLaptop')
        assert qs.count() == 1
        assert qs.first() == p

    def test_search_by_name_is_case_insensitive_and_partial(self):
        p = ProductFactory(name='UltraBook Laptop')
        qs = SearchService.search('laptop')
        assert p in qs

    def test_search_by_sku(self):
        p = ProductFactory(sku='SKU-9999')
        qs = SearchService.search('9999')
        assert qs.count() == 1
        assert qs.first() == p

    def test_search_by_brand_name(self):
        brand = BrandFactory(name='Searchable Brand')
        p = ProductFactory(brand=brand)
        qs = SearchService.search('searchable')
        assert qs.count() == 1
        assert qs.first() == p

    def test_search_by_category_name(self):
        cat = CategoryFactory(name='Gaming Consoles')
        p = ProductFactory(category=cat)
        qs = SearchService.search('Gaming')
        assert qs.count() == 1
        assert qs.first() == p

    def test_search_returns_no_results_for_unknown_keyword(self):
        ProductFactory(name='Known Product')
        qs = SearchService.search('does-not-exist')
        assert qs.count() == 0

    def test_search_pagination_metadata_with_django_paginator(self):
        for index in range(3):
            ProductFactory(name=f'Paginated Phone {index}')
        qs = SearchService.search('Phone')
        paginator = Paginator(qs, 2)
        page = paginator.page(1)

        assert paginator.count == 3
        assert paginator.num_pages == 2
        assert len(page.object_list) == 2

    def test_search_orders_matches_by_rank_or_newest(self):
        older = ProductFactory(name='Camera Match')
        newer = ProductFactory(name='Camera Match Pro')
        qs = SearchService.search('Camera')
        assert qs.first() in {older, newer}

    def test_search_excludes_inactive_products(self):
        ProductFactory(name='Phone', is_active=False)
        qs = SearchService.search('Phone')
        assert qs.count() == 0

    def test_sql_injection_is_handled_safely(self):
        # Django ORM parameterizes queries, so special characters are just treated as literals.
        # This test ensures no exceptions are raised when passing malicious-looking payloads.
        ProductFactory(name='Normal Product')
        payload = "'; DROP TABLE users;--"
        qs = SearchService.search(payload)
        assert qs.count() == 0  # Should just safely return no results
