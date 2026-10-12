"""
test_db_unit.py - Focused Unit Tests for Database URL Loading and Normalization
Validates URL parsing, prefix handling, and rejection of malformed strings without requiring live credentials.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from db import get_db_url, get_connection


class TestDBUrlLoading(unittest.TestCase):

    def test_valid_postgresql_url_appends_sslmode(self):
        url = "postgresql://user:pass@localhost:5432/mydb"
        result = get_db_url(url)
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")

    def test_valid_postgres_alias_scheme(self):
        url = "postgres://user:pass@localhost:5432/mydb"
        result = get_db_url(url)
        self.assertEqual(result, "postgres://user:pass@localhost:5432/mydb?sslmode=require")

    def test_existing_query_params_appends_ampersand_sslmode(self):
        url = "postgresql://user:pass@localhost:5432/mydb?connect_timeout=10"
        result = get_db_url(url)
        self.assertEqual(
            result,
            "postgresql://user:pass@localhost:5432/mydb?connect_timeout=10&sslmode=require"
        )

    def test_existing_sslmode_preserved(self):
        url = "postgresql://user:pass@localhost:5432/mydb?sslmode=require"
        result = get_db_url(url)
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")

    def test_malformed_database_url_prefix_stripped(self):
        url = "DATABASE_URL=postgresql://user:pass@localhost:5432/mydb?sslmode=require"
        result = get_db_url(url)
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")

    def test_quoted_url_stripped(self):
        url = '"postgresql://user:pass@localhost:5432/mydb"'
        result = get_db_url(url)
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")

        url_single = "'postgresql://user:pass@localhost:5432/mydb'"
        result_single = get_db_url(url_single)
        self.assertEqual(result_single, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")

    def test_quoted_url_with_prefix_normalized(self):
        url = 'DATABASE_URL="postgresql://user:pass@localhost:5432/mydb?sslmode=require"'
        result = get_db_url(url)
        self.assertEqual(result, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")

    @patch.dict(os.environ, {"DATABASE_URL": "postgresql://testuser:testpass@localhost:5432/testdb"}, clear=False)
    def test_loads_from_environment_variable(self):
        result = get_db_url()
        self.assertEqual(result, "postgresql://testuser:testpass@localhost:5432/testdb?sslmode=require")

    @patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False)
    def test_missing_database_url_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            get_db_url()
        self.assertIn("DATABASE_URL is not set", str(ctx.exception))

    def test_invalid_scheme_raises_value_error(self):
        invalid_urls = [
            "DATABASE_URL",
            "mysql://user:pass@localhost:3306/mydb",
            "http://example.com/db",
            "invalid_connection_string",
        ]
        for inv in invalid_urls:
            with self.subTest(inv=inv):
                with self.assertRaises(ValueError) as ctx:
                    get_db_url(inv)
                self.assertIn("Invalid DATABASE_URL scheme", str(ctx.exception))

    @patch("db.psycopg.connect")
    def test_get_connection_passes_normalized_url(self, mock_connect):
        fake_conn = MagicMock()
        mock_connect.return_value = fake_conn

        conn = get_connection("DATABASE_URL=postgresql://user:pass@localhost:5432/mydb")
        self.assertEqual(conn, fake_conn)
        mock_connect.assert_called_once()
        called_url, called_kwargs = mock_connect.call_args[0][0], mock_connect.call_args[1]
        self.assertEqual(called_url, "postgresql://user:pass@localhost:5432/mydb?sslmode=require")
        self.assertIn("row_factory", called_kwargs)


if __name__ == "__main__":
    unittest.main()
