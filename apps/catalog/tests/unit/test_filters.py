import pytest
from decimal import Decimal
from apps.catalog.models import Product
from apps.catalog.filters import ProductFilter, apply_sorting
from common.tests.factories import ProductFactory, CategoryFactory, BrandFactory, ProductVariantFactory


@pytest.mark.django_db
class TestProductFilter:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.cat1 = CategoryFactory(slug='cat-1')
        self.cat2 = CategoryFactory(slug='cat-2')
        self.brand1 = BrandFactory(slug='brand-1')
        
        self.p1 = ProductFactory(category=self.cat1, brand=self.brand1, base_price=Decimal('50.00'), is_featured=True)
        self.p2 = ProductFactory(category=self.cat2, brand=self.brand1, base_price=Decimal('150.00'), is_featured=False)
        self.p3 = ProductFactory(category=self.cat1, base_price=Decimal('200.00'), is_featured=False)
        
        # p1 is in stock
        ProductVariantFactory(product=self.p1, stock_quantity=10, is_active=True, attributes={'color': 'Red', 'size': 'M'})
        # p2 is out of stock (stock = 0)
        ProductVariantFactory(product=self.p2, stock_quantity=0, is_active=True, attributes={'color': 'Blue', 'size': 'L'})
        # p3 has no variants, so out of stock by default definition

    def test_filter_by_category(self):
        qs = ProductFilter({'category': 'cat-1'}, queryset=Product.objects.all()).qs
        assert qs.count() == 2
        assert self.p1 in qs
        assert self.p3 in qs

    def test_filter_by_brand(self):
        qs = ProductFilter({'brand': 'brand-1'}, queryset=Product.objects.all()).qs
        assert qs.count() == 2
        assert self.p1 in qs
        assert self.p2 in qs

    def test_filter_by_price_min(self):
        qs = ProductFilter({'price_min': 100}, queryset=Product.objects.all()).qs
        assert qs.count() == 2
        assert self.p2 in qs
        assert self.p3 in qs

    def test_filter_by_price_max(self):
        qs = ProductFilter({'price_max': 100}, queryset=Product.objects.all()).qs
        assert qs.count() == 1
        assert self.p1 in qs

    def test_filter_in_stock(self):
        qs = ProductFilter({'in_stock': 'true'}, queryset=Product.objects.all()).qs
        assert qs.count() == 1
        assert self.p1 in qs

    def test_filter_out_of_stock(self):
        qs = ProductFilter({'in_stock': 'false'}, queryset=Product.objects.all()).qs
        assert qs.count() == 2
        assert self.p2 in qs
        assert self.p3 in qs

    def test_filter_is_featured(self):
        qs = ProductFilter({'is_featured': 'true'}, queryset=Product.objects.all()).qs
        assert qs.count() == 1
        assert self.p1 in qs

    def test_multiple_filters_are_combined(self):
        qs = ProductFilter({
            'category': 'cat-1',
            'brand': 'brand-1',
            'price_min': '40',
            'price_max': '60',
            'in_stock': 'true',
            'is_featured': 'true',
        }, queryset=Product.objects.all()).qs
        assert list(qs) == [self.p1]

    def test_filter_by_variant_attribute(self):
        qs = ProductFilter({'attribute': 'color:red'}, queryset=Product.objects.all()).qs
        assert list(qs) == [self.p1]

    def test_invalid_attribute_filter_returns_no_results(self):
        qs = ProductFilter({'attribute': 'not-a-valid-format'}, queryset=Product.objects.all()).qs
        assert qs.count() == 0

    def test_invalid_price_filter_is_invalid_without_crashing(self):
        product_filter = ProductFilter({'price_min': 'not-a-number'}, queryset=Product.objects.all())
        assert product_filter.is_valid() is False


@pytest.mark.django_db
class TestSorting:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.p_cheap = ProductFactory(name='Zebra', base_price=Decimal('10.00'))
        self.p_mid = ProductFactory(name='Monkey', base_price=Decimal('50.00'))
        self.p_expensive = ProductFactory(name='Aardvark', base_price=Decimal('100.00'))

    def test_sort_price_asc(self):
        qs = apply_sorting(Product.objects.all(), 'price_asc')
        assert list(qs) == [self.p_cheap, self.p_mid, self.p_expensive]

    def test_sort_price_desc(self):
        qs = apply_sorting(Product.objects.all(), 'price_desc')
        assert list(qs) == [self.p_expensive, self.p_mid, self.p_cheap]

    def test_sort_name_asc(self):
        qs = apply_sorting(Product.objects.all(), 'name_asc')
        assert list(qs) == [self.p_expensive, self.p_mid, self.p_cheap]

    def test_sort_name_desc(self):
        qs = apply_sorting(Product.objects.all(), 'name_desc')
        assert list(qs) == [self.p_cheap, self.p_mid, self.p_expensive]

    def test_sort_invalid_falls_back_to_newest(self):
        qs = apply_sorting(Product.objects.all(), 'invalid_sort')
        # ordered by -created_at by default
        assert list(qs) == [self.p_expensive, self.p_mid, self.p_cheap]

    def test_sort_created_date_newest(self):
        qs = apply_sorting(Product.objects.all(), 'newest')
        assert list(qs) == [self.p_expensive, self.p_mid, self.p_cheap]

    def test_unsupported_popularity_sort_falls_back_to_newest(self):
        qs = apply_sorting(Product.objects.all(), 'popularity')
        assert list(qs) == [self.p_expensive, self.p_mid, self.p_cheap]
