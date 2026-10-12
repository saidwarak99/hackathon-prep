import io
import uuid
import unittest
from fastapi.testclient import TestClient
from api import app

class TestE2EDatasetWorkflow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_e2e_dataset_preview_ingest_chat_and_missing_sections(self):
        # 1. Preview a small synthetic menu CSV
        run_id = uuid.uuid4().hex[:6]
        menu_csv = (
            "dish_name,category,price,dietary,is_available\n"
            f"Masala Chai {run_id},Beverages,40.00,Vegetarian,true\n"
            f"Filter Coffee {run_id},Beverages,50.00,Vegetarian,true\n"
            f"Paneer Tikka Roll {run_id},Snacks,120.00,Vegetarian,true\n"
        ).encode("utf-8")

        preview_resp = self.client.post(
            "/api/datasets/preview",
            files={"file": ("test_rasaiq_menu.csv", io.BytesIO(menu_csv), "text/csv")},
            data={"restaurant_id": "test_tenant"}
        )
        self.assertEqual(preview_resp.status_code, 200, f"Preview failed: {preview_resp.text}")
        preview_data = preview_resp.json()
        self.assertTrue(preview_data["is_valid"])
        self.assertIn("menu_items", preview_data["detected_sections"])
        self.assertEqual(preview_data["total_rows"], 3)

        # 2. Ingest the dataset
        ingest_resp = self.client.post(
            "/api/datasets/ingest",
            files={"file": ("test_rasaiq_menu.csv", io.BytesIO(menu_csv), "text/csv")},
            data={"dataset_name": "RasaIQ Test Menu", "restaurant_id": "test_tenant"}
        )
        self.assertEqual(ingest_resp.status_code, 200, f"Ingest failed: {ingest_resp.text}")
        ingest_data = ingest_resp.json()
        self.assertEqual(ingest_data["status"], "success")
        dataset_id = ingest_data["dataset_id"]
        self.assertTrue(dataset_id.startswith("DS_"))
        self.assertEqual(ingest_data["rows_ingested"], 3)
        self.assertEqual(ingest_data["data_origin"], "UPLOADED")

        # 3. List datasets and verify our dataset is present
        list_resp = self.client.get("/api/datasets?restaurant_id=test_tenant")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        matching = [d for d in list_data["datasets"] if d["dataset_id"] == dataset_id]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["dataset_name"], "RasaIQ Test Menu")

        # 4. Check details of dataset
        detail_resp = self.client.get(f"/api/datasets/{dataset_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["dataset"]["dataset_id"], dataset_id)

        # 5. Query /api/chat with dataset_id (simulate or test route)
        # We can test direct tool calls or unified chat in simulation mode
        # In tools.py:
        import tools
        menu_result = tools.get_menu(dataset_id=dataset_id)
        self.assertEqual(menu_result["dataset_id"], dataset_id)
        self.assertEqual(menu_result["data_origin"], "UPLOADED")
        self.assertEqual(menu_result["data"]["total_items"], 3)

        # 6. Verify missing section behavior: Inventory query on a menu-only dataset
        # Should NOT fall back to baseline synthetic records!
        inv_result = tools.get_inventory(dataset_id=dataset_id)
        self.assertEqual(inv_result["dataset_id"], dataset_id)
        self.assertEqual(inv_result["data_origin"], "UPLOADED")
        self.assertEqual(inv_result["summary"]["total_items"], 0)
        self.assertIn("limitations", inv_result)
        self.assertTrue(any("does not contain inventory records" in lim for lim in inv_result["limitations"]))
        print("End-to-end dataset workflow verification passed successfully!")

if __name__ == "__main__":
    unittest.main()
