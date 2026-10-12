"""
dataset_ingestion.py - Safe, Dynamic CSV and ZIP Dataset Ingestion

Supports:
- Single CSV uploads and multi-file ZIP archive uploads
- Safe in-memory stream processing and zip-bomb/path traversal prevention
- Automatic section detection and column alias normalization
- Rigorous data validation (types, ranges, required fields, constraints)
- Duplicate content detection via SHA-256 hash
- Non-mutating preview endpoint
- Atomic database ingestion into datasets and dataset_records
"""

import io
import csv
import json
import uuid
import hashlib
import zipfile
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from db import execute_query, execute_single, execute_statement, get_connection, sanitize_error

# -----------------------------------------------------------------------------
# 1. INGESTION SETTINGS & LIMITS
# -----------------------------------------------------------------------------

class DatasetIngestionConfig:
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024       # 10 MB upload limit
    MAX_ZIP_EXPANSION_BYTES = 50 * 1024 * 1024   # 50 MB max expanded ZIP size
    MAX_ROWS_PER_FILE = 10000                    # 10,000 rows max per file
    ALLOWED_EXTENSIONS = {".csv", ".zip"}
    ALLOWED_ENCODINGS = ["utf-8-sig", "utf-8", "latin-1"]
    PREVIEW_SAMPLE_LIMIT = 5


# -----------------------------------------------------------------------------
# 2. SECTION SCHEMAS & ALIAS MAPPINGS
# -----------------------------------------------------------------------------

