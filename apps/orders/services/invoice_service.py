"""InvoiceService – PDF invoice generation using reportlab.

Generates downloadable PDF invoices with:
- Company info
- Customer info
- Order number
- Product lines
- Totals, tax, shipping

Caches generated invoices under MEDIA_ROOT/invoices/.
"""
import logging
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.orders.models import Order
from apps.users.services import create_audit_log

logger = logging.getLogger(__name__)


class InvoiceService:
    """Generates and caches PDF invoices."""

    INVOICE_DIR = 'invoices'

    @classmethod
    def get_invoice_path(cls, order: Order) -> str:
        """Return the relative storage path for an invoice file."""
        return f"{cls.INVOICE_DIR}/{order.order_number}.pdf"

    @classmethod
    def invoice_exists(cls, order: Order) -> bool:
        """Check if a cached invoice already exists."""
        path = cls.get_invoice_path(order)
        return default_storage.exists(path)

    @classmethod
    def generate_invoice(cls, order: Order, user=None) -> bytes:
        """Generate a PDF invoice for the given order.

        Args:
            order: The Order instance with prefetched items.
            user: Optional user for audit logging.

        Returns:
            Raw PDF bytes.

        Raises:
            ImportError: If reportlab is not installed.
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            )
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF invoice generation. "
                "Install it with: pip install reportlab"
            )

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
        elements = []
        styles = getSampleStyleSheet()

        # --- Header ---
        elements.append(Paragraph("<b>INVOICE</b>", styles['Title']))
        elements.append(Spacer(1, 6*mm))

        # Company info
        company_info = [
            Paragraph("<b>AntiGravity E-Commerce</b>", styles['Normal']),
            Paragraph("123 Commerce Street, Dhaka, Bangladesh", styles['Normal']),
            Paragraph("Email: support@antigravity.com", styles['Normal']),
            Paragraph("Phone: +880-1XXX-XXXXXX", styles['Normal']),
        ]
        elements.extend(company_info)
        elements.append(Spacer(1, 6*mm))

        # Customer & Order info table
        customer_data = [
            ["<b>Order Number:</b>", order.order_number],
            ["<b>Date:</b>", order.created_at.strftime('%Y-%m-%d %H:%M')],
            ["<b>Customer:</b>", order.user.full_name or order.user.email],
            ["<b>Email:</b>", order.user.email],
            ["<b>Status:</b>", order.get_status_display()],
        ]

        addr = order.address_snapshot or {}
        if addr:
            customer_data.append(
                ["<b>Shipping Address:</b>",
                 f"{addr.get('name', '')}, {addr.get('address_line', '')}, "
                 f"{addr.get('city', '')}, {addr.get('country', '')}"]
            )

        info_table = Table(customer_data, colWidths=[40*mm, 120*mm])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 10*mm))

        # --- Items Table ---
        items_header = ['#', 'Product', 'SKU', 'Qty', 'Unit Price', 'Line Total']
        items_data = [items_header]

        for i, item in enumerate(order.items.all(), start=1):
            items_data.append([
                str(i),
                item.product_name,
                item.sku,
                str(item.quantity),
                f"${item.unit_price:,.2f}",
                f"${item.line_total:,.2f}",
            ])

        items_table = Table(items_data, colWidths=[8*mm, 55*mm, 30*mm, 12*mm, 25*mm, 25*mm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 10*mm))

        # --- Totals ---
        totals_data = [
            ['Subtotal:', f"${order.subtotal:,.2f}"],
            ['Discount:', f"-${order.discount:,.2f}"],
            ['Shipping Fee:', f"${order.shipping_fee:,.2f}"],
            ['Tax:', f"${order.tax:,.2f}"],
            ['', ''],
            ['<b>Grand Total:</b>', f"<b>${order.grand_total:,.2f}</b>"],
        ]

        totals_table = Table(totals_data, colWidths=[40*mm, 30*mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ]))
        # Right-align the totals table
        from reportlab.platypus import HRFlowable
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        elements.append(Spacer(1, 4*mm))

        # Build a right-aligned wrapper
        totals_wrapper = Table([[totals_table]], colWidths=[160*mm])
        totals_wrapper.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ]))
        elements.append(totals_wrapper)
        elements.append(Spacer(1, 15*mm))

        # --- Footer ---
        elements.append(Paragraph("<i>Thank you for your order!</i>", styles['Normal']))
        elements.append(Paragraph(
            "<i>For any inquiries, please contact support@antigravity.com</i>",
            styles['Normal'],
        ))

        # Build PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Cache to storage
        path = cls.get_invoice_path(order)
        default_storage.save(path, ContentFile(pdf_bytes))

        # Audit log
        if user:
            create_audit_log(
                action='INVOICE_GENERATED',
                user=user,
                resource_type='Order',
                resource_id=str(order.id),
                metadata={
                    'order_number': order.order_number,
                    'file_path': path,
                },
            )

        logger.info(
            "Invoice generated: %s, size=%s bytes",
            order.order_number, len(pdf_bytes),
            extra={
                'order_number': order.order_number,
                'user_id': str(user.id) if user else None,
                'event': 'INVOICE_GENERATED',
                'status': 'success',
            },
        )

        return pdf_bytes

    @classmethod
    def get_or_generate_invoice(cls, order: Order, user=None) -> tuple[bytes, bool]:
        """Get cached invoice or generate new one.

        Returns:
            Tuple of (pdf_bytes, is_cached).
        """
        if cls.invoice_exists(order):
            path = cls.get_invoice_path(order)
            with default_storage.open(path, 'rb') as f:
                pdf_bytes = f.read()
            logger.info("Invoice served from cache: %s", order.order_number)
            return pdf_bytes, True

        pdf_bytes = cls.generate_invoice(order, user=user)
        return pdf_bytes, False
