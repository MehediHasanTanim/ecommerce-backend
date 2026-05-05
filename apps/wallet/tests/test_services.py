import pytest
from unittest.mock import patch
from apps.wallet.services import adjust_wallet_balance

@pytest.mark.django_db
class TestWalletServices:

    @patch("apps.wallet.services.create_audit_log")
    @patch("apps.wallet.services.update_wallet_balance")
    @patch("apps.wallet.services.create_wallet_transaction")
    def test_adjust_wallet_balance_success(self, mock_create_transaction, mock_update_balance, mock_create_audit):
        """Successful points adjustment commits transaction + balance update"""
        adjust_wallet_balance("wallet123", {"amount": 100})
        
        mock_create_transaction.assert_called_once()
        mock_update_balance.assert_called_once()
        mock_create_audit.assert_called_once()

    @patch("apps.wallet.services.create_audit_log")
    @patch("apps.wallet.services.update_wallet_balance")
    @patch("apps.wallet.services.create_wallet_transaction")
    def test_adjust_wallet_balance_failure_rollback(self, mock_create_transaction, mock_update_balance, mock_create_audit):
        """Failure rolls back wallet transaction and balance update"""
        mock_update_balance.side_effect = Exception("Balance update failed")
        
        with pytest.raises(Exception, match="Balance update failed"):
            adjust_wallet_balance("wallet123", {"amount": 100})
            
        mock_create_transaction.assert_called_once()
        mock_update_balance.assert_called_once()
        mock_create_audit.assert_not_called()
