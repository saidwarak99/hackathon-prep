"""
test_tools_unit.py - Unit Tests for DB Tools using Mocked Database Responses
"""

import unittest
from unittest.mock import patch
from tools import get_menu, get_inventory, get_today_sales


class TestDBTools(unittest.TestCase):

    @patch("tools.execute_query")
    def test_get_menu_success(self, mock_exec):
        mock_exec.return_value = [
            {
                "menu_item_id": "item_1",
                "item_name": "Espresso",
                "category_id": "cat_1",
                "category_name": "Coffee",
                "list_price_inr": 150.0,
                "diet_type": "vegan",
                "is_available": True
            },
            {
                "menu_item_id": "item_2",
                "item_name": "Latte",
                "category_id": "cat_1",
                "category_name": "Coffee",
                "list_price_inr": 220.0,
                "diet_type": "vegetarian",
                "is_available": True
            }
        ]

        result = get_menu()
        self.assertEqual(result["status"], "success")
        data = result["data"]
        self.assertEqual(data["total_items"], 2)
        self.assertEqual(len(data["categories"]), 1)
        self.assertEqual(data["categories"][0]["category_name"], "Coffee")
        self.assertEqual(len(data["categories"][0]["items"]), 2)

    @patch("tools.execute_query")
    def test_get_inventory_success(self, mock_exec):
        mock_exec.return_value = [
            {
                "ingredient_id": "ing_1",
                "ingredient_name": "Milk",
                "ingredient_category": "Dairy",
                "on_hand_quantity": 2.0,
                "reorder_level": 5.0,
                "unit": "L",
                "last_count_date": "2026-10-01",
                "status": "Low Stock - Reorder Needed!"
            },
            {
                "ingredient_id": "ing_2",
                "ingredient_name": "Coffee Beans",
                "ingredient_category": "Dry",
                "on_hand_quantity": 20.0,
                "reorder_level": 5.0,
                "unit": "kg",
                "last_count_date": "2026-10-01",
                "status": "In Stock"
            }
        ]

        result = get_inventory()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["total_items"], 2)
        self.assertEqual(result["summary"]["low_stock_items_count"], 1)
        self.assertIn("ing_1", result["data"])
        self.assertEqual(result["data"]["ing_1"]["status"], "Low Stock - Reorder Needed!")

    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_today_sales_success(self, mock_single, mock_query):
        # 1. max_date or today check
        mock_single.side_effect = [
            {"count": 0},                     # today count check
            {"max_date": "2026-10-08"},       # max completed date
            {"total_orders": 25, "total_revenue": 12500.0, "average_order_value": 500.0}, # summary
            {"hour": 9, "order_count": 8}     # busiest hour
        ]
        # 2. top items & payments
        mock_query.side_effect = [
            [{"item": "Latte", "quantity_sold": 15, "revenue": 3300.0}], # top items
            [{"payment_method": "upi", "total_amount": 10000.0}, {"payment_method": "card", "total_amount": 2500.0}] # payments
        ]

        result = get_today_sales()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["date"], "2026-10-08")
        self.assertEqual(result["data"]["summary"]["total_revenue"], 12500.0)
        self.assertEqual(result["data"]["summary"]["total_orders"], 25)
        self.assertEqual(len(result["data"]["top_selling_items"]), 1)
        self.assertEqual(result["data"]["payment_breakdown"]["upi"], 10000.0)


if __name__ == "__main__":
    unittest.main()
