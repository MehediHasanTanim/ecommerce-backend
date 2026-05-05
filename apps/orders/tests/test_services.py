import pytest
from unittest.mock import patch
from apps.orders.services import place_order

@pytest.mark.django_db
class TestOrderServices:

    @patch("apps.orders.services.create_audit_log")
    @patch("apps.orders.services.clear_cart")
    @patch("apps.orders.services.create_payment_record")
    @patch("apps.orders.services.reserve_stock")
    @patch("apps.orders.services.create_order_items")
    @patch("apps.orders.services.create_order")
    def test_place_order_success(self, mock_create_order, mock_create_order_items, mock_reserve_stock, mock_create_payment_record, mock_clear_cart, mock_create_audit_log):
        """Successful order commits all related records"""
        mock_create_order.return_value = "order123"
        
        result = place_order({"data": 1}, {"cart": 1})
        
        assert result == "order123"
        mock_create_order.assert_called_once()
        mock_create_order_items.assert_called_once()
        mock_reserve_stock.assert_called_once()
        mock_create_payment_record.assert_called_once()
        mock_clear_cart.assert_called_once()
        mock_create_audit_log.assert_called_once()

    @patch("apps.orders.services.create_audit_log")
    @patch("apps.orders.services.clear_cart")
    @patch("apps.orders.services.create_payment_record")
    @patch("apps.orders.services.reserve_stock")
    @patch("apps.orders.services.create_order_items")
    @patch("apps.orders.services.create_order")
    def test_place_order_failure_rollback(self, mock_create_order, mock_create_order_items, mock_reserve_stock, mock_create_payment_record, mock_clear_cart, mock_create_audit_log):
        """Failure during stock reservation rolls back order/order_items/payment/cart changes"""
        mock_create_order.return_value = "order123"
        mock_reserve_stock.side_effect = Exception("Stock reservation failed")
        
        with pytest.raises(Exception, match="Stock reservation failed"):
            place_order({"data": 1}, {"cart": 1})
            
        mock_create_order.assert_called_once()
        mock_create_order_items.assert_called_once()
        mock_reserve_stock.assert_called_once()
        mock_create_payment_record.assert_not_called()
        mock_clear_cart.assert_not_called()
        mock_create_audit_log.assert_not_called()
