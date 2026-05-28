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

    def test_category_cannot_be_its_own_parent(self):
        category = CategoryFactory()
        serializer = CategoryWriteSerializer(category, data={'parent': category.id}, partial=True)
        assert not serializer.is_valid()
        assert 'parent' in serializer.errors


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

    def test_valid_data_with_variants(self, category, brand):
        data = {
            'name': 'MacBook Pro',
            'sku': 'MBP-2024',
            'category': category.id,
            'brand': brand.id,
            'base_price': '1999.99',
            'variants': [
                {
                    'sku': 'MBP-2024-16',
                    'variant_name': '16GB RAM',
                    'attributes': {'memory': '16GB'},
                    'price': '2099.99',
                    'sale_price': '1999.99',
                    'stock_quantity': 5,
                    'is_active': True,
                }
            ],
        }

        serializer = ProductWriteSerializer(data=data)

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['variants'][0]['attributes'] == {'memory': '16GB'}

    def test_required_fields_are_enforced(self):
        serializer = ProductWriteSerializer(data={})
        assert not serializer.is_valid()
        assert {'name', 'sku', 'base_price'}.issubset(serializer.errors.keys())

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

    def test_base_price_cannot_be_zero(self):
        serializer = ProductWriteSerializer(data={'name': 'Mac', 'sku': 'MBP-1', 'base_price': '0.00'})
        assert not serializer.is_valid()
        assert 'base_price' in serializer.errors

    def test_sale_price_cannot_be_zero(self):
        data = {'name': 'Mac', 'sku': 'MBP-1', 'base_price': '100.00', 'sale_price': '0.00'}
        serializer = ProductWriteSerializer(data=data)
        assert not serializer.is_valid()
        assert 'sale_price' in serializer.errors

    def test_nullable_category_and_brand_are_accepted(self):
        data = {'name': 'Standalone Product', 'sku': 'STANDALONE-1', 'base_price': '10.00'}
        serializer = ProductWriteSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

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

    def test_price_cannot_be_negative_or_zero(self):
        serializer = ProductVariantWriteSerializer(data={
            'sku': 'VAR-002',
            'variant_name': 'Small',
            'price': '0.00',
            'stock_quantity': 10,
        })
        assert not serializer.is_valid()
        assert 'price' in serializer.errors

    def test_sale_price_must_be_less_than_price(self):
        serializer = ProductVariantWriteSerializer(data={
            'sku': 'VAR-003',
            'variant_name': 'Small',
            'price': '10.00',
            'sale_price': '10.00',
            'stock_quantity': 10,
        })
        assert not serializer.is_valid()
        assert 'sale_price' in serializer.errors

    def test_optional_defaults_are_valid(self):
        serializer = ProductVariantWriteSerializer(data={'sku': 'VAR-004', 'variant_name': 'Default'})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['attributes'] == {}

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

    def test_negative_display_order_is_rejected(self):
        image = make_test_image()
        serializer = ProductImageUploadSerializer(data={'image': image, 'display_order': -1})
        assert not serializer.is_valid()
        assert 'display_order' in serializer.errors

    def test_optional_metadata_defaults_are_applied(self):
        image = make_test_image()
        serializer = ProductImageUploadSerializer(data={'image': image})
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['alt_text'] == ''
        assert serializer.validated_data['is_primary'] is False
        assert serializer.validated_data['display_order'] == 0
