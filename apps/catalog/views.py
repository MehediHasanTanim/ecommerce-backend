import logging
from rest_framework import status, generics, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes, OpenApiExample
)

from .models import Category, Brand, Product, ProductImage
from .serializers import (
    CategorySerializer, CategoryWriteSerializer,
    BrandSerializer, BrandWriteSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductWriteSerializer,
    ProductImageSerializer, ProductImageUploadSerializer,
)
from .services import CategoryService, BrandService, ProductService, ProductImageService, SearchService
from .filters import ProductFilter, apply_sorting
from .permissions import IsAdminOrStaffUser, ReadOnly

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Public: Category
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Catalog – Categories'])
class CategoryListView(generics.ListAPIView):
    """
    GET /api/v1/categories/
    Lists all active categories ordered by display_order then name.
    """
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None  # Return full list for nav menus

    def get_queryset(self):
        return (
            Category.objects
            .filter(is_active=True)
            .select_related('parent')
            .order_by('display_order', 'name')
        )


@extend_schema(tags=['Catalog – Categories'])
class CategoryDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/categories/{slug}/
    Returns a single active category by slug.
    """
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Category.objects.filter(is_active=True).select_related('parent')


# ──────────────────────────────────────────────────────────────────────────────
# Public: Brand
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Catalog – Brands'])
class BrandListView(generics.ListAPIView):
    """
    GET /api/v1/brands/
    Lists all active brands.
    """
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return Brand.objects.filter(is_active=True).order_by('name')


@extend_schema(tags=['Catalog – Brands'])
class BrandDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/brands/{slug}/
    Returns a single active brand by slug.
    """
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Brand.objects.filter(is_active=True)


# ──────────────────────────────────────────────────────────────────────────────
# Public: Product Listing
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Catalog – Products'],
    parameters=[
        OpenApiParameter('category', OpenApiTypes.STR, description='Filter by category slug'),
        OpenApiParameter('brand', OpenApiTypes.STR, description='Filter by brand slug'),
        OpenApiParameter('price_min', OpenApiTypes.FLOAT, description='Minimum price'),
        OpenApiParameter('price_max', OpenApiTypes.FLOAT, description='Maximum price'),
        OpenApiParameter('in_stock', OpenApiTypes.BOOL, description='Filter in-stock products'),
        OpenApiParameter('is_featured', OpenApiTypes.BOOL, description='Filter featured products'),
        OpenApiParameter(
            'sort', OpenApiTypes.STR,
            description='Sort order: newest | price_asc | price_desc | name_asc | name_desc',
        ),
    ],
)
class ProductListView(generics.ListAPIView):
    """
    GET /api/v1/products/
    Paginated list of active products with filtering and sorting.
    Only active products are visible.
    """
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    filterset_class = ProductFilter
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        qs = (
            Product.objects
            .filter(is_active=True)
            .select_related('category', 'brand')
            .prefetch_related('images', 'variants')
        )
        sort_param = self.request.query_params.get('sort', 'newest')
        return apply_sorting(qs, sort_param)


