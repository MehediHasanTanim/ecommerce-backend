import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.catalog.services import (
    CategoryService, BrandService, ProductService,
    ProductImageService, SearchService
)
from apps.catalog.models import Category, Brand, Product, ProductImage
from apps.users.models import AuditLog
from common.tests.factories import ProductFactory, CategoryFactory, BrandFactory


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


@pytest.mark.django_db
class TestProductImageService:

    def test_upload_image_sets_primary(self, user, product):
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        data = {'is_primary': True, 'alt_text': 'Front view'}
        
        img_obj = ProductImageService.upload(product, image, data, actor=user)
        assert img_obj.is_primary is True
        assert img_obj.alt_text == 'Front view'
        assert AuditLog.objects.filter(resource_type='ProductImage', action='PRODUCT_IMAGE_UPLOADED').exists()

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

    def test_search_by_sku(self):
        p = ProductFactory(sku='SKU-9999')
        qs = SearchService.search('9999')
        assert qs.count() == 1
        assert qs.first() == p

    def test_search_by_category_name(self):
        cat = CategoryFactory(name='Gaming Consoles')
        p = ProductFactory(category=cat)
        qs = SearchService.search('Gaming')
        assert qs.count() == 1
        assert qs.first() == p

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
