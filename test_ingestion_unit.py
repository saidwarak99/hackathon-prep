"""
Unit tests for Dynamic Dataset Ingestion (Phase 4).
Tests cover:
- CSV parsing and encoding handling (UTF-8, UTF-8-BOM, Latin-1, empty files)
- ZIP validation, path traversal prevention, non-CSV rejection, and expansion limits
- File size and row limit enforcement
- Section detection and column alias normalization
- Missing required fields and type validations
- Content hash (SHA-256) duplicate detection
- Non-mutating preview functionality
- Dataset query layer isolation (zero fallback to baseline data)
- Tool delegation to dataset query layer
- FastAPI endpoints for dataset preview, ingestion, listing, and retrieval
- Unified chat endpoint dataset_id propagation
"""

import io
import json
import unittest
import zipfile
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from dataset_ingestion import (
    DatasetIngestionConfig,
    SECTION_SCHEMAS,
    normalize_header,
    match_column_alias,
    detect_section,
    validate_and_cast_row,
    parse_csv_stream,
    extract_files_from_upload,
    preview_dataset,
    ingest_dataset,
    list_datasets,
    get_dataset_metadata,
)
import dataset_queries
import tools
from api import app


class TestDatasetIngestionUnit(unittest.TestCase):

    # -------------------------------------------------------------
    # 1. CSV Parsing and Encoding
    # -------------------------------------------------------------
    def test_parse_utf8_csv(self):
        csv_data = "dish_name,category,price\nEspresso,Coffee,3.50\nLatte,Coffee,4.50\n".encode("utf-8")
        res = parse_csv_stream(io.BytesIO(csv_data), "menu.csv")
        self.assertIsNone(res["error"])
        self.assertEqual(res["headers"], ["dish_name", "category", "price"])
        self.assertEqual(len(res["raw_rows"]), 2)
        self.assertEqual(res["raw_rows"][0]["dish_name"], "Espresso")

    def test_parse_utf8_bom_csv(self):
        csv_data = b"\xef\xbb\xbfdish_name,category,price\nCortado,Coffee,4.00\n"
        res = parse_csv_stream(io.BytesIO(csv_data), "menu_bom.csv")
        self.assertIsNone(res["error"])
        self.assertEqual(res["headers"], ["dish_name", "category", "price"])
        self.assertEqual(len(res["raw_rows"]), 1)
        self.assertEqual(res["raw_rows"][0]["dish_name"], "Cortado")

    def test_parse_latin1_csv(self):
        csv_data = "dish_name,category,price\nCafé au Lait,Coffee,4.75\n".encode("latin-1")
        res = parse_csv_stream(io.BytesIO(csv_data), "menu_latin1.csv")
        self.assertIsNone(res["error"])
        self.assertEqual(len(res["raw_rows"]), 1)
        self.assertIn("Caf", res["raw_rows"][0]["dish_name"])

    def test_parse_empty_csv_fails(self):
        res = parse_csv_stream(io.BytesIO(b""), "empty.csv")
        self.assertIsNotNone(res["error"])
        self.assertIn("empty", res["error"].lower())

    def test_parse_header_only_csv_fails(self):
        res = parse_csv_stream(io.BytesIO(b"dish_name,price\n"), "headers_only.csv")
        self.assertIsNotNone(res["error"])
        self.assertIn("no data records", res["error"].lower())

    def test_row_limit_enforced(self):
        with patch.object(DatasetIngestionConfig, "MAX_ROWS_PER_FILE", 10):
            rows = ["dish_name,category,price"] + [f"Item_{i},Cat,10.0" for i in range(15)]
            csv_data = "\n".join(rows).encode("utf-8")
            res = parse_csv_stream(io.BytesIO(csv_data), "too_many_rows.csv")
            self.assertIsNotNone(res["error"])
            self.assertIn("exceeds maximum allowed limit", res["error"].lower())

    # -------------------------------------------------------------
    # 2. ZIP Archive Validation & Security (Path Traversal, Limits)
    # -------------------------------------------------------------
    def test_zip_with_path_traversal_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/passwd.csv", "dish_name,price\nMalicious,100\n")
        buf.seek(0)

        extracted, err = extract_files_from_upload(buf.getvalue(), "traversal.zip")
        self.assertEqual(extracted, [])
        self.assertIsNotNone(err)
        self.assertIn("path traversal", err.lower())

    def test_zip_with_absolute_path_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("/root/secret.csv", "dish_name,price\nMalicious,100\n")
        buf.seek(0)

        extracted, err = extract_files_from_upload(buf.getvalue(), "abspath.zip")
        self.assertEqual(extracted, [])
        self.assertIsNotNone(err)
        self.assertIn("path traversal", err.lower())

    def test_zip_with_non_csv_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("menu.csv", "dish_name,category,price\nLatte,Coffee,4.50\n")
            zf.writestr("payload.exe", b"binary executable content")
        buf.seek(0)

        extracted, err = extract_files_from_upload(buf.getvalue(), "invalid_content.zip")
        self.assertEqual(extracted, [])
        self.assertIsNotNone(err)
        self.assertIn("non-csv file", err.lower())

    def test_zip_expansion_limit_enforced(self):
        with patch.object(DatasetIngestionConfig, "MAX_ZIP_EXPANSION_BYTES", 200):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("large.csv", "a" * 500)
            buf.seek(0)

            extracted, err = extract_files_from_upload(buf.getvalue(), "bomb.zip")
            self.assertEqual(extracted, [])
            self.assertIsNotNone(err)
            self.assertIn("expansion size exceeds safety limit", err.lower())

    def test_empty_zip_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            pass
        buf.seek(0)

        extracted, err = extract_files_from_upload(buf.getvalue(), "empty.zip")
        self.assertEqual(extracted, [])
        self.assertIsNotNone(err)
        self.assertIn("empty", err.lower())

    # -------------------------------------------------------------
    # 3. Section Detection and Column Alias Normalization
    # -------------------------------------------------------------
    def test_detect_menu_items_section(self):
        headers = ["dish_name", "category_name", "unit_price", "is_available"]
        section, mapping, missing = detect_section(headers)
        self.assertEqual(section, "menu_items")
        self.assertEqual(mapping["dish_name"], "item_name")
        self.assertEqual(mapping["category_name"], "category_name")
        self.assertEqual(mapping["unit_price"], "list_price_inr")
        self.assertEqual(missing, [])

    def test_detect_reviews_section(self):
        headers = ["rating", "comment", "review_date"]
        section, mapping, missing = detect_section(headers)
        self.assertEqual(section, "reviews")
        self.assertEqual(mapping["rating"], "rating")
        self.assertEqual(mapping["comment"], "review_text")
        self.assertEqual(missing, [])

    def test_detect_inventory_section(self):
        headers = ["ingredient_name", "on_hand_quantity", "unit", "reorder_level"]
        section, mapping, missing = detect_section(headers)
        self.assertEqual(section, "inventory")
        self.assertEqual(mapping["ingredient_name"], "ingredient_name")
        self.assertEqual(mapping["on_hand_quantity"], "on_hand_quantity")
        self.assertEqual(missing, [])

    def test_detect_orders_section(self):
        headers = ["bill_no", "order_date", "total_inr"]
        section, mapping, missing = detect_section(headers)
        self.assertEqual(section, "orders")
        self.assertEqual(mapping["bill_no"], "order_id")
        self.assertEqual(mapping["total_inr"], "total_inr")
        self.assertEqual(missing, [])

    def test_unrecognized_columns_rejected(self):
        headers = ["unknown_column_1", "random_metric_2", "mystery_field_3"]
        section, mapping, missing = detect_section(headers)
        self.assertIsNone(section)

    # -------------------------------------------------------------
    # 4. Data Validation (Types, Required Fields, Formats)
    # -------------------------------------------------------------
    def test_menu_items_validation_success(self):
        mapping = {"dish_name": "item_name", "category": "category_name", "price": "list_price_inr"}
        raw_row = {"dish_name": "Croissant", "category": "Bakery", "price": "180.50"}
        cleaned, errors = validate_and_cast_row(raw_row, mapping, "menu_items", 1)
        self.assertEqual(errors, [])
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned["item_name"], "Croissant")
        self.assertEqual(cleaned["list_price_inr"], 180.50)
        self.assertTrue(cleaned["is_available"])

    def test_menu_items_negative_price_rejected(self):
        mapping = {"dish_name": "item_name", "category": "category_name", "price": "list_price_inr"}
        raw_row = {"dish_name": "Freebie", "category": "Bakery", "price": "-25.0"}
        cleaned, errors = validate_and_cast_row(raw_row, mapping, "menu_items", 1)
        self.assertIsNone(cleaned)
        self.assertTrue(any("cannot be negative" in err for err in errors))

    def test_reviews_invalid_rating_rejected(self):
        mapping = {"rating": "rating", "comment": "review_text"}
        raw_row = {"rating": "6", "comment": "Over the top"}
        cleaned, errors = validate_and_cast_row(raw_row, mapping, "reviews", 1)
        self.assertIsNone(cleaned)
        self.assertTrue(any("between 1 and 5" in err for err in errors))

    def test_missing_required_fields_rejected(self):
        # Menu items requires item_name, category_name, list_price_inr
        mapping = {"category": "category_name", "price": "list_price_inr"}
        raw_row = {"category": "Beverage", "price": "120.0"}
        cleaned, errors = validate_and_cast_row(raw_row, mapping, "menu_items", 1)
        self.assertIsNone(cleaned)
        self.assertTrue(any("Missing required field 'item_name'" in err for err in errors))

    # -------------------------------------------------------------
    # 5. Non-Mutating Preview Guarantee
    # -------------------------------------------------------------
    @patch("dataset_ingestion.execute_single")
    @patch("dataset_ingestion.execute_statement")
    def test_preview_does_not_mutate_db(self, mock_exec_statement, mock_exec_single):
        # execute_single for duplicate check returns None (no duplicate)
        mock_exec_single.return_value = None

        csv_content = b"dish_name,category_name,price\nMatcha Latte,Beverage,280.00\n"
        preview_res = preview_dataset(
            file_bytes=csv_content,
            original_filename="preview_menu.csv",
            restaurant_id="rest-001"
        )

        self.assertEqual(preview_res["filename"], "preview_menu.csv")
        self.assertTrue(preview_res["is_valid"])
        self.assertEqual(preview_res["detected_sections"], ["menu_items"])
        self.assertEqual(preview_res["total_rows"], 1)

        # Ensure no mutating statements were executed
        mock_exec_statement.assert_not_called()

    # -------------------------------------------------------------
    # 6. Content Hash & Duplicate Detection
    # -------------------------------------------------------------
    @patch("dataset_ingestion.execute_single")
    def test_duplicate_upload_detection(self, mock_exec_single):
        # Mock database lookup finding existing dataset with identical hash
        mock_exec_single.return_value = {"dataset_id": "DS_20261009_existing1"}

        csv_content = b"dish_name,category_name,price\nMatcha Latte,Beverage,280.00\n"
        preview_res = preview_dataset(
            file_bytes=csv_content,
            original_filename="dup.csv",
            restaurant_id="rest-001"
        )
        self.assertTrue(preview_res["is_duplicate"])
        self.assertEqual(preview_res["existing_dataset_id"], "DS_20261009_existing1")

    # -------------------------------------------------------------
    # 7. Dataset Query Isolation & Zero Fallback Guarantee
    # -------------------------------------------------------------
    @patch("dataset_queries.execute_query")
    def test_dataset_menu_query_isolation(self, mock_exec_query):
        # Mock query on dataset_records
        mock_exec_query.return_value = [
            {"data": {"item_name": "Iced Hibiscus Tea", "category_name": "Cold Drinks", "list_price_inr": 180.0, "is_available": True}},
            {"data": {"item_name": "Cold Brew", "category_name": "Cold Drinks", "list_price_inr": 220.0, "is_available": True}},
        ]

        res = dataset_queries.get_dataset_menu("DS_TEST_456")
        self.assertEqual(res["data_origin"], "UPLOADED")
        self.assertEqual(res["dataset_id"], "DS_TEST_456")
        self.assertEqual(res["data"]["total_items"], 2)
        self.assertEqual(res["data"]["categories"][0]["items"][0]["name"], "Iced Hibiscus Tea")

    @patch("dataset_queries.execute_query")
    def test_missing_section_never_falls_back_to_baseline(self, mock_exec_query):
        # Dataset query on dataset_records returns empty list (section not uploaded)
        mock_exec_query.return_value = []

        res = dataset_queries.get_dataset_inventory("DS_MENU_ONLY")
        self.assertEqual(res["data_origin"], "UPLOADED")
        self.assertEqual(res["summary"]["total_items"], 0)
        self.assertEqual(res["data"], {})
        # Verify limitation is explicitly recorded and zero fallback is documented
        self.assertTrue(any("does not contain inventory records" in lim for lim in res["limitations"]))

    # -------------------------------------------------------------
    # 8. Tools Dataset-Aware Delegation
    # -------------------------------------------------------------
    @patch("tools.get_dataset_menu")
    def test_tool_delegates_to_dataset_query_when_dataset_id_provided(self, mock_dataset_menu):
        mock_dataset_menu.return_value = {
            "status": "success",
            "data_origin": "UPLOADED",
            "dataset_id": "DS_XYZ",
            "data": {"categories": [], "total_items": 1},
            "limitations": [],
        }

        result = tools.get_menu(category="Coffee", dataset_id="DS_XYZ")
        mock_dataset_menu.assert_called_once_with(dataset_id="DS_XYZ", category="Coffee")
        self.assertEqual(result["data_origin"], "UPLOADED")
        self.assertEqual(result["dataset_id"], "DS_XYZ")

    # -------------------------------------------------------------
    # 9. FastAPI Endpoints Testing
    # -------------------------------------------------------------
    def test_api_preview_csv_endpoint(self):
        client = TestClient(app)
        csv_content = "dish_name,category_name,price\nLemon Tart,Dessert,190.00\n"
        files = {"file": ("menu.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

        with patch("dataset_ingestion.execute_single") as mock_exec_single:
            mock_exec_single.return_value = None  # No duplicate

            response = client.post("/api/datasets/preview", files=files, data={"restaurant_id": "rest-001"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "valid")
            self.assertTrue(data["is_valid"])
            self.assertEqual(data["filename"], "menu.csv")
            self.assertIn("menu_items", data["detected_sections"])

    def test_api_ingest_and_get_dataset_endpoint(self):
        client = TestClient(app)
        csv_content = "ingredient_name,on_hand_quantity,unit,reorder_level\nAlmond Milk,15.0,liters,5.0\n"
        files = {"file": ("stock.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

        with patch("dataset_ingestion.execute_single") as mock_exec_single, \
             patch("dataset_ingestion.get_connection") as mock_conn_getter, \
             patch("api.get_dataset_metadata") as mock_get_meta:

            mock_exec_single.return_value = None  # No duplicate
            mock_conn = MagicMock()
            mock_cur = MagicMock()
            mock_conn.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cur
            mock_conn_getter.return_value = mock_conn

            # Ingest
            response = client.post(
                "/api/datasets/ingest",
                files=files,
                data={"restaurant_id": "rest-001", "dataset_name": "Test Inventory Batch"},
            )
            self.assertEqual(response.status_code, 200)
            ingest_data = response.json()
            self.assertEqual(ingest_data["status"], "success")
            self.assertEqual(ingest_data["data_origin"], "UPLOADED")
            dataset_id = ingest_data["dataset_id"]

            # Test GET /api/datasets/{dataset_id}
            mock_get_meta.return_value = {
                "dataset_id": dataset_id,
                "restaurant_id": "rest-001",
                "dataset_name": "Test Inventory Batch",
                "detected_section": "inventory",
                "original_filename": "stock.csv",
                "content_hash": "hash123",
                "upload_timestamp": "2026-10-09T20:00:00Z",
                "ingestion_status": "INGESTED",
                "row_count": 1,
                "schema_mapping": "{}",
                "validation_summary": "{}",
                "data_origin": "UPLOADED",
                "sections_summary": {"inventory": 1}
            }
            get_resp = client.get(f"/api/datasets/{dataset_id}")
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.json()["dataset"]["dataset_id"], dataset_id)

    def test_api_chat_with_dataset_id_parameter(self):
        client = TestClient(app)
        with patch.object(tools, "get_db_cursor", create=True), \
             patch("api.AgentOrchestrator.orchestrate") as mock_orchestrate, \
             patch.dict("os.environ", {"GEMINI_API_KEY": "fake_test_key"}):

            mock_orchestrate.return_value = {
                "status": "success",
                "route": ["menu"],
                "selected_agents": ["MenuIntelligenceAgent"],
                "agent_results": {"menu": {"answer": "The uploaded menu contains Lemon Tart."}},
                "answer": "The uploaded menu contains Lemon Tart at Rs. 190.",
                "evidence_sources": ["dataset:DS_TEST_MENU"],
                "data_origin": "UPLOADED",
                "dataset_id": "DS_TEST_MENU",
                "limitations": [],
                "errors": None
            }

            resp = client.post(
                "/api/chat",
                json={
                    "message": "What is on the uploaded dessert menu?",
                    "dataset_id": "DS_TEST_MENU",
                },
            )
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["dataset_id"], "DS_TEST_MENU")
            self.assertEqual(body["data_origin"], "UPLOADED")
            body = resp.json()
            self.assertEqual(body["dataset_id"], "DS_TEST_MENU")
            self.assertEqual(body["data_origin"], "UPLOADED")


if __name__ == "__main__":
    unittest.main()
