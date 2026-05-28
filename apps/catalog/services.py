import logging
from django.db import transaction
from django.utils.text import slugify
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.users.services import create_audit_log
from .models import Category, Brand, Product, ProductVariant, ProductImage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _unique_slug(model_class, base_slug, instance_pk=None):
    """Return a unique slug for *model_class*, avoiding *instance_pk* (for updates)."""
    slug = base_slug
    counter = 1
    qs = model_class.objects.all()
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _validate_image_file(image_file):
    """Raise ValidationError if image does not meet type/size requirements."""
    allowed_types = getattr(settings, 'CATALOG_ALLOWED_IMAGE_TYPES', ['image/jpeg', 'image/png', 'image/webp'])
    max_mb = getattr(settings, 'CATALOG_IMAGE_MAX_SIZE_MB', 5)

    content_type = getattr(image_file, 'content_type', None)
    if content_type and content_type not in allowed_types:
        raise ValidationError(
            f"Unsupported file type '{content_type}'. Allowed: {', '.join(allowed_types)}."
        )

    # Extension check as fallback
    name = getattr(image_file, 'name', '')
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    allowed_exts = {'jpg', 'jpeg', 'png', 'webp'}
    if ext not in allowed_exts:
        raise ValidationError(
            f"Unsupported file extension '.{ext}'. Allowed: jpg, jpeg, png, webp."
        )

    size_bytes = getattr(image_file, 'size', 0)
    if size_bytes > max_mb * 1024 * 1024:
        raise ValidationError(f"File size exceeds {max_mb} MB limit.")


# ---------------------------------------------------------------------------
# Category Service
# ---------------------------------------------------------------------------

class CategoryService:

    @staticmethod
    @transaction.atomic
    def create(data: dict, actor=None) -> Category:
        if 'slug' not in data or not data['slug']:
            data['slug'] = _unique_slug(Category, slugify(data['name']))
        category = Category.objects.create(**data)
        create_audit_log(
            'CATEGORY_CREATED',
            user=actor,
            resource_type='Category',
            resource_id=str(category.id),
            metadata={'name': category.name},
        )
        logger.info("Category created: %s (id=%s)", category.name, category.id)
        return category

    @staticmethod
    @transaction.atomic
    def update(category: Category, data: dict, actor=None) -> Category:
        if 'name' in data and ('slug' not in data or not data.get('slug')):
            data['slug'] = _unique_slug(Category, slugify(data['name']), category.pk)
        for attr, value in data.items():
            setattr(category, attr, value)
        category.save()
        create_audit_log(
            'CATEGORY_UPDATED',
            user=actor,
            resource_type='Category',
            resource_id=str(category.id),
            metadata={'fields': list(data.keys())},
        )
        logger.info("Category updated: %s (id=%s)", category.name, category.id)
        return category

    @staticmethod
    @transaction.atomic
    def delete(category: Category, actor=None) -> None:
        category_id = str(category.id)
        category_name = category.name
        category.delete()
        create_audit_log(
            'CATEGORY_DELETED',
            user=actor,
            resource_type='Category',
            resource_id=category_id,
            metadata={'name': category_name},
        )
        logger.info("Category deleted: %s (id=%s)", category_name, category_id)


# ---------------------------------------------------------------------------
# Brand Service
# ---------------------------------------------------------------------------

class BrandService:

    @staticmethod
    @transaction.atomic
    def create(data: dict, actor=None) -> Brand:
        if 'slug' not in data or not data['slug']:
            data['slug'] = _unique_slug(Brand, slugify(data['name']))
        brand = Brand.objects.create(**data)
        create_audit_log(
            'BRAND_CREATED',
            user=actor,
            resource_type='Brand',
            resource_id=str(brand.id),
            metadata={'name': brand.name},
        )
        logger.info("Brand created: %s (id=%s)", brand.name, brand.id)
        return brand

    @staticmethod
    @transaction.atomic
    def update(brand: Brand, data: dict, actor=None) -> Brand:
        if 'name' in data and ('slug' not in data or not data.get('slug')):
            data['slug'] = _unique_slug(Brand, slugify(data['name']), brand.pk)
        for attr, value in data.items():
            setattr(brand, attr, value)
        brand.save()
        create_audit_log(
            'BRAND_UPDATED',
            user=actor,
            resource_type='Brand',
            resource_id=str(brand.id),
            metadata={'fields': list(data.keys())},
        )
        logger.info("Brand updated: %s (id=%s)", brand.name, brand.id)
        return brand

    @staticmethod
    @transaction.atomic
    def delete(brand: Brand, actor=None) -> None:
        brand_id = str(brand.id)
        brand_name = brand.name
        brand.delete()
        create_audit_log(
            'BRAND_DELETED',
            user=actor,
            resource_type='Brand',
            resource_id=brand_id,
            metadata={'name': brand_name},
        )
        logger.info("Brand deleted: %s (id=%s)", brand_name, brand_id)


# ---------------------------------------------------------------------------
# Product Service
# ---------------------------------------------------------------------------

