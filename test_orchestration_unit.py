"""
test_orchestration_unit.py - Unit Test Suite for Unified Agent Orchestrator

Tests:
- Correct intent routing for all 6 capabilities
- Multi-agent query routing
- Ambiguous question handling (clarification)
- Greeting handling
- No unnecessary agent calls
- Evidence consolidation and deduplication
- Preservation of synthetic data provenance
- Preservation of RAG citations
- Partial agent failure disclosure
- Total failure handling
- FastAPI POST /api/chat schema validation and execution
- No mock fallback on real API execution error
- Backward compatibility of all registered endpoints
"""

import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from orchestrator import AgentOrchestrator
from api import app, UnifiedChatRequest, UnifiedChatResponse


class TestAgentOrchestrator(unittest.TestCase):

    def setUp(self):
        self.orchestrator = AgentOrchestrator(strict_mode=True)
        self.client = TestClient(app)

    # -------------------------------------------------------------------------
    # 1. INTENT ROUTING TESTS (ALL 6 CAPABILITIES)
    # -------------------------------------------------------------------------

    def test_routing_sales_capability(self):
        query = "How many orders did we complete last week?"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["sales"])

    def test_routing_menu_capability(self):
        query = "Which menu items perform poorly?"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["menu"])

    def test_routing_feedback_capability(self):
        query = "What are customers complaining about?"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["feedback"])

    def test_routing_inventory_capability(self):
        query = "What ingredients need restocking?"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["inventory"])

    def test_routing_recommendations_capability(self):
        query = "What actions should management prioritize?"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["recommendations"])

    def test_routing_knowledge_capability(self):
        query = "What does our food safety SOP say?"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["knowledge"])

    # -------------------------------------------------------------------------
    # 2. MULTI-AGENT & CROSS-DOMAIN ROUTING
    # -------------------------------------------------------------------------

    def test_routing_multi_agent_complex_query(self):
        query = "Our popular dishes are receiving poor ratings and ingredients are running low. What should we do?"
        route = self.orchestrator.route_query(query)
        # Expected to touch menu, feedback, inventory, and recommendations
        self.assertIn("menu", route)
        self.assertIn("feedback", route)
        self.assertIn("inventory", route)
        self.assertIn("recommendations", route)
        self.assertNotIn("knowledge", route)

    def test_routing_cross_domain_pair(self):
        query = "Compare our sales trends with customer review ratings for last week"
        route = self.orchestrator.route_query(query)
        self.assertIn("sales", route)
        self.assertIn("feedback", route)
        self.assertNotIn("inventory", route)

    def test_routing_inventory_and_knowledge(self):
        query = "What does our milk storage SOP say and do we have low milk stock?"
        route = self.orchestrator.route_query(query)
        self.assertIn("knowledge", route)
        self.assertIn("inventory", route)

    # -------------------------------------------------------------------------
    # 3. AMBIGUOUS & GREETING HANDLING
    # -------------------------------------------------------------------------

    def test_routing_ambiguous_question(self):
        query = "Tell me something"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, [])

        res = self.orchestrator.orchestrate(query)
        self.assertEqual(res["status"], "clarification_needed")
        self.assertIn("please clarify which area", res["answer"])
        self.assertEqual(res["selected_agents"], [])

    def test_routing_greeting(self):
        query = "hello"
        route = self.orchestrator.route_query(query)
        self.assertEqual(route, ["greeting"])

        res = self.orchestrator.orchestrate(query)
        self.assertEqual(res["status"], "success")
        self.assertIn("Unified Restaurant Intelligence Orchestrator", res["answer"])

    # -------------------------------------------------------------------------
    # 4. SELECTIVE EXECUTION (NO UNNECESSARY CALLS)
    # -------------------------------------------------------------------------

    def test_no_unnecessary_agent_calls(self):
        query = "How many orders did we complete last week?"
        
        mock_sales = MagicMock()
        mock_sales.run_simulation.return_value = {
            "executed_tools": ["get_sales_performance"],
            "final_response": "Total completed orders: 150."
        }
        mock_inv = MagicMock()

        with patch.dict(self.orchestrator.agent_factories, {
            "sales": lambda llm: mock_sales,
            "inventory": lambda llm: mock_inv
        }):
            res = self.orchestrator.orchestrate(query, run_mode="simulation")

        self.assertEqual(res["route"], ["sales"])
        mock_sales.run_simulation.assert_called_once()
        mock_inv.run_simulation.assert_not_called()

    # -------------------------------------------------------------------------
    # 5. EVIDENCE CONSOLIDATION & DEDUPLICATION
    # -------------------------------------------------------------------------

    def test_consolidation_and_provenance(self):
        query = "Compare sales and inventory status"
        mock_sales = MagicMock()
        mock_sales.run_simulation.return_value = {
            "executed_tools": ["get_sales_performance"],
            "final_response": "Revenue: INR 45,000 across 120 orders. (Synthetic Dataset)"
        }
        mock_inv = MagicMock()
        mock_inv.run_simulation.return_value = {
            "executed_tools": ["get_inventory_status"],
            "final_response": "Critical items: Rice, Milk. (Synthetic Dataset)"
        }

        with patch.dict(self.orchestrator.agent_factories, {
            "sales": lambda llm: mock_sales,
            "inventory": lambda llm: mock_inv
        }):
            res = self.orchestrator.orchestrate(query, run_mode="simulation")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["data_origin"], "SYNTHETIC")
        self.assertIn("Revenue: INR 45,000", res["answer"])
        self.assertIn("Critical items: Rice, Milk", res["answer"])
        self.assertIn("get_sales_performance", res["evidence_sources"])
        self.assertIn("get_inventory_status", res["evidence_sources"])
        self.assertTrue(len(res["limitations"]) >= 2)

    def test_preservation_of_rag_citations(self):
        query = "What does our milk storage SOP say?"
        mock_know = MagicMock()
        mock_know.run_simulation.return_value = {
            "executed_tools": ["search_restaurant_knowledge"],
            "final_response": "Milk must be kept below 4°C. Sources: [Cafe Operations SOP v1.0, Chunk 0, Page 1]"
        }

        with patch.dict(self.orchestrator.agent_factories, {
            "knowledge": lambda llm: mock_know
        }):
            res = self.orchestrator.orchestrate(query, run_mode="simulation")

        self.assertEqual(res["status"], "success")
        self.assertIn("[Cafe Operations SOP v1.0, Chunk 0, Page 1]", res["answer"])
        self.assertIn("search_restaurant_knowledge", res["evidence_sources"])

    # -------------------------------------------------------------------------
    # 6. ERROR & FAILURE DISCLOSURE (NO SILENT MOCK FALLBACK)
    # -------------------------------------------------------------------------

    def test_partial_agent_failure_disclosed(self):
        query = "Compare sales and inventory status"
        mock_sales = MagicMock()
        mock_sales.run_simulation.return_value = {
            "executed_tools": ["get_sales_performance"],
            "final_response": "Revenue: INR 45,000."
        }
        mock_inv = MagicMock()
        mock_inv.run_simulation.side_effect = RuntimeError("Database connection timeout on inventory table")

        with patch.dict(self.orchestrator.agent_factories, {
            "sales": lambda llm: mock_sales,
            "inventory": lambda llm: mock_inv
        }):
            res = self.orchestrator.orchestrate(query, run_mode="simulation")

        self.assertEqual(res["status"], "partial_success")
        self.assertIn("Revenue: INR 45,000", res["answer"])
        self.assertIn("Database connection timeout", res["answer"])
        self.assertIsNotNone(res["errors"])
        self.assertEqual(len(res["errors"]), 1)
        self.assertEqual(res["errors"][0]["agent"], "InventoryIntelligenceAgent")

    def test_all_agents_failure(self):
        query = "How many orders did we complete last week?"
        mock_sales = MagicMock()
        mock_sales.run_simulation.side_effect = RuntimeError("Sales table locked")

        with patch.dict(self.orchestrator.agent_factories, {
            "sales": lambda llm: mock_sales
        }):
            res = self.orchestrator.orchestrate(query, run_mode="simulation")

        self.assertEqual(res["status"], "error")
        self.assertIn("Sales table locked", res["answer"])
        self.assertEqual(len(res["errors"]), 1)

    # -------------------------------------------------------------------------
    # 7. FASTAPI /api/chat ENDPOINT VALIDATION
    # -------------------------------------------------------------------------

    def test_api_chat_empty_message_validation(self):
        response = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(response.status_code, 422)

    def test_api_chat_success_endpoint(self):
        with patch.object(AgentOrchestrator, "orchestrate") as mock_orch:
            mock_orch.return_value = {
                "status": "success",
                "answer": "Total completed orders: 142. Revenue: INR 52,000.",
                "route": ["sales"],
                "selected_agents": ["SalesIntelligenceAgent"],
                "agent_results": {"sales": {"status": "success", "answer": "Total completed orders: 142."}},
                "evidence_sources": ["get_sales_performance"],
                "data_origin": "SYNTHETIC",
                "limitations": ["Sales metrics derived from synthetic benchmark data."],
                "errors": None
            }
            with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_key"}):
                response = self.client.post("/api/chat", json={"message": "What were our total sales last week?"})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data["status"], "success")
                self.assertEqual(data["route"], ["sales"])
                self.assertEqual(data["data_origin"], "SYNTHETIC")
                self.assertIn("get_sales_performance", data["evidence_sources"])

    def test_api_chat_no_mock_fallback_on_total_failure(self):
        with patch.object(AgentOrchestrator, "orchestrate") as mock_orch:
            mock_orch.return_value = {
                "status": "error",
                "answer": "All agents failed.",
                "route": ["sales"],
                "selected_agents": ["SalesIntelligenceAgent"],
                "agent_results": {},
                "evidence_sources": [],
                "data_origin": "SYNTHETIC",
                "limitations": [],
                "errors": [{"agent": "SalesIntelligenceAgent", "message": "Database 503 unavailable"}]
            }
            with patch.dict("os.environ", {"GEMINI_API_KEY": "dummy_key"}):
                response = self.client.post("/api/chat", json={"message": "What were our total sales last week?"})
                # Must return error HTTP status code, never fake 200 mock success
                self.assertEqual(response.status_code, 503)

    # -------------------------------------------------------------------------
    # 8. BACKWARD COMPATIBILITY OF ALL REGISTERED ENDPOINTS
    # -------------------------------------------------------------------------

    def test_backward_compatibility_routes_exist(self):
        route_paths = [r.path for r in app.routes]
        expected_paths = [
            "/health",
            "/api/menu",
            "/api/inventory",
            "/api/sales",
            "/api/chat",
            "/api/agents/chat",
            "/api/agents/sales/chat",
            "/api/agents/menu/chat",
            "/api/agents/feedback/chat",
            "/api/agents/inventory/chat",
            "/api/agents/recommendations/chat",
            "/api/knowledge/search",
            "/api/knowledge/ingest"
        ]
        for p in expected_paths:
            self.assertIn(p, route_paths, f"Expected endpoint route '{p}' not found in FastAPI app.")


if __name__ == "__main__":
    unittest.main()
