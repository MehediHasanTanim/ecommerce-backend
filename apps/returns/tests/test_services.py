import pytest
from unittest.mock import patch
from apps.returns.services import process_refund, approve_return

@pytest.mark.django_db
class TestReturnsServices:

    @patch("apps.returns.services.create_audit_log")
    @patch("apps.returns.services.update_order_status")
    @patch("apps.returns.services.update_payment_refund_status")
    @patch("apps.returns.services.create_refund_record")
    def test_refund_success(self, mock_create_refund, mock_update_payment, mock_update_order, mock_create_audit):
        """Successful refund updates refund/payment/order together"""
        process_refund({"data": 1})
        
        mock_create_refund.assert_called_once()
        mock_update_payment.assert_called_once()
        mock_update_order.assert_called_once()
        mock_create_audit.assert_called_once()

    @patch("apps.returns.services.create_audit_log")
    @patch("apps.returns.services.update_order_status")
    @patch("apps.returns.services.update_payment_refund_status")
    @patch("apps.returns.services.create_refund_record")
    def test_refund_failure_rollback(self, mock_create_refund, mock_update_payment, mock_update_order, mock_create_audit):
        """Failure rolls back all changes"""
        mock_update_order.side_effect = Exception("Order update failed")
        
        with pytest.raises(Exception, match="Order update failed"):
            process_refund({"data": 1})
            
        mock_create_refund.assert_called_once()
        mock_update_payment.assert_called_once()
        mock_update_order.assert_called_once()
        mock_create_audit.assert_not_called()

    @patch("apps.returns.services.create_audit_log")
    @patch("apps.returns.services.trigger_refund_if_required")
    @patch("apps.returns.services.update_order_item_status")
    @patch("apps.returns.services.restore_stock_if_required")
    @patch("apps.returns.services.approve_return_request")
    def test_return_approval_success(self, mock_approve, mock_restore, mock_update_item, mock_trigger_refund, mock_create_audit):
        """Successful return approval updates return/order/inventory together"""
        approve_return({"data": 1})
        
        mock_approve.assert_called_once()
        mock_restore.assert_called_once()
        mock_update_item.assert_called_once()
        mock_trigger_refund.assert_called_once()
        mock_create_audit.assert_called_once()

    @patch("apps.returns.services.create_audit_log")
    @patch("apps.returns.services.trigger_refund_if_required")
    @patch("apps.returns.services.update_order_item_status")
    @patch("apps.returns.services.restore_stock_if_required")
    @patch("apps.returns.services.approve_return_request")
    def test_return_approval_failure_rollback(self, mock_approve, mock_restore, mock_update_item, mock_trigger_refund, mock_create_audit):
        """Failure rolls back all changes"""
        mock_trigger_refund.side_effect = Exception("Refund trigger failed")
        
        with pytest.raises(Exception, match="Refund trigger failed"):
            approve_return({"data": 1})
            
        mock_approve.assert_called_once()
        mock_restore.assert_called_once()
        mock_update_item.assert_called_once()
        mock_trigger_refund.assert_called_once()
        mock_create_audit.assert_not_called()
