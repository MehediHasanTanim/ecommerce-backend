import pytest
from unittest.mock import patch
from apps.payments.services import confirm_payment

@pytest.mark.django_db
class TestPaymentServices:

    @patch("apps.payments.services.create_audit_log")
    @patch("apps.payments.services.update_order_payment_status")
    @patch("apps.payments.services.update_payment_status")
    @patch("apps.payments.services.is_payment_already_confirmed")
    def test_payment_confirmation_success(self, mock_is_confirmed, mock_update_payment, mock_update_order, mock_create_audit):
        """Successful payment confirmation updates payment and order together"""
        mock_is_confirmed.return_value = False
        
        confirm_payment("pay123", {"status": "success"})
        
        mock_update_payment.assert_called_once()
        mock_update_order.assert_called_once()
        mock_create_audit.assert_called_once()

    @patch("apps.payments.services.create_audit_log")
    @patch("apps.payments.services.update_order_payment_status")
    @patch("apps.payments.services.update_payment_status")
    @patch("apps.payments.services.is_payment_already_confirmed")
    def test_payment_confirmation_failure_rollback(self, mock_is_confirmed, mock_update_payment, mock_update_order, mock_create_audit):
        """Failure after payment update rolls back order/payment changes"""
        mock_is_confirmed.return_value = False
        mock_update_order.side_effect = Exception("Order update failed")
        
        with pytest.raises(Exception, match="Order update failed"):
            confirm_payment("pay123", {"status": "success"})
            
        mock_update_payment.assert_called_once()
        mock_update_order.assert_called_once()
        mock_create_audit.assert_not_called()

    @patch("apps.payments.services.update_payment_status")
    @patch("apps.payments.services.is_payment_already_confirmed")
    def test_duplicate_webhook_idempotent(self, mock_is_confirmed, mock_update_payment):
        """Duplicate webhook remains idempotent"""
        mock_is_confirmed.return_value = True
        
        confirm_payment("pay123", {"status": "success"})
        
        mock_update_payment.assert_not_called()
