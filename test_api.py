"""
test_api.py - Comprehensive Test Suite for FastAPI Backend Endpoints
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api import app


class TestFastAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # -------------------------------------------------------------------------
    # 1 & 2: Health Check Tests
    # -------------------------------------------------------------------------
    @patch("api.test_connection")
    def test_health_connected(self, mock_test_conn):
        """Test GET /health when database is connected."""
        mock_test_conn.return_value = {
            "status": "connected",
            "server_version": "PostgreSQL 15.1"
        }
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "connected")
        self.assertEqual(data["server_version"], "PostgreSQL 15.1")

    @patch("api.test_connection")
    def test_health_unavailable(self, mock_test_conn):
        """Test GET /health when database is unavailable."""
        mock_test_conn.return_value = {
            "status": "error",
            "message": "Connection refused to database"
        }
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["detail"]["database"], "unavailable")

    # -------------------------------------------------------------------------
    # 3 & 4: Menu Endpoint Tests
    # -------------------------------------------------------------------------
    @patch("api.get_menu")
    def test_get_menu_success(self, mock_menu):
        """Test GET /api/menu returns expected structure."""
        mock_menu.return_value = {
            "status": "success",
            "data": {
                "categories": [
                    {
                        "category_name": "Hot Coffee",
                        "items": [
                            {
                                "menu_item_id": "item_101",
                                "name": "Cappuccino",
                                "price": 180.0,
                                "dietary": ["vegetarian"],
                                "description": "vegetarian item priced at INR 180.0",
                                "is_available": True
                            }
                        ]
                    }
                ],
                "total_items": 1
            }
        }
        response = self.client.get("/api/menu")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_items"], 1)
        self.assertEqual(len(data["categories"]), 1)
        self.assertEqual(data["categories"][0]["items"][0]["name"], "Cappuccino")

    @patch("api.get_menu")
    def test_get_menu_with_category_filter(self, mock_menu):
        """Test GET /api/menu?category=Teas passes category parameter correctly."""
        mock_menu.return_value = {
            "status": "success",
            "data": {"categories": [], "total_items": 0}
        }
        response = self.client.get("/api/menu?category=Teas")
        self.assertEqual(response.status_code, 200)
        mock_menu.assert_called_once_with(category="Teas")

    @patch("api.get_menu")
    def test_get_menu_database_error(self, mock_menu):
        """Test GET /api/menu handles database failures with 503."""
        mock_menu.return_value = {
            "status": "error",
            "message": "Database query failed: timeout"
        }
        response = self.client.get("/api/menu")
        self.assertEqual(response.status_code, 503)
        self.assertIn("timeout", response.json()["detail"])

    # -------------------------------------------------------------------------
    # 5: Inventory Endpoint Tests
    # -------------------------------------------------------------------------
    @patch("api.get_inventory")
    def test_get_inventory_success(self, mock_inv):
        """Test GET /api/inventory returns valid inventory data."""
        mock_inv.return_value = {
            "status": "success",
            "data": {
                "ing_01": {
                    "item_name": "Espresso Beans",
                    "category": "Coffee",
                    "current_stock": 12.0,
                    "unit": "kg",
                    "min_reorder_level": 5.0,
                    "last_count_date": "2026-10-01",
                    "status": "In Stock"
                }
            },
            "summary": {
                "total_items": 1,
                "low_stock_items_count": 0
            }
        }
        response = self.client.get("/api/inventory")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_items"], 1)
        self.assertIn("ing_01", data["items"])

    @patch("api.get_inventory")
    def test_get_inventory_low_stock_filter(self, mock_inv):
        """Test GET /api/inventory?low_stock_only=true."""
        mock_inv.return_value = {
            "status": "success",
            "data": {},
            "summary": {"total_items": 10, "low_stock_items_count": 0}
        }
        response = self.client.get("/api/inventory?low_stock_only=true")
        self.assertEqual(response.status_code, 200)
        mock_inv.assert_called_once_with(low_stock_only=True)

    # -------------------------------------------------------------------------
    # 6 & 7: Sales Endpoint Tests & Date Validation
    # -------------------------------------------------------------------------
    @patch("api.get_today_sales")
    def test_get_sales_success(self, mock_sales):
        """Test GET /api/sales returns calculated metrics."""
        mock_sales.return_value = {
            "status": "success",
            "data": {
                "date": "2026-10-08",
                "shift_status": "Active / Historical Shift",
                "summary": {
                    "total_orders": 42,
                    "total_revenue": 15400.0,
                    "average_order_value": 366.67,
                    "busiest_hour": "09:00 - 10:00"
                },
                "top_selling_items": [
                    {"item": "Cold Brew", "quantity_sold": 20, "revenue": 4400.0}
                ],
                "payment_breakdown": {"upi": 12000.0, "card": 3400.0}
            }
        }
        response = self.client.get("/api/sales")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["date"], "2026-10-08")
        self.assertEqual(data["summary"]["total_orders"], 42)
        self.assertEqual(data["summary"]["total_revenue"], 15400.0)

    def test_get_sales_invalid_date_format(self):
        """Test GET /api/sales with malformed date format rejects with 400."""
        response = self.client.get("/api/sales?date=2026/10/08")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid date format", response.json()["detail"])

    def test_get_sales_invalid_calendar_date(self):
        """Test GET /api/sales with invalid calendar date rejects with 400."""
        response = self.client.get("/api/sales?date=2026-02-31")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid calendar date", response.json()["detail"])

    # -------------------------------------------------------------------------
    # 8, 9, 10, 11: Agent Chat Endpoint Tests
    # -------------------------------------------------------------------------
    def test_chat_empty_message_rejected(self):
        """Test POST /api/agents/chat with empty or whitespace message rejects with 422."""
        response = self.client.post("/api/agents/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 422)

    def test_chat_missing_body_rejected(self):
        """Test POST /api/agents/chat with missing body rejects with 422."""
        response = self.client.post("/api/agents/chat", json={})
        self.assertEqual(response.status_code, 422)

    @patch("api.os.getenv")
    def test_chat_no_gemini_api_key(self, mock_getenv):
        """Test POST /api/agents/chat when GEMINI_API_KEY is missing returns 503."""
        mock_getenv.return_value = None
        response = self.client.post("/api/agents/chat", json={"message": "Hello!"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM Provider is not configured", response.json()["detail"])

    @patch("api.CafeAgent")
    @patch("api.GeminiProvider")
    def test_chat_valid_request(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/chat successfully invokes request-scoped agent."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.return_value = {
            "user_request": "What are top sellers?",
            "executed_tools": [{"tool_name": "get_today_sales", "arguments": {}, "result": {"status": "success"}}],
            "final_response": "Top seller today is Cold Brew with 20 orders."
        }
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/chat",
            json={"message": "What are top sellers?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["answer"], "Top seller today is Cold Brew with 20 orders.")
        self.assertEqual(len(data["executed_tools"]), 1)

    @patch("api.CafeAgent")
    @patch("api.GeminiProvider")
    def test_chat_agent_error_no_leaks(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/chat sanitizes errors and does not leak credentials."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.side_effect = RuntimeError(
            "connection to postgresql://postgres:secret_pass@db.example.com:5432 failed"
        )
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/chat",
            json={"message": "Check sales"}
        )
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertNotIn("secret_pass", detail)
        self.assertIn("***:***", detail)

    # -------------------------------------------------------------------------
    # 6: Sales Intelligence Agent Chat Tests
    # -------------------------------------------------------------------------
    def test_sales_chat_empty_message(self):
        """Test POST /api/agents/sales/chat with empty message returns 422."""
        response = self.client.post("/api/agents/sales/chat", json={"message": ""})
        self.assertEqual(response.status_code, 422)

    @patch("api.os.getenv")
    def test_sales_chat_no_gemini_api_key(self, mock_getenv):
        """Test POST /api/agents/sales/chat when GEMINI_API_KEY is missing returns 503."""
        mock_getenv.return_value = None
        response = self.client.post("/api/agents/sales/chat", json={"message": "Sales analysis"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM Provider is not configured", response.json()["detail"])

    @patch("api.SalesIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_sales_chat_valid_request(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/sales/chat returns proper structure and agent name."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.return_value = {
            "user_request": "Which menu items sold the most during the last seven days?",
            "executed_tools": [{"tool_name": "get_top_selling_items", "arguments": {"limit": 5}, "result": {"status": "success"}}],
            "final_response": "Top selling item during the last 7 days was Butter Chicken with 45 units sold."
        }
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/sales/chat",
            json={"message": "Which menu items sold the most during the last seven days?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["agent"], "SalesIntelligenceAgent")
        self.assertEqual(data["answer"], "Top selling item during the last 7 days was Butter Chicken with 45 units sold.")
        self.assertEqual(len(data["executed_tools"]), 1)

    @patch("api.SalesIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_sales_chat_error_sanitization(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/sales/chat sanitizes errors and hides sensitive credentials."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.side_effect = RuntimeError(
            "connection to postgresql://postgres:secret_pass@db.example.com:5432 failed"
        )
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/sales/chat",
            json={"message": "Analyze revenue"}
        )
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertNotIn("secret_pass", detail)
        self.assertIn("***:***", detail)

    # -------------------------------------------------------------------------
    # 7: Menu Intelligence Agent Chat Tests
    # -------------------------------------------------------------------------
    def test_menu_chat_empty_message(self):
        """Test POST /api/agents/menu/chat with empty message returns 422."""
        response = self.client.post("/api/agents/menu/chat", json={"message": ""})
        self.assertEqual(response.status_code, 422)

    @patch("api.os.getenv")
    def test_menu_chat_no_gemini_api_key(self, mock_getenv):
        """Test POST /api/agents/menu/chat when GEMINI_API_KEY is missing returns 503."""
        mock_getenv.return_value = None
        response = self.client.post("/api/agents/menu/chat", json={"message": "Menu analysis"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM Provider is not configured", response.json()["detail"])

    @patch("api.MenuIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_menu_chat_valid_request(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/menu/chat returns proper structure and agent name."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.return_value = {
            "user_request": "Which menu items performed best and which to investigate?",
            "executed_tools": [{"tool_name": "get_menu_performance", "arguments": {"sort_by": "quantity"}, "result": {"status": "success"}}],
            "final_response": "Top item is Butter Chicken with 13 units sold. Zero sales item to investigate: Masala Chai."
        }
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/menu/chat",
            json={"message": "Which menu items performed best and which to investigate?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["agent"], "MenuIntelligenceAgent")
        self.assertEqual(data["answer"], "Top item is Butter Chicken with 13 units sold. Zero sales item to investigate: Masala Chai.")
        self.assertEqual(len(data["executed_tools"]), 1)

    @patch("api.MenuIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_menu_chat_error_sanitization(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/menu/chat sanitizes errors and hides credentials."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.side_effect = RuntimeError(
            "connection to postgresql://postgres:secret_pass@db.example.com:5432 failed"
        )
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/menu/chat",
            json={"message": "Analyze menu"}
        )
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertNotIn("secret_pass", detail)
        self.assertIn("***:***", detail)

    # -------------------------------------------------------------------------
    # 8: Feedback Intelligence Agent Chat Tests
    # -------------------------------------------------------------------------
    def test_feedback_chat_empty_message(self):
        """Test POST /api/agents/feedback/chat with empty message returns 422."""
        response = self.client.post("/api/agents/feedback/chat", json={"message": ""})
        self.assertEqual(response.status_code, 422)

    @patch("api.os.getenv")
    def test_feedback_chat_no_gemini_api_key(self, mock_getenv):
        """Test POST /api/agents/feedback/chat when GEMINI_API_KEY is missing returns 503."""
        mock_getenv.return_value = None
        response = self.client.post("/api/agents/feedback/chat", json={"message": "Feedback analysis"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM Provider is not configured", response.json()["detail"])

    @patch("api.FeedbackIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_feedback_chat_valid_request(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/feedback/chat returns proper structure and agent name."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.return_value = {
            "user_request": "What are our overall customer reviews and top complaints?",
            "executed_tools": [{"tool_name": "get_feedback_overview", "arguments": {}, "result": {"status": "success"}}],
            "final_response": "Overall average rating is 4.25 across 900 reviews. Leading complaint category is food_quality."
        }
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/feedback/chat",
            json={"message": "What are our overall customer reviews and top complaints?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["agent"], "FeedbackIntelligenceAgent")
        self.assertEqual(data["answer"], "Overall average rating is 4.25 across 900 reviews. Leading complaint category is food_quality.")
        self.assertEqual(len(data["executed_tools"]), 1)

    @patch("api.FeedbackIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_feedback_chat_error_sanitization(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/feedback/chat sanitizes errors and hides credentials."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.side_effect = RuntimeError(
            "connection to postgresql://postgres:secret_pass@db.example.com:5432 failed"
        )
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/feedback/chat",
            json={"message": "Analyze feedback"}
        )
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertNotIn("secret_pass", detail)
        self.assertIn("***:***", detail)

    # -------------------------------------------------------------------------
    # 9: Inventory & Waste Intelligence Agent Chat Tests
    # -------------------------------------------------------------------------
    def test_inventory_chat_empty_message(self):
        """Test POST /api/agents/inventory/chat with empty message returns 422."""
        response = self.client.post("/api/agents/inventory/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 422)

    @patch("api.os.getenv")
    def test_inventory_chat_no_gemini_api_key(self, mock_getenv):
        """Test POST /api/agents/inventory/chat when GEMINI_API_KEY is missing returns 503."""
        mock_getenv.return_value = None
        response = self.client.post("/api/agents/inventory/chat", json={"message": "Which items are low in stock?"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM Provider is not configured", response.json()["detail"])

    @patch("api.InventoryIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_inventory_chat_valid_request(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/inventory/chat successfully invokes request-scoped agent."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.return_value = {
            "user_request": "Which items are low in stock?",
            "executed_tools": [{"tool_name": "get_inventory_status", "arguments": {}, "result": {"status": "success"}}],
            "final_response": "Critical items include Rice (24g) and Water Bottle (32 each)."
        }
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/inventory/chat",
            json={"message": "Which items are low in stock?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["agent"], "InventoryIntelligenceAgent")
        self.assertEqual(data["answer"], "Critical items include Rice (24g) and Water Bottle (32 each).")
        self.assertEqual(len(data["executed_tools"]), 1)

    @patch("api.InventoryIntelligenceAgent")
    @patch("api.GeminiProvider")
    def test_inventory_chat_agent_error_no_leaks(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/inventory/chat sanitizes errors and does not leak credentials."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.side_effect = RuntimeError(
            "connection to postgresql://postgres:secret_pass@db.example.com:5432 failed"
        )
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/inventory/chat",
            json={"message": "Check inventory variance"}
        )
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertNotIn("secret_pass", detail)
        self.assertIn("***:***", detail)

    # -------------------------------------------------------------------------
    # 24, 25, 26, 27: Recommendation Agent Endpoint Tests
    # -------------------------------------------------------------------------
    def test_recommendations_chat_empty_message_rejected(self):
        """Test POST /api/agents/recommendations/chat rejects empty or whitespace-only messages with 422."""
        response = self.client.post(
            "/api/agents/recommendations/chat",
            json={"message": "   "}
        )
        self.assertEqual(response.status_code, 422)

    @patch("api.os.getenv")
    def test_recommendations_chat_no_gemini_api_key(self, mock_getenv):
        """Test POST /api/agents/recommendations/chat returns 503 when LLM API key is missing."""
        mock_getenv.return_value = None
        response = self.client.post(
            "/api/agents/recommendations/chat",
            json={"message": "What are our recommendations?"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("LLM Provider is not configured", response.json()["detail"])

    @patch("api.DecisionRecommendationAgent")
    @patch("api.GeminiProvider")
    def test_recommendations_chat_valid_request(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/recommendations/chat returns 200 with structured response."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.return_value = {
            "user_request": "What should we do about low stock?",
            "executed_tools": [{"tool_name": "get_stockout_risk_recommendations", "arguments": {}, "result": {"status": "success"}}],
            "final_response": "[CRITICAL] Restock Rice (REC-INV-001) to protect INR 5,750 weekly revenue."
        }
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/recommendations/chat",
            json={"message": "What should we do about low stock?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["agent"], "DecisionRecommendationAgent")
        self.assertIn("REC-INV-001", data["answer"])
        self.assertEqual(len(data["executed_tools"]), 1)

    @patch("api.DecisionRecommendationAgent")
    @patch("api.GeminiProvider")
    def test_recommendations_chat_agent_error_no_leaks(self, mock_provider_cls, mock_agent_cls):
        """Test POST /api/agents/recommendations/chat sanitizes errors and does not leak credentials."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_llm.side_effect = RuntimeError(
            "connection to postgresql://postgres:secret_pass@db.example.com:5432 failed"
        )
        mock_agent_cls.return_value = mock_agent_instance

        response = self.client.post(
            "/api/agents/recommendations/chat",
            json={"message": "Executive plan"}
        )
        self.assertEqual(response.status_code, 503)
        detail = response.json()["detail"]
        self.assertNotIn("secret_pass", detail)
        self.assertIn("***:***", detail)

    # -------------------------------------------------------------------------
    # 28, 29, 30, 31: Knowledge RAG Endpoints Tests
    # -------------------------------------------------------------------------
    def test_knowledge_search_empty_query_rejected(self):
        """Test POST /api/knowledge/search rejects empty query with 422."""
        response = self.client.post(
            "/api/knowledge/search",
            json={"query": "   "}
        )
        self.assertEqual(response.status_code, 422)

    @patch("api.search_restaurant_knowledge")
    def test_knowledge_search_valid_request(self, mock_search):
        """Test POST /api/knowledge/search returns 200 with citations and results."""
        mock_search.return_value = {
            "status": "success",
            "query": "milk rules",
            "total_results": 1,
            "results": [
                {
                    "chunk_id": "CH001",
                    "document_id": "DOC001",
                    "source_title": "Milk Storage SOP",
                    "source_version": "1.0",
                    "chunk_index": 0,
                    "page_number": 1,
                    "chunk_text": "Store milk below 4°C.",
                    "similarity": 0.85,
                    "citation": "[Milk Storage SOP v1.0, Chunk 0]",
                    "data_origin": "SYNTHETIC"
                }
            ],
            "citations": ["[Milk Storage SOP v1.0, Chunk 0]"],
            "data_origin": "SYNTHETIC"
        }

        response = self.client.post(
            "/api/knowledge/search",
            json={"query": "milk rules", "top_k": 1}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_results"], 1)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["citations"][0], "[Milk Storage SOP v1.0, Chunk 0]")

    def test_knowledge_ingest_empty_content_rejected(self):
        """Test POST /api/knowledge/ingest rejects empty content with 422."""
        response = self.client.post(
            "/api/knowledge/ingest",
            json={"title": "Policy", "content": "   "}
        )
        self.assertEqual(response.status_code, 422)

    @patch("api.ingest_document")
    def test_knowledge_ingest_valid_request(self, mock_ingest):
        """Test POST /api/knowledge/ingest successfully indexes and returns 200."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "DOC_TEST_01",
            "title": "Cleanliness Protocol",
            "chunks_indexed": 3,
            "embedding_model": "gemini-embedding-2",
            "embedding_dimension": 768,
            "restaurant_id": "default_restaurant",
            "data_origin": "SYNTHETIC"
        }

        response = self.client.post(
            "/api/knowledge/ingest",
            json={
                "title": "Cleanliness Protocol",
                "content": "Employees must sanitize counters every hour.",
                "document_type": "sop"
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["document_id"], "DOC_TEST_01")
        self.assertEqual(data["chunks_indexed"], 3)


class TestFastAPILiveSupabase(unittest.TestCase):
    """
    Live tests executed directly against Supabase database without mocks.
    """
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_live_health_endpoint(self):
        """Live Test: GET /health against Supabase."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["database"], "connected")

    def test_live_menu_endpoint(self):
        """Live Test: GET /api/menu against Supabase."""
        response = self.client.get("/api/menu")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["total_items"], 1)
        self.assertGreaterEqual(len(data["categories"]), 1)

    def test_live_inventory_endpoint(self):
        """Live Test: GET /api/inventory against Supabase."""
        response = self.client.get("/api/inventory")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(data["total_items"], 1)

    def test_live_sales_endpoint(self):
        """Live Test: GET /api/sales against Supabase."""
        response = self.client.get("/api/sales")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("summary", data)


if __name__ == "__main__":
    unittest.main()
