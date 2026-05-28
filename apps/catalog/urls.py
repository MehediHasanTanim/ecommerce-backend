from django.urls import path
from .views import (
    # Public
    CategoryListView, CategoryDetailView,
    BrandListView, BrandDetailView,
    ProductListView, ProductDetailView,
    ProductSearchView,
    # Admin
    AdminCategoryCreateView, AdminCategoryDetailView,
    AdminBrandCreateView, AdminBrandDetailView,
    AdminProductCreateView, AdminProductDetailView,
    AdminProductImageUploadView, AdminProductImageDeleteView,
)

urlpatterns = [
    # ── Public: Categories ────────────────────────────────────────────────────
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/<slug:slug>/', CategoryDetailView.as_view(), name='category-detail'),

    # ── Public: Brands ────────────────────────────────────────────────────────
    path('brands/', BrandListView.as_view(), name='brand-list'),
    path('brands/<slug:slug>/', BrandDetailView.as_view(), name='brand-detail'),

    # ── Public: Products ──────────────────────────────────────────────────────
    # NOTE: 'search/' must appear before '<slug:slug>/' to avoid slug capture
    path('products/search/', ProductSearchView.as_view(), name='product-search'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<slug:slug>/', ProductDetailView.as_view(), name='product-detail'),

    # ── Admin: Categories ─────────────────────────────────────────────────────
    path('admin/categories/', AdminCategoryCreateView.as_view(), name='admin-category-create'),
    path('admin/categories/<int:pk>/', AdminCategoryDetailView.as_view(), name='admin-category-detail'),

    # ── Admin: Brands ─────────────────────────────────────────────────────────
    path('admin/brands/', AdminBrandCreateView.as_view(), name='admin-brand-create'),
    path('admin/brands/<int:pk>/', AdminBrandDetailView.as_view(), name='admin-brand-detail'),

    # ── Admin: Products ───────────────────────────────────────────────────────
    path('admin/products/', AdminProductCreateView.as_view(), name='admin-product-create'),
    path('admin/products/<int:pk>/', AdminProductDetailView.as_view(), name='admin-product-detail'),

    # ── Admin: Product Images ─────────────────────────────────────────────────
    path('admin/products/<int:pk>/images/', AdminProductImageUploadView.as_view(), name='admin-product-image-upload'),
    path('admin/products/images/<int:image_id>/', AdminProductImageDeleteView.as_view(), name='admin-product-image-delete'),
]