SECTION_SCHEMAS = {
    "menu_items": {
        "required": ["item_name", "list_price_inr", "category_name"],
        "optional": ["menu_item_id", "diet_type", "is_available", "description"],
        "aliases": {
            "menu_item_id": ["id", "item_id", "item_code", "menu_id"],
            "item_name": ["name", "dish", "dish_name", "title", "product_name"],
            "category_name": ["category", "category_id", "section", "menu_category", "group"],
            "list_price_inr": ["price", "list_price", "price_inr", "cost_inr", "rate", "unit_price"],
            "diet_type": ["diet", "dietary", "is_veg", "vegetarian", "food_type"],
            "is_available": ["available", "in_stock", "is_active", "active", "status"],
            "description": ["desc", "item_description", "notes", "details"]
        },
        "types": {
            "menu_item_id": "string",
            "item_name": "string",
            "category_name": "string",
            "list_price_inr": "float",
            "diet_type": "string",
            "is_available": "boolean",
            "description": "string"
        }
    },
    "orders": {
        "required": ["order_id", "order_date", "total_inr"],
        "optional": ["channel", "order_status", "subtotal_inr", "tax_inr", "service_charge_inr", "customer_id"],
        "aliases": {
            "order_id": ["id", "order_number", "invoice_id", "bill_no"],
            "order_date": ["date", "order_ts", "timestamp", "created_at", "order_time"],
            "total_inr": ["total", "order_total", "amount", "bill_amount", "total_amount", "net_amount"],
            "channel": ["order_channel", "order_type", "type", "source"],
            "order_status": ["status", "state"],
            "subtotal_inr": ["subtotal", "sub_total"],
            "tax_inr": ["tax", "tax_amount", "gst"],
            "service_charge_inr": ["service_charge", "service_tax"],
            "customer_id": ["cust_id", "customer", "customer_number"]
        },
        "types": {
            "order_id": "string",
            "order_date": "date",
            "total_inr": "float",
            "channel": "string",
            "order_status": "string",
            "subtotal_inr": "float",
            "tax_inr": "float",
            "service_charge_inr": "float",
            "customer_id": "string"
        }
    },
    "order_items": {
        "required": ["order_item_id", "order_id", "item_name", "quantity", "unit_price_inr"],
        "optional": ["discount_inr", "line_total_inr"],
        "aliases": {
            "order_item_id": ["id", "item_id", "order_line_id"],
            "order_id": ["order_number", "order"],
            "item_name": ["menu_item_name", "dish_name", "menu_item_id", "item", "product"],
            "quantity": ["qty", "count", "units", "quantity_sold"],
            "unit_price_inr": ["unit_price", "price", "item_price"],
            "discount_inr": ["discount", "discount_amount"],
            "line_total_inr": ["line_total", "total", "item_total"]
        },
        "types": {
            "order_item_id": "string",
            "order_id": "string",
            "item_name": "string",
            "quantity": "integer",
            "unit_price_inr": "float",
            "discount_inr": "float",
            "line_total_inr": "float"
        }
    },
    "reviews": {
        "required": ["rating", "review_text"],
        "optional": ["review_id", "review_date", "reviewed_menu_item_id", "item_name", "sentiment_label", "issue_category", "order_id"],
        "aliases": {
            "review_id": ["id", "feedback_id", "review_no"],
            "rating": ["stars", "score", "rating_score", "customer_rating"],
            "review_text": ["text", "comment", "review", "feedback", "content", "comments"],
            "review_date": ["date", "created_at", "timestamp", "review_time"],
            "item_name": ["dish", "item", "menu_item", "dish_name", "reviewed_menu_item_id"],
            "sentiment_label": ["sentiment", "sentiment_type"],
            "issue_category": ["category", "issue", "complaint_type", "feedback_category"],
            "order_id": ["order", "order_number"]
        },
        "types": {
            "review_id": "string",
            "rating": "integer",
            "review_text": "string",
            "review_date": "date",
            "item_name": "string",
            "sentiment_label": "string",
            "issue_category": "string",
            "order_id": "string"
        }
    },
    "inventory": {
        "required": ["ingredient_name", "on_hand_quantity", "reorder_level", "unit"],
        "optional": ["ingredient_id", "ingredient_category", "last_count_date", "status"],
        "aliases": {
            "ingredient_id": ["id", "item_id", "ingredient_code"],
            "ingredient_name": ["item_name", "name", "ingredient", "item", "stock_item"],
            "on_hand_quantity": ["current_stock", "stock", "quantity", "qty", "on_hand"],
            "reorder_level": ["min_reorder_level", "threshold", "reorder_threshold", "min_stock", "reorder_point"],
            "unit": ["uom", "measurement_unit", "stock_unit"],
            "ingredient_category": ["category", "section", "type"],
            "last_count_date": ["count_date", "date", "last_updated"],
            "status": ["stock_status", "alert_status"]
        },
        "types": {
            "ingredient_id": "string",
            "ingredient_name": "string",
            "on_hand_quantity": "float",
            "reorder_level": "float",
            "unit": "string",
            "ingredient_category": "string",
            "last_count_date": "date",
            "status": "string"
        }
    },
    "payments": {
        "required": ["payment_id", "order_id", "payment_method", "amount_inr"],
        "optional": ["payment_status", "refund_amount_inr", "payment_ts"],
        "aliases": {
            "payment_id": ["id", "txn_id", "transaction_id"],
            "order_id": ["order_number", "order"],
            "payment_method": ["method", "mode", "payment_mode", "channel"],
            "amount_inr": ["amount", "paid_amount", "total"],
            "payment_status": ["status", "state"],
            "refund_amount_inr": ["refund_amount", "refund"],
            "payment_ts": ["timestamp", "date", "payment_date"]
        },
        "types": {
            "payment_id": "string",
            "order_id": "string",
            "payment_method": "string",
            "amount_inr": "float",
            "payment_status": "string",
            "refund_amount_inr": "float",
            "payment_ts": "date"
        }
    }
}


# -----------------------------------------------------------------------------
# 3. NORMALIZATION & SECTION DETECTION
# -----------------------------------------------------------------------------

def normalize_header(header: str) -> str:
    """Normalizes header string into lowercase underscored token."""
    h = header.strip().lower()
    h = re.sub(r"[^\w\s]", "", h)
    h = re.sub(r"\s+", "_", h)
    return h


def match_column_alias(normalized_col: str, section: str) -> Optional[str]:
    """Matches a normalized column name to a canonical target column in the section."""
    schema = SECTION_SCHEMAS.get(section)
    if not schema:
        return None

    # Check exact match
    if normalized_col in schema["required"] or normalized_col in schema["optional"]:
        return normalized_col

    # Check alias match
    for target_col, aliases in schema["aliases"].items():
        if normalized_col in aliases:
            return target_col

    return None


