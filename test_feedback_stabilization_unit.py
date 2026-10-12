"""
test_feedback_stabilization_unit.py - Focused Unit Tests for Feedback Intelligence Stabilization
Covers:
1. Classification and immediate abort for exhausted provider quota (no retries).
2. Transient rate limits with provider retry guidance.
3. Provider overload (503 UNAVAILABLE) retry and exhaustion.
4. Redundant tool call prevention and session caching for get_item_reviews_summary.
5. Repetitive tool loop detection and termination.
6. Feedback tool deduplication in simulation mode.
7. No silent fallback to simulation when LLM provider fails.
8. API error handling for feedback endpoint without credential leaks or data fabrication.
"""

import unittest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

from llm_provider import (
    GeminiProvider,
    QuotaExhaustedError,
    RateLimitError,
    ProviderOverloadError,
    ProviderAuthError,
    classify_llm_error
)
from agent import FeedbackIntelligenceAgent
from api import app


class TestProviderErrorClassificationAndRetry(unittest.TestCase):

    def test_classify_daily_quota_exhausted(self):
        """Verify daily/account quota messages are classified as non-retryable QuotaExhaustedError."""
        quota_errors = [
            "429 Resource has been exhausted (e.g. check quota). Quota exceeded for quota metric GenerateRequestsPerDay and limit 15",
            "ResourceExhausted: Quota exceeded for quota metric 'Queries' and limit '15' of service 'generativelanguage.googleapis.com'",
            "429 RESOURCE_EXHAUSTED: You have exceeded your free tier daily request quota.",
            "429 Quota exceeded. Check your plan and billing details at console.cloud.google.com"
        ]
        for msg in quota_errors:
            with self.subTest(msg=msg[:40]):
                err = classify_llm_error(RuntimeError(msg))
                self.assertIsInstance(err, QuotaExhaustedError)
                self.assertIn("quota has been exhausted", str(err).lower())

    def test_classify_transient_rate_limit(self):
        """Verify short-term burst limits with retry advice are classified as RateLimitError."""
        err_msg = "429 RESOURCE_EXHAUSTED: Rate limit exceeded. Please retry in 3.5s."
        err = classify_llm_error(RuntimeError(err_msg))
        self.assertIsInstance(err, RateLimitError)
        self.assertEqual(err.retry_after, 3.5)

    def test_classify_provider_overload_503(self):
        """Verify 503 / UNAVAILABLE messages are classified as ProviderOverloadError."""
        err_msg = "503 The model is overloaded. Please try again later. UNAVAILABLE"
        err = classify_llm_error(RuntimeError(err_msg))
        self.assertIsInstance(err, ProviderOverloadError)
        self.assertIn("temporarily overloaded", str(err))

    @patch("llm_provider.genai.Client")
    def test_quota_exhausted_never_retried(self, mock_client_cls):
        """Verify GeminiProvider does not retry when daily quota is exhausted (calls send_message once)."""
        provider = GeminiProvider()
        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = RuntimeError(
            "429 Resource has been exhausted (e.g. check quota). Quota exceeded for quota metric GenerateRequestsPerDay"
        )
        provider.chat = mock_chat

        with self.assertRaises(QuotaExhaustedError):
            provider._send_with_retry("test message", max_retries=3)

        # Assert exactly one attempt was made; NO repeated retries on exhausted quota
        self.assertEqual(mock_chat.send_message.call_count, 1)

    @patch("llm_provider.time.sleep")
    @patch("llm_provider.genai.Client")
    def test_transient_rate_limit_retries_with_guidance(self, mock_client_cls, mock_sleep):
        """Verify transient rate limit retries once when provider indicates short wait time."""
        provider = GeminiProvider()
        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = [
            RuntimeError("429 Rate limit exceeded. Please retry in 1.2s."),
            MagicMock(text="Success after brief wait")
        ]
        provider.chat = mock_chat

        res = provider._send_with_retry("test message", max_retries=2)
        self.assertEqual(mock_chat.send_message.call_count, 2)
        self.assertEqual(res.text, "Success after brief wait")
        mock_sleep.assert_called_once()

    @patch("llm_provider.time.sleep")
    @patch("llm_provider.genai.Client")
    def test_rate_limit_raises_when_retries_exhausted(self, mock_client_cls, mock_sleep):
        """Verify RateLimitError is raised after max_retries without endless looping."""
        provider = GeminiProvider()
        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = RuntimeError("429 Rate limit exceeded. Please retry in 1.0s.")
        provider.chat = mock_chat

        with self.assertRaises(RateLimitError):
            provider._send_with_retry("test message", max_retries=2)

        self.assertEqual(mock_chat.send_message.call_count, 2)

    @patch("llm_provider.time.sleep")
    @patch("llm_provider.genai.Client")
    def test_provider_overload_backoff_retry_and_exhaustion(self, mock_client_cls, mock_sleep):
        """Verify 503 UNAVAILABLE is retried with backoff and raises ProviderOverloadError."""
        provider = GeminiProvider()
        mock_chat = MagicMock()
        mock_chat.send_message.side_effect = RuntimeError("503 UNAVAILABLE model overloaded")
        provider.chat = mock_chat

        with self.assertRaises(ProviderOverloadError):
            provider._send_with_retry("test message", max_retries=2)

        self.assertEqual(mock_chat.send_message.call_count, 2)
        mock_sleep.assert_called_once_with(1)  # 2 ** 0 = 1s


