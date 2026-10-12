"""
test_rag_unit.py - Unit Tests for Restaurant Knowledge pgvector RAG
"""

import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from rag.embeddings import get_embedding, DEFAULT_EMBEDDING_MODEL, DEFAULT_EMBEDDING_DIM
from rag.ingestion import (
    compute_file_hash,
    split_text_into_chunks,
    ingest_document
)
from rag.retrieval import search_restaurant_knowledge
import tools


class TestRagUnit(unittest.TestCase):
    """Unit test suite for pgvector-backed RAG components."""

    # -------------------------------------------------------------------------
    # 1. Chunking and text processing tests
    # -------------------------------------------------------------------------
    def test_compute_file_hash(self):
        """Verify deterministic SHA-256 computation."""
        h1 = compute_file_hash(b"hello world")
        h2 = compute_file_hash(b"hello world")
        h3 = compute_file_hash(b"different content")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)

    def test_split_text_into_chunks(self):
        """Verify chunk splitting preserves order, page numbers, and chunk sizes."""
        sample_text = (
            "POLICY 1\n\nFirst paragraph of food safety.\n\n"
            "POLICY 2\n\nSecond paragraph of food safety with additional details."
        )
        chunks = split_text_into_chunks(sample_text, page_number=2, max_chunk_size=100)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertEqual(chunks[0]["page_number"], 2)
        self.assertIn("POLICY 1", chunks[0]["text"])

    def test_split_empty_text(self):
        """Verify empty text yields no chunks."""
        chunks = split_text_into_chunks("   ", page_number=1)
        self.assertEqual(chunks, [])

    # -------------------------------------------------------------------------
    # 2. Embedding generation tests
    # -------------------------------------------------------------------------
    @patch("rag.embeddings.genai.Client")
    def test_get_embedding_success(self, mock_client_cls):
        """Verify get_embedding calls Gemini API with correct dimensionality."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.embeddings = [MagicMock(values=[0.1] * 768)]
        mock_client.models.embed_content.return_value = mock_response

        vec = get_embedding("Test inquiry", client=mock_client)
        self.assertEqual(len(vec), 768)
        self.assertEqual(vec[0], 0.1)

    def test_get_embedding_empty_input_rejected(self):
        """Verify empty text raises ValueError."""
        with self.assertRaises(ValueError):
            get_embedding("   ")

    # -------------------------------------------------------------------------
    # 3. Document ingestion tests
    # -------------------------------------------------------------------------
    @patch("rag.ingestion.get_connection")
    @patch("rag.ingestion.get_embedding")
    @patch("rag.ingestion.execute_single")
    def test_ingest_document_success(self, mock_single, mock_embed, mock_conn):
        """Verify document and chunks are inserted atomically with vectors."""
        mock_single.return_value = None  # No existing doc
        mock_embed.return_value = [0.05] * 768

        mock_cur = MagicMock()
        mock_connection = MagicMock()
        mock_connection.__enter__.return_value = mock_connection
        mock_connection.cursor.return_value.__enter__.return_value = mock_cur
        mock_conn.return_value = mock_connection

        res = ingest_document(
            raw_content="MILK POLICY\n\nStore below 4C.\n\nDiscard after 3 days.",
            title="Milk Storage SOP",
            document_type="sop",
            restaurant_id="rest_01"
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Milk Storage SOP")
        self.assertEqual(res["restaurant_id"], "rest_01")
        self.assertEqual(res["embedding_dimension"], 768)
        self.assertGreaterEqual(res["chunks_indexed"], 1)

    @patch("rag.ingestion.execute_single")
    def test_ingest_document_duplicate_avoidance(self, mock_single):
        """Verify duplicate ingestion is skipped when content hash matches."""
        content = "MILK POLICY\n\nStore below 4C."
        h = compute_file_hash(content.encode("utf-8"))

        mock_single.side_effect = [
            {"document_id": "DOC001", "file_hash": h, "status": "indexed"},
            {"cnt": 2}  # 2 chunks exist
        ]

        res = ingest_document(
            raw_content=content,
            title="Milk Storage SOP",
            restaurant_id="rest_01",
            force_reprocess=False
        )

        self.assertEqual(res["status"], "already_indexed")
        self.assertIn("already indexed", res["message"])
        self.assertEqual(res["chunks_count"], 2)

    # -------------------------------------------------------------------------
    # 4. Semantic retrieval and citation tests
    # -------------------------------------------------------------------------
    @patch("rag.retrieval.execute_query")
    @patch("rag.retrieval.get_embedding")
    def test_search_restaurant_knowledge_success(self, mock_embed, mock_query):
        """Verify pgvector query formats citations and returns passing matches."""
        mock_embed.return_value = [0.1] * 768
        mock_query.return_value = [
            {
                "chunk_id": "CH001",
                "document_id": "DOC001",
                "chunk_index": 0,
                "page_number": 1,
                "chunk_text": "Whole milk must be stored below 4°C at all times.",
                "source_title": "Milk Storage SOP",
                "source_version": "1.0",
                "effective_date": "2026-01-01",
                "document_type": "sop",
                "data_origin": "SYNTHETIC",
                "similarity": Decimal("0.8450")
            }
        ]

        res = search_restaurant_knowledge("How to store milk?", top_k=1, similarity_threshold=0.5)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["total_results"], 1)
        self.assertEqual(len(res["retrieved_chunks"]), 1)
        self.assertIn("stored below 4°C", res["retrieved_chunks"][0])
        self.assertEqual(res["citations"][0], "[Milk Storage SOP v1.0, Chunk 0]")
        self.assertEqual(res["data_origin"], "SYNTHETIC")

    @patch("rag.retrieval.execute_query")
    @patch("rag.retrieval.get_embedding")
    def test_search_restaurant_knowledge_no_results_below_threshold(self, mock_embed, mock_query):
        """Verify inquiry returns no_results when similarity is below cutoff threshold."""
        mock_embed.return_value = [0.1] * 768
        mock_query.return_value = [
            {
                "chunk_id": "CH001",
                "document_id": "DOC001",
                "chunk_index": 0,
                "page_number": 1,
                "chunk_text": "Unrelated dishwasher policy.",
                "source_title": "Dishwashing SOP",
                "source_version": "1.0",
                "effective_date": "2026-01-01",
                "document_type": "sop",
                "data_origin": "SYNTHETIC",
                "similarity": Decimal("0.3200")
            }
        ]

        res = search_restaurant_knowledge("How to prepare gelato?", similarity_threshold=0.50)
        self.assertEqual(res["status"], "no_results")
        self.assertEqual(res["total_results"], 0)
        self.assertEqual(res["retrieved_chunks"], [])
        self.assertIn("insufficient similarity score", res["message"])

    def test_search_restaurant_knowledge_empty_query(self):
        """Verify empty query returns error."""
        res = search_restaurant_knowledge("   ")
        self.assertEqual(res["status"], "error")
        self.assertIn("cannot be empty", res["message"])

    # -------------------------------------------------------------------------
    # 5. tools.py integration tests
    # -------------------------------------------------------------------------
    @patch("rag.retrieval.search_restaurant_knowledge")
    def test_search_cafe_knowledge_tool_delegation(self, mock_search):
        """Verify search_cafe_knowledge delegates to pgvector retrieval."""
        mock_search.return_value = {
            "status": "success",
            "query": "milk storage",
            "total_results": 1,
            "retrieved_chunks": ["Milk below 4C"],
            "citations": ["[SOP, Chunk 0]"],
            "data_origin": "SYNTHETIC"
        }

        res = tools.search_cafe_knowledge(query="milk storage")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["retrieved_chunks"], ["Milk below 4C"])

    def test_tool_registry_contains_both_tools(self):
        """Verify TOOL_REGISTRY contains both search_cafe_knowledge and search_restaurant_knowledge."""
        self.assertIn("search_cafe_knowledge", tools.TOOL_REGISTRY)
        self.assertIn("search_restaurant_knowledge", tools.TOOL_REGISTRY)
        self.assertEqual(tools.TOOL_REGISTRY["search_restaurant_knowledge"]["schema"]["name"], "search_restaurant_knowledge")


if __name__ == "__main__":
    unittest.main()