class ProductService:

    @staticmethod
    @transaction.atomic
    def create(data: dict, actor=None) -> Product:
        variants_data = data.pop('variants', [])
        if 'slug' not in data or not data['slug']:
            data['slug'] = _unique_slug(Product, slugify(data['name']))
        product = Product.objects.create(**data)

        for variant_data in variants_data:
            ProductVariant.objects.create(product=product, **variant_data)

        create_audit_log(
            'PRODUCT_CREATED',
            user=actor,
            resource_type='Product',
            resource_id=str(product.id),
            metadata={'name': product.name, 'sku': product.sku},
        )
        logger.info("Product created: %s (id=%s, sku=%s)", product.name, product.id, product.sku)
        return product

    @staticmethod
    @transaction.atomic
    def update(product: Product, data: dict, actor=None) -> Product:
        variants_data = data.pop('variants', None)
        if 'name' in data and ('slug' not in data or not data.get('slug')):
            data['slug'] = _unique_slug(Product, slugify(data['name']), product.pk)
        for attr, value in data.items():
            setattr(product, attr, value)
        product.save()

        if variants_data is not None:
            product.variants.all().delete()
            for variant_data in variants_data:
                ProductVariant.objects.create(product=product, **variant_data)

        create_audit_log(
            'PRODUCT_UPDATED',
            user=actor,
            resource_type='Product',
            resource_id=str(product.id),
            metadata={'fields': list(data.keys())},
        )
        logger.info("Product updated: %s (id=%s)", product.name, product.id)
        return product

    @staticmethod
    @transaction.atomic
    def delete(product: Product, actor=None) -> None:
        product_id = str(product.id)
        product_name = product.name
        product.delete()
        create_audit_log(
            'PRODUCT_DELETED',
            user=actor,
            resource_type='Product',
            resource_id=product_id,
            metadata={'name': product_name},
        )
        logger.info("Product deleted: %s (id=%s)", product_name, product_id)


# ---------------------------------------------------------------------------
# Product Image Service
# ---------------------------------------------------------------------------

class ProductImageService:

    @staticmethod
    @transaction.atomic
    def upload(product: Product, image_file, data: dict, actor=None) -> ProductImage:
        _validate_image_file(image_file)

        is_primary = data.get('is_primary', False)
        if is_primary:
            # Clear existing primary
            ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)

        variant = data.get('variant')
        image_obj = ProductImage.objects.create(
            product=product,
            image=image_file,
            alt_text=data.get('alt_text', ''),
            is_primary=is_primary,
            display_order=data.get('display_order', 0),
            variant=variant,
        )
        create_audit_log(
            'PRODUCT_IMAGE_UPLOADED',
            user=actor,
            resource_type='ProductImage',
            resource_id=str(image_obj.id),
            metadata={'product_id': str(product.id), 'is_primary': is_primary},
        )
        logger.info("ProductImage uploaded: id=%s for product=%s", image_obj.id, product.id)
        return image_obj

    @staticmethod
    @transaction.atomic
    def delete(image: ProductImage, actor=None) -> None:
        image_id = str(image.id)
        product_id = str(image.product_id)
        # Remove the file from storage
        if image.image:
            image.image.delete(save=False)
        image.delete()
        create_audit_log(
            'PRODUCT_IMAGE_DELETED',
            user=actor,
            resource_type='ProductImage',
            resource_id=image_id,
            metadata={'product_id': product_id},
        )
        logger.info("ProductImage deleted: id=%s from product=%s", image_id, product_id)


# ---------------------------------------------------------------------------
# Search Service
# ---------------------------------------------------------------------------

class SearchService:
    """
    Searches active products using PostgreSQL full-text search.
    Falls back to icontains for fields not covered by SearchVector.
    SQL injection is inherently safe via Django ORM parameterisation.
    """

    @staticmethod
    def search(q: str):
        """
        Return a queryset of active Products matching the search query *q*.
        Searches: name, SKU, description, category name, brand name.
        Empty *q* returns an empty queryset.
        """
        if not q or not q.strip():
            return Product.objects.none()

        q = q.strip()

        base_qs = (
            Product.objects
            .filter(is_active=True)
            .select_related('category', 'brand')
            .prefetch_related('images', 'variants')
        )

        # PostgreSQL full-text search on name + description
        search_vector = SearchVector('name', weight='A') + SearchVector('description', weight='C')
        search_query = SearchQuery(q, search_type='websearch')

        # icontains for sku, category name, brand name (not easily vectorised via joins)
        broad_q = (
            Q(name__icontains=q) |
            Q(sku__icontains=q) |
            Q(description__icontains=q) |
            Q(category__name__icontains=q) |
            Q(brand__name__icontains=q)
        )

        try:
            qs = (
                base_qs
                .annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query),
                )
                .filter(Q(search=search_query) | broad_q)
                .order_by('-rank', '-created_at')
                .distinct()
            )
            # Force evaluation to detect potential issues with FTS
            list(qs[:1])
            return qs
        except Exception:
            # Graceful fallback to pure icontains if FTS fails
            logger.warning("FTS search failed, falling back to icontains for q=%r", q)
            return base_qs.filter(broad_q).distinct()
