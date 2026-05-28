import pytest
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from apps.catalog.serializers import (
    CategoryWriteSerializer, BrandWriteSerializer, ProductWriteSerializer,
    ProductImageUploadSerializer, ProductVariantWriteSerializer
)
from common.tests.factories import CategoryFactory, BrandFactory, ProductFactory, ProductVariantFactory


def make_test_image(name='test.jpg', content_type='image/jpeg', image_format='JPEG'):
    image_io = BytesIO()
    Image.new('RGB', (10, 10), color='white').save(image_io, image_format)
    image_io.seek(0)
    return SimpleUploadedFile(name, image_io.read(), content_type=content_type)


@pytest.mark.django_db
class TestCategoryWriteSerializer:

    def test_valid_data(self):
        serializer = CategoryWriteSerializer(data={'name': 'Books', 'slug': 'books'})
        assert serializer.is_valid()

    def test_slug_uniqueness_validation(self):
        CategoryFactory(name='Books', slug='books')
        serializer = CategoryWriteSerializer(data={'name': 'Books 2', 'slug': 'books'})
        assert not serializer.is_valid()
        assert 'slug' in serializer.errors


@pytest.mark.django_db
class TestBrandWriteSerializer:

    def test_valid_data(self):
        serializer = BrandWriteSerializer(data={'name': 'Apple', 'slug': 'apple'})
        assert serializer.is_valid()

    def test_slug_uniqueness_validation(self):
        BrandFactory(name='Apple', slug='apple')
        serializer = BrandWriteSerializer(data={'name': 'Apple 2', 'slug': 'apple'})
        assert not serializer.is_valid()
        assert 'slug' in serializer.errors


@pytest.mark.django_db
class TestProductWriteSerializer:

    def test_valid_data(self, category, brand):
        data = {
            'name': 'MacBook Pro',
            'slug': 'macbook-pro',
            'sku': 'MBP-2023',
            'category': category.id,
            'brand': brand.id,
            'base_price': '1999.99',
            'sale_price': '1899.99'
        }
        serializer = ProductWriteSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_sale_price_cannot_be_greater_than_base_price(self):
        data = {
            'name': 'MacBook Pro',
            'slug': 'macbook-pro',
            'sku': 'MBP-2023',
            'base_price': '1000.00',
            'sale_price': '1500.00'
        }
        serializer = ProductWriteSerializer(data=data)
        assert not serializer.is_valid()
        assert 'sale_price' in serializer.errors

    def test_slug_uniqueness(self):
        ProductFactory(slug='macbook-pro')
        data = {'name': 'Mac', 'slug': 'macbook-pro', 'sku': 'MBP-1', 'base_price': '100'}
        serializer = ProductWriteSerializer(data=data)
        assert not serializer.is_valid()
        assert 'slug' in serializer.errors

    def test_sku_uniqueness(self):
        ProductFactory(sku='MBP-1')
        data = {'name': 'Mac', 'slug': 'mac', 'sku': 'MBP-1', 'base_price': '100'}
        serializer = ProductWriteSerializer(data=data)
        assert not serializer.is_valid()
        assert 'sku' in serializer.errors


@pytest.mark.django_db
class TestProductVariantWriteSerializer:

    def test_stock_quantity_cannot_be_negative(self):
        data = {
            'sku': 'VAR-001',
            'variant_name': 'Small',
            'stock_quantity': -5
        }
        serializer = ProductVariantWriteSerializer(data=data)
        assert not serializer.is_valid()
        assert 'stock_quantity' in serializer.errors

    def test_sku_uniqueness(self):
        ProductVariantFactory(sku='VAR-001')
        data = {
            'sku': 'VAR-001',
            'variant_name': 'Small',
            'stock_quantity': 10
        }
        serializer = ProductVariantWriteSerializer(data=data)
        assert not serializer.is_valid()
        assert 'sku' in serializer.errors


class TestProductImageUploadSerializer:

    def test_valid_image(self):
        image = make_test_image()
        serializer = ProductImageUploadSerializer(data={'image': image, 'is_primary': True})
        assert serializer.is_valid(), serializer.errors

    def test_invalid_file_type(self):
        txt_file = SimpleUploadedFile("test.txt", b"file_content", content_type="text/plain")
        serializer = ProductImageUploadSerializer(data={'image': txt_file})
        assert not serializer.is_valid()
        assert 'image' in serializer.errors

    def test_invalid_extension(self):
        bad_ext_file = SimpleUploadedFile("test.pdf", b"file_content", content_type="image/jpeg")
        serializer = ProductImageUploadSerializer(data={'image': bad_ext_file})
        assert not serializer.is_valid()
        assert 'image' in serializer.errors
