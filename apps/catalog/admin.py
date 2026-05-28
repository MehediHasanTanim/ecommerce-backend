from django.contrib import admin
from .models import Category, Brand, Product, ProductVariant, ProductImage


# ── Inlines ───────────────────────────────────────────────────────────────────

class CategoryChildInline(admin.TabularInline):
    model = Category
    fk_name = 'parent'
    extra = 0
    fields = ('name', 'slug', 'is_active', 'display_order')
    readonly_fields = ('slug',)
    show_change_link = True


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ('sku', 'variant_name', 'attributes', 'price', 'sale_price', 'stock_quantity', 'is_active')
    readonly_fields = ()


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ('image', 'alt_text', 'is_primary', 'display_order')


# ── Admin Classes ─────────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active', 'display_order', 'created_at')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('display_order', 'name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CategoryChildInline]

    fieldsets = (
        (None, {'fields': ('name', 'slug', 'parent', 'description', 'image')}),
        ('Status', {'fields': ('is_active', 'display_order')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {'fields': ('name', 'slug', 'logo', 'description')}),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'brand', 'base_price', 'is_active', 'is_featured', 'created_at')
    list_filter = ('is_active', 'is_featured', 'category', 'brand')
    search_fields = ('name', 'slug', 'sku')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('category', 'brand')
    inlines = [ProductVariantInline, ProductImageInline]

    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'sku', 'category', 'brand')}),
        ('Description', {'fields': ('short_description', 'description')}),
        ('Pricing', {'fields': ('base_price', 'sale_price')}),
        ('Status', {'fields': ('is_active', 'is_featured')}),
        ('SEO', {'fields': ('meta_title', 'meta_description'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('variant_name', 'sku', 'product', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('sku', 'variant_name', 'product__name')
    raw_id_fields = ('product',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_primary', 'display_order', 'alt_text', 'created_at')
    list_filter = ('is_primary',)
    search_fields = ('product__name', 'alt_text')
    raw_id_fields = ('product', 'variant')
    readonly_fields = ('created_at',)
