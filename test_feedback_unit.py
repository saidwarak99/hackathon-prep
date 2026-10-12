"""
test_feedback_unit.py - Unit Test Suite for Feedback Intelligence Agent & Tools
"""

import unittest
from unittest.mock import patch, MagicMock
from tools import (
    get_feedback_overview,
    get_item_reviews_summary,
    get_feedback_trends_and_issues
)
from agent import FeedbackIntelligenceAgent, FEEDBACK_AGENT_SYSTEM_PROMPT


class TestFeedbackUnit(unittest.TestCase):

    @patch("tools.execute_single")
    @patch("tools.execute_query")
    def test_get_feedback_overview_calculations(self, mock_query, mock_single):
        """Test feedback metrics, rating distribution, sentiment and issue percentages."""
        mock_single.return_value = {
            "total_reviews": 100,
            "average_rating": 4.25,
            "rating_5_count": 40,
            "rating_4_count": 45,
            "rating_3_count": 10,
            "rating_2_count": 3,
            "rating_1_count": 2,
            "positive_count": 85,
            "neutral_count": 10,
            "negative_count": 5
        }
        mock_query.return_value = [
            {"issue_category": "food_quality", "issue_count": 30},
            {"issue_category": "service_time", "issue_count": 20},
            {"issue_category": "packaging", "issue_count": 15}
        ]

        res = get_feedback_overview(start_date="2026-09-01", end_date="2026-09-30")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["summary"]["total_reviews"], 100)
        self.assertEqual(data["summary"]["average_rating"], 4.25)
        self.assertEqual(data["summary"]["positive_sentiment_percentage"], 85.0)
        self.assertEqual(data["summary"]["negative_sentiment_percentage"], 5.0)
        self.assertEqual(data["rating_distribution"]["5_star"]["percentage"], 40.0)
        self.assertEqual(len(data["issue_breakdown"]), 3)
        self.assertEqual(data["issue_breakdown"][0]["percentage_of_reviews"], 30.0)

    @patch("tools.execute_single")
    @patch("tools.execute_query")
    def test_get_feedback_overview_empty(self, mock_query, mock_single):
        """Test feedback overview returns clean empty metrics when no records found."""
        mock_single.return_value = {
            "total_reviews": 0,
            "average_rating": 0.0,
            "rating_5_count": 0,
            "rating_4_count": 0,
            "rating_3_count": 0,
            "rating_2_count": 0,
            "rating_1_count": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0
        }
        mock_query.return_value = []

        res = get_feedback_overview(start_date="2026-09-01", end_date="2026-09-30", menu_item_name="NonExistentItem")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["summary"]["total_reviews"], 0)
        self.assertEqual(data["summary"]["average_rating"], 0.0)
        self.assertEqual(len(data["issue_breakdown"]), 0)

    @patch("tools.execute_query")
    def test_get_item_reviews_summary_privacy_and_ratings(self, mock_query):
        """Test item reviews summary returns ratings and anonymized reviews without customer PII."""
        mock_query.side_effect = [
            # Item aggregations
            [
                {
                    "menu_item_id": "MI001",
                    "item_name": "Butter Chicken",
                    "category_name": "Curries",
                    "review_count": 50,
                    "average_rating": 4.60,
                    "positive_count": 45,
                    "negative_count": 2,
                    "neutral_count": 3
                }
            ],
            # Sample reviews
            [
                {
                    "review_id": "R001",
                    "item_name": "Butter Chicken",
                    "category_name": "Curries",
                    "rating": 5,
                    "review_text": "Rich gravy and very tender chicken!",
                    "sentiment_label": "positive",
                    "issue_category": "none",
                    "review_date": "2026-09-15"
                }
            ]
        ]

        res = get_item_reviews_summary(menu_item_name="Butter Chicken", start_date="2026-09-01", end_date="2026-09-30")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["items_analyzed_count"], 1)
        item = data["items_summary"][0]
        self.assertEqual(item["item_name"], "Butter Chicken")
        self.assertEqual(item["average_rating"], 4.60)
        self.assertEqual(item["positive_reviews"], 45)

        samples = data["sample_reviews"]
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["review_text"], "Rich gravy and very tender chicken!")
        # Confirm no customer_id field exists in returned review sample
        self.assertNotIn("customer_id", samples[0])

    @patch("tools.execute_single")
    @patch("tools.execute_query")
    def test_get_feedback_trends_and_issues_comparison(self, mock_query, mock_single):
        """Test period-over-period feedback comparisons, rating deltas, and issue trends."""
        # execute_single called twice (current period stats, prior period stats)
        mock_single.side_effect = [
            {
                "review_count": 50,
                "average_rating": 4.40,
                "positive_count": 40,
                "neutral_count": 6,
                "negative_count": 4
            },
            {
                "review_count": 40,
                "average_rating": 4.00,
                "positive_count": 28,
                "neutral_count": 6,
                "negative_count": 6
            }
        ]

        # execute_query called 4 times: curr issues, prev issues, praised items, complained items
        mock_query.side_effect = [
            [{"issue_category": "packaging", "cnt": 8}, {"issue_category": "service_time", "cnt": 5}],
            [{"issue_category": "packaging", "cnt": 12}, {"issue_category": "service_time", "cnt": 4}],
            [{"item_name": "Cold Brew", "category_name": "Beverages", "positive_reviews": 15, "average_rating": 4.8}],
            [{"item_name": "French Fries", "category_name": "Starters", "negative_reviews": 3, "average_rating": 2.5}]
        ]

        res = get_feedback_trends_and_issues(period_type="7_days", end_date="2026-10-08")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["comparison"]["average_rating_delta"], 0.40)
        self.assertEqual(data["comparison"]["review_volume_change"], 10)
        self.assertEqual(data["comparison"]["positive_sentiment_shift"], 10.0)
        self.assertEqual(len(data["most_praised_items"]), 1)
        self.assertEqual(data["most_praised_items"][0]["item_name"], "Cold Brew")

    def test_invalid_date_filtering(self):
        """Test invalid date formats produce clear error dictionary."""
        res = get_feedback_overview(start_date="2026-99-99", end_date="2026-10-08")
        self.assertEqual(res["status"], "error")
        self.assertIn("Invalid start_date", res["message"])

    def test_feedback_agent_tool_routing(self):
        """Test FeedbackIntelligenceAgent deterministic tool decision matching."""
        agent = FeedbackIntelligenceAgent()
        self.assertEqual(agent.decide_tool("What are our customer feedback trends and rating changes?")["tool_name"], "get_feedback_trends_and_issues")
        self.assertEqual(agent.decide_tool("What do customers say about Butter Chicken?")["tool_name"], "get_item_reviews_summary")
        self.assertEqual(agent.decide_tool("What is our overall rating and common complaints?")["tool_name"], "get_feedback_overview")
        self.assertEqual(agent.decide_tool("Show me the food menu")["tool_name"], "get_menu")

    def test_feedback_agent_system_prompt_rules(self):
        """Test FeedbackIntelligenceAgent system prompt contains grounding and privacy rules."""
        agent = FeedbackIntelligenceAgent()
        self.assertIn("privacy", agent.system_prompt.lower())
        self.assertIn("synthetic", agent.system_prompt.lower())
        self.assertIn("ground every single metric", agent.system_prompt.lower())
        self.assertIn("never invent", agent.system_prompt.lower())

    @patch("tools.execute_single")
    @patch("tools.execute_query")
    def test_feedback_agent_simulation_response(self, mock_query, mock_single):
        """Test FeedbackIntelligenceAgent response formatting in simulation mode."""
        mock_single.return_value = {
            "total_reviews": 60,
            "average_rating": 4.10,
            "rating_5_count": 25,
            "rating_4_count": 25,
            "rating_3_count": 5,
            "rating_2_count": 3,
            "rating_1_count": 2,
            "positive_count": 48,
            "neutral_count": 7,
            "negative_count": 5
        }
        mock_query.return_value = [
            {"issue_category": "food_quality", "issue_count": 15},
            {"issue_category": "packaging", "issue_count": 10}
        ]

        agent = FeedbackIntelligenceAgent()
        out = agent.run_simulation("What is our customer review feedback and common complaints?")
        self.assertIn("Customer Feedback Overview", out["final_response"])
        self.assertIn("Total Reviews: 60", out["final_response"])
        self.assertIn("Synthetic Dataset", out["final_response"])


if __name__ == "__main__":
    unittest.main()
