"""
test_sales_unit.py - Comprehensive Unit Tests for Sales Intelligence Tools & Agent
"""

import unittest
from unittest.mock import patch, MagicMock
from tools import (
    _resolve_date_range,
    get_sales_performance,
    get_top_selling_items,
    get_sales_trends_and_comparison,
    get_peak_hours_and_dayparts,
    get_payment_methods_breakdown
)
from agent import SalesIntelligenceAgent


class TestSalesDateResolution(unittest.TestCase):

    @patch("tools.execute_single")
    def test_resolve_date_range_defaults(self, mock_single):
        mock_single.return_value = {"max_date": "2026-10-08"}
        start, end = _resolve_date_range(default_days=7)
        self.assertEqual(end, "2026-10-08")
        self.assertEqual(start, "2026-10-02")

    @patch("tools.execute_single")
    def test_resolve_date_range_custom_dates(self, mock_single):
        start, end = _resolve_date_range(start_date="2026-09-01", end_date="2026-09-30")
        self.assertEqual(start, "2026-09-01")
        self.assertEqual(end, "2026-09-30")
        mock_single.assert_not_called()

    @patch("tools.execute_single")
    def test_resolve_date_range_inverted(self, mock_single):
        start, end = _resolve_date_range(start_date="2026-10-10", end_date="2026-10-01")
        self.assertEqual(start, "2026-10-01")
        self.assertEqual(end, "2026-10-10")

    def test_resolve_date_range_invalid(self):
        with self.assertRaises(ValueError):
            _resolve_date_range(start_date="invalid-date")