def detect_section(headers: List[str]) -> Tuple[Optional[str], Dict[str, str], List[str]]:
    """
    Detects the best matching section for a set of CSV headers.
    Returns:
        (detected_section, column_mapping, missing_required_fields)
    """
    norm_headers = [normalize_header(h) for h in headers]
    best_section = None
    best_score = -1
    best_mapping = {}
    best_missing = []

    for sec_name, schema in SECTION_SCHEMAS.items():
        mapping = {}
        matched_required = set()
        matched_optional = set()

        for original_col, norm_col in zip(headers, norm_headers):
            target = match_column_alias(norm_col, sec_name)
            if target:
                mapping[original_col] = target
                if target in schema["required"]:
                    matched_required.add(target)
                elif target in schema["optional"]:
                    matched_optional.add(target)

        missing_required = [req for req in schema["required"] if req not in matched_required]
        score = len(matched_required) * 3 + len(matched_optional)

        # To be a valid candidate, it must match at least 2 required columns or all required if fewer
        min_required_needed = min(2, len(schema["required"]))
        if len(matched_required) >= min_required_needed and score > best_score:
            best_score = score
            best_section = sec_name
            best_mapping = mapping
            best_missing = missing_required

    # Check if all required fields are present for the best candidate
    if best_section and not best_missing:
        return best_section, best_mapping, []

    if best_section and best_missing:
        return best_section, best_mapping, best_missing

    return None, {}, ["No matching section detected."]


# -----------------------------------------------------------------------------
# 4. ROW VALIDATION & TYPE CASTING
# -----------------------------------------------------------------------------

