from rest_framework import serializers
from django.conf import settings
from .models import Category, Brand, Product, ProductVariant, ProductImage

ALLOWED_EXTS = {'jpg', 'jpeg', 'png', 'webp'}


# ---------------------------------------------------------------------------
# Category Serializers
# ---------------------------------------------------------------------------

class CategorySerializer(serializers.ModelSerializer):
    """Public read serializer — flat representation with parent id."""
    parent = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'parent', 'description',
            'image', 'is_active', 'display_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class CategoryWriteSerializer(serializers.ModelSerializer):
    """Admin write serializer for Category create/update."""
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = [
            'name', 'slug', 'parent', 'description',
            'image', 'is_active', 'display_order',
        ]

    def validate_slug(self, value):
        if not value:
            return value
        qs = Category.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this slug already exists.")
        return value


# ---------------------------------------------------------------------------
# Brand Serializers
# ---------------------------------------------------------------------------

class BrandSerializer(serializers.ModelSerializer):
    """Public read serializer for Brand."""

    class Meta:
        model = Brand
        fields = [
            'id', 'name', 'slug', 'logo', 'description',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class BrandWriteSerializer(serializers.ModelSerializer):
    """Admin write serializer for Brand create/update."""
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Brand
        fields = ['name', 'slug', 'logo', 'description', 'is_active']

    def validate_slug(self, value):
        if not value:
            return value
        qs = Brand.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A brand with this slug already exists.")
        return value


# ---------------------------------------------------------------------------
# Product Image Serializer
# ---------------------------------------------------------------------------

class ProductImageSerializer(serializers.ModelSerializer):
    """Returns absolute image URL via request context."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            'id', 'image_url', 'alt_text',
            'is_primary', 'display_order', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            return obj.image.url
        return None


class ProductImageUploadSerializer(serializers.Serializer):
    """Validates image upload: file type, size, and metadata."""
    image = serializers.ImageField()
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(default=False)
    display_order = serializers.IntegerField(default=0, min_value=0)
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_image(self, image_file):
        max_mb = getattr(settings, 'CATALOG_IMAGE_MAX_SIZE_MB', 5)
        allowed_types = getattr(
            settings, 'CATALOG_ALLOWED_IMAGE_TYPES',
            ['image/jpeg', 'image/png', 'image/webp'],
        )
        # File size
        if image_file.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"File size exceeds {max_mb} MB limit.")
        # Content-type
        content_type = getattr(image_file, 'content_type', None)
        if content_type and content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Unsupported file type. Allowed: jpg, jpeg, png, webp."
            )
        # Extension fallback
        name = getattr(image_file, 'name', '')
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if ext not in ALLOWED_EXTS:
            raise serializers.ValidationError(
                f"Unsupported file extension '.{ext}'. Allowed: jpg, jpeg, png, webp."
            )
        return image_file


# ---------------------------------------------------------------------------
# Product Variant Serializer
# ---------------------------------------------------------------------------

class ProductVariantSerializer(serializers.ModelSerializer):
    """Public read serializer for ProductVariant."""
    effective_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'sku', 'variant_name', 'attributes',
            'price', 'sale_price', 'effective_price',
            'stock_quantity', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductVariantWriteSerializer(serializers.ModelSerializer):
    """Admin write serializer for ProductVariant."""

    class Meta:
        model = ProductVariant
        fields = [
            'sku', 'variant_name', 'attributes',
            'price', 'sale_price', 'stock_quantity', 'is_active',
        ]

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock quantity cannot be negative.")
        return value

    def validate_sku(self, value):
        qs = ProductVariant.objects.filter(sku=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A variant with this SKU already exists.")
        return value


# ---------------------------------------------------------------------------
# Product Listing Serializer (lightweight)
# ---------------------------------------------------------------------------

class ProductListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the product list endpoint.
    Returns only what the listing UI needs.
    """
    category = serializers.StringRelatedField()
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    brand = serializers.StringRelatedField()
    brand_slug = serializers.CharField(source='brand.slug', read_only=True)
    primary_image = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    price = serializers.DecimalField(source='base_price', max_digits=12, decimal_places=2)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug',
            'category', 'category_slug',
            'brand', 'brand_slug',
            'price', 'sale_price',
            'primary_image', 'stock_status', 'is_featured',
        ]

    def get_primary_image(self, obj):
        request = self.context.get('request')
        primary = next((img for img in obj.images.all() if img.is_primary), None)
        if primary is None:
            primary = next(iter(obj.images.all()), None)
        if primary and primary.image:
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None

    def get_stock_status(self, obj):
        """'in_stock' if any active variant has stock > 0, else 'out_of_stock'."""
        for variant in obj.variants.all():
            if variant.is_active and variant.stock_quantity > 0:
                return 'in_stock'
        return 'out_of_stock'


# ---------------------------------------------------------------------------
# Product Detail Serializer (full)
# ---------------------------------------------------------------------------

class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for the product detail endpoint.
    Includes variants, images, SEO fields, related products.
    """
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    variants = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'category', 'brand',
            'short_description', 'description',
            'base_price', 'sale_price', 'effective_price',
            'is_active', 'is_featured',
            'meta_title', 'meta_description',
            'stock_status',
            'variants', 'images',
            'related_products',
            'created_at', 'updated_at',
        ]

    def get_variants(self, obj):
        active_variants = [v for v in obj.variants.all() if v.is_active]
        return ProductVariantSerializer(
            active_variants, many=True, context=self.context
        ).data

    def get_images(self, obj):
        return ProductImageSerializer(
            obj.images.all(), many=True, context=self.context
        ).data

    def get_related_products(self, obj):
        if not obj.category_id:
            return []
        related = (
            Product.objects
            .filter(category_id=obj.category_id, is_active=True)
            .exclude(pk=obj.pk)
            .prefetch_related('images')
            .select_related('category', 'brand')[:6]
        )
        return ProductListSerializer(related, many=True, context=self.context).data

    def get_stock_status(self, obj):
        for variant in obj.variants.all():
            if variant.is_active and variant.stock_quantity > 0:
                return 'in_stock'
        return 'out_of_stock'


# ---------------------------------------------------------------------------
# Product Write Serializer (admin)
# ---------------------------------------------------------------------------

class ProductWriteSerializer(serializers.ModelSerializer):
    """Admin write serializer for Product create/update."""
    slug = serializers.SlugField(required=False, allow_blank=True)
    variants = ProductVariantWriteSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'name', 'slug', 'sku', 'category', 'brand',
            'short_description', 'description',
            'base_price', 'sale_price',
            'is_active', 'is_featured',
            'meta_title', 'meta_description', 'variants',
        ]

    def validate_slug(self, value):
        if not value:
            return value
        qs = Product.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A product with this slug already exists.")
        return value

    def validate_sku(self, value):
        qs = Product.objects.filter(sku=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A product with this SKU already exists.")
        return value

    def validate(self, attrs):
        sale_price = attrs.get('sale_price')
        base_price = attrs.get('base_price') or (self.instance.base_price if self.instance else None)
        if sale_price is not None and base_price is not None:
            if sale_price >= base_price:
                raise serializers.ValidationError(
                    {"sale_price": "Sale price must be less than base price."}
                )
        return attrs
