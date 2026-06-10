"""Serializers for WishlistItem."""
from rest_framework import serializers
from apps.catalog.models import Product
from .models import WishlistItem


class WishlistAddRequestSerializer(serializers.Serializer):
    """Request payload to add a product to the wishlist."""
    product_id = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value: int) -> int:
        try:
            product = Product.objects.get(pk=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found.")

        if not product.is_active:
            raise serializers.ValidationError("This product is no longer available.")

        self._validated_product = product
        return value


class WishlistItemSerializer(serializers.ModelSerializer):
    """Read serializer for wishlist items with product summary."""
    product_id = serializers.IntegerField(source='product_id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    price = serializers.DecimalField(
        source='product.effective_price',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    image_url = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = [
            'id', 'product_id', 'product_name', 'product_slug',
            'price', 'image_url', 'in_stock', 'created_at',
        ]
        read_only_fields = [
            'id', 'product_id', 'product_name', 'product_slug',
            'price', 'image_url', 'in_stock', 'created_at',
        ]

    def get_image_url(self, obj) -> str | None:
        """Return the primary image URL for the product."""
        request = self.context.get('request')
        primary_image = obj.product.images.filter(is_primary=True).first()
        if not primary_image:
            primary_image = obj.product.images.first()
        if primary_image and primary_image.image:
            if request:
                return request.build_absolute_uri(primary_image.image.url)
            return primary_image.image.url
        return None

    def get_in_stock(self, obj) -> bool:
        """Check if any active variant has stock."""
        return obj.product.variants.filter(
            is_active=True, stock_quantity__gt=0
        ).exists()