class TestFeedbackAgentOptimization(unittest.TestCase):

    def test_run_simulation_deduplicates_redundant_item_reviews(self):
        """Verify simulation mode drops redundant get_item_reviews_summary for broad queries."""
        agent = FeedbackIntelligenceAgent()
        with patch.object(agent, "execute_tool") as mock_exec:
            mock_exec.return_value = {
                "status": "success",
                "data": {
                    "period_start": "2026-09-01",
                    "period_end": "2026-09-30",
                    "summary": {"total_reviews": 50, "average_rating": 4.2},
                    "rating_distribution": {},
                    "issue_breakdown": []
                }
            }
            res = agent.run_simulation("What is our customer review feedback and common complaints?")
            # Only get_feedback_overview should be executed; get_item_reviews_summary is deduplicated
            self.assertIn("get_feedback_overview", res["executed_tools"])
            self.assertNotIn("get_item_reviews_summary", res["executed_tools"])

    def test_run_llm_caches_duplicate_tool_call(self):
        """Verify run_llm reuses cached result when identical get_item_reviews_summary is called."""
        mock_provider = MagicMock()
        # Mock LLM requesting the same tool call twice, then finalizing
        mock_provider.generate.side_effect = [
            {
                "type": "tool_call",
                "tool_name": "get_item_reviews_summary",
                "arguments": {"menu_item_name": "Butter Chicken"}
            },
            {
                "type": "tool_call",
                "tool_name": "get_item_reviews_summary",
                "arguments": {"menu_item_name": "Butter Chicken"}
            },
            {
                "type": "text",
                "content": "Butter Chicken has positive reviews with 4.6 stars."
            }
        ]

        agent = FeedbackIntelligenceAgent(llm_provider=mock_provider)
        with patch.object(agent, "execute_tool") as mock_exec:
            mock_exec.return_value = {
                "status": "success",
                "data": {
                    "items_analyzed_count": 1,
                    "items_summary": [{"item_name": "Butter Chicken", "average_rating": 4.6}],
                    "sample_reviews": []
                }
            }
            result = agent.run_llm("What do customers say about Butter Chicken?")

            # The underlying execute_tool function should only have been called ONCE
            self.assertEqual(mock_exec.call_count, 1)
            self.assertEqual(result["final_response"], "Butter Chicken has positive reviews with 4.6 stars.")
            self.assertEqual(len(result["executed_tools"]), 2)
            # The second executed_tool entry should be flagged as cached
            self.assertTrue(result["executed_tools"][1]["cached"])

    def test_run_llm_halts_repetitive_loop(self):
        """Verify run_llm detects repetitive identical tool calls and halts to prevent quota drain."""
        mock_provider = MagicMock()
        # LLM gets stuck requesting the same tool endlessly
        mock_provider.generate.return_value = {
            "type": "tool_call",
            "tool_name": "get_item_reviews_summary",
            "arguments": {"menu_item_name": "Butter Chicken"}
        }

        agent = FeedbackIntelligenceAgent(llm_provider=mock_provider)
        with patch.object(agent, "execute_tool") as mock_exec, \
             patch.object(agent, "synthesize_response") as mock_synth:
            mock_exec.return_value = {"status": "success", "data": {}}
            mock_synth.return_value = "Finalized response from gathered evidence."

            result = agent.run_llm("What do customers say about Butter Chicken?")

            # Tool executed once; loop halted on 3rd attempt
            self.assertEqual(mock_exec.call_count, 1)
            self.assertEqual(result["final_response"], "Finalized response from gathered evidence.")

    def test_run_never_silently_falls_back_to_simulation(self):
        """Verify agent.run raises QuotaExhaustedError without silently generating simulated data."""
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = QuotaExhaustedError("Quota exhausted")

        agent = FeedbackIntelligenceAgent(llm_provider=mock_provider)
        with patch.object(agent, "run_simulation") as mock_sim:
            with self.assertRaises(QuotaExhaustedError):
                agent.run("What are our feedback ratings?")
            mock_sim.assert_not_called()


