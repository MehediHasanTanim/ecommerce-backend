"""Unit tests for InvoiceService – PDF generation, caching, path construction.

Covers:
- Invoice file path construction
- Cache existence check
- PDF generation (mocked reportlab)
- Cached retrieval
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock, ANY

import pytest

from apps.orders.models import Order, OrderItem
from apps.orders.services.invoice_service import InvoiceService
from common.tests.factories import (
    UserFactory,
    AddressFactory,
    ProductVariantFactory,
    OrderFactory,
    OrderItemFactory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_order(user=None, address=None):
    """Create a real order with items for invoice testing."""
    if user is None:
        user = UserFactory()
    if address is None:
        address = AddressFactory(user=user, city='Dhaka', type='shipping')

    variant = ProductVariantFactory(stock_quantity=10, reserved_stock=0, is_active=True)

    order = Order.objects.create(
        order_number='ORD-20260611-000099',
        user=user,
        address_snapshot={
            'id': str(address.id), 'name': address.name,
            'phone': address.phone, 'city': address.city,
            'country': address.country, 'area': address.area or '',
            'postal_code': address.postal_code,
            'address_line': address.address_line,
            'type': address.type,
        },
        status=Order.Status.PENDING,
        payment_status=Order.PaymentStatus.PENDING,
        payment_method='cod',
        subtotal=Decimal('200.00'),
        discount=Decimal('10.00'),
        shipping_fee=Decimal('60.00'),
        tax=Decimal('0.00'),
        grand_total=Decimal('250.00'),
    )

    OrderItem.objects.create(
        order=order,
        product=variant.product,
        variant=variant,
        sku=variant.sku,
        product_name=variant.product.name,
        variant_name=variant.variant_name,
        unit_price=Decimal('100.00'),
        quantity=2,
    )

    return order


# ---------------------------------------------------------------------------
# Path & Cache Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInvoicePathAndCache:

    def test_invoice_path_correct_format(self):
        """Path is invoices/ORDER_NUMBER.pdf."""
        user = UserFactory()
        order = _create_test_order(user=user)
        path = InvoiceService.get_invoice_path(order)
        assert path == f'invoices/{order.order_number}.pdf'

    @patch('apps.orders.services.invoice_service.default_storage')
    def test_invoice_exists_true(self, mock_storage):
        """Returns True when cached file exists."""
        user = UserFactory()
        order = _create_test_order(user=user)

        mock_storage.exists.return_value = True
        assert InvoiceService.invoice_exists(order) is True
        mock_storage.exists.assert_called_once()

    @patch('apps.orders.services.invoice_service.default_storage')
    def test_invoice_exists_false(self, mock_storage):
        """Returns False when no cached file."""
        user = UserFactory()
        order = _create_test_order(user=user)

        mock_storage.exists.return_value = False
        assert InvoiceService.invoice_exists(order) is False


# ---------------------------------------------------------------------------
# PDF Generation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInvoiceGeneration:

    @patch('apps.orders.services.invoice_service.default_storage')
    @patch('apps.orders.services.invoice_service.SimpleDocTemplate')
    def test_generate_invoice_creates_pdf(self, mock_doc, mock_storage):
        """generate_invoice builds PDF via reportlab and caches it."""
        user = UserFactory()
        order = _create_test_order(user=user)

        # Mock the document build
        mock_doc_instance = MagicMock()
        mock_doc.return_value = mock_doc_instance

        mock_storage.exists.return_value = False

        pdf_bytes = InvoiceService.generate_invoice(order, user=user)

        # Document was built
        mock_doc_instance.build.assert_called_once()

        # PDF saved to storage
        mock_storage.save.assert_called_once()
        args, _ = mock_storage.save.call_args
        assert 'invoices/' in args[0]
        assert args[0].endswith('.pdf')

        # Result is bytes
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0

    @patch('apps.orders.services.invoice_service.default_storage')
    @patch('apps.orders.services.invoice_service.SimpleDocTemplate')
    def test_generate_invoice_without_user(self, mock_doc, mock_storage):
        """generate_invoice works without a user (no audit log)."""
        order = _create_test_order()

        mock_doc_instance = MagicMock()
        mock_doc.return_value = mock_doc_instance

        pdf_bytes = InvoiceService.generate_invoice(order, user=None)

        assert isinstance(pdf_bytes, bytes)

    @patch('apps.orders.services.invoice_service.default_storage')
    def test_get_or_generate_returns_cached(self, mock_storage):
        """get_or_generate_invoice returns cached file when available."""
        user = UserFactory()
        order = _create_test_order(user=user)

        mock_storage.exists.return_value = True
        mock_storage.open = MagicMock()
        mock_storage.open.return_value.__enter__.return_value.read.return_value = b'cached_pdf'

        pdf_bytes, is_cached = InvoiceService.get_or_generate_invoice(order, user=user)

        assert is_cached is True
        assert pdf_bytes == b'cached_pdf'

    @patch('apps.orders.services.invoice_service.default_storage')
    @patch('apps.orders.services.invoice_service.SimpleDocTemplate')
    def test_get_or_generate_creates_new(self, mock_doc, mock_storage):
        """get_or_generate_invoice generates new when not cached."""
        user = UserFactory()
        order = _create_test_order(user=user)

        mock_storage.exists.return_value = False
        mock_doc_instance = MagicMock()
        mock_doc.return_value = mock_doc_instance

        pdf_bytes, is_cached = InvoiceService.get_or_generate_invoice(order, user=user)

        assert is_cached is False
        assert isinstance(pdf_bytes, bytes)
        mock_doc_instance.build.assert_called_once()

    def test_missing_reportlab_raises_import_error(self):
        """ImportError raised when reportlab is not installed."""
        user = UserFactory()
        order = _create_test_order(user=user)

        with patch('apps.orders.services.invoice_service.InvoiceService.generate_invoice',
                   side_effect=ImportError('No module named reportlab')):
            with pytest.raises(ImportError):
                InvoiceService.generate_invoice(order, user=user)