# ──────────────────────────────────────────────────────────────────────────────
# Public: Product Detail
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Catalog – Products'])
class ProductDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/products/{slug}/
    Returns full product detail. Inactive products return 404.
    """
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            Product.objects
            .filter(is_active=True)
            .select_related('category', 'brand')
            .prefetch_related('images', 'variants')
        )


# ──────────────────────────────────────────────────────────────────────────────
# Public: Search
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Catalog – Search'],
    parameters=[
        OpenApiParameter(
            'q', OpenApiTypes.STR, required=True,
            description='Search keyword (name, SKU, description, category, brand)',
        ),
    ],
    responses={200: ProductListSerializer(many=True), 400: None},
)
class ProductSearchView(generics.ListAPIView):
    """
    GET /api/v1/products/search/?q=keyword
    Full-text search across name, SKU, description, category, brand.
    Returns only active products. Empty query returns validation error.
    """
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        q = self.request.query_params.get('q', '').strip()
        if not q:
            return Product.objects.none()
        return SearchService.search(q)

    def list(self, request, *args, **kwargs):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response(
                {'detail': 'Search query parameter "q" is required and cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().list(request, *args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# Admin: Category
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Admin – Categories'])
class AdminCategoryCreateView(views.APIView):
    """POST /api/v1/admin/categories/ — Create a new category."""
    permission_classes = [IsAdminOrStaffUser]

    @extend_schema(request=CategoryWriteSerializer, responses={201: CategorySerializer})
    def post(self, request):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.create(serializer.validated_data, actor=request.user)
        return Response(CategorySerializer(category, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(tags=['Admin – Categories'])
class AdminCategoryDetailView(views.APIView):
    """PATCH / DELETE /api/v1/admin/categories/{id}/"""
    permission_classes = [IsAdminOrStaffUser]

    def _get_object(self, pk):
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return None

    @extend_schema(request=CategoryWriteSerializer, responses={200: CategorySerializer})
    def patch(self, request, pk):
        category = self._get_object(pk)
        if not category:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = CategoryService.update(category, serializer.validated_data, actor=request.user)
        return Response(CategorySerializer(category, context={'request': request}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        category = self._get_object(pk)
        if not category:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        CategoryService.delete(category, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────────────
# Admin: Brand
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Admin – Brands'])
class AdminBrandCreateView(views.APIView):
    """POST /api/v1/admin/brands/ — Create a new brand."""
    permission_classes = [IsAdminOrStaffUser]

    @extend_schema(request=BrandWriteSerializer, responses={201: BrandSerializer})
    def post(self, request):
        serializer = BrandWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        brand = BrandService.create(serializer.validated_data, actor=request.user)
        return Response(BrandSerializer(brand, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(tags=['Admin – Brands'])
class AdminBrandDetailView(views.APIView):
    """PATCH / DELETE /api/v1/admin/brands/{id}/"""
    permission_classes = [IsAdminOrStaffUser]

    def _get_object(self, pk):
        try:
            return Brand.objects.get(pk=pk)
        except Brand.DoesNotExist:
            return None

    @extend_schema(request=BrandWriteSerializer, responses={200: BrandSerializer})
    def patch(self, request, pk):
        brand = self._get_object(pk)
        if not brand:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = BrandWriteSerializer(brand, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        brand = BrandService.update(brand, serializer.validated_data, actor=request.user)
        return Response(BrandSerializer(brand, context={'request': request}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        brand = self._get_object(pk)
        if not brand:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        BrandService.delete(brand, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────────────
# Admin: Product
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Admin – Products'])
class AdminProductCreateView(views.APIView):
    """POST /api/v1/admin/products/ — Create a new product."""
    permission_classes = [IsAdminOrStaffUser]

    @extend_schema(request=ProductWriteSerializer, responses={201: ProductDetailSerializer})
    def post(self, request):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = ProductService.create(serializer.validated_data, actor=request.user)
        product_fresh = (
            Product.objects
            .select_related('category', 'brand')
            .prefetch_related('images', 'variants')
            .get(pk=product.pk)
        )
        return Response(
            ProductDetailSerializer(product_fresh, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Admin – Products'])
class AdminProductDetailView(views.APIView):
    """PATCH / DELETE /api/v1/admin/products/{id}/"""
    permission_classes = [IsAdminOrStaffUser]

    def _get_object(self, pk):
        try:
            return Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return None

    @extend_schema(request=ProductWriteSerializer, responses={200: ProductDetailSerializer})
    def patch(self, request, pk):
        product = self._get_object(pk)
        if not product:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProductWriteSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = ProductService.update(product, serializer.validated_data, actor=request.user)
        product_fresh = (
            Product.objects
            .select_related('category', 'brand')
            .prefetch_related('images', 'variants')
            .get(pk=product.pk)
        )
        return Response(ProductDetailSerializer(product_fresh, context={'request': request}).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        product = self._get_object(pk)
        if not product:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ProductService.delete(product, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────────────────────────
# Admin: Product Image Upload / Delete
# ──────────────────────────────────────────────────────────────────────────────

@extend_schema(tags=['Admin – Product Images'])
class AdminProductImageUploadView(views.APIView):
    """
    POST /api/v1/admin/products/{id}/images/
    Upload an image for a product. Supports multipart/form-data.
    """
    permission_classes = [IsAdminOrStaffUser]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={'multipart/form-data': ProductImageUploadSerializer},
        responses={201: ProductImageSerializer},
    )
    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_file = serializer.validated_data.pop('image')
        try:
            image_obj = ProductImageService.upload(
                product=product,
                image_file=image_file,
                data=serializer.validated_data,
                actor=request.user,
            )
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            ProductImageSerializer(image_obj, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Admin – Product Images'])
class AdminProductImageDeleteView(views.APIView):
    """DELETE /api/v1/admin/products/images/{image_id}/"""
    permission_classes = [IsAdminOrStaffUser]

    @extend_schema(responses={204: None})
    def delete(self, request, image_id):
        try:
            image = ProductImage.objects.get(pk=image_id)
        except ProductImage.DoesNotExist:
            return Response({'detail': 'Image not found.'}, status=status.HTTP_404_NOT_FOUND)
        ProductImageService.delete(image, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
