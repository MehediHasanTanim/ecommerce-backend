import pytest
from django.urls import reverse
from rest_framework import status

from apps.catalog.models import Brand, Category, Product
from apps.catalog.tests.unit.test_serializers import make_test_image
from common.tests.factories import ProductImageFactory


@pytest.mark.django_db
class TestAdminCatalogPermissions:
    def test_anonymous_user_cannot_create_product(self, api_client):
        response = api_client.post(reverse('admin-product-create'), {})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_customer_cannot_create_update_or_delete_product(self, authenticated_client, product):
        create_response = authenticated_client.post(reverse('admin-product-create'), {})
        update_response = authenticated_client.patch(reverse('admin-product-detail', kwargs={'pk': product.pk}), {})
        delete_response = authenticated_client.delete(reverse('admin-product-detail', kwargs={'pk': product.pk}))

        assert create_response.status_code == status.HTTP_403_FORBIDDEN
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_create_update_and_delete_product(self, admin_client, category, brand):
        create_payload = {
            'name': 'Admin Product',
            'sku': 'ADMIN-PRODUCT-1',
            'category': category.id,
            'brand': brand.id,
            'base_price': '100.00',
        }
        create_response = admin_client.post(reverse('admin-product-create'), create_payload, format='json')
        product_id = create_response.data['id']

        update_response = admin_client.patch(
            reverse('admin-product-detail', kwargs={'pk': product_id}),
            {'name': 'Updated Admin Product'},
            format='json',
        )
        delete_response = admin_client.delete(reverse('admin-product-detail', kwargs={'pk': product_id}))

        assert create_response.status_code == status.HTTP_201_CREATED
        assert update_response.status_code == status.HTTP_200_OK
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        assert not Product.objects.filter(pk=product_id).exists()

    def test_customer_can_view_public_product_data(self, authenticated_client, product):
        response = authenticated_client.get(reverse('product-detail', kwargs={'slug': product.slug}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['slug'] == product.slug

    def test_admin_can_manage_categories(self, admin_client):
        create_response = admin_client.post(reverse('admin-category-create'), {'name': 'Admin Category'}, format='json')
        category_id = create_response.data['id']
        update_response = admin_client.patch(
            reverse('admin-category-detail', kwargs={'pk': category_id}),
            {'name': 'Updated Category'},
            format='json',
        )
        delete_response = admin_client.delete(reverse('admin-category-detail', kwargs={'pk': category_id}))

        assert create_response.status_code == status.HTTP_201_CREATED
        assert update_response.status_code == status.HTTP_200_OK
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(pk=category_id).exists()

    def test_customer_cannot_manage_categories(self, authenticated_client, category):
        assert authenticated_client.post(reverse('admin-category-create'), {}).status_code == status.HTTP_403_FORBIDDEN
        assert authenticated_client.patch(reverse('admin-category-detail', kwargs={'pk': category.pk}), {}).status_code == status.HTTP_403_FORBIDDEN
        assert authenticated_client.delete(reverse('admin-category-detail', kwargs={'pk': category.pk})).status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_manage_brands(self, admin_client):
        create_response = admin_client.post(reverse('admin-brand-create'), {'name': 'Admin Brand'}, format='json')
        brand_id = create_response.data['id']
        update_response = admin_client.patch(
            reverse('admin-brand-detail', kwargs={'pk': brand_id}),
            {'name': 'Updated Brand'},
            format='json',
        )
        delete_response = admin_client.delete(reverse('admin-brand-detail', kwargs={'pk': brand_id}))

        assert create_response.status_code == status.HTTP_201_CREATED
        assert update_response.status_code == status.HTTP_200_OK
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT
        assert not Brand.objects.filter(pk=brand_id).exists()

    def test_customer_cannot_manage_brands(self, authenticated_client, brand):
        assert authenticated_client.post(reverse('admin-brand-create'), {}).status_code == status.HTTP_403_FORBIDDEN
        assert authenticated_client.patch(reverse('admin-brand-detail', kwargs={'pk': brand.pk}), {}).status_code == status.HTTP_403_FORBIDDEN
        assert authenticated_client.delete(reverse('admin-brand-detail', kwargs={'pk': brand.pk})).status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_upload_and_delete_product_image(self, admin_client, product):
        image = make_test_image()
        upload_response = admin_client.post(
            reverse('admin-product-image-upload', kwargs={'pk': product.pk}),
            {'image': image, 'alt_text': 'Front', 'is_primary': True},
            format='multipart',
        )
        image_id = upload_response.data['id']
        delete_response = admin_client.delete(reverse('admin-product-image-delete', kwargs={'image_id': image_id}))

        assert upload_response.status_code == status.HTTP_201_CREATED
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    def test_customer_cannot_upload_or_delete_product_image(self, authenticated_client, product):
        product_image = ProductImageFactory(product=product)
        upload_response = authenticated_client.post(
            reverse('admin-product-image-upload', kwargs={'pk': product.pk}),
            {'image': make_test_image()},
            format='multipart',
        )
        delete_response = authenticated_client.delete(
            reverse('admin-product-image-delete', kwargs={'image_id': product_image.pk})
        )

        assert upload_response.status_code == status.HTTP_403_FORBIDDEN
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