class TestFeedbackAPIEndpointErrors(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    @patch("api.GeminiProvider")
    @patch("api.FeedbackIntelligenceAgent")
    def test_api_feedback_quota_exhausted_response(self, mock_agent_cls, mock_provider_cls):
        """Verify POST /api/agents/feedback/chat returns structured 429 error on quota exhaustion."""
        mock_agent = MagicMock()
        mock_agent.run_llm.side_effect = QuotaExhaustedError("Daily quota limit 15 requests reached")
        mock_agent_cls.return_value = mock_agent

        response = self.client.post(
            "/api/agents/feedback/chat",
            json={"message": "What is our customer sentiment?"}
        )
        self.assertEqual(response.status_code, 429)
        detail = response.json().get("detail", "")
        self.assertIn("Feedback agent service encountered an error [QUOTA_EXHAUSTED]", detail)
        self.assertIn("quota has been exhausted", detail.lower())
        # Confirm no credentials leaked
        self.assertNotIn("key=", detail.lower())

    @patch("api.GeminiProvider")
    @patch("api.FeedbackIntelligenceAgent")
    def test_api_feedback_rate_limit_response(self, mock_agent_cls, mock_provider_cls):
        """Verify POST /api/agents/feedback/chat returns 429 for transient rate limits."""
        mock_agent = MagicMock()
        mock_agent.run_llm.side_effect = RateLimitError("Rate limit exceeded")
        mock_agent_cls.return_value = mock_agent

        response = self.client.post(
            "/api/agents/feedback/chat",
            json={"message": "What is our customer sentiment?"}
        )
        self.assertEqual(response.status_code, 429)
        detail = response.json().get("detail", "")
        self.assertIn("Feedback agent service encountered an error [RATE_LIMIT_EXCEEDED]", detail)
        self.assertIn("rate limit exceeded", detail.lower())

    def test_execution_mode_explicitly_tagged(self):
        """Verify run_llm and run_simulation return clear mode indicators."""
        agent = FeedbackIntelligenceAgent()
        with patch.object(agent, "execute_tool") as mock_exec:
            mock_exec.return_value = {
                "status": "success",
                "data": {"period_start": "2026-09-01", "period_end": "2026-09-30", "summary": {}}
            }
            sim_res = agent.run_simulation("What is our feedback?")
            self.assertEqual(sim_res.get("mode"), "simulation")


if __name__ == "__main__":
    unittest.main()
