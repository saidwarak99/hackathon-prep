"""
dataset_queries.py - Controlled Dataset-Aware Query Layer

Provides section-specific queries against user-uploaded datasets stored in dataset_records.
Rules:
- Scopes queries strictly to the requested dataset_id.
- Returns explicit limitations when requested section data is absent.
- NEVER falls back to baseline synthetic records when an uploaded dataset is targeted.
- Explicitly labels data_origin as 'UPLOADED'.
"""

from typing import Dict, Any, List, Optional
from db import execute_query, execute_single


def has_dataset_section(dataset_id: str, section: str) -> bool:
    """Checks whether a dataset contains records for a specific section."""
    row = execute_single(
        "SELECT 1 FROM dataset_records WHERE dataset_id = %s AND section = %s LIMIT 1",
        (dataset_id, section)
    )
    return row is not None


def get_dataset_menu(
    dataset_id: str,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves menu items from an uploaded dataset.
    Never falls back to baseline synthetic data.
    """
    rows = execute_query(
        "SELECT data FROM dataset_records WHERE dataset_id = %s AND section = 'menu_items' ORDER BY row_index",
        (dataset_id,)
    )

    if not rows:
        return {
            "status": "success",
            "data": {
                "categories": [],
                "total_items": 0
            },
            "dataset_id": dataset_id,
            "data_origin": "UPLOADED",
            "message": f"Dataset '{dataset_id}' contains no menu items data. No fallback to baseline data permitted.",
            "limitations": [f"Selected dataset '{dataset_id}' does not contain menu_items records."]
        }

    # Group into categories
    category_map = {}
    total_items = 0

    for r in rows:
        item = r["data"]
        cat_name = item.get("category_name", "General")
        if category and cat_name.lower() != category.lower():
            continue

        if cat_name not in category_map:
            category_map[cat_name] = []

        category_map[cat_name].append({
            "menu_item_id": item.get("menu_item_id"),
            "name": item.get("item_name"),
            "price": float(item.get("list_price_inr", 0.0)),
            "dietary": [item.get("diet_type")] if item.get("diet_type") else [],
            "description": item.get("description"),
            "is_available": item.get("is_available", True)
        })
        total_items += 1

    categories_list = [
        {"category_name": cat, "items": items}
        for cat, items in category_map.items()
    ]

    return {
        "status": "success",
        "data": {
            "categories": categories_list,
            "total_items": total_items
        },
        "dataset_id": dataset_id,
        "data_origin": "UPLOADED"
    }


def get_dataset_inventory(
    dataset_id: str,
    low_stock_only: bool = False
) -> Dict[str, Any]:
    """
    Retrieves inventory supplies and stock alerts from an uploaded dataset.
    Never falls back to baseline synthetic data.
    """
    rows = execute_query(
        "SELECT data FROM dataset_records WHERE dataset_id = %s AND section = 'inventory' ORDER BY row_index",
        (dataset_id,)
    )

    if not rows:
        return {
            "status": "success",
            "data": {},
            "summary": {
                "total_items": 0,
                "low_stock_items_count": 0
            },
            "dataset_id": dataset_id,
            "data_origin": "UPLOADED",
            "message": f"Dataset '{dataset_id}' contains no inventory data. No fallback to baseline data permitted.",
            "limitations": [f"Selected dataset '{dataset_id}' does not contain inventory records."]
        }

    inv_dict = {}
    low_stock_count = 0

    for idx, r in enumerate(rows, start=1):
        item = r["data"]
        name = item.get("ingredient_name", f"Item_{idx}")
        on_hand = float(item.get("on_hand_quantity", 0.0))
        reorder = float(item.get("reorder_level", 0.0))
        is_low = on_hand <= reorder

        if is_low:
            low_stock_count += 1

        if low_stock_only and not is_low:
            continue

        item_key = item.get("ingredient_id") or f"ING_{idx:03d}"
        inv_dict[item_key] = {
            "item_name": name,
            "category": item.get("ingredient_category", "general"),
            "current_stock": on_hand,
            "unit": item.get("unit", "units"),
            "min_reorder_level": reorder,
            "last_count_date": item.get("last_count_date", "N/A"),
            "status": "Low Stock - Reorder Needed!" if is_low else "In Stock"
        }

    return {
        "status": "success",
        "data": inv_dict,
        "summary": {
            "total_items": len(rows),
            "low_stock_items_count": low_stock_count
        },
        "dataset_id": dataset_id,
        "data_origin": "UPLOADED"
    }


def get_dataset_reviews(
    dataset_id: str,
    menu_item_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves customer feedback, ratings, and issue themes from an uploaded dataset.
    Never falls back to baseline synthetic data.
    """
    rows = execute_query(
        "SELECT data FROM dataset_records WHERE dataset_id = %s AND section = 'reviews' ORDER BY row_index",
        (dataset_id,)
    )

    if not rows:
        return {
            "status": "success",
            "data": {},
            "dataset_id": dataset_id,
            "data_origin": "UPLOADED",
            "message": f"Dataset '{dataset_id}' contains no reviews data. No fallback to baseline data permitted.",
            "limitations": [f"Selected dataset '{dataset_id}' does not contain customer feedback records."]
        }

    matched_reviews = []
    ratings = []
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    issues = {}

    for r in rows:
        rev = r["data"]
        item = rev.get("item_name") or ""
        if menu_item_name and menu_item_name.lower() not in item.lower():
            continue

        matched_reviews.append(rev)
        rating = int(rev.get("rating", 3))
        ratings.append(rating)
        rating_dist[rating] = rating_dist.get(rating, 0) + 1

        sent = str(rev.get("sentiment_label", "neutral")).lower()
        if sent in sentiments:
            sentiments[sent] += 1

        issue = str(rev.get("issue_category", "general")).lower()
        issues[issue] = issues.get(issue, 0) + 1

    total_revs = len(matched_reviews)
    avg_rating = round(sum(ratings) / total_revs, 2) if total_revs > 0 else 0.0

    issue_breakdown = [
        {"issue_category": k, "count": v, "percentage_of_reviews": round((v / total_revs) * 100, 1)}
        for k, v in sorted(issues.items(), key=lambda x: -x[1])
    ]

    return {
        "status": "success",
        "data": {
            "summary": {
                "total_reviews": total_revs,
                "average_rating": avg_rating,
                "positive_sentiment_percentage": round((sentiments["positive"] / total_revs) * 100, 1) if total_revs > 0 else 0,
                "neutral_sentiment_percentage": round((sentiments["neutral"] / total_revs) * 100, 1) if total_revs > 0 else 0,
                "negative_sentiment_percentage": round((sentiments["negative"] / total_revs) * 100, 1) if total_revs > 0 else 0
            },
            "rating_distribution": {
                f"{star}_star": {"count": cnt, "percentage": round((cnt / total_revs) * 100, 1) if total_revs > 0 else 0}
                for star, cnt in rating_dist.items()
            },
            "issue_breakdown": issue_breakdown,
            "sample_reviews": matched_reviews[:5]
        },
        "dataset_id": dataset_id,
        "data_origin": "UPLOADED"
    }


def get_dataset_sales(
    dataset_id: str,
    date_str: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves sales performance from an uploaded dataset.
    Never falls back to baseline synthetic data.
    """
    rows = execute_query(
        "SELECT data FROM dataset_records WHERE dataset_id = %s AND section = 'orders' ORDER BY row_index",
        (dataset_id,)
    )

    if not rows:
        return {
            "status": "success",
            "data": {},
            "dataset_id": dataset_id,
            "data_origin": "UPLOADED",
            "message": f"Dataset '{dataset_id}' contains no orders data. No fallback to baseline data permitted.",
            "limitations": [f"Selected dataset '{dataset_id}' does not contain orders records."]
        }

    total_revenue = 0.0
    completed_orders = 0
    cancelled_orders = 0
    refunded_orders = 0
    channels = {}

    for r in rows:
        ord_data = r["data"]
        o_date = ord_data.get("order_date")
        if date_str and o_date != date_str:
            continue

        status = ord_data.get("order_status", "completed").lower()
        amount = float(ord_data.get("total_inr", 0.0))

        if status == "completed":
            completed_orders += 1
            total_revenue += amount
            ch = ord_data.get("channel", "dine_in")
            channels[ch] = channels.get(ch, 0.0) + amount
        elif status == "cancelled":
            cancelled_orders += 1
        elif status == "refunded":
            refunded_orders += 1

    aov = round(total_revenue / completed_orders, 2) if completed_orders > 0 else 0.0

    return {
        "status": "success",
        "data": {
            "summary": {
                "total_orders": completed_orders,
                "total_revenue": round(total_revenue, 2),
                "average_order_value": aov,
                "completed_orders": completed_orders,
                "cancelled_orders": cancelled_orders,
                "refunded_orders": refunded_orders
            },
            "channel_breakdown": [
                {"channel": ch, "revenue_inr": round(rev, 2)}
                for ch, rev in channels.items()
            ]
        },
        "dataset_id": dataset_id,
        "data_origin": "UPLOADED"
    }
