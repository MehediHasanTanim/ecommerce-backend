import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.catalog.models import Category, Brand, Product, ProductVariant, ProductImage
from common.tests.factories import (
    CategoryFactory, BrandFactory, ProductFactory,
    ProductVariantFactory, ProductImageFactory,
)


@pytest.mark.django_db
class TestCategoryModel:

    def test_slug_auto_generated_from_name(self):
        category = CategoryFactory(name='Electronics', slug='')
        assert category.slug == 'electronics'

    def test_slug_uniqueness_appends_counter(self):
        CategoryFactory(name='Phones', slug='phones')
        cat2 = CategoryFactory(name='Phones', slug='')
        assert cat2.slug == 'phones-1'

    def test_slug_explicit_is_preserved(self):
        cat = CategoryFactory(name='Test', slug='my-custom-slug')
        assert cat.slug == 'my-custom-slug'

    def test_parent_child_relationship(self):
        parent = CategoryFactory(name='Electronics')
        child = CategoryFactory(name='Smartphones', parent=parent)
        assert child.parent == parent
        assert child in parent.children.all()

    def test_category_str(self):
        cat = CategoryFactory(name='Footwear')
        assert str(cat) == 'Footwear'

    def test_inactive_category_is_persisted(self):
        cat = CategoryFactory(is_active=False)
        assert Category.objects.filter(id=cat.id, is_active=False).exists()


@pytest.mark.django_db
class TestBrandModel:

    def test_slug_auto_generated_from_name(self):
        brand = BrandFactory(name='Nike', slug='')
        assert brand.slug == 'nike'

    def test_slug_uniqueness_appends_counter(self):
        BrandFactory(name='Adidas', slug='adidas')
        brand2 = BrandFactory(name='Adidas', slug='')
        assert brand2.slug == 'adidas-1'

    def test_brand_str(self):
        brand = BrandFactory(name='Samsung')
        assert str(brand) == 'Samsung'

    def test_inactive_brand_is_persisted(self):
        brand = BrandFactory(is_active=False)
        assert Brand.objects.filter(id=brand.id, is_active=False).exists()


@pytest.mark.django_db
class TestProductModel:

    def test_slug_auto_generated(self):
        product = ProductFactory(name='Wireless Headphones', slug='')
        assert product.slug == 'wireless-headphones'

    def test_slug_uniqueness(self):
        ProductFactory(name='Laptop', slug='laptop')
        p2 = ProductFactory(name='Laptop', slug='')
        assert p2.slug == 'laptop-1'

    def test_sku_uniqueness(self):
        ProductFactory(sku='SKU-001')
        with pytest.raises(Exception):  # IntegrityError from DB
            ProductFactory(sku='SKU-001')

    def test_effective_price_returns_sale_price_when_set(self):
        product = ProductFactory(base_price=Decimal('100.00'), sale_price=Decimal('75.00'))
        assert product.effective_price == Decimal('75.00')

    def test_effective_price_returns_base_price_when_no_sale(self):
        product = ProductFactory(base_price=Decimal('100.00'), sale_price=None)
        assert product.effective_price == Decimal('100.00')

    def test_product_str(self):
        product = ProductFactory(name='Test Product')
        assert str(product) == 'Test Product'

    def test_inactive_product_is_persisted(self):
        product = ProductFactory(is_active=False)
        assert Product.objects.filter(id=product.id, is_active=False).exists()


@pytest.mark.django_db
class TestProductVariantModel:

    def test_variant_sku_uniqueness(self):
        v1 = ProductVariantFactory(sku='VAR-001')
        with pytest.raises(Exception):
            ProductVariantFactory(sku='VAR-001')

    def test_stock_cannot_be_negative(self):
        product = ProductFactory()
        variant = ProductVariant(
            product=product,
            sku='NEG-SKU',
            variant_name='Bad Variant',
            stock_quantity=-1,
        )
        with pytest.raises(ValidationError):
            variant.full_clean()

    def test_variant_effective_price_uses_variant_price(self):
        product = ProductFactory(base_price=Decimal('100.00'))
        variant = ProductVariantFactory(product=product, price=Decimal('80.00'), sale_price=None)
        assert variant.effective_price == Decimal('80.00')

    def test_variant_effective_price_uses_variant_sale_price(self):
        product = ProductFactory(base_price=Decimal('100.00'))
        variant = ProductVariantFactory(product=product, price=Decimal('80.00'), sale_price=Decimal('60.00'))
        assert variant.effective_price == Decimal('60.00')

    def test_variant_effective_price_falls_back_to_product(self):
        product = ProductFactory(base_price=Decimal('100.00'), sale_price=None)
        variant = ProductVariantFactory(product=product, price=None, sale_price=None)
        assert variant.effective_price == Decimal('100.00')

    def test_variant_str(self):
        product = ProductFactory(name='Shirt')
        variant = ProductVariantFactory(product=product, variant_name='Large Red')
        assert 'Shirt' in str(variant)
        assert 'Large Red' in str(variant)

    def test_inactive_variant_is_persisted(self):
        variant = ProductVariantFactory(is_active=False)
        assert ProductVariant.objects.filter(id=variant.id, is_active=False).exists()


@pytest.mark.django_db
class TestProductImageModel:

    def test_only_one_primary_image_per_product(self):
        product = ProductFactory()
        img1 = ProductImageFactory(product=product, is_primary=True)
        img2 = ProductImageFactory(product=product, is_primary=True)

        img1.refresh_from_db()
        img2.refresh_from_db()

        assert img2.is_primary is True
        assert img1.is_primary is False

    def test_multiple_non_primary_images_allowed(self):
        product = ProductFactory()
        ProductImageFactory(product=product, is_primary=False)
        ProductImageFactory(product=product, is_primary=False)
        assert ProductImage.objects.filter(product=product).count() == 2

    def test_image_str(self):
        product = ProductFactory(name='Camera')
        img = ProductImageFactory(product=product, is_primary=True)
        assert 'Camera' in str(img)
        assert 'primary=True' in str(img)
