import pytest
from unittest.mock import patch
from apps.inventory.services import reserve_stock_flow

@pytest.mark.django_db
class TestInventoryServices:

    @patch("apps.inventory.services.create_inventory_log")
    @patch("apps.inventory.services.decrement_variant_stock")
    def test_reserve_stock_flow_success(self, mock_decrement, mock_log):
        """Successful stock reservation"""
        reserve_stock_flow("var123", 5)
        
        mock_decrement.assert_called_once_with("var123", 5)
        mock_log.assert_called_once_with("var123", 5, "reserved")

    @patch("apps.inventory.services.create_inventory_log")
    @patch("apps.inventory.services.decrement_variant_stock")
    def test_reserve_stock_flow_failure(self, mock_decrement, mock_log):
        """Failure in log creation rolls back decrement"""
        mock_log.side_effect = Exception("Log failed")
        
        with pytest.raises(Exception, match="Log failed"):
            reserve_stock_flow("var123", 5)
            
        mock_decrement.assert_called_once()
        mock_log.assert_called_once()