def validate_and_cast_row(
    raw_row: Dict[str, str],
    mapping: Dict[str, str],
    section: str,
    row_idx: int
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    Validates a single row, applies canonical column mapping, and casts types.
    Returns (cleaned_row_dict, errors).
    """
    schema = SECTION_SCHEMAS[section]
    type_defs = schema["types"]
    cleaned = {}
    errors = []

    # Map raw columns to canonical columns
    for raw_col, val in raw_row.items():
        target_col = mapping.get(raw_col)
        if target_col:
            cleaned[target_col] = val.strip() if isinstance(val, str) else val

    # Verify required fields are non-empty
    for req in schema["required"]:
        val = cleaned.get(req)
        if val is None or val == "":
            errors.append(f"Row {row_idx}: Missing required field '{req}'.")

    if errors:
        return None, errors

    # Cast fields according to type definition
    casted = {}
    for col, val in cleaned.items():
        expected_type = type_defs.get(col, "string")
        if val is None or val == "":
            casted[col] = None
            continue

        try:
            if expected_type == "float":
                f_val = float(val)
                if f_val < 0:
                    errors.append(f"Row {row_idx}: '{col}' cannot be negative (got {f_val}).")
                casted[col] = f_val
            elif expected_type == "integer":
                i_val = int(float(val))
                if col == "rating" and not (1 <= i_val <= 5):
                    errors.append(f"Row {row_idx}: Rating must be between 1 and 5 (got {i_val}).")
                elif col == "quantity" and i_val <= 0:
                    errors.append(f"Row {row_idx}: Quantity must be positive (got {i_val}).")
                casted[col] = i_val
            elif expected_type == "boolean":
                str_val = str(val).strip().lower()
                casted[col] = str_val in ("true", "1", "yes", "t", "y")
            elif expected_type == "date":
                # Validate date format (YYYY-MM-DD or standard parseable ISO)
                date_str = str(val).split("T")[0].split(" ")[0].strip()
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                    # Try common MM/DD/YYYY or DD-MM-YYYY
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    casted[col] = dt.strftime("%Y-%m-%d")
                else:
                    casted[col] = date_str
            else:
                casted[col] = str(val).strip()
        except Exception as e:
            errors.append(f"Row {row_idx}: Failed to cast '{col}' value '{val}' to {expected_type}: {str(e)}")

    # Section-specific defaults & enrichment
    if section == "menu_items":
        if "menu_item_id" not in casted or not casted["menu_item_id"]:
            # Auto-generate menu item ID from name if absent
            name_slug = re.sub(r"[^\w]", "", casted["item_name"]).upper()[:6]
            casted["menu_item_id"] = f"MNU_{name_slug}_{row_idx}"
        if "diet_type" not in casted or not casted["diet_type"]:
            casted["diet_type"] = "veg"
        if "is_available" not in casted or casted["is_available"] is None:
            casted["is_available"] = True

    elif section == "inventory":
        if "ingredient_id" not in casted or not casted["ingredient_id"]:
            ing_slug = re.sub(r"[^\w]", "", casted["ingredient_name"]).upper()[:6]
            casted["ingredient_id"] = f"ING_{ing_slug}_{row_idx}"
        if "last_count_date" not in casted or not casted["last_count_date"]:
            casted["last_count_date"] = datetime.now().strftime("%Y-%m-%d")
        if "status" not in casted or not casted["status"]:
            on_hand = casted.get("on_hand_quantity", 0)
            reorder = casted.get("reorder_level", 0)
            casted["status"] = "Low Stock" if on_hand <= reorder else "In Stock"

    elif section == "reviews":
        if "sentiment_label" not in casted or not casted["sentiment_label"]:
            rating = casted.get("rating", 3)
            casted["sentiment_label"] = "positive" if rating >= 4 else ("neutral" if rating == 3 else "negative")
        if "review_date" not in casted or not casted["review_date"]:
            casted["review_date"] = datetime.now().strftime("%Y-%m-%d")
        if "issue_category" not in casted or not casted["issue_category"]:
            casted["issue_category"] = "general"

    if errors:
        return None, errors

    return casted, []


# -----------------------------------------------------------------------------
# 5. IN-MEMORY PARSERS FOR CSV AND ZIP
# -----------------------------------------------------------------------------

def parse_csv_stream(
    stream: io.BytesIO,
    filename: str
) -> Dict[str, Any]:
    """
    Parses a CSV byte stream in memory with encoding auto-detection.
    Returns:
        Dict with keys: filename, headers, raw_rows, error (if any)
    """
    content_bytes = stream.read()
    if len(content_bytes) == 0:
        return {"filename": filename, "error": "File is completely empty (0 bytes)."}

    # Detect encoding
    text = None
    for enc in DatasetIngestionConfig.ALLOWED_ENCODINGS:
        try:
            text = content_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        return {"filename": filename, "error": f"Failed to decode CSV. Supported encodings: {DatasetIngestionConfig.ALLOWED_ENCODINGS}"}

    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except Exception as e:
        return {"filename": filename, "error": f"Malformed CSV structure: {str(e)}"}

    if not rows:
        return {"filename": filename, "error": "CSV contains no rows."}

    headers = [h.strip().lstrip('\ufeff') for h in rows[0] if h.strip().lstrip('\ufeff')]
    if not headers:
        return {"filename": filename, "error": "CSV has no valid header row."}

    data_rows = rows[1:]
    if not data_rows:
        return {"filename": filename, "error": "CSV contains headers but no data records."}

    if len(data_rows) > DatasetIngestionConfig.MAX_ROWS_PER_FILE:
        return {
            "filename": filename,
            "error": f"CSV exceeds maximum allowed limit of {DatasetIngestionConfig.MAX_ROWS_PER_FILE} rows (contains {len(data_rows)})."
        }

    raw_dict_rows = []
    for idx, r in enumerate(data_rows, start=1):
        if not any(cell.strip() for cell in r):
            continue  # Skip empty trailing lines
        row_dict = {}
        for h_idx, h in enumerate(headers):
            row_dict[h] = r[h_idx].strip() if h_idx < len(r) else ""
        raw_dict_rows.append(row_dict)

    return {
        "filename": filename,
        "headers": headers,
        "raw_rows": raw_dict_rows,
        "error": None
    }


def extract_files_from_upload(
    file_bytes: bytes,
    original_filename: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Safely extracts CSV streams from direct CSV upload or ZIP archive.
    Enforces size limits, archive expansion safety, and path traversal security.
    """
    if len(file_bytes) > DatasetIngestionConfig.MAX_FILE_SIZE_BYTES:
        return [], f"Upload size ({len(file_bytes)} bytes) exceeds maximum limit of {DatasetIngestionConfig.MAX_FILE_SIZE_BYTES} bytes."

    ext = original_filename.lower().split(".")[-1]
    if f".{ext}" not in DatasetIngestionConfig.ALLOWED_EXTENSIONS:
        return [], f"Unsupported file extension '.{ext}'. Supported formats: CSV (.csv), ZIP (.zip)."

    parsed_files = []

    if ext == "csv":
        res = parse_csv_stream(io.BytesIO(file_bytes), original_filename)
        if res.get("error"):
            return [], res["error"]
        parsed_files.append(res)
        return parsed_files, None

    # Handle ZIP archive
    if ext == "zip":
        try:
            zip_buffer = io.BytesIO(file_bytes)
            with zipfile.ZipFile(zip_buffer, "r") as zf:
                total_uncompressed = 0
                members = zf.infolist()

                if not members:
                    return [], "ZIP archive is empty."

                for member in members:
                    # Security check: Path traversal prevention
                    m_name = member.filename
                    if m_name.startswith("/") or m_name.startswith("\\") or ".." in m_name or ":" in m_name:
                        return [], f"Security alert: Malicious path traversal entry detected in archive ('{m_name}')."

                    # Skip directory entries and OS metadata
                    if member.is_dir() or "__MACOSX" in m_name or m_name.startswith(".") or m_name.endswith(".DS_Store"):
                        continue

                    # Validate extension
                    m_ext = m_name.lower().split(".")[-1]
                    if m_ext != "csv":
                        return [], f"Archive contains non-CSV file '{m_name}'. Only CSV files are allowed within ZIP uploads."

                    # Check expansion limit incrementally
                    total_uncompressed += member.file_size
                    if total_uncompressed > DatasetIngestionConfig.MAX_ZIP_EXPANSION_BYTES:
                        return [], f"Archive expansion size exceeds safety limit of {DatasetIngestionConfig.MAX_ZIP_EXPANSION_BYTES} bytes."

                    # Read member stream into memory safely
                    with zf.open(member) as file_stream:
                        m_bytes = file_stream.read()
                        res = parse_csv_stream(io.BytesIO(m_bytes), member.filename)
                        if res.get("error"):
                            return [], f"Error in archive member '{member.filename}': {res['error']}"
                        parsed_files.append(res)

        except zipfile.BadZipFile:
            return [], "Corrupted or invalid ZIP archive file."
        except Exception as e:
            return [], f"Failed to inspect ZIP archive: {str(e)}"

        if not parsed_files:
            return [], "ZIP archive contains no valid CSV files."

        return parsed_files, None

    return [], "Unknown file format."


# -----------------------------------------------------------------------------
# 6. DATASET PREVIEW ENGINE (NON-MUTATING)
# -----------------------------------------------------------------------------

def preview_dataset(
    file_bytes: bytes,
    original_filename: str,
    restaurant_id: str = "default_restaurant"
) -> Dict[str, Any]:
    """
    Dry-run preview and schema validation for an uploaded dataset.
    Does NOT mutate or write anything to the database.
    """
    content_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check duplicate hash against existing datasets table
    is_duplicate = False
    existing_dataset_id = None
    try:
        dup_row = execute_single(
            "SELECT dataset_id FROM datasets WHERE content_hash = %s AND restaurant_id = %s",
            (content_hash, restaurant_id)
        )
        if dup_row:
            is_duplicate = True
            existing_dataset_id = dup_row["dataset_id"]
    except Exception:
        pass  # If DB check fails, proceed with preview analysis

    extracted_files, extract_err = extract_files_from_upload(file_bytes, original_filename)
    if extract_err:
        return {
            "status": "validation_failed",
            "is_valid": False,
            "filename": original_filename,
            "content_hash": content_hash,
            "is_duplicate": is_duplicate,
            "existing_dataset_id": existing_dataset_id,
            "validation_errors": [extract_err],
            "warnings": [],
            "detected_sections": [],
            "files_summary": []
        }

    all_errors = []
    all_warnings = []
    detected_sections = []
    files_summary = []
    total_rows = 0

    for f in extracted_files:
        f_name = f["filename"]
        headers = f["headers"]
        raw_rows = f["raw_rows"]
        total_rows += len(raw_rows)

        section, mapping, missing = detect_section(headers)
        if not section:
            all_errors.append(f"File '{f_name}': Could not identify supported section from headers: {headers}.")
            files_summary.append({
                "filename": f_name,
                "detected_section": "unknown",
                "row_count": len(raw_rows),
                "headers": headers,
                "error": "No matching section detected."
            })
            continue

        if missing:
            all_errors.append(f"File '{f_name}' detected as section '{section}', but missing required fields: {missing}.")
            files_summary.append({
                "filename": f_name,
                "detected_section": section,
                "row_count": len(raw_rows),
                "headers": headers,
                "missing_required": missing,
                "error": f"Missing required fields: {missing}"
            })
            continue

        detected_sections.append(section)

        # Validate rows in file
        valid_rows_count = 0
        file_errors = []
        sample_cleaned = []
        key_set = set()

        # Identify primary natural key for duplication check
        primary_key_col = "order_id" if section == "orders" else (
            "review_id" if section == "reviews" else (
                "ingredient_name" if section == "inventory" else (
                    "item_name" if section == "menu_items" else None
                )
            )
        )

        for row_idx, r in enumerate(raw_rows, start=1):
            cleaned, r_errs = validate_and_cast_row(r, mapping, section, row_idx)
            if r_errs:
                file_errors.extend(r_errs[:5])  # Cap errors per row
                if len(file_errors) >= 20:
                    file_errors.append(f"...and more validation errors in file '{f_name}'.")
                    break
            else:
                valid_rows_count += 1
                if len(sample_cleaned) < DatasetIngestionConfig.PREVIEW_SAMPLE_LIMIT:
                    sample_cleaned.append(cleaned)

                # Check duplicate record keys within file
                if primary_key_col and primary_key_col in cleaned:
                    pk_val = str(cleaned[primary_key_col]).strip()
                    if pk_val in key_set:
                        all_warnings.append(f"File '{f_name}': Duplicate entry for {primary_key_col} '{pk_val}' at row {row_idx}.")
                    key_set.add(pk_val)

        if file_errors:
            all_errors.extend(file_errors)

        files_summary.append({
            "filename": f_name,
            "detected_section": section,
            "row_count": len(raw_rows),
            "valid_rows_count": valid_rows_count,
            "headers": headers,
            "column_mapping": mapping,
            "sample_records": sample_cleaned
        })

    is_valid = len(all_errors) == 0

    return {
        "status": "valid" if is_valid else "validation_failed",
        "is_valid": is_valid,
        "filename": original_filename,
        "content_hash": content_hash,
        "is_duplicate": is_duplicate,
        "existing_dataset_id": existing_dataset_id,
        "total_rows": total_rows,
        "detected_sections": sorted(list(set(detected_sections))),
        "files_summary": files_summary,
        "validation_errors": all_errors,
        "warnings": all_warnings
    }


# -----------------------------------------------------------------------------
# 7. ATOMIC DATASET INGESTION ENGINE
# -----------------------------------------------------------------------------

def ingest_dataset(
    file_bytes: bytes,
    original_filename: str,
    dataset_name: Optional[str] = None,
    restaurant_id: str = "default_restaurant"
) -> Dict[str, Any]:
    """
    Atomically imports validated dataset records into Supabase.
    Steps:
      1. Complete validation preview (dry run).
      2. If duplicate, returns explicit duplicate status.
      3. If invalid, aborts before any DB modification.
      4. Inserts dataset metadata record (status='PENDING').
      5. Batch inserts all validated records into dataset_records.
      6. Commits transaction and sets status='INGESTED'.
    """
    preview = preview_dataset(file_bytes, original_filename, restaurant_id)

    if not preview["is_valid"]:
        return {
            "status": "error",
            "message": "Dataset validation failed. No records were imported.",
            "validation_errors": preview["validation_errors"],
            "warnings": preview["warnings"],
            "content_hash": preview["content_hash"]
        }

    # If duplicate upload detected
    if preview["is_duplicate"]:
        return {
            "status": "duplicate",
            "message": f"This identical dataset has already been uploaded as '{preview['existing_dataset_id']}'.",
            "dataset_id": preview["existing_dataset_id"],
            "content_hash": preview["content_hash"],
            "detected_sections": preview["detected_sections"],
            "total_rows": preview["total_rows"]
        }

    clean_dataset_name = dataset_name.strip() if dataset_name else original_filename.rsplit(".", 1)[0]
    dataset_id = f"DS_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
    main_section = preview["detected_sections"][0] if len(preview["detected_sections"]) == 1 else "multi_section"

    extracted_files, _ = extract_files_from_upload(file_bytes, original_filename)

    # Begin atomic transaction
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Insert dataset record with status PENDING
                cur.execute("""
                    INSERT INTO datasets (
                        dataset_id, restaurant_id, dataset_name, detected_section,
                        original_filename, content_hash, ingestion_status, row_count,
                        schema_mapping, validation_summary, data_origin
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    dataset_id,
                    restaurant_id,
                    clean_dataset_name,
                    main_section,
                    original_filename,
                    preview["content_hash"],
                    "PENDING",
                    preview["total_rows"],
                    json.dumps({f["filename"]: f["column_mapping"] for f in preview["files_summary"]}),
                    json.dumps({
                        "files": len(preview["files_summary"]),
                        "sections": preview["detected_sections"],
                        "warnings": preview["warnings"]
                    }),
                    "UPLOADED"
                ))

                # 2. Insert records for each file
                total_inserted = 0
                for f_info, f_extract in zip(preview["files_summary"], extracted_files):
                    sec = f_info["detected_section"]
                    mapping = f_info["column_mapping"]
                    raw_rows = f_extract["raw_rows"]

                    for row_idx, r in enumerate(raw_rows, start=1):
                        cleaned, _ = validate_and_cast_row(r, mapping, sec, row_idx)
                        if not cleaned:
                            continue

                        # Determine natural record key
                        rec_key = cleaned.get("order_id") or cleaned.get("review_id") or cleaned.get("ingredient_name") or cleaned.get("item_name") or f"{sec}_{row_idx}"

                        cur.execute("""
                            INSERT INTO dataset_records (
                                dataset_id, restaurant_id, section, record_key, data, row_index
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            dataset_id,
                            restaurant_id,
                            sec,
                            str(rec_key),
                            json.dumps(cleaned),
                            row_idx
                        ))
                        total_inserted += 1

                # 3. Promote dataset status to INGESTED
                cur.execute("""
                    UPDATE datasets
                    SET ingestion_status = 'INGESTED', row_count = %s
                    WHERE dataset_id = %s
                """, (total_inserted, dataset_id))

            conn.commit()

        return {
            "status": "success",
            "message": f"Successfully ingested {total_inserted} records into dataset '{dataset_id}'.",
            "dataset_id": dataset_id,
            "dataset_name": clean_dataset_name,
            "restaurant_id": restaurant_id,
            "detected_sections": preview["detected_sections"],
            "rows_ingested": total_inserted,
            "content_hash": preview["content_hash"],
            "data_origin": "UPLOADED",
            "warnings": preview["warnings"],
            "limitations": [
                f"Dataset '{dataset_id}' contains uploaded records for section(s): {', '.join(preview['detected_sections'])}.",
                "Sections not included in this upload cannot be queried without co-uploading dependent files.",
                "Original baseline synthetic dataset remains preserved and unmodified."
            ]
        }

    except Exception as e:
        safe_msg = sanitize_error(e)
        # Attempt to record FAILED status safely
        try:
            execute_statement(
                "UPDATE datasets SET ingestion_status = 'FAILED' WHERE dataset_id = %s",
                (dataset_id,)
            )
        except Exception:
            pass
        return {
            "status": "error",
            "message": f"Database ingestion failure: {safe_msg}",
            "dataset_id": dataset_id
        }


# -----------------------------------------------------------------------------
# 8. DATASET REPOSITORY QUERIES
# -----------------------------------------------------------------------------

def list_datasets(restaurant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all registered datasets and their status."""
    if restaurant_id:
        sql = """
            SELECT 
                dataset_id, restaurant_id, dataset_name, detected_section,
                original_filename, upload_timestamp::text as upload_timestamp,
                ingestion_status, row_count, data_origin
            FROM datasets
            WHERE restaurant_id = %s
            ORDER BY upload_timestamp DESC
        """
        return execute_query(sql, (restaurant_id,))
    else:
        sql = """
            SELECT 
                dataset_id, restaurant_id, dataset_name, detected_section,
                original_filename, upload_timestamp::text as upload_timestamp,
                ingestion_status, row_count, data_origin
            FROM datasets
            ORDER BY upload_timestamp DESC
        """
        return execute_query(sql)


def get_dataset_metadata(dataset_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves metadata and section breakdown for a specific dataset."""
    ds = execute_single("""
        SELECT 
            dataset_id, restaurant_id, dataset_name, detected_section,
            original_filename, content_hash, upload_timestamp::text as upload_timestamp,
            ingestion_status, row_count, schema_mapping, validation_summary, data_origin
        FROM datasets
        WHERE dataset_id = %s
    """, (dataset_id,))

    if not ds:
        return None

    # Get section row counts
    section_counts = execute_query("""
        SELECT section, COUNT(*) as count
        FROM dataset_records
        WHERE dataset_id = %s
        GROUP BY section
    """, (dataset_id,))

    ds["sections_summary"] = {r["section"]: r["count"] for r in section_counts}
    return ds
