"""
test_recommendations_unit.py - Unit Tests for Decision & Recommendation Intelligence Tools and Agent
"""

import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import date, datetime

import tools
from agent import DecisionRecommendationAgent, DECISION_AGENT_SYSTEM_PROMPT


class TestRecommendationsUnit(unittest.TestCase):
    """Test suite for Decision & Recommendation SQL tools and Agent."""

    # -------------------------------------------------------------------------
    # 1. get_stockout_risk_recommendations tests
    # -------------------------------------------------------------------------
    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_stockout_risk_recommendations_success(self, mock_single, mock_exec):
        """Verify stockout risk recommendations correlate critical ingredients with impacted menu items."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_exec.return_value = [
            {
                "ingredient_id": "ING001",
                "ingredient_name": "Rice",
                "on_hand_quantity": Decimal("24"),
                "reorder_level": Decimal("100"),
                "deficit": Decimal("76"),
                "unit": "g",
                "ingredient_unit": "g",
                "stock_status": "CRITICAL",
                "menu_item_id": "MI010",
                "item_name": "Chicken Biryani",
                "category_name": "Biryani & Rice",
                "units_sold": 15,
                "sales_revenue": Decimal("3750.00")
            },
            {
                "ingredient_id": "ING001",
                "ingredient_name": "Rice",
                "on_hand_quantity": Decimal("24"),
                "reorder_level": Decimal("100"),
                "deficit": Decimal("76"),
                "unit": "g",
                "ingredient_unit": "g",
                "stock_status": "CRITICAL",
                "menu_item_id": "MI011",
                "item_name": "Veg Biryani",
                "category_name": "Biryani & Rice",
                "units_sold": 10,
                "sales_revenue": Decimal("2000.00")
            }
        ]

        res = tools.get_stockout_risk_recommendations(start_date="2026-10-02", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["data_origin"], "SYNTHETIC")
        self.assertEqual(data["total_stockout_risks"], 1)

        rec = data["recommendations"][0]
        self.assertEqual(rec["recommendation_id"], "REC-INV-001")
        self.assertEqual(rec["priority"], "critical")
        self.assertEqual(rec["category"], "inventory_stockout_risk")
        self.assertEqual(rec["data_origin"], "SYNTHETIC")
        self.assertIn("deficit of 76.0 g", rec["observation"])
        self.assertIn("Rice", rec["title"])

        evidence = rec["supporting_evidence"]
        self.assertEqual(evidence["ingredient_name"], "Rice")
        self.assertEqual(evidence["deficit"], 76.0)
        self.assertEqual(evidence["total_units_at_risk"], 25)
        self.assertEqual(evidence["total_revenue_at_risk_inr"], 5750.00)
        self.assertIn("Chicken Biryani", evidence["impacted_menu_items"])
        self.assertIn("Supplier delivery lead times", rec["limitations"])

    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_stockout_risk_recommendations_empty(self, mock_single, mock_exec):
        """Verify handling when all ingredients have healthy stock levels."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_exec.return_value = []

        res = tools.get_stockout_risk_recommendations()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["total_stockout_risks"], 0)
        self.assertEqual(res["data"]["recommendations"], [])

    def test_get_stockout_risk_recommendations_invalid_date(self):
        """Verify error response upon invalid date format."""
        res = tools.get_stockout_risk_recommendations(start_date="2026/10/02")
        self.assertEqual(res["status"], "error")
        self.assertIn("Expected YYYY-MM-DD", res["message"])

    # -------------------------------------------------------------------------
    # 2. get_quality_and_complaint_recommendations tests
    # -------------------------------------------------------------------------
    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_quality_and_complaint_recommendations_success(self, mock_single, mock_exec):
        """Verify operational interventions and dish quality reviews generated from review data."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        
        # First query for issues, second query for adverse item ratings
        mock_exec.side_effect = [
            [
                {
                    "issue_category": "packaging",
                    "complaint_count": 26,
                    "percentage_of_issues": Decimal("30.59")
                },
                {
                    "issue_category": "service_time",
                    "complaint_count": 19,
                    "percentage_of_issues": Decimal("22.35")
                }
            ],
            [
                {
                    "menu_item_id": "MI005",
                    "item_name": "Chicken Tikka",
                    "category_name": "Starters",
                    "total_reviews": 4,
                    "avg_rating": Decimal("3.25"),
                    "negative_reviews": 2,
                    "cited_issues": "food_quality, portion_size"
                }
            ]
        ]

        res = tools.get_quality_and_complaint_recommendations(start_date="2026-09-08", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["data_origin"], "SYNTHETIC")
        self.assertEqual(data["total_quality_recommendations"], 3)

        recs = data["recommendations"]
        # First recommendation is packaging
        self.assertEqual(recs[0]["recommendation_id"], "REC-OPS-001")
        self.assertIn("Packaging", recs[0]["title"])
        self.assertEqual(recs[0]["category"], "operational_efficiency")
        self.assertEqual(recs[0]["priority"], "high")
        self.assertEqual(recs[0]["data_origin"], "SYNTHETIC")
        self.assertIn("leak-proof containers", recs[0]["recommended_action"])

        # Second recommendation is service_time
        self.assertEqual(recs[1]["recommendation_id"], "REC-OPS-002")
        self.assertIn("Kitchen Prep", recs[1]["title"])

        # Third recommendation is item recipe review
        self.assertEqual(recs[2]["recommendation_id"], "REC-QLT-003")
        self.assertIn("Chicken Tikka", recs[2]["title"])
        self.assertEqual(recs[2]["category"], "quality_intervention")
        self.assertEqual(recs[2]["priority"], "medium")
        self.assertEqual(recs[2]["supporting_evidence"]["negative_reviews_count"], 2)

    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_quality_and_complaint_empty(self, mock_single, mock_exec):
        """Verify handling when no complaints or adverse item reviews exist."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_exec.side_effect = [[], []]

        res = tools.get_quality_and_complaint_recommendations()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["total_quality_recommendations"], 0)
        self.assertEqual(res["data"]["recommendations"], [])

    # -------------------------------------------------------------------------
    # 3. get_underperforming_menu_recommendations tests
    # -------------------------------------------------------------------------
    @patch("tools.execute_query")
    @patch("tools.execute_single")
    def test_get_underperforming_menu_recommendations_success(self, mock_single, mock_exec):
        """Verify identification of zero-sales items and catalog review actions."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_exec.return_value = [
            {
                "menu_item_id": "MI021",
                "item_name": "Veg Upma",
                "category_name": "Breakfast",
                "list_price_inr": Decimal("80.00"),
                "units_sold": 0,
                "sales_revenue": Decimal("0.00")
            },
            {
                "menu_item_id": "MI022",
                "item_name": "Rumali Roti",
                "category_name": "Breads",
                "list_price_inr": Decimal("40.00"),
                "units_sold": 0,
                "sales_revenue": Decimal("0.00")
            },
            {
                "menu_item_id": "MI023",
                "item_name": "Sweet Lassi",
                "category_name": "Beverages",
                "list_price_inr": Decimal("90.00"),
                "units_sold": 1,
                "sales_revenue": Decimal("90.00")
            }
        ]

        res = tools.get_underperforming_menu_recommendations(start_date="2026-10-02", end_date="2026-10-08", threshold_units=2)
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["zero_sales_count"], 2)
        self.assertEqual(data["low_sales_count"], 1)
        self.assertEqual(data["data_origin"], "SYNTHETIC")

        rec = data["recommendations"][0]
        self.assertEqual(rec["recommendation_id"], "REC-MNU-001")
        self.assertEqual(rec["category"], "menu_catalog_optimization")
        self.assertEqual(rec["priority"], "low")
        self.assertIn("Veg Upma", rec["title"])
        self.assertIn("perishable ingredients", rec["recommended_action"])

    # -------------------------------------------------------------------------
    # 4. get_actionable_recommendations tests
    # -------------------------------------------------------------------------
    @patch("tools.get_underperforming_menu_recommendations")
    @patch("tools.get_quality_and_complaint_recommendations")
    @patch("tools.get_stockout_risk_recommendations")
    @patch("tools.execute_single")
    def test_get_actionable_recommendations_synthesis(self, mock_single, mock_inv, mock_qlt, mock_mnu):
        """Verify comprehensive cross-domain synthesis and priority ranking."""
        mock_single.return_value = {"max_date": "2026-10-08"}

        mock_inv.return_value = {
            "status": "success",
            "data": {
                "recommendations": [
                    {
                        "recommendation_id": "REC-INV-001",
                        "title": "Restock Critical Stock Ingredient: Rice",
                        "priority": "critical",
                        "category": "inventory_stockout_risk",
                        "observation": "Rice is at 24g.",
                        "supporting_evidence": {"ingredient_name": "Rice"},
                        "recommended_action": "Order 152g.",
                        "expected_impact": "Prevents stockouts.",
                        "confidence": "high",
                        "data_origin": "SYNTHETIC",
                        "limitations": "Lead times not tracked."
                    }
                ]
            }
        }

        mock_qlt.return_value = {
            "status": "success",
            "data": {
                "recommendations": [
                    {
                        "recommendation_id": "REC-OPS-001",
                        "title": "Upgrade Takeaway Packaging",
                        "priority": "high",
                        "category": "operational_efficiency",
                        "observation": "26 packaging complaints.",
                        "supporting_evidence": {"complaint_count": 26},
                        "recommended_action": "Audit containers.",
                        "expected_impact": "Reduces spills.",
                        "confidence": "high",
                        "data_origin": "SYNTHETIC",
                        "limitations": "Synthetic data."
                    }
                ]
            }
        }

        mock_mnu.return_value = {
            "status": "success",
            "data": {
                "recommendations": [
                    {
                        "recommendation_id": "REC-MNU-001",
                        "title": "Evaluate Zero-Sales Menu Items",
                        "priority": "low",
                        "category": "menu_catalog_optimization",
                        "observation": "2 items had 0 sales.",
                        "supporting_evidence": {"zero_sales_items_count": 2},
                        "recommended_action": "Delist or feature.",
                        "expected_impact": "Streamlines prep.",
                        "confidence": "medium",
                        "data_origin": "SYNTHETIC",
                        "limitations": "Carrying cost not tracked."
                    }
                ]
            }
        }

        res = tools.get_actionable_recommendations(start_date="2026-10-02", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["total_recommendations"], 3)
        self.assertEqual(data["priority_breakdown"]["critical"], 1)
        self.assertEqual(data["priority_breakdown"]["high"], 1)
        self.assertEqual(data["priority_breakdown"]["low"], 1)

        # Confirm priority sorting order: critical first, high second, low third
        self.assertEqual(data["recommendations"][0]["priority"], "critical")
        self.assertEqual(data["recommendations"][1]["priority"], "high")
        self.assertEqual(data["recommendations"][2]["priority"], "low")
        self.assertIn("SYNTHETIC", data["data_origin"])
        self.assertIn("Profit margins cannot be calculated", data["general_limitations"])

    @patch("tools.get_stockout_risk_recommendations")
    @patch("tools.execute_single")
    def test_get_actionable_recommendations_focus_area_filter(self, mock_single, mock_inv):
        """Verify focus_area filter restricts calls to targeted domain."""
        mock_single.return_value = {"max_date": "2026-10-08"}
        mock_inv.return_value = {
            "status": "success",
            "data": {
                "recommendations": [
                    {
                        "recommendation_id": "REC-INV-001",
                        "title": "Restock Rice",
                        "priority": "critical",
                        "category": "inventory_stockout_risk",
                        "observation": "Rice critical.",
                        "supporting_evidence": {},
                        "recommended_action": "Restock.",
                        "expected_impact": "Safe.",
                        "confidence": "high",
                        "data_origin": "SYNTHETIC",
                        "limitations": "None."
                    }
                ]
            }
        }

        res = tools.get_actionable_recommendations(focus_area="inventory")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data"]["total_recommendations"], 1)
        self.assertEqual(res["data"]["recommendations"][0]["category"], "inventory_stockout_risk")

    @patch("tools.get_actionable_recommendations")
    def test_decision_agent_tool_access_restrictions(self, mock_act):
        """Verify DecisionRecommendationAgent is strictly configured with approved recommendation tools."""
        agent = DecisionRecommendationAgent()
        approved_tools = [
            "get_actionable_recommendations",
            "get_stockout_risk_recommendations",
            "get_quality_and_complaint_recommendations",
            "get_underperforming_menu_recommendations",
            "get_sales_performance",
            "get_inventory_status",
            "get_feedback_overview",
            "get_menu_performance"
        ]
        for t in approved_tools:
            self.assertIn(t, agent.tools)

        # Verify specialist tools not in its approved set are excluded
        self.assertNotIn("search_cafe_knowledge", agent.tools)
        self.assertNotIn("get_inventory_variance", agent.tools)

    def test_decision_agent_decide_tool_routing(self):
        """Verify DecisionRecommendationAgent intent classification in simulation mode."""
        agent = DecisionRecommendationAgent()

        # Stockout intent
        dec1 = agent.decide_tool("Which dishes have stockout risk or ingredient bottlenecks?")
        self.assertEqual(dec1["tool_name"], "get_stockout_risk_recommendations")

        # Quality / complaints intent
        dec2 = agent.decide_tool("What actions should we take for packaging complaints and customer feedback?")
        self.assertEqual(dec2["tool_name"], "get_quality_and_complaint_recommendations")

        # Underperforming menu intent
        dec3 = agent.decide_tool("Which underperforming or zero sales menu items should we delist?")
        self.assertEqual(dec3["tool_name"], "get_underperforming_menu_recommendations")

        # General executive recommendation intent
        dec4 = agent.decide_tool("What are the top prioritized recommendations for our restaurant?")
        self.assertEqual(dec4["tool_name"], "get_actionable_recommendations")

        # Direct greeting
        dec5 = agent.decide_tool("Hello!")
        self.assertIsNone(dec5["tool_name"])

    @patch("tools.get_actionable_recommendations")
    def test_decision_agent_simulation_response(self, mock_recs):
        """Verify DecisionRecommendationAgent generates structured simulation output with provenance."""
        mock_recs.return_value = {
            "status": "success",
            "data": {
                "period_start": "2026-10-02",
                "period_end": "2026-10-08",
                "total_recommendations": 1,
                "priority_breakdown": {"critical": 1, "high": 0, "medium": 0, "low": 0},
                "executive_summary": "1 critical inventory risk requires urgent action.",
                "recommendations": [
                    {
                        "recommendation_id": "REC-INV-001",
                        "title": "Restock Critical Stock Ingredient: Rice",
                        "priority": "critical",
                        "category": "inventory_stockout_risk",
                        "observation": "Rice is at 24g against 100g reorder level.",
                        "recommended_action": "Order 152g immediately.",
                        "expected_impact": "Protects INR 5750.00 weekly revenue.",
                        "confidence": "high",
                        "data_origin": "SYNTHETIC",
                        "limitations": "Wholesale costs not recorded."
                    }
                ],
                "data_origin": "SYNTHETIC",
                "general_limitations": "No wholesale costs or supplier lead times."
            }
        }

        agent = DecisionRecommendationAgent()
        out = agent.run_simulation("What are our top recommendations?")

        self.assertIsInstance(out, dict)
        self.assertIn("user_request", out)
        self.assertIn("executed_tools", out)
        self.assertIn("final_response", out)
        self.assertIn("get_actionable_recommendations", out["executed_tools"])

        final_text = out["final_response"]
        self.assertIn("Executive Decision & Action Plan", final_text)
        self.assertIn("REC-INV-001", final_text)
        self.assertIn("Restock Critical Stock Ingredient: Rice", final_text)
        self.assertIn("CRITICAL", final_text)
        self.assertIn("SYNTHETIC", final_text)

    @patch("tools.execute_query")
    def test_tool_database_error_handled_cleanly(self, mock_exec):
        """Verify database exception during query execution is handled without crashing."""
        mock_exec.side_effect = RuntimeError("Database connection timed out")
        res = tools.get_stockout_risk_recommendations(start_date="2026-10-02", end_date="2026-10-08")
        self.assertEqual(res["status"], "error")
        self.assertIn("Database connection timed out", res["message"])


if __name__ == "__main__":
    unittest.main()
