import django_filters
from django.db.models import Q
from .models import Product


class ProductFilter(django_filters.FilterSet):
    """
    Reusable filter class for the Product listing and search endpoints.

    Supported query params:
        category    – category slug (exact match)
        brand       – brand slug (exact match)
        price_min   – minimum base_price (inclusive)
        price_max   – maximum base_price (inclusive)
        in_stock    – true/false, whether any variant has stock > 0
        is_featured – true/false
        ordering    – newest | price_asc | price_desc | name_asc | name_desc
    """

    category = django_filters.CharFilter(
        field_name='category__slug',
        lookup_expr='exact',
        label='Category slug',
    )
    brand = django_filters.CharFilter(
        field_name='brand__slug',
        lookup_expr='exact',
        label='Brand slug',
    )
    price_min = django_filters.NumberFilter(
        field_name='base_price',
        lookup_expr='gte',
        label='Minimum price',
    )
    price_max = django_filters.NumberFilter(
        field_name='base_price',
        lookup_expr='lte',
        label='Maximum price',
    )
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='In stock (has variant with stock > 0)',
    )
    is_featured = django_filters.BooleanFilter(
        field_name='is_featured',
        label='Featured products only',
    )
    ordering = django_filters.OrderingFilter(
        fields={
            'created_at': 'newest',
            'base_price': 'price',
            'name': 'name',
        },
        field_labels={
            'created_at': 'Newest',
            'base_price': 'Price',
            'name': 'Name',
        },
        label='Sort order',
    )

    class Meta:
        model = Product
        fields = ['category', 'brand', 'price_min', 'price_max', 'in_stock', 'is_featured']

    def filter_in_stock(self, queryset, name, value):
        """
        Filter products that have at least one active variant with stock_quantity > 0.
        When value=True  → in-stock products only.
        When value=False → out-of-stock products only.
        """
        if value is True:
            return queryset.filter(
                variants__is_active=True,
                variants__stock_quantity__gt=0,
            ).distinct()
        elif value is False:
            # Exclude any product that HAS an in-stock variant
            in_stock_ids = Product.objects.filter(
                variants__is_active=True,
                variants__stock_quantity__gt=0,
            ).values_list('id', flat=True)
            return queryset.exclude(id__in=in_stock_ids)
        return queryset


SORT_MAP = {
    'newest':     '-created_at',
    'price_asc':  'base_price',
    'price_desc': '-base_price',
    'name_asc':   'name',
    'name_desc':  '-name',
}


def apply_sorting(queryset, sort_param: str):
    """
    Apply one of the named sort options to *queryset*.
    Falls back to '-created_at' (newest) for unknown values.
    """
    order_by = SORT_MAP.get(sort_param, '-created_at')
    return queryset.order_by(order_by)