class TestSalesToolsUnit(unittest.TestCase):

    @patch("tools._resolve_date_range")
    @patch("tools.execute_single")
    @patch("tools.execute_query")
    def test_get_sales_performance_success(self, mock_query, mock_single, mock_resolve):
        mock_resolve.return_value = ("2026-10-01", "2026-10-07")
        mock_single.side_effect = [
            # summary row
            {
                "completed_orders": 100,
                "cancelled_orders": 5,
                "refunded_orders": 2,
                "total_orders": 107,
                "total_revenue": 50000.0,
                "subtotal": 45000.0,
                "tax": 2500.0,
                "service_charge": 2500.0,
                "average_order_value": 500.0
            },
            # discount row
            {
                "total_items_sold": 250,
                "discounted_items_count": 30,
                "total_discount_given": 1500.0,
                "total_item_revenue": 48500.0
            }
        ]
        mock_query.return_value = [
            {"channel": "dine_in", "order_count": 60, "revenue": 30000.0, "average_order_value": 500.0},
            {"channel": "delivery", "order_count": 40, "revenue": 20000.0, "average_order_value": 500.0}
        ]

        res = get_sales_performance()
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["period_start"], "2026-10-01")
        self.assertEqual(data["period_end"], "2026-10-07")
        self.assertEqual(data["summary"]["total_revenue_inr"], 50000.0)
        self.assertEqual(data["summary"]["completed_orders"], 100)
        self.assertEqual(data["summary"]["subtotal_inr"], 45000.0)
        self.assertEqual(data["summary"]["tax_inr"], 2500.0)
        self.assertEqual(data["summary"]["service_charge_inr"], 2500.0)
        self.assertEqual(data["summary"]["gross_billed_revenue_inr"], 50000.0)
        self.assertEqual(data["summary"]["aov_denominator"], "completed_orders")
        self.assertEqual(len(data["channel_breakdown"]), 2)
        self.assertEqual(data["channel_breakdown"][0]["revenue_percentage"], 60.0)
        self.assertEqual(data["discount_impact"]["total_discount_given_inr"], 1500.0)
        self.assertEqual(data["discount_impact"]["discount_applied_status"], "already_deducted_from_subtotal")

    @patch("tools._resolve_date_range")
    @patch("tools.execute_query")
    def test_get_top_selling_items_success(self, mock_query, mock_resolve):
        mock_resolve.return_value = ("2026-10-01", "2026-10-07")
        mock_query.return_value = [
            {
                "menu_item_id": "item_1",
                "item_name": "Butter Chicken",
                "category_name": "Main Course",
                "list_price_inr": 350.0,
                "total_quantity": 45,
                "total_revenue": 15750.0,
                "total_discount": 500.0,
                "order_appearances": 40
            },
            {
                "menu_item_id": "item_2",
                "item_name": "Masala Chai",
                "category_name": "Beverages",
                "list_price_inr": 50.0,
                "total_quantity": 100,
                "total_revenue": 5000.0,
                "total_discount": 0.0,
                "order_appearances": 85
            }
        ]

        res = get_top_selling_items(limit=2, sort_by="quantity")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["total_items_returned"], 2)
        self.assertEqual(data["top_items"][0]["item_name"], "Butter Chicken")
        self.assertEqual(data["top_items"][0]["quantity_sold"], 45)

    @patch("tools._resolve_date_range")
    @patch("tools.execute_query")
    def test_top_selling_items_tied_quantity_ranking(self, mock_query, mock_resolve):
        """Test deterministic tie-breaking in get_top_selling_items for tied quantities."""
        mock_resolve.return_value = ("2026-10-02", "2026-10-08")
        mock_query.return_value = [
            {"menu_item_id": "MI020", "item_name": "Andhra Chicken Meals", "category_name": "Rice & Meals", "list_price_inr": 230.0, "total_quantity": 7, "total_revenue": 1552.49, "total_discount": 57.51, "order_appearances": 7},
            {"menu_item_id": "MI010", "item_name": "Veg Spring Rolls", "category_name": "Starters", "list_price_inr": 140.0, "total_quantity": 7, "total_revenue": 945.0, "total_discount": 35.0, "order_appearances": 6},
            {"menu_item_id": "MI036", "item_name": "Water Bottle", "category_name": "Beverages", "list_price_inr": 20.0, "total_quantity": 7, "total_revenue": 138.05, "total_discount": 2.95, "order_appearances": 6},
            {"menu_item_id": "MI031", "item_name": "Tea", "category_name": "Beverages", "list_price_inr": 20.0, "total_quantity": 7, "total_revenue": 130.9, "total_discount": 11.1, "order_appearances": 5}
        ]

        res = get_top_selling_items(start_date="2026-10-02", end_date="2026-10-08", sort_by="quantity", limit=4)
        self.assertEqual(res["status"], "success")
        top_items = res["data"]["top_items"]
        self.assertEqual(len(top_items), 4)

        # Expected deterministic ordering:
        # Andhra Chicken Meals (₹1552.49) -> Veg Spring Rolls (₹945.00) -> Water Bottle (₹138.05) -> Tea (₹130.90)
        self.assertEqual(top_items[0]["item_name"], "Andhra Chicken Meals")
        self.assertEqual(top_items[1]["item_name"], "Veg Spring Rolls")
        self.assertEqual(top_items[2]["item_name"], "Water Bottle")
        self.assertEqual(top_items[3]["item_name"], "Tea")

        # Verify the executed SQL query contains deterministic tie-break ordering
        call_sql = mock_query.call_args[0][0]
        self.assertIn("ORDER BY total_quantity DESC, total_revenue DESC, mi.item_name ASC", call_sql)

    @patch("tools._resolve_date_range")
    @patch("tools.execute_single")
    @patch("tools.execute_query")
    def test_get_sales_trends_and_comparison_success(self, mock_query, mock_single, mock_resolve):
        mock_resolve.return_value = ("2026-10-08", "2026-10-14")
        # current period metrics, prior period metrics
        mock_single.side_effect = [
            {"completed_orders": 120, "total_revenue": 60000.0, "average_order_value": 500.0},
            {"completed_orders": 100, "total_revenue": 50000.0, "average_order_value": 500.0}
        ]
        mock_query.return_value = [
            {"date": "2026-10-08", "order_count": 20, "revenue": 10000.0, "average_order_value": 500.0}
        ]

        res = get_sales_trends_and_comparison(period_type="7_days")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["current_period"]["total_revenue_inr"], 60000.0)
        self.assertEqual(data["previous_period"]["total_revenue_inr"], 50000.0)
        growth = data["comparison_growth"]
        self.assertEqual(growth["revenue_change_inr"], 10000.0)
        self.assertEqual(growth["revenue_growth_percentage"], 20.0)
        self.assertEqual(growth["orders_change"], 20)
        self.assertEqual(growth["orders_growth_percentage"], 20.0)

    @patch("tools._resolve_date_range")
    @patch("tools.execute_query")
    def test_get_peak_hours_and_dayparts_success(self, mock_query, mock_resolve):
        mock_resolve.return_value = ("2026-10-01", "2026-10-07")
        mock_query.return_value = [
            {"hour": 9, "order_count": 15, "total_revenue": 3000.0},
            {"hour": 13, "order_count": 35, "total_revenue": 12000.0},
            {"hour": 20, "order_count": 50, "total_revenue": 25000.0}
        ]

        res = get_peak_hours_and_dayparts()
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["busiest_hour"]["hour"], 20)
        self.assertEqual(data["busiest_hour"]["order_count"], 50)
        self.assertEqual(len(data["daypart_summary"]), 4)

    @patch("tools._resolve_date_range")
    @patch("tools.execute_query")
    def test_get_payment_methods_breakdown_success(self, mock_query, mock_resolve):
        mock_resolve.return_value = ("2026-10-01", "2026-10-07")
        mock_query.return_value = [
            {"payment_method": "upi", "transaction_count": 60, "total_amount": 30000.0, "total_refunded": 0.0},
            {"payment_method": "card", "transaction_count": 40, "total_amount": 20000.0, "total_refunded": 500.0}
        ]

        res = get_payment_methods_breakdown()
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["total_settled_amount_inr"], 50000.0)
        self.assertEqual(len(data["methods"]), 2)
        self.assertEqual(data["methods"][0]["percentage_share"], 60.0)


