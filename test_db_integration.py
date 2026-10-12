"""
test_db_integration.py - Validation Suite for Database Connection & Tools
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db import test_connection, execute_query, execute_single
from tools import get_menu, get_inventory, get_today_sales
from agent import CafeAgent


def run_all_tests():
    print("=" * 70)
    print("RUNNING SUPABASE INTEGRATION TEST SUITE")
    print("=" * 70)
    
    results = {}

    # Test 1: Database Connection
    print("\n[Test 1] Testing Database Connection...")
    conn_res = test_connection()
    print(f"Result: {conn_res}")
    results["1_db_connection"] = conn_res.get("status") == "connected"

    # If DB is connected, run data tests
    if results["1_db_connection"]:
        # Test 2: Menu Tool
        print("\n[Test 2] Testing get_menu()...")
        menu_res = get_menu()
        print(f"Status: {menu_res.get('status')}")
        if menu_res.get("status") == "success":
            total_items = menu_res.get("data", {}).get("total_items", 0)
            categories = len(menu_res.get("data", {}).get("categories", []))
            print(f"Retrieved {total_items} items across {categories} categories.")
            results["2_get_menu"] = total_items > 0
        else:
            print(f"Error: {menu_res.get('message')}")
            results["2_get_menu"] = False

        # Test 3: Inventory Tool
        print("\n[Test 3] Testing get_inventory()...")
        inv_res = get_inventory()
        print(f"Status: {inv_res.get('status')}")
        if inv_res.get("status") == "success":
            total_tracked = len(inv_res.get("data", {}))
            low_stock = inv_res.get("summary", {}).get("low_stock_items_count", 0)
            print(f"Retrieved {total_tracked} inventory items ({low_stock} low stock).")
            results["3_get_inventory"] = total_tracked > 0
        else:
            print(f"Error: {inv_res.get('message')}")
            results["3_get_inventory"] = False

        # Test 4: Sales Tool
        print("\n[Test 4] Testing get_today_sales()...")
        sales_res = get_today_sales()
        print(f"Status: {sales_res.get('status')}")
        if sales_res.get("status") == "success":
            s_data = sales_res.get("data", {})
            summary = s_data.get("summary", {})
            print(f"Date: {s_data.get('date')}")
            print(f"Orders: {summary.get('total_orders')}, Revenue: INR {summary.get('total_revenue')}")
            results["4_get_today_sales"] = True
        else:
            print(f"Error: {sales_res.get('message')}")
            results["4_get_today_sales"] = False

        # Test 5: Filtered menu / parameterized input
        print("\n[Test 5] Testing parameterized tool inputs (Category filtering)...")
        filter_res = get_menu(category="NonExistentCategory123")
        print(f"Empty category query result: {filter_res.get('status')}, items: {filter_res.get('data', {}).get('total_items')}")
        results["5_parameterized_inputs"] = filter_res.get("status") == "success" and filter_res.get("data", {}).get("total_items") == 0

        # Test 6: Sales Performance Tool
        print("\n[Test 6] Testing get_sales_performance()...")
        from tools import (
            get_sales_performance,
            get_top_selling_items,
            get_sales_trends_and_comparison,
            get_peak_hours_and_dayparts,
            get_payment_methods_breakdown
        )
        perf_res = get_sales_performance(start_date="2026-10-01", end_date="2026-10-07")
        print(f"Status: {perf_res.get('status')}")
        if perf_res.get("status") == "success":
            p_data = perf_res.get("data", {})
            p_sum = p_data.get("summary", {})
            print(f"Period: {p_data.get('period_start')} to {p_data.get('period_end')}")
            print(f"Completed Orders: {p_sum.get('completed_orders')}, Revenue: INR {p_sum.get('total_revenue_inr')}, AOV: INR {p_sum.get('average_order_value_inr')}")
            print(f"Channels: {len(p_data.get('channel_breakdown', []))}, Discount Given: INR {p_data.get('discount_impact', {}).get('total_discount_given_inr')}")
            results["6_get_sales_performance"] = p_sum.get("completed_orders", 0) > 0
        else:
            print(f"Error: {perf_res.get('message')}")
            results["6_get_sales_performance"] = False

        # Test 7: Top Selling Items Tool
        print("\n[Test 7] Testing get_top_selling_items()...")
        top_res = get_top_selling_items(start_date="2026-10-01", end_date="2026-10-07", limit=3, sort_by="quantity")
        print(f"Status: {top_res.get('status')}")
        if top_res.get("status") == "success":
            top_items = top_res.get("data", {}).get("top_items", [])
            print(f"Top 3 Items: {[it['item_name'] for it in top_items]}")
            results["7_get_top_selling_items"] = len(top_items) > 0
        else:
            print(f"Error: {top_res.get('message')}")
            results["7_get_top_selling_items"] = False

        # Test 8: Sales Trends and Period Comparison Tool
        print("\n[Test 8] Testing get_sales_trends_and_comparison()...")
        trend_res = get_sales_trends_and_comparison(period_type="7_days", end_date="2026-10-08")
        print(f"Status: {trend_res.get('status')}")
        if trend_res.get("status") == "success":
            t_data = trend_res.get("data", {})
            curr_rev = t_data.get("current_period", {}).get("total_revenue_inr")
            prev_rev = t_data.get("previous_period", {}).get("total_revenue_inr")
            growth = t_data.get("comparison_growth", {})
            print(f"Current 7d Rev: INR {curr_rev}, Prior 7d Rev: INR {prev_rev}, Growth: {growth.get('revenue_growth_percentage')}%")
            results["8_get_sales_trends_and_comparison"] = len(t_data.get("daily_trends", [])) > 0
        else:
            print(f"Error: {trend_res.get('message')}")
            results["8_get_sales_trends_and_comparison"] = False

        # Test 9: Peak Hours and Dayparts Tool
        print("\n[Test 9] Testing get_peak_hours_and_dayparts()...")
        peak_res = get_peak_hours_and_dayparts(start_date="2026-10-01", end_date="2026-10-07")
        print(f"Status: {peak_res.get('status')}")
        if peak_res.get("status") == "success":
            pk_data = peak_res.get("data", {})
            busiest = pk_data.get("busiest_hour", {})
            print(f"Busiest Hour: {busiest.get('time_window')} ({busiest.get('order_count')} orders, INR {busiest.get('revenue_inr')})")
            results["9_get_peak_hours_and_dayparts"] = len(pk_data.get("daypart_summary", [])) == 4
        else:
            print(f"Error: {peak_res.get('message')}")
            results["9_get_peak_hours_and_dayparts"] = False

        # Test 10: Payment Methods Breakdown Tool
        print("\n[Test 10] Testing get_payment_methods_breakdown()...")
        pay_res = get_payment_methods_breakdown(start_date="2026-10-01", end_date="2026-10-07")
        print(f"Status: {pay_res.get('status')}")
        if pay_res.get("status") == "success":
            pm_data = pay_res.get("data", {})
            methods = pm_data.get("methods", [])
            print(f"Payment Methods: {[m['payment_method'] for m in methods]}")
            results["10_get_payment_methods_breakdown"] = len(methods) > 0
        else:
            print(f"Error: {pay_res.get('message')}")
            results["10_get_payment_methods_breakdown"] = False

        # Test 13: Menu Performance Tool
        print("\n[Test 13] Testing get_menu_performance()...")
        from tools import (
            get_menu_performance,
            get_category_performance,
            get_menu_item_comparison
        )
        menu_perf_res = get_menu_performance(start_date="2026-10-01", end_date="2026-10-07", sort_by="quantity")
        print(f"Status: {menu_perf_res.get('status')}")
        if menu_perf_res.get("status") == "success":
            mp_data = menu_perf_res.get("data", {})
            mp_summary = mp_data.get("summary", {})
            print(f"Total Menu Items Analyzed: {mp_summary.get('total_menu_items_analyzed')}, Units Sold: {mp_summary.get('total_units_sold')}, Rev: INR {mp_summary.get('total_revenue_inr')}")
            print(f"Zero Sales Items Count: {mp_summary.get('zero_sales_items_count')}")
            results["13_get_menu_performance"] = mp_summary.get("total_menu_items_analyzed", 0) > 0
        else:
            print(f"Error: {menu_perf_res.get('message')}")
            results["13_get_menu_performance"] = False

        # Test 14: Category Performance Tool
        print("\n[Test 14] Testing get_category_performance()...")
        cat_perf_res = get_category_performance(start_date="2026-10-01", end_date="2026-10-07")
        print(f"Status: {cat_perf_res.get('status')}")
        if cat_perf_res.get("status") == "success":
            cp_data = cat_perf_res.get("data", {})
            categories = cp_data.get("categories", [])
            print(f"Categories Analyzed: {len(categories)}, Total Rev: INR {cp_data.get('total_revenue_inr')}")
            for cat in categories[:3]:
                print(f"  - {cat['category_name']}: INR {cat['revenue_inr']} ({cat['revenue_share_percentage']}% share, Top: {cat['top_performing_item']['name']})")
            results["14_get_category_performance"] = len(categories) > 0
        else:
            print(f"Error: {cat_perf_res.get('message')}")
            results["14_get_category_performance"] = False

        # Test 15: Menu Item Comparison Tool
        print("\n[Test 15] Testing get_menu_item_comparison()...")
        comp_res = get_menu_item_comparison(item_names=["Butter Chicken", "Masala Dosa"], start_date="2026-10-01", end_date="2026-10-07")
        print(f"Status: {comp_res.get('status')}")
        if comp_res.get("status") == "success":
            comp_data = comp_res.get("data", {})
            items = comp_data.get("compared_items", [])
            print(f"Compared {len(items)} items: {[it['item_name'] for it in items]}")
            results["15_get_menu_item_comparison"] = len(items) == 2
        else:
            print(f"Error: {comp_res.get('message')}")
            results["15_get_menu_item_comparison"] = False

        # Test 17: Feedback Overview Tool
        print("\n[Test 17] Testing get_feedback_overview()...")
        from tools import (
            get_feedback_overview,
            get_item_reviews_summary,
            get_feedback_trends_and_issues
        )
        fb_res = get_feedback_overview(start_date="2026-09-01", end_date="2026-10-08")
        print(f"Status: {fb_res.get('status')}")
        if fb_res.get("status") == "success":
            fb_data = fb_res.get("data", {})
            fb_summary = fb_data.get("summary", {})
            print(f"Total Reviews: {fb_summary.get('total_reviews')}, Avg Rating: {fb_summary.get('average_rating')}, Positive %: {fb_summary.get('positive_sentiment_percentage')}")
            print(f"Issues: {[iss['issue_category'] for iss in fb_data.get('issue_breakdown', [])]}")
            results["17_get_feedback_overview"] = fb_summary.get("total_reviews", 0) > 0
        else:
            print(f"Error: {fb_res.get('message')}")
            results["17_get_feedback_overview"] = False

        # Test 18: Item Reviews Summary Tool
        print("\n[Test 18] Testing get_item_reviews_summary()...")
        item_fb_res = get_item_reviews_summary(menu_item_name="Butter Chicken", start_date="2026-08-01", end_date="2026-10-08", limit=3)
        print(f"Status: {item_fb_res.get('status')}")
        if item_fb_res.get("status") == "success":
            ifb_data = item_fb_res.get("data", {})
            items_s = ifb_data.get("items_summary", [])
            samples = ifb_data.get("sample_reviews", [])
            print(f"Item Summary: {[it['item_name'] for it in items_s]}, Sample Reviews: {len(samples)}")
            results["18_get_item_reviews_summary"] = len(items_s) > 0
        else:
            print(f"Error: {item_fb_res.get('message')}")
            results["18_get_item_reviews_summary"] = False

        # Test 19: Feedback Trends and Issues Tool
        print("\n[Test 19] Testing get_feedback_trends_and_issues()...")
        trend_fb_res = get_feedback_trends_and_issues(period_type="30_days", end_date="2026-10-08")
        print(f"Status: {trend_fb_res.get('status')}")
        if trend_fb_res.get("status") == "success":
            tfb_data = trend_fb_res.get("data", {})
            comp = tfb_data.get("comparison", {})
            print(f"Rating Delta: {comp.get('average_rating_delta')}, Volume Change: {comp.get('review_volume_change')}, Sentiment Shift: {comp.get('positive_sentiment_shift')}%")
            results["19_get_feedback_trends_and_issues"] = tfb_data.get("current_period", {}).get("review_count", 0) > 0
        else:
            print(f"Error: {trend_fb_res.get('message')}")
            results["19_get_feedback_trends_and_issues"] = False

        # Test 21: Inventory Status Tool
        print("\n[Test 21] Testing get_inventory_status()...")
        from tools import (
            get_inventory_status,
            get_ingredient_consumption,
            get_stock_movement_summary,
            get_inventory_variance
        )
        inv_status_res = get_inventory_status()
        print(f"Status: {inv_status_res.get('status')}")
        if inv_status_res.get("status") == "success":
            inv_data = inv_status_res.get("data", {})
            inv_sum = inv_data.get("summary", {})
            print(f"Total: {inv_sum.get('total_items')}, Critical: {inv_sum.get('critical_items_count')}, Low Stock: {inv_sum.get('low_stock_items_count')}")
            print(f"Priorities: {[p['ingredient_name'] for p in inv_data.get('replenishment_priorities', [])[:3]]}")
            results["21_get_inventory_status"] = inv_sum.get("total_items", 0) > 0
        else:
            print(f"Error: {inv_status_res.get('message')}")
            results["21_get_inventory_status"] = False

        # Test 22: Ingredient Consumption Tool
        print("\n[Test 22] Testing get_ingredient_consumption()...")
        cons_res = get_ingredient_consumption(start_date="2026-10-01", end_date="2026-10-08")
        print(f"Status: {cons_res.get('status')}")
        if cons_res.get("status") == "success":
            c_data = cons_res.get("data", {})
            top_vel = c_data.get("top_consumed_by_velocity", [])
            print(f"Ingredients Consumed: {c_data.get('ingredients_analyzed_count')}, Top Velocity: {[v['ingredient_name'] for v in top_vel[:3]]}")
            results["22_get_ingredient_consumption"] = len(top_vel) > 0
        else:
            print(f"Error: {cons_res.get('message')}")
            results["22_get_ingredient_consumption"] = False

        # Test 23: Stock Movement Summary Tool
        print("\n[Test 23] Testing get_stock_movement_summary()...")
        sm_res = get_stock_movement_summary(start_date="2026-10-01", end_date="2026-10-08")
        print(f"Status: {sm_res.get('status')}")
        if sm_res.get("status") == "success":
            sm_data = sm_res.get("data", {})
            print(f"Total Movement Records: {sm_data.get('total_movements_count')}, Types: {len(sm_data.get('movement_types_summary', []))}")
            results["23_get_stock_movement_summary"] = sm_data.get("total_movements_count", 0) > 0
        else:
            print(f"Error: {sm_res.get('message')}")
            results["23_get_stock_movement_summary"] = False

        # Test 24: Inventory Variance Tool
        print("\n[Test 24] Testing get_inventory_variance()...")
        var_res = get_inventory_variance(start_date="2026-10-01", end_date="2026-10-08")
        print(f"Status: {var_res.get('status')}")
        if var_res.get("status") == "success":
            var_data = var_res.get("data", {})
            var_sum = var_data.get("summary", {})
            print(f"Analyzed: {var_data.get('ingredients_analyzed_count')}, Exact Matches: {var_sum.get('exact_matches_count')}, Elevated: {var_sum.get('elevated_outflows_count')}")
            results["24_get_inventory_variance"] = var_data.get("ingredients_analyzed_count", 0) > 0
        else:
            print(f"Error: {var_res.get('message')}")
            results["24_get_inventory_variance"] = False

        # Test 26: Stockout Risk Recommendations Tool
        print("\n[Test 26] Testing get_stockout_risk_recommendations()...")
        from tools import (
            get_stockout_risk_recommendations,
            get_quality_and_complaint_recommendations,
            get_underperforming_menu_recommendations,
            get_actionable_recommendations
        )
        stock_rec = get_stockout_risk_recommendations(start_date="2026-10-02", end_date="2026-10-08")
        print(f"Status: {stock_rec.get('status')}")
        if stock_rec.get("status") == "success":
            s_data = stock_rec.get("data", {})
            print(f"Stockout Risks Identified: {s_data.get('total_stockout_risks')}")
            results["26_get_stockout_risk_recommendations"] = s_data.get("data_origin") == "SYNTHETIC" and s_data.get("total_stockout_risks", 0) > 0
        else:
            print(f"Error: {stock_rec.get('message')}")
            results["26_get_stockout_risk_recommendations"] = False

        # Test 27: Quality & Complaint Recommendations Tool
        print("\n[Test 27] Testing get_quality_and_complaint_recommendations()...")
        qlt_rec = get_quality_and_complaint_recommendations(start_date="2026-09-08", end_date="2026-10-08")
        print(f"Status: {qlt_rec.get('status')}")
        if qlt_rec.get("status") == "success":
            q_data = qlt_rec.get("data", {})
            print(f"Quality Interventions: {q_data.get('total_quality_recommendations')}")
            results["27_get_quality_and_complaint_recommendations"] = q_data.get("data_origin") == "SYNTHETIC" and q_data.get("total_quality_recommendations", 0) > 0
        else:
            print(f"Error: {qlt_rec.get('message')}")
            results["27_get_quality_and_complaint_recommendations"] = False

        # Test 28: Underperforming Menu Recommendations Tool
        print("\n[Test 28] Testing get_underperforming_menu_recommendations()...")
        mnu_rec = get_underperforming_menu_recommendations(start_date="2026-10-02", end_date="2026-10-08", threshold_units=2)
        print(f"Status: {mnu_rec.get('status')}")
        if mnu_rec.get("status") == "success":
            m_data = mnu_rec.get("data", {})
            print(f"Zero Sales: {m_data.get('zero_sales_count')}, Low Sales: {m_data.get('low_sales_count')}")
            results["28_get_underperforming_menu_recommendations"] = m_data.get("data_origin") == "SYNTHETIC" and m_data.get("zero_sales_count", 0) > 0
        else:
            print(f"Error: {mnu_rec.get('message')}")
            results["28_get_underperforming_menu_recommendations"] = False

        # Test 29: Actionable Recommendations Synthesis Tool
        print("\n[Test 29] Testing get_actionable_recommendations()...")
        act_rec = get_actionable_recommendations(start_date="2026-10-02", end_date="2026-10-08")
        print(f"Status: {act_rec.get('status')}")
        if act_rec.get("status") == "success":
            a_data = act_rec.get("data", {})
            print(f"Total Recommendations: {a_data.get('total_recommendations')}, Breakdown: {a_data.get('priority_breakdown')}")
            results["29_get_actionable_recommendations"] = a_data.get("data_origin") == "SYNTHETIC" and a_data.get("total_recommendations", 0) > 0
        else:
            print(f"Error: {act_rec.get('message')}")
            results["29_get_actionable_recommendations"] = False

        # Test 31: Supabase pgvector Knowledge Retrieval
        print("\n[Test 31] Testing search_restaurant_knowledge()...")
        from rag.retrieval import search_restaurant_knowledge
        rag_res = search_restaurant_knowledge("What are the rules for storing milk?", top_k=2)
        print(f"Status: {rag_res.get('status')}")
        if rag_res.get("status") == "success":
            print(f"Results: {rag_res.get('total_results')}, Citations: {rag_res.get('citations')}")
            results["31_search_restaurant_knowledge"] = (
                rag_res.get("total_results", 0) > 0
                and len(rag_res.get("citations", [])) > 0
                and rag_res.get("data_origin") == "SYNTHETIC"
            )
        else:
            print(f"Error: {rag_res.get('message')}")
            results["31_search_restaurant_knowledge"] = False

        # Test 32: search_cafe_knowledge Tool (pgvector backed)
        print("\n[Test 32] Testing search_cafe_knowledge()...")
        from tools import search_cafe_knowledge
        cafe_res = search_cafe_knowledge(query="customer complaints procedure")
        print(f"Status: {cafe_res.get('status')}")
        if cafe_res.get("status") == "success":
            print(f"Retrieved Chunks: {len(cafe_res.get('retrieved_chunks', []))}")
            results["32_search_cafe_knowledge"] = len(cafe_res.get("retrieved_chunks", [])) > 0
        else:
            print(f"Error: {cafe_res.get('message')}")
            results["32_search_cafe_knowledge"] = False

    else:
        print("\n[!] Database is not reachable with current DATABASE_URL. Skipping data extraction tests.")
        results["2_get_menu"] = False
        results["3_get_inventory"] = False
        results["4_get_today_sales"] = False
        results["5_parameterized_inputs"] = False
        results["6_get_sales_performance"] = False
        results["7_get_top_selling_items"] = False
        results["8_get_sales_trends_and_comparison"] = False
        results["9_get_peak_hours_and_dayparts"] = False
        results["10_get_payment_methods_breakdown"] = False
        results["13_get_menu_performance"] = False
        results["14_get_category_performance"] = False
        results["15_get_menu_item_comparison"] = False
        results["17_get_feedback_overview"] = False
        results["18_get_item_reviews_summary"] = False
        results["19_get_feedback_trends_and_issues"] = False
        results["21_get_inventory_status"] = False
        results["22_get_ingredient_consumption"] = False
        results["23_get_stock_movement_summary"] = False
        results["24_get_inventory_variance"] = False
        results["26_get_stockout_risk_recommendations"] = False
        results["27_get_quality_and_complaint_recommendations"] = False
        results["28_get_underperforming_menu_recommendations"] = False
        results["29_get_actionable_recommendations"] = False
        results["31_search_restaurant_knowledge"] = False
        results["32_search_cafe_knowledge"] = False

    # Test 11: Safe Error Handling / No Mock Fallback
    print("\n[Test 11] Testing Agent Error Handling (No mock fallback on failure)...")
    agent = CafeAgent(name="TestBot")
    agent_res = agent.synthesize_response("What is on the menu?", "get_menu", {"status": "error", "message": "Database connection timed out"})
    print(f"Agent Synthesis Output on DB Error: {agent_res}")
    results["11_no_mock_fallback"] = "Error executing get_menu" in agent_res and "mock" not in agent_res.lower()

    # Test 12: SalesIntelligenceAgent Simulation Execution
    print("\n[Test 12] Testing SalesIntelligenceAgent Simulation...")
    from agent import SalesIntelligenceAgent
    sales_agent = SalesIntelligenceAgent()
    sales_agent_res = sales_agent.run_simulation("Which menu items sold the most during the last seven days?")
    print(f"Sales Agent Output:\n{sales_agent_res.get('final_response')}")
    results["12_sales_agent_simulation"] = len(sales_agent_res.get("executed_tools", [])) > 0 and "Top Selling Items" in sales_agent_res.get("final_response", "")

    # Test 16: MenuIntelligenceAgent Simulation Execution
    print("\n[Test 16] Testing MenuIntelligenceAgent Simulation...")
    from agent import MenuIntelligenceAgent
    menu_agent = MenuIntelligenceAgent()
    menu_agent_res = menu_agent.run_simulation("What was our menu performance and best sellers over the last seven days?")
    print(f"Menu Agent Output:\n{menu_agent_res.get('final_response')}")
    results["16_menu_agent_simulation"] = len(menu_agent_res.get("executed_tools", [])) > 0 and "Menu Performance Analysis" in menu_agent_res.get("final_response", "")

    # Test 20: FeedbackIntelligenceAgent Simulation Execution
    print("\n[Test 20] Testing FeedbackIntelligenceAgent Simulation...")
    from agent import FeedbackIntelligenceAgent
    feedback_agent = FeedbackIntelligenceAgent()
    feedback_agent_res = feedback_agent.run_simulation("What are our overall customer reviews and top complaints?")
    print(f"Feedback Agent Output:\n{feedback_agent_res.get('final_response')}")
    results["20_feedback_agent_simulation"] = len(feedback_agent_res.get("executed_tools", [])) > 0 and "Customer Feedback Overview" in feedback_agent_res.get("final_response", "")

    # Test 25: InventoryIntelligenceAgent Simulation Execution
    print("\n[Test 25] Testing InventoryIntelligenceAgent Simulation...")
    from agent import InventoryIntelligenceAgent
    inventory_agent = InventoryIntelligenceAgent()
    inventory_agent_res = inventory_agent.run_simulation("Which ingredients are running low on stock and need replenishment?")
    print(f"Inventory Agent Output:\n{inventory_agent_res.get('final_response')}")
    results["25_inventory_agent_simulation"] = len(inventory_agent_res.get("executed_tools", [])) > 0 and "Inventory Status & Stock Health Overview" in inventory_agent_res.get("final_response", "")

    # Test 30: DecisionRecommendationAgent Simulation Execution
    print("\n[Test 30] Testing DecisionRecommendationAgent Simulation...")
    from agent import DecisionRecommendationAgent
    rec_agent = DecisionRecommendationAgent()
    rec_agent_res = rec_agent.run_simulation("What are our top executive recommendations to improve operations and protect revenue?")
    print(f"Recommendation Agent Output:\n{rec_agent_res.get('final_response')}")
    results["30_recommendation_agent_simulation"] = (
        len(rec_agent_res.get("executed_tools", [])) > 0
        and "Executive Decision & Action Plan" in rec_agent_res.get("final_response", "")
        and "SYNTHETIC" in rec_agent_res.get("final_response", "")
    )

    # Test 33: RAG Knowledge Agent Simulation Execution
    print("\n[Test 33] Testing CafeAgent RAG Knowledge Simulation...")
    knowledge_agent = CafeAgent(name="BaristaBot")
    know_agent_res = knowledge_agent.run_simulation("What is our milk storage policy and SOP?")
    print(f"Knowledge Agent Output:\n{know_agent_res.get('final_response')}")
    results["33_rag_knowledge_agent_simulation"] = (
        len(know_agent_res.get("executed_tools", [])) > 0
        and "According to Cafe SOP / Policy Guidelines" in know_agent_res.get("final_response", "")
        and "SYNTHETIC" in know_agent_res.get("final_response", "")
    )

    # Test 34: AgentOrchestrator Single-Domain Live Routing & Execution
    print("\n[Test 34] Testing AgentOrchestrator Single-Domain Live Routing & Execution...")
    from orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator()
    orch_res_sales = orchestrator.orchestrate("How many orders did we complete last week?", run_mode="simulation")
    print(f"Orchestrator Single-Domain Output:\nStatus: {orch_res_sales.get('status')} | Route: {orch_res_sales.get('route')}")
    results["34_orchestrator_single_domain"] = (
        orch_res_sales.get("status") == "success"
        and orch_res_sales.get("route") == ["sales"]
        and len(orch_res_sales.get("evidence_sources", [])) > 0
        and ("Sales Performance Analysis" in orch_res_sales.get("answer", "") or "sales summary" in orch_res_sales.get("answer", "").lower())
        and orch_res_sales.get("data_origin") == "SYNTHETIC"
    )

    # Test 35: AgentOrchestrator Multi-Agent Live Execution & Synthesis
    print("\n[Test 35] Testing AgentOrchestrator Multi-Agent Live Execution & Synthesis...")
    orch_res_multi = orchestrator.orchestrate(
        "Our popular dishes are receiving poor ratings and ingredients are running low. What should we do?",
        run_mode="simulation"
    )
    print(f"Orchestrator Multi-Agent Output:\nStatus: {orch_res_multi.get('status')} | Route: {orch_res_multi.get('route')}")
    results["35_orchestrator_multi_agent"] = (
        orch_res_multi.get("status") == "success"
        and set(orch_res_multi.get("route", [])) >= {"menu", "feedback", "inventory", "recommendations"}
        and len(orch_res_multi.get("selected_agents", [])) >= 4
        and len(orch_res_multi.get("evidence_sources", [])) >= 3
        and orch_res_multi.get("data_origin") == "SYNTHETIC"
        and len(orch_res_multi.get("limitations", [])) >= 3
    )

    print("\n" + "=" * 70)
    print("TEST SUMMARY:")
    for test_name, passed in results.items():
        mark = "[PASS]" if passed else "[FAIL / UNREACHABLE]"
        print(f"  - {test_name}: {mark}")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()


