"""
test_inventory_unit.py - Unit Tests for Inventory & Waste Intelligence Tools and Agent
"""

import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date, datetime

import tools
from agent import InventoryIntelligenceAgent, INVENTORY_AGENT_SYSTEM_PROMPT


class TestInventoryUnit(unittest.TestCase):
    """Test suite for Inventory & Waste Intelligence SQL tools and Agent."""

    @patch("tools.execute_query")
    def test_get_inventory_status_success(self, mock_exec):
        """Verify stock health classifications, reorder ratios, and replenishment priorities."""
        mock_exec.return_value = [
            {
                "ingredient_id": "ING001",
                "ingredient_name": "Rice",
                "ingredient_category": "dry_goods",
                "on_hand_quantity": Decimal("24"),
                "reorder_level": Decimal("100"),
                "unit": "g",
                "last_count_date": date(2026, 10, 8),
                "stock_status": "CRITICAL",
                "stock_to_reorder_ratio": Decimal("0.24")
            },
            {
                "ingredient_id": "ING004",
                "ingredient_name": "Egg",
                "ingredient_category": "dairy_eggs",
                "on_hand_quantity": Decimal("84"),
                "reorder_level": Decimal("100"),
                "unit": "each",
                "last_count_date": date(2026, 10, 8),
                "stock_status": "LOW_STOCK",
                "stock_to_reorder_ratio": Decimal("0.84")
            },
            {
                "ingredient_id": "ING002",
                "ingredient_name": "Chicken",
                "ingredient_category": "meat",
                "on_hand_quantity": Decimal("1500"),
                "reorder_level": Decimal("185"),
                "unit": "g",
                "last_count_date": date(2026, 10, 8),
                "stock_status": "HEALTHY",
                "stock_to_reorder_ratio": Decimal("8.11")
            }
        ]

        res = tools.get_inventory_status()
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["summary"]["total_items"], 3)
        self.assertEqual(data["summary"]["critical_items_count"], 1)
        self.assertEqual(data["summary"]["low_stock_items_count"], 1)
        self.assertEqual(data["summary"]["healthy_items_count"], 1)
        self.assertEqual(len(data["replenishment_priorities"]), 2)
        self.assertEqual(data["replenishment_priorities"][0]["ingredient_name"], "Rice")
        self.assertEqual(data["replenishment_priorities"][0]["urgency"], "Urgent Restock (Critical)")

    @patch("tools.execute_query")
    def test_get_inventory_status_empty(self, mock_exec):
        """Verify empty result when no items match filters."""
        mock_exec.return_value = []
        res = tools.get_inventory_status(category="nonexistent")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["summary"]["total_items"], 0)
        self.assertEqual(len(res["data"]["items"]), 0)

    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_ingredient_consumption(self, mock_single, mock_exec):
        """Verify recipe-based consumption calculation, daily burn rate, and stockout projection."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_exec.return_value = [
            {
                "ingredient_id": "ING001",
                "ingredient_name": "Rice",
                "ingredient_category": "dry_goods",
                "unit": "g",
                "current_stock": Decimal("24"),
                "reorder_level": Decimal("100"),
                "recipe_consumed_quantity": Decimal("700"),
                "orders_count": 35
            }
        ]

        res = tools.get_ingredient_consumption(start_date="2026-10-02", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["days_in_period"], 7)
        consumed = data["consumed_ingredients"][0]
        self.assertEqual(consumed["daily_burn_rate"], 100.0)  # 700 / 7 days
        self.assertEqual(consumed["estimated_days_of_stock_left"], 0.2)  # 24 / 100.0
        self.assertEqual(len(data["stockout_risk_ingredients"]), 1)

    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_stock_movement_summary(self, mock_single, mock_exec):
        """Verify movement type aggregation and unit segregation (no incompatible unit sums)."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        # Return 2 queries: type summary and ingredient movements
        mock_exec.side_effect = [
            [
                {
                    "movement_type": "purchase_receipt",
                    "unit": "g",
                    "movement_count": 5,
                    "total_inflow": Decimal("10000"),
                    "total_outflow": Decimal("0"),
                    "net_delta": Decimal("10000")
                },
                {
                    "movement_type": "sale_consumption",
                    "unit": "ml",
                    "movement_count": 8,
                    "total_inflow": Decimal("0"),
                    "total_outflow": Decimal("1500"),
                    "net_delta": Decimal("-1500")
                }
            ],
            [
                {
                    "ingredient_id": "ING001",
                    "ingredient_name": "Rice",
                    "ingredient_category": "dry_goods",
                    "unit": "g",
                    "movement_count": 5,
                    "total_inflow": Decimal("10000"),
                    "total_outflow": Decimal("0"),
                    "net_delta": Decimal("10000")
                }
            ]
        ]

        res = tools.get_stock_movement_summary(start_date="2026-10-01", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["total_movements_count"], 13)
        self.assertEqual(len(data["movement_types_summary"]), 2)
        # Verify units are separated
        self.assertEqual(data["movement_types_summary"][0]["unit"], "g")
        self.assertEqual(data["movement_types_summary"][1]["unit"], "ml")

    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_inventory_variance(self, mock_single, mock_exec):
        """Verify variance calculation between recipe expectations and recorded stock outflows."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_exec.return_value = [
            {
                "ingredient_id": "ING002",
                "ingredient_name": "Chicken",
                "ingredient_category": "meat",
                "unit": "g",
                "expected_consumption": Decimal("10600"),
                "recorded_outflow": Decimal("10600"),
                "variance_quantity": Decimal("0")
            },
            {
                "ingredient_id": "ING006",
                "ingredient_name": "Onion",
                "ingredient_category": "produce",
                "unit": "g",
                "expected_consumption": Decimal("5000"),
                "recorded_outflow": Decimal("5500"),
                "variance_quantity": Decimal("500")
            }
        ]

        res = tools.get_inventory_variance(start_date="2026-10-01", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["summary"]["exact_matches_count"], 1)
        self.assertEqual(data["summary"]["elevated_outflows_count"], 1)
        self.assertEqual(data["variance_details"][1]["status"], "ELEVATED_OUTFLOW")
        self.assertEqual(data["variance_details"][1]["variance_percentage"], 10.0)
        self.assertIn("waste_and_variance_advisory", data)

    def test_invalid_date_format_handling(self):
        """Verify invalid date formatting returns clean error rather than unhandled exception."""
        res = tools.get_ingredient_consumption(start_date="invalid-date", end_date="2026-10-08")
        self.assertEqual(res["status"], "error")
        self.assertIn("Invalid start_date format", res["message"])

    def test_inventory_agent_tool_selection(self):
        """Verify InventoryIntelligenceAgent correctly maps intents to specialized inventory tools."""
        agent = InventoryIntelligenceAgent()
        
        # Test variance intent
        dec1 = agent.decide_tool("Is there any ingredient variance or potential waste?")
        self.assertEqual(dec1["tool_name"], "get_inventory_variance")
        
        # Test stock movement intent
        dec2 = agent.decide_tool("Show me stock movement logs and purchase receipts")
        self.assertEqual(dec2["tool_name"], "get_stock_movement_summary")
        
        # Test burn rate / consumption intent
        dec3 = agent.decide_tool("What is the daily burn rate and consumption velocity for our ingredients?")
        self.assertEqual(dec3["tool_name"], "get_ingredient_consumption")
        
        # Test stock health / replenishment intent
        dec4 = agent.decide_tool("Which items are low stock and need urgent replenishment?")
        self.assertEqual(dec4["tool_name"], "get_inventory_status")

    @patch("tools.execute_query")
    def test_inventory_agent_simulation_response(self, mock_exec):
        """Verify InventoryIntelligenceAgent produces structured simulation response with provenance."""
        mock_exec.return_value = [
            {
                "ingredient_id": "ING001",
                "ingredient_name": "Rice",
                "ingredient_category": "dry_goods",
                "on_hand_quantity": Decimal("24"),
                "reorder_level": Decimal("100"),
                "unit": "g",
                "last_count_date": date(2026, 10, 8),
                "stock_status": "CRITICAL",
                "status": "Low Stock - Reorder Needed!",
                "stock_to_reorder_ratio": Decimal("0.24")
            }
        ]

        agent = InventoryIntelligenceAgent()
        out = agent.run_simulation("Which items have low stock?")
        
        # Verify dictionary structure and expected provenance fields
        self.assertIsInstance(out, dict)
        self.assertIn("user_request", out)
        self.assertIn("executed_tools", out)
        self.assertIn("final_response", out)
        self.assertIn("get_inventory_status", out["executed_tools"])
        
        final_text = out["final_response"]
        self.assertIn("Inventory Status & Stock Health Overview", final_text)
        self.assertIn("Rice", final_text)
        self.assertIn("Critical", final_text)
        self.assertIn("Synthetic Dataset", final_text)


if __name__ == "__main__":
    unittest.main()
