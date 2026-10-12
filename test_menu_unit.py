"""
test_menu_unit.py - Unit Test Suite for Menu Intelligence Agent & Menu Tools
"""

import unittest
from unittest.mock import patch, MagicMock
from tools import (
    get_menu_performance,
    get_category_performance,
    get_menu_item_comparison,
    get_menu
)
from agent import MenuIntelligenceAgent, MENU_AGENT_SYSTEM_PROMPT


class TestMenuUnit(unittest.TestCase):

    @patch("tools.execute_query")
    def test_get_menu_performance_ranking_and_zero_sales(self, mock_query):
        """Test menu performance calculations, ranking, and zero-sales separation."""
        mock_query.return_value = [
            {
                "menu_item_id": "M001",
                "item_name": "Butter Chicken",
                "category_name": "Curries",
                "list_price_inr": 280.0,
                "diet_type": "non-veg",
                "is_available": True,
                "total_quantity_sold": 15,
                "total_revenue_inr": 4200.0,
                "total_discount_inr": 0.0,
                "order_appearances": 12
            },
            {
                "menu_item_id": "M002",
                "item_name": "Masala Chai",
                "category_name": "Beverages",
                "list_price_inr": 40.0,
                "diet_type": "veg",
                "is_available": True,
                "total_quantity_sold": 0,
                "total_revenue_inr": 0.0,
                "total_discount_inr": 0.0,
                "order_appearances": 0
            }
        ]

        res = get_menu_performance(start_date="2026-10-01", end_date="2026-10-07")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["summary"]["total_menu_items_analyzed"], 2)
        self.assertEqual(data["summary"]["total_units_sold"], 15)
        self.assertEqual(data["summary"]["total_revenue_inr"], 4200.0)
        self.assertEqual(data["summary"]["zero_sales_items_count"], 1)
        self.assertEqual(len(data["zero_sales_items"]), 1)
        self.assertEqual(data["zero_sales_items"][0]["item_name"], "Masala Chai")

    @patch("tools.execute_query")
    def test_menu_performance_tied_quantity_ranking(self, mock_query):
        """Test deterministic tie-breaking for tied quantities (revenue DESC, item_name ASC)."""
        mock_query.return_value = [
            {
                "menu_item_id": "MI020",
                "item_name": "Andhra Chicken Meals",
                "category_name": "Rice & Meals",
                "list_price_inr": 230.0,
                "diet_type": "non-veg",
                "is_available": True,
                "total_quantity_sold": 7,
                "total_revenue_inr": 1552.49,
                "total_discount_inr": 57.51,
                "order_appearances": 7
            },
            {
                "menu_item_id": "MI010",
                "item_name": "Veg Spring Rolls",
                "category_name": "Starters",
                "list_price_inr": 140.0,
                "diet_type": "veg",
                "is_available": True,
                "total_quantity_sold": 7,
                "total_revenue_inr": 945.00,
                "total_discount_inr": 35.00,
                "order_appearances": 6
            },
            {
                "menu_item_id": "MI036",
                "item_name": "Water Bottle",
                "category_name": "Beverages",
                "list_price_inr": 20.0,
                "diet_type": "veg",
                "is_available": True,
                "total_quantity_sold": 7,
                "total_revenue_inr": 138.05,
                "total_discount_inr": 2.95,
                "order_appearances": 6
            },
            {
                "menu_item_id": "MI031",
                "item_name": "Tea",
                "category_name": "Beverages",
                "list_price_inr": 20.0,
                "diet_type": "veg",
                "is_available": True,
                "total_quantity_sold": 7,
                "total_revenue_inr": 130.90,
                "total_discount_inr": 11.10,
                "order_appearances": 5
            }
        ]

        res = get_menu_performance(start_date="2026-10-02", end_date="2026-10-08", sort_by="quantity")
        self.assertEqual(res["status"], "success")
        items = res["data"]["items"]
        self.assertEqual(len(items), 4)

        # Expected deterministic ordering:
        # Andhra Chicken Meals (₹1552.49) -> Veg Spring Rolls (₹945.00) -> Water Bottle (₹138.05) -> Tea (₹130.90)
        self.assertEqual(items[0]["item_name"], "Andhra Chicken Meals")
        self.assertEqual(items[1]["item_name"], "Veg Spring Rolls")
        self.assertEqual(items[2]["item_name"], "Water Bottle")
        self.assertEqual(items[3]["item_name"], "Tea")

        # Verify the executed SQL query contains deterministic tie-break ordering
        call_sql = mock_query.call_args[0][0]
        self.assertIn("ORDER BY total_quantity_sold DESC, total_revenue_inr DESC, mi.item_name ASC", call_sql)

    @patch("tools.execute_query")
    def test_get_menu_performance_empty_results(self, mock_query):
        """Test empty result handling for menu performance."""
        mock_query.return_value = []
        res = get_menu_performance(start_date="2026-10-01", end_date="2026-10-07", category="GhostCategory")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["summary"]["total_menu_items_analyzed"], 0)
        self.assertEqual(res["data"]["summary"]["total_revenue_inr"], 0.0)
        self.assertEqual(len(res["data"]["items"]), 0)

    @patch("tools.execute_query")
    def test_get_category_performance_shares(self, mock_query):
        """Test category performance aggregation, revenue share % and top items."""
        # mock_query is called twice: once for category rows, once for top item rows
        mock_query.side_effect = [
            [
                {
                    "category_id": "CAT01",
                    "category_name": "Curries",
                    "total_items": 5,
                    "active_items": 5,
                    "total_quantity_sold": 30,
                    "total_revenue_inr": 7500.0,
                    "total_discount_inr": 100.0,
                    "average_item_price_inr": 250.0
                },
                {
                    "category_id": "CAT02",
                    "category_name": "Beverages",
                    "total_items": 10,
                    "active_items": 9,
                    "total_quantity_sold": 50,
                    "total_revenue_inr": 2500.0,
                    "total_discount_inr": 50.0,
                    "average_item_price_inr": 50.0
                }
            ],
            [
                {
                    "category_id": "CAT01",
                    "top_item_name": "Butter Chicken",
                    "item_quantity": 20,
                    "item_revenue": 5000.0
                },
                {
                    "category_id": "CAT02",
                    "top_item_name": "Cold Coffee",
                    "item_quantity": 30,
                    "item_revenue": 1800.0
                }
            ]
        ]

        res = get_category_performance(start_date="2026-10-01", end_date="2026-10-07")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["total_revenue_inr"], 10000.0)
        self.assertEqual(len(data["categories"]), 2)

        curries = data["categories"][0]
        self.assertEqual(curries["category_name"], "Curries")
        self.assertEqual(curries["revenue_share_percentage"], 75.0)
        self.assertEqual(curries["top_performing_item"]["name"], "Butter Chicken")

        bevs = data["categories"][1]
        self.assertEqual(bevs["revenue_share_percentage"], 25.0)
        self.assertEqual(bevs["active_items"], 9)

    @patch("tools.execute_query")
    def test_get_menu_item_comparison_with_recipes(self, mock_query):
        """Test side-by-side menu item comparison with recipe ingredients attached."""
        mock_query.side_effect = [
            [
                {
                    "menu_item_id": "M101",
                    "item_name": "Cappuccino",
                    "category_name": "Coffee",
                    "list_price_inr": 120.0,
                    "diet_type": "veg",
                    "is_available": True,
                    "item_added_date": "2026-01-01",
                    "total_quantity_sold": 25,
                    "total_revenue_inr": 3000.0,
                    "total_discount_inr": 0.0,
                    "order_appearances": 20
                }
            ],
            [
                {
                    "menu_item_id": "M101",
                    "ingredient_name": "Espresso Beans",
                    "quantity_per_portion": 0.018,
                    "unit": "kg"
                },
                {
                    "menu_item_id": "M101",
                    "ingredient_name": "Whole Milk",
                    "quantity_per_portion": 0.150,
                    "unit": "liters"
                }
            ]
        ]

        res = get_menu_item_comparison(item_names=["Cappuccino"], start_date="2026-10-01", end_date="2026-10-07")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["items_count"], 1)
        item = data["compared_items"][0]
        self.assertEqual(item["item_name"], "Cappuccino")
        self.assertEqual(item["average_realized_price_inr"], 120.0)
        self.assertEqual(len(item["recipe_ingredients"]), 2)
        self.assertEqual(item["recipe_ingredients"][0]["ingredient"], "Espresso Beans")

    def test_invalid_date_boundaries(self):
        """Test that invalid date strings produce clean error responses."""
        res = get_menu_performance(start_date="2026-13-45", end_date="2026-10-07")
        self.assertEqual(res["status"], "error")
        self.assertIn("Invalid start_date", res["message"])

    def test_menu_agent_tool_routing(self):
        """Test MenuIntelligenceAgent deterministic tool decision matching."""
        agent = MenuIntelligenceAgent()
        self.assertEqual(agent.decide_tool("What are our best selling and worst selling menu items?")["tool_name"], "get_menu_performance")
        self.assertEqual(agent.decide_tool("Which categories drive the highest revenue share?")["tool_name"], "get_category_performance")
        self.assertEqual(agent.decide_tool("Compare Butter Chicken vs Paneer Butter Masala pricing")["tool_name"], "get_menu_item_comparison")
        self.assertEqual(agent.decide_tool("Show me the current drinks on the menu")["tool_name"], "get_menu")

    def test_menu_agent_system_prompt_grounding_rules(self):
        """Test MenuIntelligenceAgent system prompt contains strict grounding & synthetic rules."""
        agent = MenuIntelligenceAgent()
        self.assertIn("synthetic", agent.system_prompt.lower())
        self.assertIn("ground every single claim", agent.system_prompt.lower())
        self.assertIn("never invent", agent.system_prompt.lower())

    @patch("tools.execute_query")
    def test_menu_agent_simulation_response_synthesis(self, mock_query):
        """Test simulation synthesis output formatting."""
        mock_query.return_value = [
            {
                "menu_item_id": "M001",
                "item_name": "Idli",
                "category_name": "Breakfast",
                "list_price_inr": 60.0,
                "diet_type": "veg",
                "is_available": True,
                "total_quantity_sold": 40,
                "total_revenue_inr": 2400.0,
                "total_discount_inr": 0.0,
                "order_appearances": 30
            }
        ]

        agent = MenuIntelligenceAgent()
        out = agent.run_simulation("What was our menu performance and best sellers over the last 7 days?")
        self.assertIn("Menu Performance Analysis", out["final_response"])
        self.assertIn("Idli", out["final_response"])
        self.assertIn("Synthetic Dataset", out["final_response"])



if __name__ == "__main__":
    unittest.main()
