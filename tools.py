"""
tools.py - Agent Tools Definition connected to Supabase PostgreSQL Database

In AI agent architecture, a "tool" is an executable function or API client
that gives the agent the ability to take actions, query databases, or interact
with the outside world.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date, timedelta
from db import execute_query, execute_single
from dataset_queries import (
    get_dataset_menu,
    get_dataset_inventory,
    get_dataset_reviews,
    get_dataset_sales
)


def _resolve_date_range(start_date: Optional[str] = None, end_date: Optional[str] = None, default_days: int = 7) -> Tuple[str, str]:
    """
    Resolves start and end date strings.
    If end_date is missing, retrieves the latest completed order_date from database or current date.
    If start_date is missing, looks back default_days.
    """
    if end_date:
        end_clean = end_date.strip()
    else:
        max_row = execute_single("SELECT MAX(order_date)::text as max_date FROM orders WHERE order_status = 'completed';")
        end_clean = (max_row and max_row.get("max_date")) or date.today().isoformat()
        
    try:
        end_dt = datetime.strptime(end_clean, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid end_date format: '{end_date}'. Expected YYYY-MM-DD.")

    if start_date:
        start_clean = start_date.strip()
        try:
            start_dt = datetime.strptime(start_clean, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise ValueError(f"Invalid start_date format: '{start_date}'. Expected YYYY-MM-DD.")
    else:
        start_dt = end_dt - timedelta(days=default_days - 1)
        start_clean = start_dt.isoformat()

    if start_dt > end_dt:
        start_clean, end_clean = end_clean, start_clean

    return start_clean, end_clean


def get_inventory(low_stock_only: bool = False, dataset_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool: get_inventory

    Description:
        Retrieves current stock levels of cafe ingredients, supplies,
        units of measurement, and identifies items that need reordering from the database.

    Returns:
        Dict[str, Any]: Inventory data including stock amounts and alert statuses.
    """
    if dataset_id:
        return get_dataset_inventory(dataset_id=dataset_id, low_stock_only=low_stock_only)

    try:
        query = """
            SELECT 
                inv.ingredient_id,
                ing.ingredient_name,
                ing.ingredient_category,
                inv.on_hand_quantity,
                inv.reorder_level,
                inv.unit,
                inv.last_count_date,
                CASE 
                    WHEN inv.on_hand_quantity <= inv.reorder_level THEN 'Low Stock - Reorder Needed!'
                    ELSE 'In Stock'
                END as status
            FROM inventory inv
            JOIN ingredients ing ON inv.ingredient_id = ing.ingredient_id
            ORDER BY ing.ingredient_category, ing.ingredient_name;
        """
        rows = execute_query(query)

        if not rows:
            return {
                "status": "success",
                "data": {},
                "summary": {
                    "total_items": 0,
                    "low_stock_items_count": 0
                },
                "message": "No inventory records found in database."
            }

        inventory_dict = {}
        low_stock_count = 0
        for row in rows:
            on_hand = row.get("on_hand_quantity")
            reorder = row.get("reorder_level")
            is_low = (on_hand is not None and reorder is not None and on_hand <= reorder)
            if is_low:
                low_stock_count += 1

            if low_stock_only and not is_low:
                continue

            # Respect explicit 'status', or mapped 'stock_status', or compute from threshold
            raw_status = row.get("status")
            if not raw_status:
                raw_stock_st = row.get("stock_status")
                if raw_stock_st in ("CRITICAL", "LOW_STOCK") or is_low:
                    raw_status = "Low Stock - Reorder Needed!"
                else:
                    raw_status = "In Stock"

            ing_id = row.get("ingredient_id", "")
            inventory_dict[ing_id] = {
                "item_name": row.get("ingredient_name", ""),
                "category": row.get("ingredient_category", ""),
                "current_stock": float(on_hand) if on_hand is not None else 0.0,
                "unit": row.get("unit", ""),
                "min_reorder_level": float(reorder) if reorder is not None else 0.0,
                "last_count_date": str(row.get("last_count_date", "")),
                "status": raw_status
            }

        return {
            "status": "success",
            "data": inventory_dict,
            "summary": {
                "total_items": len(rows),
                "low_stock_items_count": low_stock_count
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error fetching inventory: {str(e)}"
        }


def get_today_sales(date_str: Optional[str] = None, dataset_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool: get_today_sales

    Description:
        Retrieves sales metrics from completed orders for the current day
        (or latest recorded date in the database), including total revenue,
        order count, average order value, top-selling items, and payment breakdowns.

    Returns:
        Dict[str, Any]: Sales metrics for the target date.
    """
    if dataset_id:
        return get_dataset_sales(dataset_id=dataset_id, date_str=date_str)

    try:
        target_date = date_str
        if not target_date:
            # Check if there are completed orders for CURRENT_DATE
            today_check = execute_single(
                "SELECT COUNT(*) as count FROM orders WHERE order_date = CURRENT_DATE AND order_status = 'completed';"
            )
            if today_check and today_check.get("count", 0) > 0:
                target_date_row = execute_single("SELECT CURRENT_DATE::text as t_date;")
                target_date = target_date_row["t_date"] if target_date_row else None
            else:
                # Find most recent date with completed orders
                max_row = execute_single(
                    "SELECT MAX(order_date)::text as max_date FROM orders WHERE order_status = 'completed';"
                )
                target_date = max_row.get("max_date") if max_row else None

        if not target_date:
            return {
                "status": "success",
                "data": {
                    "date": "N/A",
                    "shift_status": "No completed orders found",
                    "summary": {
                        "total_orders": 0,
                        "total_revenue": 0.0,
                        "average_order_value": 0.0,
                        "busiest_hour": "N/A"
                    },
                    "top_selling_items": [],
                    "payment_breakdown": {}
                },
                "message": "No completed sales records found in database."
            }

        # 1. Summary Metrics
        summary_row = execute_single(
            """
            SELECT 
                COUNT(*) as total_orders,
                COALESCE(SUM(total_inr), 0) as total_revenue,
                COALESCE(AVG(total_inr), 0) as average_order_value
            FROM orders
            WHERE order_date = %s AND order_status = 'completed';
            """,
            (target_date,)
        )

        # 2. Busiest Hour
        busiest_row = execute_single(
            """
            SELECT 
                EXTRACT(HOUR FROM order_ts) as hour,
                COUNT(*) as order_count
            FROM orders
            WHERE order_date = %s AND order_status = 'completed'
            GROUP BY EXTRACT(HOUR FROM order_ts)
            ORDER BY order_count DESC
            LIMIT 1;
            """,
            (target_date,)
        )
        busiest_hour_str = "N/A"
        if busiest_row and busiest_row.get("hour") is not None:
            hr = int(busiest_row["hour"])
            busiest_hour_str = f"{hr:02d}:00 - {(hr+1):02d}:00"

        # 3. Top Selling Items
        top_items_rows = execute_query(
            """
            SELECT 
                mi.item_name as item,
                SUM(oi.quantity) as quantity_sold,
                SUM(oi.line_total_inr) as revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN menu_items mi ON oi.menu_item_id = mi.menu_item_id
            WHERE o.order_date = %s AND o.order_status = 'completed'
            GROUP BY mi.item_name
            ORDER BY quantity_sold DESC, revenue DESC
            LIMIT 5;
            """,
            (target_date,)
        )

        # 4. Payment Breakdown
        payment_rows = execute_query(
            """
            SELECT 
                p.payment_method,
                SUM(p.amount_inr) as total_amount
            FROM payments p
            JOIN orders o ON p.order_id = o.order_id
            WHERE o.order_date = %s AND p.payment_status = 'paid'
            GROUP BY p.payment_method;
            """,
            (target_date,)
        )
        payment_breakdown = {row["payment_method"]: row["total_amount"] for row in payment_rows}

        total_orders = summary_row.get("total_orders", 0) if summary_row else 0
        total_revenue = summary_row.get("total_revenue", 0.0) if summary_row else 0.0
        avg_order_value = summary_row.get("average_order_value", 0.0) if summary_row else 0.0

        return {
            "status": "success",
            "data": {
                "date": target_date,
                "shift_status": "Active / Historical Shift",
                "summary": {
                    "total_orders": total_orders,
                    "total_revenue": total_revenue,
                    "average_order_value": avg_order_value,
                    "busiest_hour": busiest_hour_str
                },
                "top_selling_items": top_items_rows,
                "payment_breakdown": payment_breakdown
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error fetching sales: {str(e)}"
        }


def get_menu(category: Optional[str] = None, dataset_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool: get_menu

    Description:
        Retrieves current cafe menu organized by categories,
        along with prices (in INR), descriptions, and dietary information from the database.

    Returns:
        Dict[str, Any]: Menu items categorized with pricing and dietary notes.
    """
    if dataset_id:
        return get_dataset_menu(dataset_id=dataset_id, category=category)

    try:
        if category:
            query = """
                SELECT 
                    mi.menu_item_id,
                    mi.item_name,
                    mi.category_id,
                    mc.category_name,
                    mi.list_price_inr,
                    mi.diet_type,
                    mi.is_available
                FROM menu_items mi
                JOIN menu_categories mc ON mi.category_id = mc.category_id
                WHERE LOWER(mc.category_name) = LOWER(%s)
                ORDER BY mc.category_name, mi.item_name;
            """
            rows = execute_query(query, (category,))
        else:
            query = """
                SELECT 
                    mi.menu_item_id,
                    mi.item_name,
                    mi.category_id,
                    mc.category_name,
                    mi.list_price_inr,
                    mi.diet_type,
                    mi.is_available
                FROM menu_items mi
                JOIN menu_categories mc ON mi.category_id = mc.category_id
                ORDER BY mc.category_name, mi.item_name;
            """
            rows = execute_query(query)

        if not rows:
            return {
                "status": "success",
                "data": {
                    "categories": [],
                    "total_items": 0
                },
                "message": "No menu items found in database."
            }

        categories_map: Dict[str, list] = {}
        for row in rows:
            cat = row["category_name"]
            if cat not in categories_map:
                categories_map[cat] = []
            categories_map[cat].append({
                "menu_item_id": row["menu_item_id"],
                "name": row["item_name"],
                "price": row["list_price_inr"],
                "dietary": [row["diet_type"]] if row.get("diet_type") else [],
                "description": f"{row.get('diet_type', '')} item priced at INR {row['list_price_inr']}",
                "is_available": row["is_available"]
            })

        categories = [{"category_name": cat, "items": items} for cat, items in categories_map.items()]

        return {
            "status": "success",
            "data": {
                "categories": categories,
                "total_items": len(rows)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error fetching menu: {str(e)}"
        }


def search_restaurant_knowledge_tool(
    query: str = "",
    top_k: int = 3,
    restaurant_id: str = "default_restaurant"
) -> Dict[str, Any]:
    """
    Tool: search_restaurant_knowledge

    Description:
        Searches restaurant standard operating procedures (SOP), employee policies, rules,
        hygiene guidelines, storage protocols, and operational manuals using Supabase pgvector semantic retrieval.
        Returns top relevant document chunks with source document citations and similarity metrics.

    Parameters:
        query (str): The natural language knowledge question or search phrase.
        top_k (int, optional): Number of relevant chunks to retrieve (1-10, default: 3).
        restaurant_id (str, optional): Restaurant / tenant identifier for isolated knowledge retrieval.

    Returns:
        Dict[str, Any]: Retrieved knowledge chunks, citations, document titles, and similarity scores.
    """
    if not query or not str(query).strip():
        return {
            "status": "error",
            "message": "Query parameter cannot be empty."
        }

    try:
        from rag.retrieval import search_restaurant_knowledge
        return search_restaurant_knowledge(str(query).strip(), top_k=top_k, restaurant_id=restaurant_id)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to retrieve restaurant knowledge: {str(e)}"
        }


def search_cafe_knowledge(query: str = "") -> Dict[str, Any]:
    """
    Tool: search_cafe_knowledge

    Description:
        Searches cafe standard operating procedures (SOP), employee policies, rules,
        hygiene guidelines, storage protocols, and operational manuals using Supabase pgvector retrieval.
        Returns the top relevant document chunks without generating the final answer.

    Parameters:
        query (str): The natural language knowledge question or search phrase.

    Returns:
        Dict[str, Any]: Retrieved knowledge chunks relevant to the query with citations.
    """
    return search_restaurant_knowledge_tool(query=query, top_k=3)



def get_sales_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channel: Optional[str] = None,
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_sales_performance

    Description:
        Retrieves comprehensive sales totals, revenue (total, subtotal, tax, service charges),
        order status counts (completed, cancelled, refunded), average order value (AOV),
        channel performance breakdown, and discount impact over a specified date range.

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        channel (str, optional): Filter by channel ('dine_in', 'takeaway', 'delivery').
        dataset_id (str, optional): Scopes query to uploaded dataset records.

    Returns:
        Dict[str, Any]: Detailed sales metrics, channel breakdowns, discount metrics, and metadata.
    """
    if dataset_id:
        return get_dataset_sales(dataset_id=dataset_id)

    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        # 1. Summary Query
        params: List[Any] = [start_clean, end_clean]
        channel_filter_sql = ""
        if channel and channel.strip():
            channel_filter_sql = " AND channel = %s"
            params.append(channel.strip().lower())

        summary_sql = f"""
            SELECT 
                COUNT(*) FILTER (WHERE order_status = 'completed') as completed_orders,
                COUNT(*) FILTER (WHERE order_status = 'cancelled') as cancelled_orders,
                COUNT(*) FILTER (WHERE order_status = 'refunded') as refunded_orders,
                COUNT(*) as total_orders,
                COALESCE(SUM(total_inr) FILTER (WHERE order_status = 'completed'), 0) as total_revenue,
                COALESCE(SUM(subtotal_inr) FILTER (WHERE order_status = 'completed'), 0) as subtotal,
                COALESCE(SUM(tax_inr) FILTER (WHERE order_status = 'completed'), 0) as tax,
                COALESCE(SUM(service_charge_inr) FILTER (WHERE order_status = 'completed'), 0) as service_charge,
                COALESCE(AVG(total_inr) FILTER (WHERE order_status = 'completed'), 0) as average_order_value
            FROM orders
            WHERE order_date >= %s AND order_date <= %s{channel_filter_sql};
        """
        summary = execute_single(summary_sql, tuple(params)) or {}

        # 2. Channel Performance Breakdown
        channel_sql = f"""
            SELECT 
                channel,
                COUNT(*) as order_count,
                COALESCE(SUM(total_inr), 0) as revenue,
                COALESCE(AVG(total_inr), 0) as average_order_value
            FROM orders
            WHERE order_date >= %s AND order_date <= %s AND order_status = 'completed'{channel_filter_sql}
            GROUP BY channel
            ORDER BY revenue DESC;
        """
        channel_rows = execute_query(channel_sql, tuple(params))

        total_rev = summary.get("total_revenue", 0.0)
        channel_breakdown = []
        for ch in channel_rows:
            ch_rev = ch.get("revenue", 0.0)
            pct = round((ch_rev / total_rev * 100), 2) if total_rev > 0 else 0.0
            channel_breakdown.append({
                "channel": ch["channel"],
                "order_count": ch["order_count"],
                "revenue_inr": ch_rev,
                "average_order_value_inr": round(ch["average_order_value"], 2),
                "revenue_percentage": pct
            })

        # 3. Discount Impact from Order Items
        discount_params: List[Any] = [start_clean, end_clean]
        discount_ch_filter = ""
        if channel and channel.strip():
            discount_ch_filter = " AND o.channel = %s"
            discount_params.append(channel.strip().lower())

        discount_sql = f"""
            SELECT 
                COUNT(oi.order_item_id) as total_items_sold,
                COUNT(oi.order_item_id) FILTER (WHERE oi.discount_inr > 0) as discounted_items_count,
                COALESCE(SUM(oi.discount_inr), 0) as total_discount_given,
                COALESCE(SUM(oi.line_total_inr), 0) as total_item_revenue
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.order_date >= %s AND o.order_date <= %s AND o.order_status = 'completed'{discount_ch_filter};
        """
        discount_row = execute_single(discount_sql, tuple(discount_params)) or {}

        completed_cnt = summary.get("completed_orders", 0)
        tot_discount = discount_row.get("total_discount_given", 0.0)
        avg_disc_per_order = round(tot_discount / completed_cnt, 2) if completed_cnt > 0 else 0.0

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "channel_filter": channel or "all",
                "summary": {
                    "completed_orders": summary.get("completed_orders", 0),
                    "cancelled_orders": summary.get("cancelled_orders", 0),
                    "refunded_orders": summary.get("refunded_orders", 0),
                    "total_orders": summary.get("total_orders", 0),
                    "total_revenue_inr": round(summary.get("total_revenue", 0.0), 2),
                    "subtotal_inr": round(summary.get("subtotal", 0.0), 2),
                    "tax_inr": round(summary.get("tax", 0.0), 2),
                    "service_charge_inr": round(summary.get("service_charge", 0.0), 2),
                    "average_order_value_inr": round(summary.get("average_order_value", 0.0), 2),
                    "gross_billed_revenue_inr": round(summary.get("total_revenue", 0.0), 2),
                    "aov_denominator": "completed_orders"
                },
                "channel_breakdown": channel_breakdown,
                "discount_impact": {
                    "total_items_sold": discount_row.get("total_items_sold", 0),
                    "discounted_items_count": discount_row.get("discounted_items_count", 0),
                    "total_discount_given_inr": round(tot_discount, 2),
                    "average_discount_per_order_inr": avg_disc_per_order,
                    "discount_applied_status": "already_deducted_from_subtotal"
                },
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_sales_performance: {str(e)}"}


def get_top_selling_items(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5,
    sort_by: str = "quantity",
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_top_selling_items

    Description:
        Retrieves top-performing menu items ranked by quantity sold or revenue earned
        over a specified date range. Includes category classification and discount metrics.

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        limit (int, optional): Number of top items to return (1-50, default: 5).
        sort_by (str, optional): Rank by 'quantity' or 'revenue' (default: 'quantity').
        category (str, optional): Optional menu category name filter.

    Returns:
        Dict[str, Any]: Ranked list of menu items with quantities, revenue, and list prices.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    # Validate sort_by
    clean_sort = sort_by.strip().lower()
    if clean_sort == "revenue":
        order_clause = "total_revenue DESC, total_quantity DESC, mi.item_name ASC"
    else:
        order_clause = "total_quantity DESC, total_revenue DESC, mi.item_name ASC"

    # Clamp limit
    clamped_limit = max(1, min(int(limit), 50))

    try:
        params: List[Any] = [start_clean, end_clean]
        cat_filter = ""
        if category and category.strip():
            cat_filter = " AND LOWER(mc.category_name) = LOWER(%s)"
            params.append(category.strip())
        params.append(clamped_limit)

        sql = f"""
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                mi.list_price_inr,
                COALESCE(SUM(oi.quantity), 0) as total_quantity,
                COALESCE(SUM(oi.line_total_inr), 0) as total_revenue,
                COALESCE(SUM(oi.discount_inr), 0) as total_discount,
                COUNT(DISTINCT o.order_id) as order_appearances
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            JOIN menu_items mi ON oi.menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE o.order_date >= %s AND o.order_date <= %s AND o.order_status = 'completed'{cat_filter}
            GROUP BY mi.menu_item_id, mi.item_name, mc.category_name, mi.list_price_inr
            ORDER BY {order_clause}
            LIMIT %s;
        """
        rows = execute_query(sql, tuple(params))

        items = []
        for r in rows:
            items.append({
                "menu_item_id": r["menu_item_id"],
                "item_name": r["item_name"],
                "category_name": r["category_name"],
                "list_price_inr": r["list_price_inr"],
                "quantity_sold": r["total_quantity"],
                "revenue_inr": round(r["total_revenue"], 2),
                "discount_inr": round(r["total_discount"], 2),
                "order_appearances": r["order_appearances"]
            })

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "ranked_by": sort_by.strip().lower(),
                "category_filter": category or "all",
                "total_items_returned": len(items),
                "top_items": items,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_top_selling_items: {str(e)}"}


def get_sales_trends_and_comparison(
    period_type: str = "7_days",
    end_date: Optional[str] = None,
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_sales_trends_and_comparison

    Description:
        Analyzes sales trends and performs period-over-period comparison (e.g. current 7 days
        vs immediately preceding 7 days, or custom date ranges). Computes absolute and percentage
        deltas for revenue, order volume, and average order value, along with daily time-series data.

    Parameters:
        period_type (str, optional): '7_days', '14_days', '30_days', or 'custom'. Default is '7_days'.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        start_date (str, optional): ISO date string for custom period start.

    Returns:
        Dict[str, Any]: Current period metrics, prior period metrics, delta comparisons, and daily breakdown.
    """
    # Determine days duration
    days_map = {"7_days": 7, "14_days": 14, "30_days": 30}
    num_days = days_map.get(period_type.lower(), 7)

    try:
        if start_date and end_date:
            curr_start, curr_end = _resolve_date_range(start_date, end_date)
            start_dt = datetime.strptime(curr_start, "%Y-%m-%d").date()
            end_dt = datetime.strptime(curr_end, "%Y-%m-%d").date()
            duration_days = (end_dt - start_dt).days + 1
        else:
            curr_start, curr_end = _resolve_date_range(end_date=end_date, default_days=num_days)
            duration_days = num_days

        curr_start_dt = datetime.strptime(curr_start, "%Y-%m-%d").date()
        prev_end_dt = curr_start_dt - timedelta(days=1)
        prev_start_dt = prev_end_dt - timedelta(days=duration_days - 1)
        prev_start = prev_start_dt.isoformat()
        prev_end = prev_end_dt.isoformat()
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        # Metrics helper query
        def _get_metrics(p_start: str, p_end: str) -> Dict[str, Any]:
            sql = """
                SELECT 
                    COUNT(*) as completed_orders,
                    COALESCE(SUM(total_inr), 0) as total_revenue,
                    COALESCE(AVG(total_inr), 0) as average_order_value
                FROM orders
                WHERE order_date >= %s AND order_date <= %s AND order_status = 'completed';
            """
            row = execute_single(sql, (p_start, p_end)) or {}
            return {
                "orders": row.get("completed_orders", 0),
                "revenue": round(row.get("total_revenue", 0.0), 2),
                "aov": round(row.get("average_order_value", 0.0), 2)
            }

        current_metrics = _get_metrics(curr_start, curr_end)
        prior_metrics = _get_metrics(prev_start, prev_end)

        # Delta calculations
        rev_delta = round(current_metrics["revenue"] - prior_metrics["revenue"], 2)
        orders_delta = current_metrics["orders"] - prior_metrics["orders"]
        aov_delta = round(current_metrics["aov"] - prior_metrics["aov"], 2)

        rev_growth_pct = round((rev_delta / prior_metrics["revenue"] * 100), 2) if prior_metrics["revenue"] > 0 else 0.0
        orders_growth_pct = round((orders_delta / prior_metrics["orders"] * 100), 2) if prior_metrics["orders"] > 0 else 0.0

        # Daily Trends for Current Period
        daily_sql = """
            SELECT 
                order_date::text as date,
                COUNT(*) as order_count,
                COALESCE(SUM(total_inr), 0) as revenue,
                COALESCE(AVG(total_inr), 0) as average_order_value
            FROM orders
            WHERE order_date >= %s AND order_date <= %s AND order_status = 'completed'
            GROUP BY order_date
            ORDER BY order_date ASC;
        """
        daily_rows = execute_query(daily_sql, (curr_start, curr_end))
        daily_trends = [
            {
                "date": r["date"],
                "order_count": r["order_count"],
                "revenue_inr": round(r["revenue"], 2),
                "average_order_value_inr": round(r["average_order_value"], 2)
            }
            for r in daily_rows
        ]

        return {
            "status": "success",
            "data": {
                "period_type": period_type,
                "current_period": {
                    "start_date": curr_start,
                    "end_date": curr_end,
                    "total_revenue_inr": current_metrics["revenue"],
                    "total_orders": current_metrics["orders"],
                    "average_order_value_inr": current_metrics["aov"]
                },
                "previous_period": {
                    "start_date": prev_start,
                    "end_date": prev_end,
                    "total_revenue_inr": prior_metrics["revenue"],
                    "total_orders": prior_metrics["orders"],
                    "average_order_value_inr": prior_metrics["aov"]
                },
                "comparison_growth": {
                    "revenue_change_inr": rev_delta,
                    "revenue_growth_percentage": rev_growth_pct,
                    "orders_change": orders_delta,
                    "orders_growth_percentage": orders_growth_pct,
                    "aov_change_inr": aov_delta
                },
                "daily_trends": daily_trends,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_sales_trends_and_comparison: {str(e)}"}


def get_peak_hours_and_dayparts(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_peak_hours_and_dayparts

    Description:
        Analyzes order timestamps to determine peak hourly order volume and revenue,
        and aggregates demand across standardized dayparts (Morning, Lunch, Evening, Late Night).

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.

    Returns:
        Dict[str, Any]: Hourly volume distribution, daypart summaries, and identified peak operating hours.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        sql = """
            SELECT 
                EXTRACT(HOUR FROM order_ts)::int as hour,
                COUNT(*) as order_count,
                COALESCE(SUM(total_inr), 0) as total_revenue
            FROM orders
            WHERE order_date >= %s AND order_date <= %s AND order_status = 'completed'
            GROUP BY EXTRACT(HOUR FROM order_ts)
            ORDER BY hour ASC;
        """
        rows = execute_query(sql, (start_clean, end_clean))

        # Standard daypart categorization
        dayparts = {
            "Morning (06:00 - 11:59)": {"order_count": 0, "revenue_inr": 0.0},
            "Lunch / Afternoon (12:00 - 16:59)": {"order_count": 0, "revenue_inr": 0.0},
            "Evening / Dinner (17:00 - 22:59)": {"order_count": 0, "revenue_inr": 0.0},
            "Late Night / Early Morning (23:00 - 05:59)": {"order_count": 0, "revenue_inr": 0.0}
        }

        hourly_distribution = []
        busiest_hour_data = None
        max_orders = -1

        for r in rows:
            hr = r["hour"]
            orders = r["order_count"]
            rev = round(r["total_revenue"], 2)
            time_window = f"{hr:02d}:00 - {(hr+1):02d}:00"

            hourly_distribution.append({
                "hour": hr,
                "time_window": time_window,
                "order_count": orders,
                "revenue_inr": rev
            })

            if orders > max_orders:
                max_orders = orders
                busiest_hour_data = {
                    "hour": hr,
                    "time_window": time_window,
                    "order_count": orders,
                    "revenue_inr": rev
                }

            # Map to daypart
            if 6 <= hr < 12:
                dayparts["Morning (06:00 - 11:59)"]["order_count"] += orders
                dayparts["Morning (06:00 - 11:59)"]["revenue_inr"] += rev
            elif 12 <= hr < 17:
                dayparts["Lunch / Afternoon (12:00 - 16:59)"]["order_count"] += orders
                dayparts["Lunch / Afternoon (12:00 - 16:59)"]["revenue_inr"] += rev
            elif 17 <= hr < 23:
                dayparts["Evening / Dinner (17:00 - 22:59)"]["order_count"] += orders
                dayparts["Evening / Dinner (17:00 - 22:59)"]["revenue_inr"] += rev
            else:
                dayparts["Late Night / Early Morning (23:00 - 05:59)"]["order_count"] += orders
                dayparts["Late Night / Early Morning (23:00 - 05:59)"]["revenue_inr"] += rev

        # Format dayparts summary
        daypart_summary = [
            {
                "daypart": name,
                "order_count": data["order_count"],
                "revenue_inr": round(data["revenue_inr"], 2)
            }
            for name, data in dayparts.items()
        ]

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "busiest_hour": busiest_hour_data or {"time_window": "N/A", "order_count": 0, "revenue_inr": 0.0},
                "daypart_summary": daypart_summary,
                "hourly_distribution": hourly_distribution,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_peak_hours_and_dayparts: {str(e)}"}


def get_payment_methods_breakdown(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_payment_methods_breakdown

    Description:
        Retrieves payment distribution (UPI, Card, Cash, Wallet) for completed orders,
        including transaction counts, total amounts, refunds, and percentage shares.

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.

    Returns:
        Dict[str, Any]: Payment breakdown by method with percentages and refund statistics.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        sql = """
            SELECT 
                p.payment_method,
                COUNT(*) as transaction_count,
                COALESCE(SUM(p.amount_inr), 0) as total_amount,
                COALESCE(SUM(p.refund_amount_inr), 0) as total_refunded
            FROM payments p
            JOIN orders o ON p.order_id = o.order_id
            WHERE o.order_date >= %s AND o.order_date <= %s AND p.payment_status = 'paid'
            GROUP BY p.payment_method
            ORDER BY total_amount DESC;
        """
        rows = execute_query(sql, (start_clean, end_clean))

        total_paid = sum(r["total_amount"] for r in rows)
        methods = []
        for r in rows:
            amt = round(r["total_amount"], 2)
            pct = round((amt / total_paid * 100), 2) if total_paid > 0 else 0.0
            methods.append({
                "payment_method": r["payment_method"],
                "transaction_count": r["transaction_count"],
                "total_amount_inr": amt,
                "total_refunded_inr": round(r["total_refunded"], 2),
                "percentage_share": pct
            })

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "total_settled_amount_inr": round(total_paid, 2),
                "methods": methods,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_payment_methods_breakdown: {str(e)}"}


def get_menu_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = "quantity",
    ascending: bool = False,
    limit: int = 50,
    include_zero_sales: bool = True
) -> Dict[str, Any]:
    """
    Tool: get_menu_performance

    Description:
        Retrieves comprehensive performance metrics for menu items over a date range,
        including units sold, total revenue, discount impact, average realized price,
        order appearances, dietary type, and availability status. Supports ranking
        best and worst performers and identifying zero-sales items.

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        category (str, optional): Filter by category name (e.g. 'Beverages', 'Starters').
        sort_by (str, optional): Metric to sort by ('quantity', 'revenue', 'price', 'discount'). Default: 'quantity'.
        ascending (bool, optional): True for ascending order (worst/lowest first), False for descending (best first).
        limit (int, optional): Maximum items to return (1-100, default: 50).
        include_zero_sales (bool, optional): Whether to include items with 0 sales in the period (default: True).

    Returns:
        Dict[str, Any]: Ranked menu performance metrics, summary statistics, and items to investigate.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    clean_sort = sort_by.strip().lower()
    direction = "ASC" if ascending else "DESC"

    # Deterministic allowlisted ordering
    if clean_sort == "quantity":
        order_clause = f"total_quantity_sold {direction}, total_revenue_inr DESC, mi.item_name ASC"
    elif clean_sort == "revenue":
        order_clause = f"total_revenue_inr {direction}, total_quantity_sold DESC, mi.item_name ASC"
    elif clean_sort == "price":
        order_clause = f"mi.list_price_inr {direction}, total_revenue_inr DESC, mi.item_name ASC"
    elif clean_sort == "discount":
        order_clause = f"total_discount_inr {direction}, total_quantity_sold DESC, mi.item_name ASC"
    else:
        order_clause = f"total_quantity_sold {direction}, total_revenue_inr DESC, mi.item_name ASC"

    clamped_limit = max(1, min(int(limit), 100))

    try:
        params: List[Any] = [start_clean, end_clean]
        cat_filter = ""
        if category and category.strip():
            cat_filter = " WHERE LOWER(mc.category_name) = LOWER(%s)"
            params.append(category.strip())

        having_clause = ""
        if not include_zero_sales:
            having_clause = " HAVING COALESCE(SUM(sales.quantity), 0) > 0"

        params.append(clamped_limit)

        sql = f"""
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                mi.list_price_inr,
                mi.diet_type,
                mi.is_available,
                COALESCE(SUM(sales.quantity), 0)::int as total_quantity_sold,
                COALESCE(SUM(sales.line_total_inr), 0) as total_revenue_inr,
                COALESCE(SUM(sales.discount_inr), 0) as total_discount_inr,
                COUNT(DISTINCT sales.order_id) as order_appearances
            FROM menu_items mi
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            LEFT JOIN (
                SELECT 
                    oi.menu_item_id,
                    oi.quantity,
                    oi.line_total_inr,
                    oi.discount_inr,
                    o.order_id
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE o.order_date >= %s AND o.order_date <= %s AND o.order_status = 'completed'
            ) sales ON mi.menu_item_id = sales.menu_item_id
            {cat_filter}
            GROUP BY mi.menu_item_id, mi.item_name, mc.category_name, mi.list_price_inr, mi.diet_type, mi.is_available
            {having_clause}
            ORDER BY {order_clause}
            LIMIT %s;
        """
        rows = execute_query(sql, tuple(params))

        items = []
        zero_sales_items = []
        total_period_revenue = 0.0
        total_units_sold = 0

        for idx, r in enumerate(rows, 1):
            qty = r["total_quantity_sold"]
            rev = round(float(r["total_revenue_inr"]), 2)
            disc = round(float(r["total_discount_inr"]), 2)
            list_price = round(float(r["list_price_inr"]), 2)
            avg_realized_price = round(rev / qty, 2) if qty > 0 else list_price

            total_period_revenue += rev
            total_units_sold += qty

            item_data = {
                "rank": idx,
                "menu_item_id": r["menu_item_id"],
                "item_name": r["item_name"],
                "category_name": r["category_name"],
                "list_price_inr": list_price,
                "average_realized_price_inr": avg_realized_price,
                "diet_type": r["diet_type"],
                "is_available": r["is_available"],
                "quantity_sold": qty,
                "revenue_inr": rev,
                "discount_inr": disc,
                "order_appearances": r["order_appearances"]
            }
            items.append(item_data)
            if qty == 0:
                zero_sales_items.append({
                    "item_name": r["item_name"],
                    "category_name": r["category_name"],
                    "list_price_inr": list_price,
                    "is_available": r["is_available"]
                })

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "category_filter": category or "all",
                "sorted_by": sort_by.strip().lower(),
                "order_direction": "ascending (lowest/worst first)" if ascending else "descending (highest/best first)",
                "summary": {
                    "total_menu_items_analyzed": len(items),
                    "total_units_sold": total_units_sold,
                    "total_revenue_inr": round(total_period_revenue, 2),
                    "zero_sales_items_count": len(zero_sales_items)
                },
                "items": items,
                "zero_sales_items": zero_sales_items,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_menu_performance: {str(e)}"}


def get_category_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_category_performance

    Description:
        Compares all menu categories by total menu item count, active item count,
        total units sold, total revenue in INR, percentage share of total menu revenue,
        and identifies the top-performing item within each category over a specified date range.

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.

    Returns:
        Dict[str, Any]: Category breakdown with volume, revenue, revenue share, and top item.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        # 1. Aggregate metrics per category
        sql = """
            SELECT 
                mc.category_id,
                mc.category_name,
                COUNT(DISTINCT mi.menu_item_id) as total_items,
                COUNT(DISTINCT mi.menu_item_id) FILTER (WHERE mi.is_available = true) as active_items,
                COALESCE(SUM(sales.quantity), 0)::int as total_quantity_sold,
                COALESCE(SUM(sales.line_total_inr), 0) as total_revenue_inr,
                COALESCE(SUM(sales.discount_inr), 0) as total_discount_inr,
                COALESCE(AVG(mi.list_price_inr), 0) as average_item_price_inr
            FROM menu_categories mc
            LEFT JOIN menu_items mi ON mc.category_id = mi.category_id
            LEFT JOIN (
                SELECT 
                    oi.menu_item_id,
                    oi.quantity,
                    oi.line_total_inr,
                    oi.discount_inr
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE o.order_date >= %s AND o.order_date <= %s AND o.order_status = 'completed'
            ) sales ON mi.menu_item_id = sales.menu_item_id
            GROUP BY mc.category_id, mc.category_name
            ORDER BY total_revenue_inr DESC, total_quantity_sold DESC;
        """
        rows = execute_query(sql, (start_clean, end_clean))

        # 2. Get top-selling item per category
        top_item_sql = """
            SELECT DISTINCT ON (mc.category_id)
                mc.category_id,
                mi.item_name as top_item_name,
                COALESCE(SUM(oi.quantity), 0)::int as item_quantity,
                COALESCE(SUM(oi.line_total_inr), 0) as item_revenue
            FROM menu_categories mc
            JOIN menu_items mi ON mc.category_id = mi.category_id
            LEFT JOIN order_items oi ON mi.menu_item_id = oi.menu_item_id
            LEFT JOIN orders o ON oi.order_id = o.order_id 
                AND o.order_date >= %s AND o.order_date <= %s AND o.order_status = 'completed'
            GROUP BY mc.category_id, mi.menu_item_id, mi.item_name
            ORDER BY mc.category_id, item_quantity DESC, item_revenue DESC;
        """
        top_rows = execute_query(top_item_sql, (start_clean, end_clean))
        top_item_map = {
            r["category_id"]: {
                "name": r["top_item_name"],
                "quantity_sold": r["item_quantity"],
                "revenue_inr": round(float(r["item_revenue"]), 2)
            }
            for r in top_rows
        }

        total_menu_revenue = sum(float(r["total_revenue_inr"]) for r in rows)
        categories = []

        for r in rows:
            cat_id = r["category_id"]
            rev = round(float(r["total_revenue_inr"]), 2)
            share_pct = round((rev / total_menu_revenue * 100), 2) if total_menu_revenue > 0 else 0.0

            top_item = top_item_map.get(cat_id, {"name": "None", "quantity_sold": 0, "revenue_inr": 0.0})

            categories.append({
                "category_id": cat_id,
                "category_name": r["category_name"],
                "total_items": r["total_items"],
                "active_items": r["active_items"],
                "quantity_sold": r["total_quantity_sold"],
                "revenue_inr": rev,
                "discount_inr": round(float(r["total_discount_inr"]), 2),
                "average_item_price_inr": round(float(r["average_item_price_inr"]), 2),
                "revenue_share_percentage": share_pct,
                "top_performing_item": top_item
            })

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "total_categories": len(categories),
                "total_revenue_inr": round(total_menu_revenue, 2),
                "categories": categories,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_category_performance: {str(e)}"}


def get_menu_item_comparison(
    item_names: Optional[List[str]] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_menu_item_comparison

    Description:
        Provides a direct side-by-side performance and pricing comparison for specific
        menu items (or all items in a specific category) over a date range.
        Includes list price, realized avg price, quantity sold, total revenue, discount impact,
        dietary info, recipe ingredients (if available), and availability status.

    Parameters:
        item_names (list of str, optional): Specific item names to compare (e.g. ['Butter Chicken', 'Masala Dosa']).
        category (str, optional): Optional category name to compare all items within that category.
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 7 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.

    Returns:
        Dict[str, Any]: Detailed comparison table and individual item breakdowns.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=7)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        params: List[Any] = [start_clean, end_clean]
        filters = []

        if item_names and len(item_names) > 0:
            placeholders = ", ".join(["LOWER(%s)"] * len(item_names))
            filters.append(f"LOWER(mi.item_name) IN ({placeholders})")
            for name in item_names:
                params.append(str(name).strip())
        elif category and category.strip():
            filters.append("LOWER(mc.category_name) = LOWER(%s)")
            params.append(category.strip())

        where_clause = ""
        if filters:
            where_clause = " WHERE " + " AND ".join(filters)

        sql = f"""
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                mi.list_price_inr,
                mi.diet_type,
                mi.is_available,
                mi.created_at as item_added_date,
                COALESCE(SUM(sales.quantity), 0)::int as total_quantity_sold,
                COALESCE(SUM(sales.line_total_inr), 0) as total_revenue_inr,
                COALESCE(SUM(sales.discount_inr), 0) as total_discount_inr,
                COUNT(DISTINCT sales.order_id) as order_appearances
            FROM menu_items mi
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            LEFT JOIN (
                SELECT 
                    oi.menu_item_id,
                    oi.quantity,
                    oi.line_total_inr,
                    oi.discount_inr,
                    o.order_id
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE o.order_date >= %s AND o.order_date <= %s AND o.order_status = 'completed'
            ) sales ON mi.menu_item_id = sales.menu_item_id
            {where_clause}
            GROUP BY mi.menu_item_id, mi.item_name, mc.category_name, mi.list_price_inr, mi.diet_type, mi.is_available, mi.created_at
            ORDER BY total_revenue_inr DESC, total_quantity_sold DESC;
        """
        rows = execute_query(sql, tuple(params))

        if not rows:
            return {
                "status": "success",
                "data": {
                    "period_start": start_clean,
                    "period_end": end_clean,
                    "compared_items": [],
                    "message": "No matching menu items found for comparison."
                }
            }

        # Fetch recipes for these items if available
        menu_item_ids = [r["menu_item_id"] for r in rows]
        recipe_map: Dict[str, list] = {}
        if menu_item_ids:
            recipe_placeholders = ", ".join(["%s"] * len(menu_item_ids))
            recipe_sql = f"""
                SELECT 
                    mr.menu_item_id,
                    ing.ingredient_name,
                    mr.quantity_per_portion,
                    mr.unit
                FROM menu_recipes mr
                JOIN ingredients ing ON mr.ingredient_id = ing.ingredient_id
                WHERE mr.menu_item_id IN ({recipe_placeholders});
            """
            recipe_rows = execute_query(recipe_sql, tuple(menu_item_ids))
            for rr in recipe_rows:
                m_id = rr["menu_item_id"]
                if m_id not in recipe_map:
                    recipe_map[m_id] = []
                recipe_map[m_id].append({
                    "ingredient": rr["ingredient_name"],
                    "portion": float(rr["quantity_per_portion"]),
                    "unit": rr["unit"]
                })

        compared_items = []
        for r in rows:
            m_id = r["menu_item_id"]
            qty = r["total_quantity_sold"]
            rev = round(float(r["total_revenue_inr"]), 2)
            disc = round(float(r["total_discount_inr"]), 2)
            list_price = round(float(r["list_price_inr"]), 2)
            avg_realized = round(rev / qty, 2) if qty > 0 else list_price

            compared_items.append({
                "menu_item_id": m_id,
                "item_name": r["item_name"],
                "category_name": r["category_name"],
                "list_price_inr": list_price,
                "average_realized_price_inr": avg_realized,
                "diet_type": r["diet_type"],
                "is_available": r["is_available"],
                "quantity_sold": qty,
                "revenue_inr": rev,
                "discount_inr": disc,
                "order_appearances": r["order_appearances"],
                "recipe_ingredients": recipe_map.get(m_id, []),
                "item_added_date": str(r["item_added_date"])
            })

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "items_count": len(compared_items),
                "compared_items": compared_items,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_menu_item_comparison: {str(e)}"}


def get_feedback_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    menu_item_name: Optional[str] = None,
    category: Optional[str] = None,
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_feedback_overview

    Description:
        Retrieves comprehensive customer review statistics over a date range,
        including total review count, average rating (out of 5), rating distribution (1 to 5 stars),
        sentiment breakdown (positive, neutral, negative), and complaint / issue categories breakdown.

    Parameters:
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 30 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        menu_item_name (str, optional): Filter feedback for a specific menu item name.
        category (str, optional): Filter feedback for items within a menu category.
        dataset_id (str, optional): Scopes query to uploaded dataset records.

    Returns:
        Dict[str, Any]: Summary metrics, rating distribution, sentiment share, and issue categories.
    """
    if dataset_id:
        return get_dataset_reviews(dataset_id=dataset_id, menu_item_name=menu_item_name)

    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=30)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        params: List[Any] = [start_clean, end_clean]
        filters = []

        if menu_item_name and menu_item_name.strip():
            filters.append("LOWER(mi.item_name) = LOWER(%s)")
            params.append(menu_item_name.strip())
        if category and category.strip():
            filters.append("LOWER(mc.category_name) = LOWER(%s)")
            params.append(category.strip())

        where_filter = ""
        if filters:
            where_filter = " AND " + " AND ".join(filters)

        # 1. Summary & Distribution Query
        summary_sql = f"""
            SELECT 
                COUNT(r.review_id) as total_reviews,
                COALESCE(AVG(r.rating), 0) as average_rating,
                COUNT(r.review_id) FILTER (WHERE r.rating = 5) as rating_5_count,
                COUNT(r.review_id) FILTER (WHERE r.rating = 4) as rating_4_count,
                COUNT(r.review_id) FILTER (WHERE r.rating = 3) as rating_3_count,
                COUNT(r.review_id) FILTER (WHERE r.rating = 2) as rating_2_count,
                COUNT(r.review_id) FILTER (WHERE r.rating = 1) as rating_1_count,
                COUNT(r.review_id) FILTER (WHERE r.sentiment_label = 'positive') as positive_count,
                COUNT(r.review_id) FILTER (WHERE r.sentiment_label = 'neutral') as neutral_count,
                COUNT(r.review_id) FILTER (WHERE r.sentiment_label = 'negative') as negative_count
            FROM reviews r
            JOIN menu_items mi ON r.reviewed_menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE r.review_date >= %s AND r.review_date <= %s{where_filter};
        """
        summary_row = execute_single(summary_sql, tuple(params)) or {}

        total_revs = summary_row.get("total_reviews", 0)
        avg_rating = round(float(summary_row.get("average_rating", 0.0)), 2)

        # 2. Issue Categories Breakdown
        issue_sql = f"""
            SELECT 
                r.issue_category,
                COUNT(r.review_id) as issue_count
            FROM reviews r
            JOIN menu_items mi ON r.reviewed_menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE r.review_date >= %s AND r.review_date <= %s{where_filter}
            GROUP BY r.issue_category
            ORDER BY issue_count DESC;
        """
        issue_rows = execute_query(issue_sql, tuple(params))
        issue_breakdown = []
        for ir in issue_rows:
            cnt = ir["issue_count"]
            pct = round((cnt / total_revs * 100), 2) if total_revs > 0 else 0.0
            issue_breakdown.append({
                "issue_category": ir["issue_category"],
                "count": cnt,
                "percentage_of_reviews": pct
            })

        pos_cnt = summary_row.get("positive_count", 0)
        neu_cnt = summary_row.get("neutral_count", 0)
        neg_cnt = summary_row.get("negative_count", 0)

        pos_pct = round((pos_cnt / total_revs * 100), 2) if total_revs > 0 else 0.0
        neu_pct = round((neu_cnt / total_revs * 100), 2) if total_revs > 0 else 0.0
        neg_pct = round((neg_cnt / total_revs * 100), 2) if total_revs > 0 else 0.0

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "item_filter": menu_item_name or "all",
                "category_filter": category or "all",
                "summary": {
                    "total_reviews": total_revs,
                    "average_rating": avg_rating,
                    "positive_sentiment_percentage": pos_pct,
                    "neutral_sentiment_percentage": neu_pct,
                    "negative_sentiment_percentage": neg_pct
                },
                "rating_distribution": {
                    "5_star": {"count": summary_row.get("rating_5_count", 0), "percentage": round((summary_row.get("rating_5_count", 0) / total_revs * 100), 2) if total_revs > 0 else 0.0},
                    "4_star": {"count": summary_row.get("rating_4_count", 0), "percentage": round((summary_row.get("rating_4_count", 0) / total_revs * 100), 2) if total_revs > 0 else 0.0},
                    "3_star": {"count": summary_row.get("rating_3_count", 0), "percentage": round((summary_row.get("rating_3_count", 0) / total_revs * 100), 2) if total_revs > 0 else 0.0},
                    "2_star": {"count": summary_row.get("rating_2_count", 0), "percentage": round((summary_row.get("rating_2_count", 0) / total_revs * 100), 2) if total_revs > 0 else 0.0},
                    "1_star": {"count": summary_row.get("rating_1_count", 0), "percentage": round((summary_row.get("rating_1_count", 0) / total_revs * 100), 2) if total_revs > 0 else 0.0}
                },
                "sentiment_counts": {
                    "positive": pos_cnt,
                    "neutral": neu_cnt,
                    "negative": neg_cnt
                },
                "issue_breakdown": issue_breakdown,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_feedback_overview: {str(e)}"}


def get_item_reviews_summary(
    menu_item_name: Optional[str] = None,
    category: Optional[str] = None,
    sentiment: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Tool: get_item_reviews_summary

    Description:
        Retrieves item-specific feedback aggregations (review count, average rating, positive/negative count, top issues)
        and recent review text samples (anonymized, strictly omitting customer identifiers).

    Parameters:
        menu_item_name (str, optional): Filter for a specific menu item name.
        category (str, optional): Filter by category name.
        sentiment (str, optional): Filter reviews by sentiment ('positive', 'neutral', 'negative').
        start_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to 30 days before end_date.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        limit (int, optional): Maximum sample reviews to return (1-50, default: 10).

    Returns:
        Dict[str, Any]: Item ratings summary, praised items, items with complaints, and anonymized review samples.
    """
    try:
        start_clean, end_clean = _resolve_date_range(start_date, end_date, default_days=30)
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    clamped_limit = max(1, min(int(limit), 50))

    try:
        params: List[Any] = [start_clean, end_clean]
        filters = []

        if menu_item_name and menu_item_name.strip():
            filters.append("LOWER(mi.item_name) = LOWER(%s)")
            params.append(menu_item_name.strip())
        if category and category.strip():
            filters.append("LOWER(mc.category_name) = LOWER(%s)")
            params.append(category.strip())
        if sentiment and sentiment.strip():
            filters.append("LOWER(r.sentiment_label) = LOWER(%s)")
            params.append(sentiment.strip())

        where_filter = ""
        if filters:
            where_filter = " AND " + " AND ".join(filters)

        # 1. Per-item aggregated feedback
        item_agg_sql = f"""
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                COUNT(r.review_id) as review_count,
                COALESCE(AVG(r.rating), 0) as average_rating,
                COUNT(r.review_id) FILTER (WHERE r.sentiment_label = 'positive') as positive_count,
                COUNT(r.review_id) FILTER (WHERE r.sentiment_label = 'negative') as negative_count,
                COUNT(r.review_id) FILTER (WHERE r.sentiment_label = 'neutral') as neutral_count
            FROM reviews r
            JOIN menu_items mi ON r.reviewed_menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE r.review_date >= %s AND r.review_date <= %s{where_filter}
            GROUP BY mi.menu_item_id, mi.item_name, mc.category_name
            ORDER BY review_count DESC, average_rating DESC
            LIMIT %s;
        """
        agg_params = list(params) + [clamped_limit]
        agg_rows = execute_query(item_agg_sql, tuple(agg_params))

        items_summary = [
            {
                "menu_item_id": r["menu_item_id"],
                "item_name": r["item_name"],
                "category_name": r["category_name"],
                "review_count": r["review_count"],
                "average_rating": round(float(r["average_rating"]), 2),
                "positive_reviews": r["positive_count"],
                "negative_reviews": r["negative_count"],
                "neutral_reviews": r["neutral_count"]
            }
            for r in agg_rows
        ]

        # 2. Sample review excerpts (anonymized: review_id, rating, date, text, sentiment, issue)
        sample_sql = f"""
            SELECT 
                r.review_id,
                mi.item_name,
                mc.category_name,
                r.rating,
                r.review_text,
                r.sentiment_label,
                r.issue_category,
                r.review_date::text as review_date
            FROM reviews r
            JOIN menu_items mi ON r.reviewed_menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE r.review_date >= %s AND r.review_date <= %s{where_filter}
            ORDER BY r.review_date DESC
            LIMIT %s;
        """
        sample_params = list(params) + [clamped_limit]
        sample_rows = execute_query(sample_sql, tuple(sample_params))

        sample_reviews = [
            {
                "review_id": sr["review_id"],
                "item_name": sr["item_name"],
                "category_name": sr["category_name"],
                "rating": sr["rating"],
                "review_text": sr["review_text"],
                "sentiment": sr["sentiment_label"],
                "issue_category": sr["issue_category"],
                "review_date": sr["review_date"]
            }
            for sr in sample_rows
        ]

        return {
            "status": "success",
            "data": {
                "period_start": start_clean,
                "period_end": end_clean,
                "item_filter": menu_item_name or "all",
                "category_filter": category or "all",
                "sentiment_filter": sentiment or "all",
                "items_analyzed_count": len(items_summary),
                "items_summary": items_summary,
                "sample_reviews": sample_reviews,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_item_reviews_summary: {str(e)}"}


def get_feedback_trends_and_issues(
    period_type: str = "7_days",
    end_date: Optional[str] = None,
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_feedback_trends_and_issues

    Description:
        Performs period-over-period comparative analysis of customer sentiment and reviews
        (e.g., current 7 days vs previous 7 days). Computes rating shifts, sentiment changes,
        rising or falling complaint categories, and identifies most praised vs most complained items.

    Parameters:
        period_type (str, optional): '7_days', '14_days', '30_days', or 'custom'. Default: '7_days'.
        end_date (str, optional): ISO date string (YYYY-MM-DD). Defaults to latest available date.
        start_date (str, optional): ISO date string for custom period start.

    Returns:
        Dict[str, Any]: Current vs prior period rating metrics, issue shifts, praised items, and complaint drivers.
    """
    days_map = {"7_days": 7, "14_days": 14, "30_days": 30}
    num_days = days_map.get(period_type.lower(), 7)

    try:
        if start_date and end_date:
            curr_start, curr_end = _resolve_date_range(start_date, end_date)
            start_dt = datetime.strptime(curr_start, "%Y-%m-%d").date()
            end_dt = datetime.strptime(curr_end, "%Y-%m-%d").date()
            duration_days = (end_dt - start_dt).days + 1
        else:
            curr_start, curr_end = _resolve_date_range(end_date=end_date, default_days=num_days)
            duration_days = num_days

        curr_start_dt = datetime.strptime(curr_start, "%Y-%m-%d").date()
        prev_end_dt = curr_start_dt - timedelta(days=1)
        prev_start_dt = prev_end_dt - timedelta(days=duration_days - 1)
        prev_start = prev_start_dt.isoformat()
        prev_end = prev_end_dt.isoformat()
    except ValueError as val_err:
        return {"status": "error", "message": str(val_err)}

    try:
        def _get_period_feedback(p_start: str, p_end: str) -> Dict[str, Any]:
            sql = """
                SELECT 
                    COUNT(review_id) as review_count,
                    COALESCE(AVG(rating), 0) as average_rating,
                    COUNT(review_id) FILTER (WHERE sentiment_label = 'positive') as positive_count,
                    COUNT(review_id) FILTER (WHERE sentiment_label = 'neutral') as neutral_count,
                    COUNT(review_id) FILTER (WHERE sentiment_label = 'negative') as negative_count
                FROM reviews
                WHERE review_date >= %s AND review_date <= %s;
            """
            row = execute_single(sql, (p_start, p_end)) or {}
            total = row.get("review_count", 0)
            avg_r = round(float(row.get("average_rating", 0.0)), 2)
            pos_pct = round((row.get("positive_count", 0) / total * 100), 2) if total > 0 else 0.0
            neg_pct = round((row.get("negative_count", 0) / total * 100), 2) if total > 0 else 0.0
            return {
                "review_count": total,
                "average_rating": avg_r,
                "positive_percentage": pos_pct,
                "negative_percentage": neg_pct,
                "positive_count": row.get("positive_count", 0),
                "negative_count": row.get("negative_count", 0)
            }

        curr_stats = _get_period_feedback(curr_start, curr_end)
        prev_stats = _get_period_feedback(prev_start, prev_end)

        rating_delta = round(curr_stats["average_rating"] - prev_stats["average_rating"], 2)
        volume_delta = curr_stats["review_count"] - prev_stats["review_count"]
        pos_shift = round(curr_stats["positive_percentage"] - prev_stats["positive_percentage"], 2)

        # Issue comparison between periods
        def _get_issues(p_start: str, p_end: str) -> Dict[str, int]:
            sql = """
                SELECT issue_category, COUNT(review_id) as cnt
                FROM reviews
                WHERE review_date >= %s AND review_date <= %s
                GROUP BY issue_category;
            """
            rows = execute_query(sql, (p_start, p_end))
            return {r["issue_category"]: r["cnt"] for r in rows}

        curr_issues = _get_issues(curr_start, curr_end)
        prev_issues = _get_issues(prev_start, prev_end)

        all_categories = set(curr_issues.keys()).union(set(prev_issues.keys()))
        issue_trends = []
        for cat in all_categories:
            c_cnt = curr_issues.get(cat, 0)
            p_cnt = prev_issues.get(cat, 0)
            diff = c_cnt - p_cnt
            issue_trends.append({
                "issue_category": cat,
                "current_count": c_cnt,
                "previous_count": p_cnt,
                "change": diff
            })
        issue_trends.sort(key=lambda x: abs(x["change"]), reverse=True)

        # Most praised & complained items in current period
        praised_sql = """
            SELECT 
                mi.item_name,
                mc.category_name,
                COUNT(r.review_id) as positive_reviews,
                COALESCE(AVG(r.rating), 0) as average_rating
            FROM reviews r
            JOIN menu_items mi ON r.reviewed_menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE r.review_date >= %s AND r.review_date <= %s AND r.sentiment_label = 'positive'
            GROUP BY mi.item_name, mc.category_name
            ORDER BY positive_reviews DESC, average_rating DESC
            LIMIT 5;
        """
        praised_rows = execute_query(praised_sql, (curr_start, curr_end))
        praised_items = [
            {"item_name": r["item_name"], "category_name": r["category_name"], "positive_reviews": r["positive_reviews"], "avg_rating": round(float(r["average_rating"]), 2)}
            for r in praised_rows
        ]

        complained_sql = """
            SELECT 
                mi.item_name,
                mc.category_name,
                COUNT(r.review_id) as negative_reviews,
                COALESCE(AVG(r.rating), 0) as average_rating
            FROM reviews r
            JOIN menu_items mi ON r.reviewed_menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            WHERE r.review_date >= %s AND r.review_date <= %s AND r.sentiment_label = 'negative'
            GROUP BY mi.item_name, mc.category_name
            ORDER BY negative_reviews DESC, average_rating ASC
            LIMIT 5;
        """
        complained_rows = execute_query(complained_sql, (curr_start, curr_end))
        complained_items = [
            {"item_name": r["item_name"], "category_name": r["category_name"], "negative_reviews": r["negative_reviews"], "avg_rating": round(float(r["average_rating"]), 2)}
            for r in complained_rows
        ]

        return {
            "status": "success",
            "data": {
                "period_type": period_type,
                "current_period": {
                    "start_date": curr_start,
                    "end_date": curr_end,
                    "review_count": curr_stats["review_count"],
                    "average_rating": curr_stats["average_rating"],
                    "positive_percentage": curr_stats["positive_percentage"],
                    "negative_percentage": curr_stats["negative_percentage"]
                },
                "previous_period": {
                    "start_date": prev_start,
                    "end_date": prev_end,
                    "review_count": prev_stats["review_count"],
                    "average_rating": prev_stats["average_rating"],
                    "positive_percentage": prev_stats["positive_percentage"],
                    "negative_percentage": prev_stats["negative_percentage"]
                },
                "comparison": {
                    "average_rating_delta": rating_delta,
                    "review_volume_change": volume_delta,
                    "positive_sentiment_shift": pos_shift
                },
                "issue_trends": issue_trends,
                "most_praised_items": praised_items,
                "most_complained_items": complained_items,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_feedback_trends_and_issues: {str(e)}"}


def get_inventory_status(
    low_stock_only: bool = False,
    category: Optional[str] = None,
    ingredient_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_inventory_status

    Description:
        Provides detailed status of cafe inventory, stock health classifications
        (CRITICAL, LOW_STOCK, APPROACHING_REORDER, HEALTHY), reorder ratios,
        and replenishment priority ranking.
    """
    try:
        where_clauses = ["1=1"]
        params = {}

        if category:
            where_clauses.append("LOWER(ing.ingredient_category) = LOWER(%(category)s)")
            params["category"] = category.strip()

        if ingredient_name:
            where_clauses.append("ing.ingredient_name ILIKE %(ingredient_name)s")
            params["ingredient_name"] = f"%{ingredient_name.strip()}%"

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT 
                inv.ingredient_id,
                ing.ingredient_name,
                ing.ingredient_category,
                inv.on_hand_quantity,
                inv.reorder_level,
                inv.unit,
                inv.last_count_date,
                CASE 
                    WHEN inv.on_hand_quantity <= (inv.reorder_level * 0.5) THEN 'CRITICAL'
                    WHEN inv.on_hand_quantity <= inv.reorder_level THEN 'LOW_STOCK'
                    WHEN inv.on_hand_quantity <= (inv.reorder_level * 1.25) THEN 'APPROACHING_REORDER'
                    ELSE 'HEALTHY'
                END as stock_status,
                CASE 
                    WHEN inv.reorder_level > 0 THEN ROUND((inv.on_hand_quantity / inv.reorder_level)::numeric, 2)
                    ELSE NULL 
                END as stock_to_reorder_ratio
            FROM inventory inv
            JOIN ingredients ing ON inv.ingredient_id = ing.ingredient_id
            WHERE {where_sql}
            ORDER BY (inv.on_hand_quantity / NULLIF(inv.reorder_level, 0)) ASC, ing.ingredient_name ASC;
        """
        rows = execute_query(query, params)

        if not rows:
            return {
                "status": "success",
                "data": {
                    "items": [],
                    "summary": {
                        "total_items": 0,
                        "critical_items_count": 0,
                        "low_stock_items_count": 0,
                        "approaching_reorder_count": 0,
                        "healthy_items_count": 0
                    },
                    "replenishment_priorities": [],
                    "data_origin": "SYNTHETIC"
                },
                "message": "No inventory records matched the specified filters."
            }

        items = []
        critical_cnt = 0
        low_stock_cnt = 0
        approaching_cnt = 0
        healthy_cnt = 0
        replenishment_priorities = []

        for r in rows:
            on_hand = float(r["on_hand_quantity"]) if r.get("on_hand_quantity") is not None else 0.0
            reorder = float(r["reorder_level"]) if r.get("reorder_level") is not None else 0.0
            st = r.get("stock_status")
            if not st:
                if on_hand <= (reorder * 0.5):
                    st = "CRITICAL"
                elif on_hand <= reorder:
                    st = "LOW_STOCK"
                elif on_hand <= (reorder * 1.25):
                    st = "APPROACHING_REORDER"
                else:
                    st = "HEALTHY"

            if st == "CRITICAL":
                critical_cnt += 1
            elif st == "LOW_STOCK":
                low_stock_cnt += 1
            elif st == "APPROACHING_REORDER":
                approaching_cnt += 1
            else:
                healthy_cnt += 1

            is_reorder_candidate = st in ("CRITICAL", "LOW_STOCK", "APPROACHING_REORDER")
            if low_stock_only and not (st in ("CRITICAL", "LOW_STOCK")):
                continue

            item_name = r.get("ingredient_name", "")
            ratio_val = float(r["stock_to_reorder_ratio"]) if r.get("stock_to_reorder_ratio") is not None else (round(on_hand / reorder, 2) if reorder > 0 else None)
            item_info = {
                "ingredient_id": r.get("ingredient_id", ""),
                "ingredient_name": item_name,
                "item_name": item_name,
                "category": r.get("ingredient_category", ""),
                "on_hand_quantity": on_hand,
                "current_stock": on_hand,
                "reorder_level": reorder,
                "min_reorder_level": reorder,
                "unit": r.get("unit", ""),
                "last_count_date": str(r.get("last_count_date", "")),
                "stock_status": st,
                "status": "Low Stock - Reorder Needed!" if st in ("CRITICAL", "LOW_STOCK") else "In Stock",
                "stock_to_reorder_ratio": ratio_val
            }
            items.append(item_info)

            if is_reorder_candidate:
                priority_level = 1 if st == "CRITICAL" else (2 if st == "LOW_STOCK" else 3)
                replenishment_priorities.append({
                    "priority_rank": priority_level,
                    "ingredient_id": r.get("ingredient_id", ""),
                    "ingredient_name": item_name,
                    "category": r.get("ingredient_category", ""),
                    "current_stock": on_hand,
                    "reorder_level": reorder,
                    "unit": r.get("unit", ""),
                    "deficit": max(0.0, reorder - on_hand),
                    "urgency": "Urgent Restock (Critical)" if st == "CRITICAL" else ("Reorder Needed" if st == "LOW_STOCK" else "Approaching Threshold")
                })

        replenishment_priorities.sort(key=lambda x: (x["priority_rank"], -x["deficit"]))

        return {
            "status": "success",
            "data": {
                "items": items,
                "summary": {
                    "total_items": len(rows),
                    "critical_items_count": critical_cnt,
                    "low_stock_items_count": low_stock_cnt,
                    "approaching_reorder_count": approaching_cnt,
                    "healthy_items_count": healthy_cnt
                },
                "replenishment_priorities": replenishment_priorities,
                "data_origin": "SYNTHETIC"
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_inventory_status: {str(e)}"}


def get_ingredient_consumption(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ingredient_name: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_ingredient_consumption

    Description:
        Calculates historical ingredient consumption from completed orders,
        multiplied by standard recipe quantities.
        Computes daily burn rates, estimated days of stock remaining,
        and identifies high-velocity consumption items.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=7)
        start_dt = datetime.strptime(resolved_start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(resolved_end, "%Y-%m-%d").date()
        days_in_period = max(1, (end_dt - start_dt).days + 1)

        where_clauses = [
            "o.order_status = 'completed'",
            "o.order_date >= %(start_date)s",
            "o.order_date <= %(end_date)s"
        ]
        params = {
            "start_date": resolved_start,
            "end_date": resolved_end
        }

        if category:
            where_clauses.append("LOWER(i.ingredient_category) = LOWER(%(category)s)")
            params["category"] = category.strip()

        if ingredient_name:
            where_clauses.append("i.ingredient_name ILIKE %(ingredient_name)s")
            params["ingredient_name"] = f"%{ingredient_name.strip()}%"

        where_sql = " AND ".join(where_clauses)

        query = f"""
            SELECT 
                i.ingredient_id,
                i.ingredient_name,
                i.ingredient_category,
                i.unit,
                inv.on_hand_quantity as current_stock,
                inv.reorder_level,
                COALESCE(SUM(oi.quantity * mr.quantity_per_portion), 0) as recipe_consumed_quantity,
                COUNT(DISTINCT o.order_id)::int as orders_count
            FROM ingredients i
            JOIN menu_recipes mr ON i.ingredient_id = mr.ingredient_id
            JOIN order_items oi ON mr.menu_item_id = oi.menu_item_id
            JOIN orders o ON oi.order_id = o.order_id
            LEFT JOIN inventory inv ON i.ingredient_id = inv.ingredient_id
            WHERE {where_sql}
            GROUP BY i.ingredient_id, i.ingredient_name, i.ingredient_category, i.unit, inv.on_hand_quantity, inv.reorder_level
            ORDER BY recipe_consumed_quantity DESC;
        """
        rows = execute_query(query, params)

        items_consumption = []
        high_velocity_items = []
        stockout_risk_items = []

        for r in rows:
            consumed = float(r["recipe_consumed_quantity"]) if r["recipe_consumed_quantity"] is not None else 0.0
            stock = float(r["current_stock"]) if r["current_stock"] is not None else 0.0
            reorder = float(r["reorder_level"]) if r["reorder_level"] is not None else 0.0
            daily_rate = round(consumed / days_in_period, 2)
            days_left = round(stock / daily_rate, 1) if daily_rate > 0 else None

            item_data = {
                "ingredient_id": r["ingredient_id"],
                "ingredient_name": r["ingredient_name"],
                "category": r["ingredient_category"],
                "unit": r["unit"],
                "total_consumed_quantity": consumed,
                "daily_burn_rate": daily_rate,
                "current_stock": stock,
                "reorder_level": reorder,
                "estimated_days_of_stock_left": days_left,
                "orders_count": r["orders_count"]
            }
            items_consumption.append(item_data)

            if days_left is not None and days_left <= 3.0 and stock <= reorder:
                stockout_risk_items.append(item_data)

            if daily_rate > 0:
                high_velocity_items.append(item_data)

        high_velocity_items.sort(key=lambda x: x["daily_burn_rate"], reverse=True)

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "days_in_period": days_in_period,
                "ingredients_analyzed_count": len(items_consumption),
                "consumed_ingredients": items_consumption,
                "top_consumed_by_velocity": high_velocity_items[:5],
                "stockout_risk_ingredients": stockout_risk_items,
                "data_origin": "SYNTHETIC",
                "methodology_note": "Consumption calculated from completed order items multiplied by recipe portion specifications."
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_ingredient_consumption: {str(e)}"}


def get_stock_movement_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ingredient_name: Optional[str] = None,
    movement_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_stock_movement_summary

    Description:
        Summarizes recorded physical and transactional stock movements from stock_movements.
        Aggregates inflows (e.g. purchase receipts, opening balances) and outflows (e.g. sale consumption)
        grouped by movement type and unit without incompatible unit additions.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=7)
        start_ts = f"{resolved_start} 00:00:00"
        end_ts = f"{resolved_end} 23:59:59"

        where_clauses = [
            "sm.movement_ts >= %(start_ts)s",
            "sm.movement_ts <= %(end_ts)s"
        ]
        params = {
            "start_ts": start_ts,
            "end_ts": end_ts
        }

        if movement_type:
            where_clauses.append("LOWER(sm.movement_type) = LOWER(%(movement_type)s)")
            params["movement_type"] = movement_type.strip()

        if ingredient_name:
            where_clauses.append("i.ingredient_name ILIKE %(ingredient_name)s")
            params["ingredient_name"] = f"%{ingredient_name.strip()}%"

        where_sql = " AND ".join(where_clauses)

        type_query = f"""
            SELECT 
                sm.movement_type,
                sm.unit,
                COUNT(*)::int as movement_count,
                COALESCE(SUM(CASE WHEN sm.quantity_delta > 0 THEN sm.quantity_delta ELSE 0 END), 0) as total_inflow,
                COALESCE(SUM(CASE WHEN sm.quantity_delta < 0 THEN ABS(sm.quantity_delta) ELSE 0 END), 0) as total_outflow,
                COALESCE(SUM(sm.quantity_delta), 0) as net_delta
            FROM stock_movements sm
            JOIN ingredients i ON sm.ingredient_id = i.ingredient_id
            WHERE {where_sql}
            GROUP BY sm.movement_type, sm.unit
            ORDER BY sm.movement_type, sm.unit;
        """
        type_rows = execute_query(type_query, params)

        movement_type_breakdown = [
            {
                "movement_type": r["movement_type"],
                "unit": r["unit"],
                "movement_count": r["movement_count"],
                "total_inflow": float(r["total_inflow"]),
                "total_outflow": float(r["total_outflow"]),
                "net_delta": float(r["net_delta"])
            }
            for r in type_rows
        ]

        ing_query = f"""
            SELECT 
                sm.ingredient_id,
                i.ingredient_name,
                i.ingredient_category,
                sm.unit,
                COUNT(*)::int as movement_count,
                COALESCE(SUM(CASE WHEN sm.quantity_delta > 0 THEN sm.quantity_delta ELSE 0 END), 0) as total_inflow,
                COALESCE(SUM(CASE WHEN sm.quantity_delta < 0 THEN ABS(sm.quantity_delta) ELSE 0 END), 0) as total_outflow,
                COALESCE(SUM(sm.quantity_delta), 0) as net_delta
            FROM stock_movements sm
            JOIN ingredients i ON sm.ingredient_id = i.ingredient_id
            WHERE {where_sql}
            GROUP BY sm.ingredient_id, i.ingredient_name, i.ingredient_category, sm.unit
            ORDER BY total_outflow DESC, i.ingredient_name ASC;
        """
        ing_rows = execute_query(ing_query, params)

        ingredient_movements = [
            {
                "ingredient_id": r["ingredient_id"],
                "ingredient_name": r["ingredient_name"],
                "category": r["ingredient_category"],
                "unit": r["unit"],
                "movement_count": r["movement_count"],
                "total_inflow": float(r["total_inflow"]),
                "total_outflow": float(r["total_outflow"]),
                "net_delta": float(r["net_delta"])
            }
            for r in ing_rows
        ]

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "total_movements_count": sum(r["movement_count"] for r in movement_type_breakdown),
                "movement_types_summary": movement_type_breakdown,
                "ingredient_movements": ingredient_movements,
                "data_origin": "SYNTHETIC"
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_stock_movement_summary: {str(e)}"}


def get_inventory_variance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ingredient_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_inventory_variance

    Description:
        Compares recorded stock movement outflows against expected recipe consumption from completed orders.
        Identifies variance, unexplained gaps, and potential waste indicators without making false claims of confirmed waste.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=7)
        start_ts = f"{resolved_start} 00:00:00"
        end_ts = f"{resolved_end} 23:59:59"

        where_params = {
            "start_date": resolved_start,
            "end_date": resolved_end,
            "start_ts": start_ts,
            "end_ts": end_ts
        }
        filter_sql = ""
        if ingredient_name:
            filter_sql = " AND i.ingredient_name ILIKE %(ingredient_name)s"
            where_params["ingredient_name"] = f"%{ingredient_name.strip()}%"

        query = f"""
            WITH expected AS (
                SELECT 
                    i.ingredient_id,
                    i.ingredient_name,
                    i.ingredient_category,
                    i.unit,
                    COALESCE(SUM(oi.quantity * mr.quantity_per_portion), 0) as expected_consumption
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN menu_recipes mr ON oi.menu_item_id = mr.menu_item_id
                JOIN ingredients i ON mr.ingredient_id = i.ingredient_id
                WHERE o.order_status = 'completed'
                  AND o.order_date >= %(start_date)s AND o.order_date <= %(end_date)s
                  {filter_sql}
                GROUP BY i.ingredient_id, i.ingredient_name, i.ingredient_category, i.unit
            ),
            recorded AS (
                SELECT 
                    sm.ingredient_id,
                    COALESCE(SUM(ABS(sm.quantity_delta)), 0) as recorded_outflow
                FROM stock_movements sm
                JOIN ingredients i ON sm.ingredient_id = i.ingredient_id
                WHERE sm.movement_type = 'sale_consumption'
                  AND sm.movement_ts >= %(start_ts)s AND sm.movement_ts <= %(end_ts)s
                  {filter_sql}
                GROUP BY sm.ingredient_id
            )
            SELECT 
                e.ingredient_id,
                e.ingredient_name,
                e.ingredient_category,
                e.unit,
                e.expected_consumption,
                COALESCE(r.recorded_outflow, 0) as recorded_outflow,
                (COALESCE(r.recorded_outflow, 0) - e.expected_consumption) as variance_quantity
            FROM expected e
            LEFT JOIN recorded r ON e.ingredient_id = r.ingredient_id
            ORDER BY e.expected_consumption DESC;
        """
        rows = execute_query(query, where_params)

        variance_records = []
        matching_count = 0
        elevated_outflow_count = 0
        lower_outflow_count = 0

        for r in rows:
            expected = float(r["expected_consumption"])
            recorded = float(r["recorded_outflow"])
            variance = float(r["variance_quantity"])
            variance_pct = round((variance / expected) * 100, 2) if expected > 0 else 0.0

            if abs(variance) < 0.001:
                status_flag = "EXACT_MATCH"
                matching_count += 1
            elif variance > 0:
                status_flag = "ELEVATED_OUTFLOW"
                elevated_outflow_count += 1
            else:
                status_flag = "LOWER_OUTFLOW"
                lower_outflow_count += 1

            variance_records.append({
                "ingredient_id": r["ingredient_id"],
                "ingredient_name": r["ingredient_name"],
                "category": r["ingredient_category"],
                "unit": r["unit"],
                "expected_recipe_consumption": expected,
                "recorded_movement_outflow": recorded,
                "variance_quantity": variance,
                "variance_percentage": variance_pct,
                "status": status_flag
            })

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "ingredients_analyzed_count": len(variance_records),
                "summary": {
                    "exact_matches_count": matching_count,
                    "elevated_outflows_count": elevated_outflow_count,
                    "lower_outflows_count": lower_outflow_count
                },
                "variance_details": variance_records,
                "data_origin": "SYNTHETIC",
                "waste_and_variance_advisory": (
                    "Observed variances between recorded stock movements and recipe expectations indicate operational "
                    "or recording differences (e.g. portion deviations, preparation trim, unrecorded stock drops, or timestamp lag). "
                    "They should be treated as potential waste indicators, not confirmed waste, because the database does not contain "
                    "dedicated spoilage/discard waste logs."
                )
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_inventory_variance: {str(e)}"}


def get_stockout_risk_recommendations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_stockout_risk_recommendations

    Description:
        Identifies high-selling and core menu items whose recipe ingredients are at CRITICAL
        or LOW_STOCK inventory thresholds. Produces structured, prioritized replenishment recommendations
        calculating revenue at risk and ingredient deficits.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=7)
        
        query = """
            WITH period_sales AS (
                SELECT 
                    oi.menu_item_id,
                    COUNT(DISTINCT o.order_id)::int as orders_count,
                    SUM(oi.quantity)::int as units_sold,
                    SUM(oi.line_total_inr)::numeric as sales_revenue
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                WHERE o.order_status = 'completed'
                  AND o.order_date >= %(start_date)s AND o.order_date <= %(end_date)s
                GROUP BY oi.menu_item_id
            ),
            critical_recipes AS (
                SELECT 
                    mr.menu_item_id,
                    ing.ingredient_id,
                    ing.ingredient_name,
                    inv.on_hand_quantity,
                    inv.reorder_level,
                    inv.unit,
                    CASE 
                        WHEN inv.on_hand_quantity <= (inv.reorder_level * 0.5) THEN 'CRITICAL'
                        WHEN inv.on_hand_quantity <= inv.reorder_level THEN 'LOW_STOCK'
                        ELSE 'HEALTHY'
                    END as stock_status,
                    (inv.reorder_level - inv.on_hand_quantity) as deficit
                FROM menu_recipes mr
                JOIN ingredients ing ON mr.ingredient_id = ing.ingredient_id
                JOIN inventory inv ON ing.ingredient_id = inv.ingredient_id
                WHERE inv.on_hand_quantity <= inv.reorder_level
            )
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                mi.list_price_inr,
                COALESCE(s.units_sold, 0)::int as units_sold,
                COALESCE(s.sales_revenue, 0)::numeric as sales_revenue,
                cr.ingredient_id,
                cr.ingredient_name,
                cr.stock_status,
                cr.on_hand_quantity,
                cr.reorder_level,
                cr.deficit,
                cr.unit as ingredient_unit
            FROM menu_items mi
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            JOIN critical_recipes cr ON mi.menu_item_id = cr.menu_item_id
            LEFT JOIN period_sales s ON mi.menu_item_id = s.menu_item_id
            ORDER BY cr.stock_status ASC, s.sales_revenue DESC NULLS LAST;
        """
        rows = execute_query(query, {"start_date": resolved_start, "end_date": resolved_end})

        ing_map = {}
        for r in rows:
            ing_name = r["ingredient_name"]
            if ing_name not in ing_map:
                ing_map[ing_name] = {
                    "ingredient_id": r["ingredient_id"],
                    "ingredient_name": ing_name,
                    "stock_status": r["stock_status"],
                    "current_stock": float(r.get("on_hand_quantity", 0)),
                    "reorder_level": float(r.get("reorder_level", 0)),
                    "deficit": float(r.get("deficit") if r.get("deficit") is not None else max(0, float(r.get("reorder_level", 0)) - float(r.get("on_hand_quantity", 0)))),
                    "unit": r.get("ingredient_unit") or r.get("unit", ""),
                    "impacted_items": [],
                    "total_revenue_at_risk": 0.0,
                    "total_units_sold": 0
                }
            units = r["units_sold"]
            rev = float(r["sales_revenue"])
            ing_map[ing_name]["total_revenue_at_risk"] += rev
            ing_map[ing_name]["total_units_sold"] += units
            ing_map[ing_name]["impacted_items"].append({
                "item_name": r["item_name"],
                "category": r["category_name"],
                "units_sold": units,
                "revenue": rev
            })

        recommendations = []
        rec_idx = 1
        for ing_name, info in sorted(ing_map.items(), key=lambda x: (x[1]["stock_status"] != "CRITICAL", -x[1]["total_revenue_at_risk"])):
            priority = "critical" if info["stock_status"] == "CRITICAL" and info["total_units_sold"] >= 5 else "high"
            top_item_names = [it["item_name"] for it in info["impacted_items"][:3]]
            items_str = ", ".join([f"{it['item_name']} ({it['units_sold']} sold, INR {it['revenue']:.2f})" for it in info["impacted_items"][:3]])
            
            rec = {
                "recommendation_id": f"REC-INV-{rec_idx:03d}",
                "title": f"Restock {info['stock_status'].title()} Stock Ingredient: {ing_name}",
                "priority": priority,
                "category": "inventory_stockout_risk",
                "observation": (
                    f"On-hand inventory for {ing_name} is currently {info['current_stock']} {info['unit']} against a reorder threshold of "
                    f"{info['reorder_level']} {info['unit']} (deficit of {info['deficit']} {info['unit']}). "
                    f"Between {resolved_start} and {resolved_end}, this ingredient supported {len(info['impacted_items'])} menu items "
                    f"generating INR {info['total_revenue_at_risk']:.2f} across {info['total_units_sold']} units sold: {items_str}."
                ),
                "supporting_evidence": {
                    "ingredient_name": ing_name,
                    "current_stock": info["current_stock"],
                    "reorder_level": info["reorder_level"],
                    "deficit": info["deficit"],
                    "unit": info["unit"],
                    "stock_status": info["stock_status"],
                    "period_start": resolved_start,
                    "period_end": resolved_end,
                    "impacted_menu_items": top_item_names,
                    "total_revenue_at_risk_inr": round(info["total_revenue_at_risk"], 2),
                    "total_units_at_risk": info["total_units_sold"]
                },
                "recommended_action": (
                    f"Issue an urgent purchase order for at least {info['deficit'] + info['reorder_level']} {info['unit']} of {ing_name} "
                    f"to eliminate the current deficit and restore safe operational holding capacity."
                ),
                "expected_impact": f"Eliminates stockout risk for {len(info['impacted_items'])} menu items representing INR {info['total_revenue_at_risk']:.2f} in weekly sales.",
                "confidence": "high",
                "data_origin": "SYNTHETIC",
                "limitations": "Supplier delivery lead times, batch MOQ, and invoice wholesale costs are not tracked in database."
            }
            recommendations.append(rec)
            rec_idx += 1

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "total_stockout_risks": len(recommendations),
                "recommendations": recommendations,
                "data_origin": "SYNTHETIC"
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_stockout_risk_recommendations: {str(e)}"}


def get_quality_and_complaint_recommendations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_quality_and_complaint_recommendations

    Description:
        Analyzes customer review complaints and sentiment trends to identify systematic
        operational failure points (e.g. packaging leaks, service delays) and dishes receiving
        adverse feedback despite steady volume.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=30)
        
        issues_query = """
            SELECT 
                issue_category,
                COUNT(*)::int as complaint_count,
                ROUND((COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0))::numeric, 2) as percentage_of_issues
            FROM reviews
            WHERE LOWER(issue_category) != 'none'
              AND review_date >= %(start_date)s AND review_date <= %(end_date)s
            GROUP BY issue_category
            ORDER BY complaint_count DESC;
        """
        issues_rows = execute_query(issues_query, {"start_date": resolved_start, "end_date": resolved_end})

        item_feedback_query = """
            WITH item_fb AS (
                SELECT 
                    r.reviewed_menu_item_id as menu_item_id,
                    COUNT(*)::int as total_reviews,
                    ROUND(AVG(r.rating)::numeric, 2) as avg_rating,
                    COUNT(*) FILTER (WHERE LOWER(r.sentiment_label) = 'negative')::int as negative_reviews,
                    STRING_AGG(DISTINCT r.issue_category, ', ') FILTER (WHERE LOWER(r.issue_category) != 'none') as cited_issues
                FROM reviews r
                WHERE r.review_date >= %(start_date)s AND r.review_date <= %(end_date)s
                GROUP BY r.reviewed_menu_item_id
                HAVING COUNT(*) >= 2 AND (AVG(r.rating) <= 3.5 OR COUNT(*) FILTER (WHERE LOWER(r.sentiment_label) = 'negative') >= 1)
            )
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                fb.total_reviews,
                fb.avg_rating,
                fb.negative_reviews,
                fb.cited_issues
            FROM item_fb fb
            JOIN menu_items mi ON fb.menu_item_id = mi.menu_item_id
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            ORDER BY fb.negative_reviews DESC, fb.avg_rating ASC;
        """
        item_rows = execute_query(item_feedback_query, {"start_date": resolved_start, "end_date": resolved_end})

        recommendations = []
        rec_idx = 1

        action_map = {
            "packaging": {
                "title": "Upgrade Takeaway & Delivery Container Packaging",
                "priority": "high",
                "action": "Audit current container seal integrity and implement leak-proof containers with thermal linings for liquid curries and gravies.",
                "impact": "Reduces order delivery transit leakage complaints, protecting repeat order rates on delivery channels."
            },
            "service_time": {
                "title": "Optimize Peak Hour Kitchen Prep & Dispatch Workflows",
                "priority": "high",
                "action": "Implement pre-portioning for high-demand starter and curry bases during peak 17:00-19:00 dinner rush to compress fulfillment turnaround.",
                "impact": "Reduces ticket times by an estimated 15-20%, cutting customer wait frustration."
            },
            "food_quality": {
                "title": "Standardize Cooking Temperature & Recipe Holding Audits",
                "priority": "high",
                "action": "Audit cooking temperatures and holding warmers during shift changes to maintain consistent taste, texture, and heat upon delivery.",
                "impact": "Directly addresses core taste and temperature complaints, driving customer satisfaction scores closer to 4.5+ stars."
            },
            "portion_size": {
                "title": "Calibrate Portioning Scoops and Standard Ladles",
                "priority": "medium",
                "action": "Introduce calibrated measurement ladles and visual portion charts on prep stations to ensure uniform portioning.",
                "impact": "Eliminates perceived value discrepancies and reduces portion dissatisfaction."
            },
            "order_accuracy": {
                "title": "Implement Dispatch Checklist Verification",
                "priority": "medium",
                "action": "Require expediter ticket sign-off verifying all order items and condiments prior to handover.",
                "impact": "Prevents missing accompaniments and wrong dish delivery errors."
            }
        }

        for r in issues_rows[:2]:
            cat = r["issue_category"]
            cfg = action_map.get(cat, {
                "title": f"Operational Action on {cat.replace('_', ' ').title()}",
                "priority": "medium",
                "action": f"Review standard operating procedures for {cat.replace('_', ' ')}.",
                "impact": f"Reduces customer dissatisfaction regarding {cat}."
            })
            rec = {
                "recommendation_id": f"REC-OPS-{rec_idx:03d}",
                "title": cfg["title"],
                "priority": cfg["priority"],
                "category": "operational_efficiency",
                "observation": (
                    f"Customer reviews recorded {r['complaint_count']} complaints regarding '{cat}' between {resolved_start} and {resolved_end}, "
                    f"representing {r['percentage_of_issues']}% of all reported operational issues."
                ),
                "supporting_evidence": {
                    "issue_category": cat,
                    "complaint_count": r["complaint_count"],
                    "percentage_of_total_issues": float(r["percentage_of_issues"]),
                    "period_start": resolved_start,
                    "period_end": resolved_end
                },
                "recommended_action": cfg["action"],
                "expected_impact": cfg["impact"],
                "confidence": "high",
                "data_origin": "SYNTHETIC",
                "limitations": "Individual customer identifiable feedback not exposed to preserve privacy; feedback records are synthetic."
            }
            recommendations.append(rec)
            rec_idx += 1

        for r in item_rows[:3]:
            rec = {
                "recommendation_id": f"REC-QLT-{rec_idx:03d}",
                "title": f"Recipe & Quality Review for {r['item_name']}",
                "priority": "medium",
                "category": "quality_intervention",
                "observation": (
                    f"{r['item_name']} ({r['category_name']}) has an average rating of {r['avg_rating']}/5.00 across {r['total_reviews']} reviews, "
                    f"with {r['negative_reviews']} negative feedback entries citing issues: {r['cited_issues'] or 'general dissatisfaction'}."
                ),
                "supporting_evidence": {
                    "menu_item_id": r["menu_item_id"],
                    "item_name": r["item_name"],
                    "category": r["category_name"],
                    "average_rating": float(r["avg_rating"]),
                    "total_reviews": r["total_reviews"],
                    "negative_reviews_count": r["negative_reviews"],
                    "cited_issues": r["cited_issues"],
                    "period_start": resolved_start,
                    "period_end": resolved_end
                },
                "recommended_action": (
                    f"Review preparation procedure, spice balance, and holding time for {r['item_name']} with the culinary team. "
                    f"Sample batches during dinner prep to align with SOP quality benchmarks."
                ),
                "expected_impact": f"Improves dish rating towards category benchmarks and prevents customer churn.",
                "confidence": "medium",
                "data_origin": "SYNTHETIC",
                "limitations": "Small review sample size per individual item (< 5 reviews); feedback is synthetic."
            }
            recommendations.append(rec)
            rec_idx += 1

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "total_quality_recommendations": len(recommendations),
                "recommendations": recommendations,
                "data_origin": "SYNTHETIC"
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_quality_and_complaint_recommendations: {str(e)}"}


def get_underperforming_menu_recommendations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    threshold_units: int = 2
) -> Dict[str, Any]:
    """
    Tool: get_underperforming_menu_recommendations

    Description:
        Identifies zero-sales and low-sales menu items over a target date range.
        Recommends menu catalog optimizations, promotional bundle experiments, or dish phase-out evaluations.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=7)
        
        query = """
            WITH period_sales AS (
                SELECT 
                    oi.menu_item_id,
                    SUM(oi.quantity)::int as units_sold,
                    SUM(oi.line_total_inr)::numeric as sales_revenue
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                WHERE o.order_status = 'completed'
                  AND o.order_date >= %(start_date)s AND o.order_date <= %(end_date)s
                GROUP BY oi.menu_item_id
            )
            SELECT 
                mi.menu_item_id,
                mi.item_name,
                mc.category_name,
                mi.list_price_inr,
                COALESCE(s.units_sold, 0)::int as units_sold,
                COALESCE(s.sales_revenue, 0)::numeric as sales_revenue
            FROM menu_items mi
            JOIN menu_categories mc ON mi.category_id = mc.category_id
            LEFT JOIN period_sales s ON mi.menu_item_id = s.menu_item_id
            WHERE COALESCE(s.units_sold, 0) <= %(threshold)s
            ORDER BY units_sold ASC, mi.list_price_inr DESC;
        """
        rows = execute_query(query, {
            "start_date": resolved_start,
            "end_date": resolved_end,
            "threshold": threshold_units
        })

        zero_sales_items = [r for r in rows if r["units_sold"] == 0]
        low_sales_items = [r for r in rows if 0 < r["units_sold"] <= threshold_units]

        recommendations = []
        rec_idx = 1

        if zero_sales_items:
            item_names = [r["item_name"] for r in zero_sales_items[:4]]
            zero_summary_list = [f"{r['item_name']} ({r['category_name']}, INR {r['list_price_inr']})" for r in zero_sales_items[:4]]
            zero_summary_str = ", ".join(zero_summary_list)
            rec = {
                "recommendation_id": f"REC-MNU-{rec_idx:03d}",
                "title": f"Evaluate Zero-Sales Menu Items ({', '.join(item_names[:2])})",
                "priority": "low",
                "category": "menu_catalog_optimization",
                "observation": (
                    f"{len(zero_sales_items)} menu items recorded 0 orders between {resolved_start} and {resolved_end}: "
                    f"{zero_summary_str}."
                ),
                "supporting_evidence": {
                    "zero_sales_items_count": len(zero_sales_items),
                    "zero_sales_items": [
                        {"item_name": r["item_name"], "category": r["category_name"], "price_inr": float(r["list_price_inr"])}
                        for r in zero_sales_items[:5]
                    ],
                    "period_start": resolved_start,
                    "period_end": resolved_end
                },
                "recommended_action": (
                    "Audit whether these items require unique perishable ingredients that risk spoilage. "
                    "If ingredients are shared, feature them as promotional chef specials; otherwise evaluate temporary menu delisting."
                ),
                "expected_impact": "Streamlines kitchen prep complexity and minimizes ingredient holding costs.",
                "confidence": "medium",
                "data_origin": "SYNTHETIC",
                "limitations": "Inventory carrying cost and ingredient shelf-life data unavailable; sales observations are synthetic."
            }
            recommendations.append(rec)
            rec_idx += 1

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "zero_sales_count": len(zero_sales_items),
                "low_sales_count": len(low_sales_items),
                "recommendations": recommendations,
                "data_origin": "SYNTHETIC"
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_underperforming_menu_recommendations: {str(e)}"}


def get_actionable_recommendations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    focus_area: Optional[str] = None,
    min_priority: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: get_actionable_recommendations

    Description:
        Comprehensive multi-domain decision engine synthesizing inventory stockout risks,
        quality/complaint interventions, and menu optimization into a prioritized, evidence-backed
        executive action plan.
    """
    try:
        resolved_start, resolved_end = _resolve_date_range(start_date, end_date, default_days=7)

        all_recommendations = []

        # 1. Fetch Inventory Risks
        if not focus_area or focus_area in ("inventory", "all", "stock"):
            inv_res = get_stockout_risk_recommendations(start_date=resolved_start, end_date=resolved_end)
            if inv_res.get("status") == "success":
                all_recommendations.extend(inv_res.get("data", {}).get("recommendations", []))

        # 2. Fetch Quality & Complaints
        if not focus_area or focus_area in ("quality", "complaints", "feedback", "all", "operations"):
            qlt_res = get_quality_and_complaint_recommendations(start_date=resolved_start, end_date=resolved_end)
            if qlt_res.get("status") == "success":
                all_recommendations.extend(qlt_res.get("data", {}).get("recommendations", []))

        # 3. Fetch Menu Optimization
        if not focus_area or focus_area in ("menu", "sales", "catalog", "all"):
            mnu_res = get_underperforming_menu_recommendations(start_date=resolved_start, end_date=resolved_end)
            if mnu_res.get("status") == "success":
                all_recommendations.extend(mnu_res.get("data", {}).get("recommendations", []))

        # Priority filter if requested
        priority_order = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        if min_priority and min_priority.lower() in priority_order:
            max_level = priority_order[min_priority.lower()]
            all_recommendations = [r for r in all_recommendations if priority_order.get(r["priority"].lower(), 99) <= max_level]

        # Sort recommendations by priority order
        all_recommendations.sort(key=lambda r: priority_order.get(r["priority"].lower(), 99))

        priority_counts = {
            "critical": sum(1 for r in all_recommendations if r["priority"].lower() == "critical"),
            "high": sum(1 for r in all_recommendations if r["priority"].lower() == "high"),
            "medium": sum(1 for r in all_recommendations if r["priority"].lower() == "medium"),
            "low": sum(1 for r in all_recommendations if r["priority"].lower() == "low")
        }

        exec_summary = (
            f"Generated {len(all_recommendations)} prioritized business recommendations based on "
            f"operational data from {resolved_start} to {resolved_end}. "
            f"Key focus: {priority_counts['critical']} critical inventory risks requiring immediate restock, "
            f"{priority_counts['high']} high-priority interventions across packaging/prep, and "
            f"{priority_counts['medium'] + priority_counts['low']} menu/quality optimizations."
        )

        return {
            "status": "success",
            "data": {
                "period_start": resolved_start,
                "period_end": resolved_end,
                "total_recommendations": len(all_recommendations),
                "priority_breakdown": priority_counts,
                "executive_summary": exec_summary,
                "recommendations": all_recommendations,
                "data_origin": "SYNTHETIC",
                "general_limitations": (
                    "All findings are grounded strictly in the available database schema. Profit margins cannot be calculated "
                    "without wholesale ingredient invoice costs. Supplier lead times, purchase order MOQs, and food expiry dates "
                    "are not recorded in the database. Customer privacy is preserved by withholding customer IDs. Data is synthetic."
                )
            }
        }
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        return {"status": "error", "message": f"Database error in get_actionable_recommendations: {str(e)}"}


# -----------------------------------------------------------------------------
# Tool Registry / Tool Definitions Schema
# -----------------------------------------------------------------------------
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "get_inventory": {
        "function": get_inventory,
        "description": "Check current cafe inventory levels, stock quantities, and items that need reordering from the database.",
        "keywords": ["inventory", "stock", "ingredients", "supplies", "how much milk", "beans", "shortage"],
        "schema": {
            "name": "get_inventory",
            "description": "Check current cafe inventory levels, stock quantities, and items that need reordering from the database.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "low_stock_only": {
                        "type": "BOOLEAN",
                        "description": "If true, returns only items where current stock is at or below reorder level."
                    }
                }
            }
        }
    },
    "get_today_sales": {
        "function": get_today_sales,
        "description": "Retrieve financial performance, total revenue, order count, and best-selling items from the database for a single date.",
        "keywords": ["sales", "revenue", "earnings", "made today", "income", "orders", "best seller", "top selling", "profit"],
        "schema": {
            "name": "get_today_sales",
            "description": "Retrieve financial performance, total revenue, order count, and best-selling items from the database for a single date.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "date_str": {
                        "type": "STRING",
                        "description": "Optional ISO date string (YYYY-MM-DD) to inspect specific shift sales. Defaults to latest/current date."
                    }
                }
            }
        }
    },
    "get_sales_performance": {
        "function": get_sales_performance,
        "description": "Retrieve comprehensive sales totals, revenue (total, subtotal, tax, service charges), order status counts (completed, cancelled, refunded), average order value (AOV), channel breakdown, and discount impact over a date range.",
        "keywords": ["sales performance", "total sales", "revenue", "orders over period", "orders", "order count", "how many orders", "completed orders", "channel sales", "dine in", "delivery", "takeaway", "discount impact"],
        "schema": {
            "name": "get_sales_performance",
            "description": "Retrieve sales totals, revenue, order status counts, AOV, channel performance, and discount impact over a date range.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "channel": {
                        "type": "STRING",
                        "description": "Optional channel filter ('dine_in', 'takeaway', 'delivery')."
                    }
                }
            }
        }
    },
    "get_top_selling_items": {
        "function": get_top_selling_items,
        "description": "Retrieve top-selling menu items ranked by quantity sold or revenue earned over a date range, with category breakdown.",
        "keywords": ["top selling", "best sellers", "most popular", "highest revenue items", "top items", "sold the most"],
        "schema": {
            "name": "get_top_selling_items",
            "description": "Retrieve top-selling menu items ranked by quantity sold or revenue earned over a date range.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "limit": {
                        "type": "INTEGER",
                        "description": "Number of items to return (1-50, default: 5)."
                    },
                    "sort_by": {
                        "type": "STRING",
                        "description": "Ranking metric: 'quantity' (default) or 'revenue'."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional category filter."
                    }
                }
            }
        }
    },
    "get_sales_trends_and_comparison": {
        "function": get_sales_trends_and_comparison,
        "description": "Compare sales metrics (revenue, order counts, AOV) between two consecutive time periods (e.g. 7 days vs previous 7 days) and view daily time-series trends.",
        "keywords": ["sales trends", "period comparison", "growth", "revenue change", "weekly comparison", "daily sales"],
        "schema": {
            "name": "get_sales_trends_and_comparison",
            "description": "Compare sales metrics between consecutive periods and view daily time-series trends.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "period_type": {
                        "type": "STRING",
                        "description": "Standard period: '7_days', '14_days', '30_days', or 'custom'."
                    },
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD) for custom comparison."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_peak_hours_and_dayparts": {
        "function": get_peak_hours_and_dayparts,
        "description": "Analyze peak operational hours and daypart demand (Morning, Lunch, Evening, Late Night) for order volumes and revenue.",
        "keywords": ["peak hours", "busiest hour", "dayparts", "hourly sales", "lunch rush", "dinner rush", "morning sales"],
        "schema": {
            "name": "get_peak_hours_and_dayparts",
            "description": "Analyze peak operational hours and daypart demand for order volumes and revenue.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_payment_methods_breakdown": {
        "function": get_payment_methods_breakdown,
        "description": "Retrieve payment method distribution (UPI, Card, Cash, Wallet) with transaction counts, settled amounts, and percentages.",
        "keywords": ["payment methods", "upi", "card", "cash", "wallet", "settlement", "payment breakdown"],
        "schema": {
            "name": "get_payment_methods_breakdown",
            "description": "Retrieve payment method distribution with transaction counts, settled amounts, and percentages.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_menu": {
        "function": get_menu,
        "description": "Fetch the cafe menu with item names, prices in INR, descriptions, and dietary tags from the database.",
        "keywords": ["menu", "drinks", "food", "price", "cost", "latte", "croissant", "pastry", "coffee", "tea", "options", "buy"],
        "schema": {
            "name": "get_menu",
            "description": "Fetch the cafe menu with item names, prices in INR, descriptions, and dietary tags from the database.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "category": {
                        "type": "STRING",
                        "description": "Optional category name filter (e.g. 'Coffee', 'Desserts')."
                    }
                }
            }
        }
    },
    "get_menu_performance": {
        "function": get_menu_performance,
        "description": "Analyze menu items performance, best/worst sellers, quantities sold, revenue, discount given, and identify zero-sales items over a date range.",
        "keywords": ["best", "worst", "perform", "performed", "sold", "least popular", "investigate", "zero sales", "top items", "underperforming", "menu performance", "menu rank", "item revenue", "opportunity"],
        "schema": {
            "name": "get_menu_performance",
            "description": "Analyze menu items performance, best/worst sellers, quantities sold, revenue, discount given, and zero-sales items over a date range.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional category name filter."
                    },
                    "sort_by": {
                        "type": "STRING",
                        "description": "Metric to rank by: 'quantity' (default), 'revenue', 'price', or 'discount'."
                    },
                    "ascending": {
                        "type": "BOOLEAN",
                        "description": "Set to true to get lowest/worst performers first (ascending order), or false for highest/best performers first."
                    },
                    "limit": {
                        "type": "INTEGER",
                        "description": "Maximum number of items to return (1-100, default: 50)."
                    },
                    "include_zero_sales": {
                        "type": "BOOLEAN",
                        "description": "Whether to include menu items with 0 sales in the period (default: true)."
                    }
                }
            }
        }
    },
    "get_category_performance": {
        "function": get_category_performance,
        "description": "Compare sales, volume, revenue share %, average item prices, and top-selling items across all menu categories over a date range.",
        "keywords": ["category performance", "category breakdown", "category sales", "compare categories", "revenue share", "top category", "worst category"],
        "schema": {
            "name": "get_category_performance",
            "description": "Compare sales, volume, revenue share %, average item prices, and top items across all menu categories.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_menu_item_comparison": {
        "function": get_menu_item_comparison,
        "description": "Direct side-by-side performance, pricing, discount, and recipe ingredient comparison for specific menu items or a category over a date range.",
        "keywords": ["compare items", "item comparison", "compare menu items", "pricing analysis", "item deep dive", "recipe ingredients", "item vs item"],
        "schema": {
            "name": "get_menu_item_comparison",
            "description": "Direct side-by-side performance, pricing, discount, and recipe comparison for specific menu items or a category.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "item_names": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "List of specific item names to compare (e.g. ['Butter Chicken', 'Masala Dosa'])."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional category name to compare all items in that category."
                    },
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_feedback_overview": {
        "function": get_feedback_overview,
        "description": "Retrieve comprehensive customer review statistics, overall average rating, rating distributions (1-5 stars), sentiment shares, and complaint issue categories.",
        "keywords": ["feedback", "reviews", "rating", "average rating", "customer satisfaction", "sentiment", "complaints", "issues", "review summary", "stars"],
        "schema": {
            "name": "get_feedback_overview",
            "description": "Retrieve customer review metrics, average rating, 1-5 star distributions, sentiment shares, and issue breakdown.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "menu_item_name": {
                        "type": "STRING",
                        "description": "Optional menu item name filter."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional menu category name filter."
                    }
                }
            }
        }
    },
    "get_item_reviews_summary": {
        "function": get_item_reviews_summary,
        "description": "Retrieve item-specific feedback rankings, praise vs complaints, average ratings per item, and anonymized review text snippets.",
        "keywords": ["item feedback", "dish reviews", "praised items", "complained items", "review text", "customer comments", "item rating", "what do customers say"],
        "schema": {
            "name": "get_item_reviews_summary",
            "description": "Retrieve item-specific ratings, praise/complaint counts, and anonymized review samples.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "menu_item_name": {
                        "type": "STRING",
                        "description": "Optional menu item name to inspect."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional category name filter."
                    },
                    "sentiment": {
                        "type": "STRING",
                        "description": "Optional sentiment filter ('positive', 'neutral', 'negative')."
                    },
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "limit": {
                        "type": "INTEGER",
                        "description": "Maximum number of review samples / items to return (1-50, default: 10)."
                    }
                }
            }
        }
    },
    "get_feedback_trends_and_issues": {
        "function": get_feedback_trends_and_issues,
        "description": "Compare feedback metrics, rating shifts, changing complaint themes, and sentiment delta across consecutive time periods.",
        "keywords": ["feedback trends", "rating change", "complaint trends", "sentiment shift", "feedback comparison", "trending issues", "review trends"],
        "schema": {
            "name": "get_feedback_trends_and_issues",
            "description": "Compare feedback metrics, rating shifts, and issue trends between consecutive periods.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "period_type": {
                        "type": "STRING",
                        "description": "Standard period: '7_days', '14_days', '30_days', or 'custom'."
                    },
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD) for custom comparison."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_inventory_status": {
        "function": get_inventory_status,
        "description": "Retrieve comprehensive inventory status, stock health levels (Critical, Low Stock, Approaching Reorder, Healthy), deficit counts, and prioritized replenishment recommendations.",
        "keywords": ["inventory status", "reorder level", "low stock", "critical stock", "stock health", "replenishment", "supplies status", "on hand stock", "shortage"],
        "schema": {
            "name": "get_inventory_status",
            "description": "Retrieve inventory stock health, critical/low-stock status, deficit amounts, and replenishment priorities.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "low_stock_only": {
                        "type": "BOOLEAN",
                        "description": "If true, only returns items at or below reorder threshold."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional ingredient category filter (e.g. 'dairy_eggs', 'meat', 'produce', 'dry_goods')."
                    },
                    "ingredient_name": {
                        "type": "STRING",
                        "description": "Optional ingredient name filter."
                    }
                }
            }
        }
    },
    "get_ingredient_consumption": {
        "function": get_ingredient_consumption,
        "description": "Calculate historical ingredient consumption from completed orders linked through menu recipes, daily burn rates, estimated days of stock remaining, and stockout risk.",
        "keywords": ["consumption", "ingredient usage", "used ingredients", "burn rate", "recipe consumption", "stockout risk", "estimated runout", "how fast we use"],
        "schema": {
            "name": "get_ingredient_consumption",
            "description": "Calculate recipe-based ingredient consumption from sales, daily burn rates, and run-out projections.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "ingredient_name": {
                        "type": "STRING",
                        "description": "Optional ingredient name filter."
                    },
                    "category": {
                        "type": "STRING",
                        "description": "Optional ingredient category filter."
                    }
                }
            }
        }
    },
    "get_stock_movement_summary": {
        "function": get_stock_movement_summary,
        "description": "Summarize recorded stock movements from stock_movements by movement type (purchase receipts, opening balance, sale consumption), total inflows, total outflows, and net deltas.",
        "keywords": ["stock movements", "inflows", "outflows", "purchase receipts", "stock receipts", "inventory logs", "stock deltas"],
        "schema": {
            "name": "get_stock_movement_summary",
            "description": "Summarize recorded stock movements, receipts, and consumption deltas from stock movement logs.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "ingredient_name": {
                        "type": "STRING",
                        "description": "Optional ingredient name filter."
                    },
                    "movement_type": {
                        "type": "STRING",
                        "description": "Optional movement type filter (e.g. 'purchase_receipt', 'sale_consumption', 'opening_balance')."
                    }
                }
            }
        }
    },
    "get_inventory_variance": {
        "function": get_inventory_variance,
        "description": "Compare recorded stock movement consumption against recipe-based expected consumption from completed orders, identify variances, and evaluate potential waste indicators.",
        "keywords": ["inventory variance", "waste", "waste indicators", "spoilage", "recipe vs actual", "consumption variance", "discrepancy", "shrinkage", "unusual consumption"],
        "schema": {
            "name": "get_inventory_variance",
            "description": "Compare recorded stock movement outflows with recipe-expected consumption to identify operational variances and potential waste indicators.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "ingredient_name": {
                        "type": "STRING",
                        "description": "Optional ingredient name filter."
                    }
                }
            }
        }
    },
    "get_stockout_risk_recommendations": {
        "function": get_stockout_risk_recommendations,
        "description": "Identify menu items and popular dishes whose recipe ingredients are at critical or low stock, calculating sales revenue at risk and replenishment priorities.",
        "keywords": ["stockout risk", "revenue at risk", "stockout recommendations", "ingredient bottleneck", "urgent restock recommendations", "dishes running out"],
        "schema": {
            "name": "get_stockout_risk_recommendations",
            "description": "Identify menu items whose recipe ingredients are at critical or low stock, calculating revenue at risk and replenishment actions.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_quality_and_complaint_recommendations": {
        "function": get_quality_and_complaint_recommendations,
        "description": "Analyze recurring customer review complaints, sentiment patterns, and dishes receiving negative feedback to recommend operational actions (packaging, prep, temperature, portioning).",
        "keywords": ["quality recommendations", "complaint actions", "customer experience recommendations", "packaging fix", "service time fix", "adverse reviews"],
        "schema": {
            "name": "get_quality_and_complaint_recommendations",
            "description": "Analyze customer review complaints and adverse dish ratings to recommend operational quality interventions.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    }
                }
            }
        }
    },
    "get_underperforming_menu_recommendations": {
        "function": get_underperforming_menu_recommendations,
        "description": "Identify zero-sales and low-sales menu items over a period, providing catalog optimization, promotion, or phase-out recommendations.",
        "keywords": ["underperforming menu", "zero sales recommendations", "menu optimization", "delist menu items", "low selling recommendations"],
        "schema": {
            "name": "get_underperforming_menu_recommendations",
            "description": "Identify zero-sales and low-sales menu items to recommend catalog optimization, promotion, or delisting.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "threshold_units": {
                        "type": "INTEGER",
                        "description": "Sales volume threshold below which items are flagged (default: 2)."
                    }
                }
            }
        }
    },
    "get_actionable_recommendations": {
        "function": get_actionable_recommendations,
        "description": "Generate comprehensive, prioritized business recommendations synthesizing inventory stockout risks, quality/complaint interventions, and menu optimization.",
        "keywords": ["recommendations", "decisions", "actionable recommendations", "business recommendations", "what should we do", "action plan", "executive suggestions", "priorities", "suggest actions"],
        "schema": {
            "name": "get_actionable_recommendations",
            "description": "Generate comprehensive, prioritized business recommendations synthesizing inventory, quality, complaints, and menu performance.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "start_date": {
                        "type": "STRING",
                        "description": "Optional ISO start date (YYYY-MM-DD)."
                    },
                    "end_date": {
                        "type": "STRING",
                        "description": "Optional ISO end date (YYYY-MM-DD)."
                    },
                    "focus_area": {
                        "type": "STRING",
                        "description": "Optional focus area: 'inventory', 'quality', 'menu', or 'all'."
                    },
                    "min_priority": {
                        "type": "STRING",
                        "description": "Optional priority cutoff: 'critical', 'high', 'medium', or 'low'."
                    }
                }
            }
        }
    },
    "search_cafe_knowledge": {
        "function": search_cafe_knowledge,
        "description": "Search the cafe standard operating procedures (SOP), employee policies, rules, storage guidelines, customer complaint procedures, and operational knowledge.",
        "keywords": ["policy", "sop", "rule", "rules", "complaint", "complaints", "storing", "storage", "procedure", "guideline", "protocol", "temperature", "threshold", "what should employees do", "reorder threshold"],
        "schema": {
            "name": "search_cafe_knowledge",
            "description": "Search the cafe standard operating procedures (SOP), employee policies, rules, storage guidelines, customer complaint procedures, and operational knowledge.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {
                        "type": "STRING",
                        "description": "The specific question or search query about cafe policies, rules, SOP, or operational guidelines."
                    }
                },
                "required": ["query"]
            }
        }
    },
    "search_restaurant_knowledge": {
        "function": search_restaurant_knowledge_tool,
        "description": "Semantic search across restaurant standard operating procedures (SOP), policies, and manuals using Supabase pgvector with source citations and similarity scores.",
        "keywords": ["knowledge search", "restaurant knowledge", "sop search", "policy retrieval", "food safety sop", "escalation sop", "pgvector search"],
        "schema": {
            "name": "search_restaurant_knowledge",
            "description": "Semantic search across restaurant standard operating procedures (SOP), policies, and manuals using Supabase pgvector.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {
                        "type": "STRING",
                        "description": "The specific question or search query about restaurant policies, rules, or operational SOP."
                    },
                    "top_k": {
                        "type": "INTEGER",
                        "description": "Maximum number of chunks to retrieve (1-10, default: 3)."
                    }
                },
                "required": ["query"]
            }
        }
    }
}
