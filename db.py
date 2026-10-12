"""
db.py - Reusable Database Connection and Query Module for PostgreSQL/Supabase
"""

import os
import re
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal
from datetime import date, datetime
import psycopg
from psycopg.rows import dict_row

from pathlib import Path
_ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
    else:
        load_dotenv()
except ImportError:
    pass


def sanitize_error(e: Exception) -> str:
    """Removes sensitive credentials, API keys, tokens, and connection URLs from error messages."""
    msg = str(e)
    # Strip database connection strings or passwords if present
    msg = re.sub(r'://[^@]+@', '://***:***@', msg)
    msg = re.sub(r'password=\S+', 'password=***', msg)
    # Strip API keys or authorization tokens
    msg = re.sub(r'(api_key|apikey|key|token)=["\']?[a-zA-Z0-9_\-\.]+["\']?', r'\1=***', msg, flags=re.IGNORECASE)
    msg = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer ***', msg, flags=re.IGNORECASE)
    # Strip Google project numbers/ids if present
    msg = re.sub(r'projects/\d+', 'projects/***', msg)
    return msg


def make_json_serializable(obj: Any) -> Any:
    """Recursively converts Decimals and datetime/date objects to standard JSON serializable types."""
    if isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


def get_db_url(raw_url: Optional[str] = None) -> str:
    """
    Retrieves and normalizes the PostgreSQL database connection URL.
    - Loads from environment variable DATABASE_URL if raw_url is not provided.
    - Strips surrounding whitespace and wrapping quotes.
    - Tolerates accidental variable assignment prefix (e.g., 'DATABASE_URL=postgresql://...').
    - Validates scheme (must start with 'postgresql://' or 'postgres://').
    - Ensures sslmode=require for secure Supabase connections.
    """
    url = raw_url if raw_url is not None else os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set in environment variables.")

    url = url.strip()

    # Strip surrounding quotes if present
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1].strip()

    # Guard against accidental env assignment prefix in the value
    if url.startswith("DATABASE_URL="):
        url = url[len("DATABASE_URL="):].strip()
        if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
            url = url[1:-1].strip()

    # Validate PostgreSQL URL scheme
    if not (url.startswith("postgresql://") or url.startswith("postgres://")):
        raise ValueError(
            "Invalid DATABASE_URL scheme: connection URL must start with 'postgresql://' or 'postgres://'."
        )

    # Ensure sslmode=require for secure Supabase connection
    if "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"

    return url


def get_connection(connection_url: Optional[str] = None):
    """
    Establishes a connection to the PostgreSQL/Supabase database.
    Requires DATABASE_URL in environment or passed as an argument.
    """
    db_url = get_db_url(connection_url)
    return psycopg.connect(db_url, row_factory=dict_row)


def execute_query(query: str, params: Optional[Union[tuple, dict, list]] = None) -> List[Dict[str, Any]]:
    """
    Executes a parameterized query and returns a list of dictionary rows.
    Handles statements with or without returning result sets and commits transactions.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if cur.description is not None:
                    rows = cur.fetchall()
                else:
                    rows = []
                conn.commit()
                return make_json_serializable(rows)
    except Exception as e:
        safe_msg = sanitize_error(e)
        raise RuntimeError(f"Database query failed: {safe_msg}") from None


def execute_single(query: str, params: Optional[Union[tuple, dict, list]] = None) -> Optional[Dict[str, Any]]:
    """
    Executes a parameterized query expecting a single row or None.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                row = cur.fetchone() if cur.description is not None else None
                conn.commit()
                return make_json_serializable(row) if row else None
    except Exception as e:
        safe_msg = sanitize_error(e)
        raise RuntimeError(f"Database query failed: {safe_msg}") from None


def execute_statement(query: str, params: Optional[Union[tuple, dict, list]] = None) -> int:
    """
    Executes a parameterized data modification or DDL statement and commits.
    Returns the affected rowcount.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                rc = cur.rowcount
                conn.commit()
                return rc
    except Exception as e:
        safe_msg = sanitize_error(e)
        raise RuntimeError(f"Database statement failed: {safe_msg}") from None



def test_connection() -> Dict[str, Any]:
    """
    Tests the database connection and returns status and server version.
    Sanitizes server version string to prevent leaking OS and compiler build details.
    """
    try:
        row = execute_single("SELECT version();")
        raw_version = (row.get("version") if row else "Unknown") or "Unknown"
        match = re.search(r"PostgreSQL\s+[\d\.]+", raw_version, re.IGNORECASE)
        sanitized_version = match.group(0) if match else ("PostgreSQL" if "postgres" in raw_version.lower() else "Unknown")
        return {
            "status": "connected",
            "server_version": sanitized_version
        }
    except Exception as e:
        return {
            "status": "error",
            "message": sanitize_error(e)
        }
