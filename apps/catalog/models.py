import logging
from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.conf import settings

logger = logging.getLogger(__name__)


def _unique_slug(model_class, base_slug, instance_pk=None):
    """Generate a unique slug for a model, appending a counter if needed."""
    slug = base_slug
    counter = 1
    qs = model_class.objects.all()
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


class Category(models.Model):
    """
    Hierarchical product category.
    Supports self-referential parent/child relationships.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        db_index=True,
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['parent']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = _unique_slug(Category, base_slug, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(models.Model):
    """Product brand / manufacturer."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = _unique_slug(Brand, base_slug, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Core product entity.
    Public APIs only expose active products (is_active=True).
    """
    name = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, unique=True, blank=True, db_index=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        db_index=True,
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        db_index=True,
    )
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['category']),
            models.Index(fields=['brand']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = _unique_slug(Product, base_slug, self.pk)
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Return sale_price if set, else base_price."""
        return self.sale_price if self.sale_price is not None else self.base_price

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    """
    A product variant with its own SKU, pricing, and stock.
    Inactive variants are hidden from public APIs.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    variant_name = models.CharField(max_length=255)
    attributes = models.JSONField(
        default=dict,
        blank=True,
        help_text='e.g. {"size": "L", "color": "Red", "storage": "128GB"}'
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Overrides product base_price when set.'
    )
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['variant_name']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['sku']),
        ]

    def clean(self):
        if self.stock_quantity is not None and self.stock_quantity < 0:
            raise ValidationError({'stock_quantity': 'Stock quantity cannot be negative.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Variant price overrides product price when available."""
        if self.sale_price is not None:
            return self.sale_price
        if self.price is not None:
            return self.price
        return self.product.effective_price

    def __str__(self):
        return f"{self.product.name} – {self.variant_name}"


def _product_image_upload_path(instance, filename):
    return f"products/{instance.product_id}/{filename}"


class ProductImage(models.Model):
    """
    Product image. Only one image per product can be is_primary=True.
    File type and size are validated in the service layer.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='images',
    )
    image = models.ImageField(upload_to=_product_image_upload_path)
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-is_primary']
        indexes = [
            models.Index(fields=['product', 'is_primary']),
        ]

    def save(self, *args, **kwargs):
        # Enforce single primary image per product
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.product.name} (primary={self.is_primary})"