class TestSalesIntelligenceAgentUnit(unittest.TestCase):

    def test_sales_agent_tool_restriction(self):
        agent = SalesIntelligenceAgent()
        tool_names = list(agent.tools.keys())
        self.assertIn("get_sales_performance", tool_names)
        self.assertIn("get_top_selling_items", tool_names)
        self.assertIn("get_sales_trends_and_comparison", tool_names)
        self.assertIn("get_peak_hours_and_dayparts", tool_names)
        self.assertIn("get_payment_methods_breakdown", tool_names)
        # General non-sales tools should be excluded
        self.assertNotIn("get_inventory", tool_names)
        self.assertNotIn("get_menu", tool_names)
        self.assertNotIn("search_cafe_knowledge", tool_names)

    def test_sales_agent_decision_routing(self):
        agent = SalesIntelligenceAgent()
        
        dec1 = agent.decide_tool("What were our sales and revenue last week?")
        self.assertEqual(dec1["tool_name"], "get_sales_performance")

        dec2 = agent.decide_tool("Which items are our top selling best sellers?")
        self.assertEqual(dec2["tool_name"], "get_top_selling_items")

        dec3 = agent.decide_tool("Compare weekly growth and sales trends vs previous week")
        self.assertEqual(dec3["tool_name"], "get_sales_trends_and_comparison")

        dec4 = agent.decide_tool("When is our peak hour lunch rush?")
        self.assertEqual(dec4["tool_name"], "get_peak_hours_and_dayparts")

        dec5 = agent.decide_tool("What is the payment breakdown for UPI and cards?")
        self.assertEqual(dec5["tool_name"], "get_payment_methods_breakdown")

    def test_sales_agent_synthesis_clarity(self):
        agent = SalesIntelligenceAgent()
        tool_result = {
            "status": "success",
            "data": {
                "period_start": "2026-10-02",
                "period_end": "2026-10-08",
                "summary": {
                    "completed_orders": 73,
                    "cancelled_orders": 5,
                    "refunded_orders": 2,
                    "total_orders": 80,
                    "total_revenue_inr": 27756.03,
                    "subtotal_inr": 26005.28,
                    "tax_inr": 1300.34,
                    "service_charge_inr": 450.41,
                    "average_order_value_inr": 380.22,
                },
                "channel_breakdown": [
                    {"channel": "dine_in", "order_count": 37, "revenue_inr": 14408.21, "revenue_percentage": 51.91}
                ],
                "discount_impact": {
                    "total_items_sold": 166,
                    "discounted_items_count": 69,
                    "total_discount_given_inr": 931.47,
                    "average_discount_per_order_inr": 12.76,
                },
                "data_origin": "SYNTHETIC"
            }
        }
        text = agent.synthesize_response("Sales summary", "get_sales_performance", tool_result)
        self.assertIn("Gross Billed Revenue", text)
        self.assertIn("Net Sales Subtotal", text)
        self.assertIn("INR 27756.03", text)
        self.assertIn("INR 26005.28", text)
        self.assertIn("per completed order", text)
        self.assertIn("denominator: 73 completed orders", text)
        self.assertIn("discounts are already deducted", text)
        self.assertIn("SYNTHETIC", text)
        self.assertIn("2026-10-02 to 2026-10-08", text)


if __name__ == "__main__":
    unittest.main()
