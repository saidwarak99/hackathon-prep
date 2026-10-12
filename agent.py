"""
agent.py - The Cafe AI Agent Architecture

This file implements the core Agent logic.

WHAT IS AN AI AGENT?
-------------------
An AI Agent is a system that can:
1. Perceive an input (a user's request).
2. Reason & Decide what actions (if any) are required to satisfy the request.
3. Execute Tools (actions like database queries, API calls, calculations).
4. Observe the tool results.
5. Synthesize a final, helpful response for the user.

THE AGENT LOOP:
---------------
  [User Request]
        │
        ▼
  [Step 1: Planning / Decision]  <-- Which tool should I call, and why?
        │
        ├──────────── If no tool needed ─────────────┐
        │                                            │
        ▼ (Tool decided)                             ▼
  [Step 2: Tool Execution]                     [Direct Response]
        │                                            │
        ▼                                            │
  [Step 3: Tool Observation] (Raw Data)              │
        │                                            │
        ▼                                            │
  [Step 4: Response Synthesis]                       │
        │                                            │
        └───────────────────┬────────────────────────┘
                            ▼
                    [Final Response]

NOTE ON LLM REASONING:
In a production system, an LLM replaces the hardcoded `decide_tool()` logic
and the `synthesize_response()` template logic. The LLM reads the tool schemas,
decides when to call a tool via JSON, and summarizes the tool output in natural language.
"""

import sys
import json
from typing import Dict, Any, Optional, List
from tools import TOOL_REGISTRY

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_print(*args, **kwargs):
    """Safely print text avoiding Windows charmap/cp1252 UnicodeEncodeError."""
    try:
        print(*args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            sanitized = [str(a).encode("ascii", errors="replace").decode("ascii") for a in args]
            print(*sanitized, **kwargs)
        except Exception:
            pass


class CafeAgent:
    """
    A simulated AI Agent designed for cafe operations management.
    Demonstrates the fundamental control loop and tool-use mechanics of an agent.
    """

    def __init__(self, name: str = "BaristaBot", llm_provider=None, dataset_id: Optional[str] = None):
        self.name = name
        self.tools = TOOL_REGISTRY
        self.llm_provider = llm_provider
        self.dataset_id = dataset_id

    # -------------------------------------------------------------------------
    # STEP 1: DECISION LOGIC (Reasoning) - Simulation Fallback
    # -------------------------------------------------------------------------
    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Analyzes the user's request to decide which tool is required.

        In an actual LLM, this step is handled by prompting the model with:
        - The user request
        - Tool definitions (name, description, parameters)
        The LLM outputs a function call JSON.

        Here, we use explicit keyword and intent matching to clearly expose
        the decision process.
        """
        request_lower = user_request.lower()

        # Check for inventory / stock intent
        for kw in self.tools["get_inventory"]["keywords"]:
            if kw in request_lower:
                return {
                    "tool_name": "get_inventory",
                    "reason": f"User is asking about supplies/stock (matched keyword: '{kw}'). Needs live inventory data."
                }

        # Check for sales / revenue intent
        for kw in self.tools["get_today_sales"]["keywords"]:
            if kw in request_lower:
                return {
                    "tool_name": "get_today_sales",
                    "reason": f"User is asking about financial metrics or order volume (matched keyword: '{kw}'). Needs POS sales data."
                }

        # Check for menu / price intent
        for kw in self.tools["get_menu"]["keywords"]:
            if kw in request_lower:
                return {
                    "tool_name": "get_menu",
                    "reason": f"User is asking about menu items, drinks, or pricing (matched keyword: '{kw}'). Needs cafe menu data."
                }

        # Check for knowledge / policy / SOP intent
        for kw in self.tools["search_cafe_knowledge"]["keywords"]:
            if kw in request_lower:
                return {
                    "tool_name": "search_cafe_knowledge",
                    "reason": f"User is asking about policies, SOP, or operational knowledge (matched keyword: '{kw}'). Needs RAG retrieval."
                }

        # Check for common greetings
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
        if any(g in request_lower for g in greetings):
            return {
                "tool_name": None,
                "reason": "Greeting or general introduction. No external data lookup is required."
            }

        # Out-of-scope or unhandled intent
        return {
            "tool_name": None,
            "reason": "No cafe tools match this request. Request appears out of operational scope."
        }

    # -------------------------------------------------------------------------
    # STEP 2: TOOL EXECUTION (Action)
    # -------------------------------------------------------------------------
    def execute_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the chosen tool function and catches any errors.
        Supports optional arguments dictionary for parameterized tools like RAG search.
        """
        if tool_name not in self.tools:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not found in registry."
            }

        tool_info = self.tools[tool_name]
        tool_function = tool_info["function"]
        args = dict(arguments) if arguments else {}
        if self.dataset_id and "dataset_id" not in args:
            args["dataset_id"] = self.dataset_id

        try:
            if args:
                try:
                    result = tool_function(**args)
                except TypeError:
                    # Retry without dataset_id if tool signature does not accept it
                    filtered = {k: v for k, v in args.items() if k != "dataset_id"}
                    if filtered:
                        result = tool_function(**filtered)
                    else:
                        result = tool_function()
            else:
                result = tool_function()
            return result
        except TypeError:
            # Fallback if argument signature doesn't match
            result = tool_function()
            return result

    # -------------------------------------------------------------------------
    # STEP 3: RESPONSE SYNTHESIS (Final Response Generation) - Simulation Fallback
    # -------------------------------------------------------------------------
    def synthesize_response(
        self,
        user_request: str,
        tool_name: Optional[str],
        tool_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Takes the user request and tool results to synthesize a natural,
        human-readable answer.

        In an LLM system, the LLM receives the tool result in the conversation history
        as `{"role": "tool", "content": "..."}` and generates natural language.
        Here, we explicitly format the data into a helpful response.
        """
        # Case A: No tool was called
        if tool_name is None:
            req_lower = user_request.lower()
            if any(g in req_lower for g in ["hi", "hello", "hey", "who are you", "what can you do", "help"]):
                return (
                    f"Hello! I am {self.name}, your Cafe Operations AI Assistant.\n"
                    "I can help you monitor inventory, check today's sales and revenue, "
                    "review our current menu, or search cafe standard operating procedures (SOP). How can I assist you today?"
                )
            return (
                f"I'm sorry, but as the Cafe Assistant, I specialize in cafe operations. "
                f"I don't have tools or data to assist with: '{user_request}'."
            )

        if tool_result and tool_result.get("status") == "error":
            return f"Error executing {tool_name}: {tool_result.get('message', 'Unknown database error')}"

        data = tool_result.get("data", {}) if tool_result else {}

        # Case B: Synthesizing Inventory Response
        if tool_name == "get_inventory":
            low_stock_items = [
                f"- {item['item_name']}: {item['current_stock']} {item['unit']} (Reorder threshold: {item['min_reorder_level']} {item['unit']})"
                for item in data.values()
                if "Low Stock" in item.get("status", "")
            ]
            total_items = len(data)
            low_stock_summary = "\n".join(low_stock_items) if low_stock_items else "All items are well stocked!"
            rec = f"\n\nRecommendation: Place orders for low-stock items promptly." if low_stock_items else ""

            return (
                f"Here is the current inventory status:\n"
                f"* Total tracked items: {total_items}\n"
                f"* Attention needed (Low Stock Items):\n{low_stock_summary}{rec}"
            )

        # Case C: Synthesizing Today's Sales Response
        if tool_name == "get_today_sales":
            summary = data.get("summary", {})
            top_items = data.get("top_selling_items", [])
            top_list = "\n".join([f"    {idx+1}. {item['item']} ({item['quantity_sold']} sold - INR {item['revenue']:.2f})" for idx, item in enumerate(top_items[:5])]) if top_items else "    No top items recorded."

            return (
                f"Here is the sales summary for {data.get('date')}:\n"
                f"* Total Revenue: INR {summary.get('total_revenue', 0.0):.2f}\n"
                f"* Total Orders: {summary.get('total_orders', 0)}\n"
                f"* Average Order Value: INR {summary.get('average_order_value', 0.0):.2f}\n"
                f"* Peak Hours: {summary.get('busiest_hour')}\n\n"
                f"Top Best Sellers:\n{top_list}"
            )

        # Case D: Synthesizing Menu Response
        if tool_name == "get_menu":
            categories = data.get("categories", [])
            menu_lines = []
            for cat in categories:
                menu_lines.append(f"\n[Category: {cat['category_name']}]")
                for item in cat.get("items", []):
                    dietary_str = f" [{', '.join(item['dietary'])}]" if item.get("dietary") else ""
                    menu_lines.append(f"  * {item['name']} - INR {item['price']:.2f}{dietary_str}")
                    if item.get('description'):
                        menu_lines.append(f"    -> {item['description']}")

            return "Here is our current cafe menu:\n" + ("\n".join(menu_lines) if menu_lines else "No menu items available.")

        # Case E: Synthesizing Knowledge / RAG Response
        if tool_name in ("search_cafe_knowledge", "search_restaurant_knowledge"):
            if tool_result and tool_result.get("status") == "no_results":
                return "According to Cafe SOP & Policy Guidelines: The available documents do not contain enough information to answer this inquiry."
            chunks = tool_result.get("retrieved_chunks", []) if tool_result else []
            citations = tool_result.get("citations", []) if tool_result else []
            citations_str = f" (Sources: {', '.join(citations)})" if citations else ""
            if chunks:
                formatted_chunks = "\n".join([f"- {c}" for c in chunks])
                return (
                    f"According to Cafe SOP / Policy Guidelines{citations_str}:\n{formatted_chunks}\n\n"
                    f"* Evidence Source: Supabase pgvector semantic retrieval. Data origin: SYNTHETIC."
                )
            return "No relevant policy documents were found for this inquiry."


        return "I completed the action, but have no specific formatter for this tool."

    # -------------------------------------------------------------------------
    # REAL MULTI-TOOL LLM RUN CYCLE
    # -------------------------------------------------------------------------
    def run_llm(self, user_request: str) -> Dict[str, Any]:
        """
        Executes the LLM-powered multi-tool agent workflow.

        THE MULTI-TOOL AGENT LOOP:
        --------------------------
        1. CONVERSATION HISTORY:
           The agent starts by initializing a conversation history with the user's prompt.
           As tools are selected and executed, both the LLM's tool-call requests and the
           corresponding tool outputs are appended sequentially to the conversation history.

        2. TOOL CALLS & EXECUTION:
           The LLM inspects the available tool schemas (including database tools and RAG search)
           and decides which tool (if any) to call. When a tool call is received, the agent
           executes the local Python tool and captures the structured output.

        3. TOOL RESULTS & LOOP CONTINUATION:
           The tool result is formatted and appended to the conversation history as a 'tool'
           role message. The updated conversation history is sent back to Gemini.
           Gemini analyzes the result and either:
           - Requests ANOTHER tool (the loop continues to fetch more context), or
           - Returns a natural language answer grounded on tool observations and RAG context.

        4. STOPPING CONDITION:
           The loop terminates when Gemini returns a text response without requesting any
           further tool calls, signifying it has sufficient information to answer the user.

        5. MAXIMUM ITERATION PROTECTION:
           To protect against potential infinite loops, a hard upper limit (default: 8 iterations) is enforced.
        """
        print("\n" + "=" * 70)
        print(f"[LLM MULTI-TOOL AGENT LOOP STARTED]")
        print(f"User Request: \"{user_request}\"")
        print("=" * 70)

        # 1. Initialize Conversation History and Tool Schemas
        messages = [{"role": "user", "content": user_request}]
        tool_schemas = [info["schema"] for name, info in self.tools.items()]

        max_iterations = 8  # Safety limit: Maximum tool turns allowed
        step_number = 1
        executed_tools = []
        final_text = ""

        # Session tool execution cache to avoid redundant queries and protect quota
        tool_cache: Dict[str, Dict[str, Any]] = {}
        tool_call_counts: Dict[str, int] = {}

        # Main Multi-Tool Loop
        system_instruction = getattr(self, "system_prompt", None)
        for iteration in range(1, max_iterations + 1):
            # Send current conversation history and available tool definitions to LLM
            response = self.llm_provider.generate(
                messages,
                tool_schemas,
                system_instruction=system_instruction
            )

            # Check if LLM requested a tool execution
            if response["type"] == "tool_call":
                tool_name = response["tool_name"]
                tool_args = response.get("arguments", {})

                # STEP: LLM DECISION (Tool Selected)
                print(f"\n[STEP {step_number}: LLM DECISION]")
                print(f"Tool requested: {tool_name}")
                if tool_args:
                    print(f"Arguments     : {tool_args}")
                print(f"Reason        : LLM determined '{tool_name}' is needed to fulfill the request.")
                step_number += 1

                # Normalize arguments to create deterministic cache key
                norm_args = json.dumps({k: v for k, v in sorted(tool_args.items()) if v is not None}, sort_keys=True) if isinstance(tool_args, dict) else ""
                call_key = f"{tool_name}:{norm_args}"
                tool_call_counts[call_key] = tool_call_counts.get(call_key, 0) + 1
                repeat_count = tool_call_counts[call_key]

                # STEP: TOOL EXECUTION (with caching and loop detection)
                print(f"\n[STEP {step_number}: TOOL EXECUTION]")
                if call_key in tool_cache:
                    print(f"   [TOOL CACHE HIT] Reusing cached result for {tool_name}() (repeat count: {repeat_count})")
                    tool_result = tool_cache[call_key]
                    tool_content_for_llm = dict(tool_result)

                    if repeat_count == 2:
                        tool_content_for_llm["_cache_notice"] = (
                            "This exact data was already retrieved in a previous turn. "
                            "Please use this data to synthesize your final response rather than repeating tool calls."
                        )
                    elif repeat_count >= 3:
                        print(f"[!] [REPETITIVE LOOP PROTECTION] Tool '{tool_name}' requested {repeat_count} times with identical arguments. Halting tool loop to prevent quota exhaustion.")
                        executed_tools.append({"tool_name": tool_name, "arguments": tool_args, "result": tool_result, "cached": True})
                        final_text = self.synthesize_response(user_request, tool_name, tool_result)
                        break
                else:
                    print(f"Executing {tool_name}()")
                    tool_result = self.execute_tool(tool_name, tool_args)
                    if tool_result.get("status") == "success":
                        tool_cache[call_key] = tool_result
                    tool_content_for_llm = tool_result

                executed_tools.append({"tool_name": tool_name, "arguments": tool_args, "result": tool_result, "cached": (call_key in tool_cache and repeat_count > 1)})
                step_number += 1

                # STEP: TOOL RESULT (Observation)
                print(f"\n[STEP {step_number}: TOOL RESULT]")
                print(f"Status : {tool_result.get('status', 'success')}")
                
                # Special logging for RAG knowledge retrieval
                if tool_name in ("search_cafe_knowledge", "search_restaurant_knowledge"):
                    print("\n[RETRIEVED KNOWLEDGE]")
                    chunks = tool_result.get("retrieved_chunks", [])
                    citations = tool_result.get("citations", [])
                    if chunks:
                        for i, chunk in enumerate(chunks, 1):
                            cit = f" [{citations[i-1]}]" if i <= len(citations) else ""
                            safe_print(f"--- Chunk {i}{cit} ---\n{chunk}\n")
                    else:
                        print("No chunks retrieved.")
                else:
                    data_keys = list(tool_result.get("data", {}).keys()) if isinstance(tool_result.get("data"), dict) else []
                    if data_keys:
                        print(f"Data Preview: Keys received -> {data_keys[:5]}")
                step_number += 1

                # Update Conversation History:
                # 1. Add assistant's tool-call request
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{"name": tool_name, "arguments": tool_args}]
                })
                # 2. Add tool's execution output
                messages.append({
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": tool_content_for_llm
                })

                # Log why the loop continues
                print(f"[LOOP CONTINUATION] Tool result added to history; querying LLM for next decision or final answer...")

            elif response["type"] == "text":
                # STOPPING CONDITION REACHED: LLM produced final text response
                print(f"\n[STEP {step_number}: LLM DECISION]")
                if executed_tools:
                    print(f"LLM completed all required tool calls ({len(executed_tools)} tools executed).")
                    print(f"Stopping condition reached: Synthesizing final natural language response.")
                else:
                    print(f"LLM decided no external tools are needed for this request.")
                
                final_text = response.get("content", "").strip()
                if not final_text:
                    final_text = "Task completed successfully based on gathered data."
                break
        else:
            # Reached if loop exhausted max_iterations without breaking
            print(f"\n[!] [MAX ITERATION PROTECTION] Exceeded {max_iterations} iterations. Finalizing response...")
            final_text = "The agent reached the maximum allowed tool iterations. Please refine your query."

        safe_print(f"\n[FINAL LLM RESPONSE]:")
        safe_print("-" * 70)
        safe_print(final_text)
        safe_print("-" * 70)

        return {
            "user_request": user_request,
            "executed_tools": executed_tools,
            "final_response": final_text,
            "mode": "llm"
        }

    # -------------------------------------------------------------------------
    # THE COMPLETE AGENT RUN CYCLE (Router)
    # -------------------------------------------------------------------------
    def run(self, user_request: str) -> Dict[str, Any]:
        """
        Executes the agent workflow. If an LLM provider is available, uses it.
        Otherwise, falls back to the explicit deterministic simulation.
        Never silently falls back to simulation when an LLM provider fails.
        """
        if self.llm_provider:
            return self.run_llm(user_request)
        return self.run_simulation(user_request)
        
    def run_simulation(self, user_request: str) -> Dict[str, Any]:
        """
        Deterministic Simulation Flow (Multi-Tool Capable):
        User Request -> Agent Decisions -> Tool Executions -> Observations -> Final Response
        """
        print("\n" + "=" * 70)
        print(f"[SIMULATION AGENT LOOP STARTED] Processing user request:")
        print(f"   \"{user_request}\"")
        print("=" * 70)

        request_lower = user_request.lower()
        matched_tools = []

        # Multi-tool keyword detection in simulation mode
        for t_name, t_info in self.tools.items():
            for kw in t_info["keywords"]:
                if kw in request_lower:
                    if t_name not in matched_tools:
                        matched_tools.append(t_name)
                    break

        # Deduplicate general vs specialized tools when both are matched
        if "get_inventory_status" in matched_tools and "get_inventory" in matched_tools:
            matched_tools.remove("get_inventory")
        if "get_sales_performance" in matched_tools and "get_today_sales" in matched_tools:
            if any(p in request_lower for p in ["period", "week", "days", "last", "month", "range"]):
                matched_tools.remove("get_today_sales")
        if "get_feedback_overview" in matched_tools and "get_item_reviews_summary" in matched_tools:
            # If the user is asking general feedback questions and not dish/item-specific reviews or quotes,
            # drop get_item_reviews_summary to prevent redundant tool calls and duplicate synthesis.
            item_specific_kw = ["dish", "dishes", "item", "items", "quote", "quotes", "text", "comment", "comments", "say about", "specific", "praised", "complained"]
            if not any(k in request_lower for k in item_specific_kw):
                matched_tools.remove("get_item_reviews_summary")

        # Check greetings
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
        is_greeting = any(g in request_lower for g in greetings)

        step_num = 1
        executed_results = {}

        if matched_tools:
            for t_name in matched_tools:
                print(f"\n[STEP {step_num}: SIMULATION DECISION]")
                print(f"Tool requested: {t_name}")
                print(f"Reason        : Matched intent keywords in query.")
                step_num += 1

                print(f"\n[STEP {step_num}: TOOL EXECUTION]")
                print(f"Executing {t_name}()")
                args = {"query": user_request} if t_name in ("search_cafe_knowledge", "search_restaurant_knowledge") else None
                res = self.execute_tool(t_name, args)
                executed_results[t_name] = res
                step_num += 1

                print(f"\n[STEP {step_num}: TOOL RESULT]")
                print(f"Status : {res.get('status')}")
                if t_name in ("search_cafe_knowledge", "search_restaurant_knowledge"):
                    print("\n[RETRIEVED KNOWLEDGE]")
                    chunks = res.get("retrieved_chunks", [])
                    for i, chunk in enumerate(chunks, 1):
                        print(f"--- Chunk {i} ---\n{chunk}\n")
                else:
                    data_keys = list(res.get("data", {}).keys()) if isinstance(res.get("data"), dict) else []
                    print(f"Data Preview: Keys received -> {data_keys[:5]}")
                step_num += 1

            print(f"\n[STEP {step_num}: RESPONSE SYNTHESIS]")
            print(f"Synthesizing unified response from {len(matched_tools)} tool results...")
            
            # Check for errors in executed tools to avoid presenting partial results as complete
            errors = [f"Error executing {t_name}: {res.get('message', 'Database error')}" for t_name, res in executed_results.items() if res.get("status") == "error"]
            successful_parts = [self.synthesize_response(user_request, t_name, res) for t_name, res in executed_results.items() if res.get("status") != "error"]

            if errors and not successful_parts:
                final_response = "\n".join(errors)
            elif errors and successful_parts:
                final_response = (
                    "⚠️ Warning: Partial data. One or more operations failed:\n"
                    + "\n".join([f"  - {err}" for err in errors])
                    + "\n\n"
                    + "\n\n".join(successful_parts)
                )
            else:
                final_response = "\n\n".join(successful_parts)
        elif is_greeting:
            print(f"\n[STEP {step_num}: SIMULATION DECISION]")
            print(f"Tool requested: None (Direct Greeting)")
            step_num += 1
            print(f"\n[STEP {step_num}: RESPONSE SYNTHESIS]")
            final_response = self.synthesize_response(user_request, None, None)
        else:
            print(f"\n[STEP {step_num}: SIMULATION DECISION]")
            print(f"Tool requested: None (Out of Scope)")
            step_num += 1
            print(f"\n[STEP {step_num}: RESPONSE SYNTHESIS]")
            final_response = self.synthesize_response(user_request, None, None)

        safe_print(f"\n[FINAL AGENT RESPONSE]:")
        safe_print("-" * 70)
        safe_print(final_response)
        safe_print("-" * 70)

        return {
            "user_request": user_request,
            "executed_tools": list(executed_results.keys()),
            "final_response": final_response,
            "mode": "simulation"
        }


# =============================================================================
# SPECIALIZED SALES INTELLIGENCE AGENT
# =============================================================================

SALES_AGENT_SYSTEM_PROMPT = """You are the Sales Intelligence Agent for restaurant operations management.
Your role is to analyze sales totals, revenue trends, top-selling items, period comparisons, daypart demand, and payment breakdowns.

STRICT OPERATIONAL GUIDELINES:
1. Ground every single claim, metric, and finding strictly in the numerical database evidence returned by your sales tools.
2. Explicitly state the exact date range / analysis period (e.g. '2026-10-02 to 2026-10-08') for every metric provided.
3. Explicitly distinguish between Gross Billed Revenue (which includes net sales subtotal, tax/GST, and service charges) and Net Sales Subtotal (pure food & beverage sales after discounts).
4. Clearly label Average Order Value (AOV) as the average value per completed order, explicitly stating its denominator (completed orders count; cancelled and refunded orders are excluded).
5. Explicitly state that reported discounts are already deducted from the net sales subtotal and gross revenue, and must NOT be subtracted again.
6. Clearly distinguish between total orders logged, completed orders, cancelled orders, and refunded orders. Cancelled and refunded orders are not included in completed revenue.
7. Explicitly label the data as synthetic (data_origin: 'SYNTHETIC') when presenting findings.
8. If the database returns no records for a given date or period, state clearly that the dataset has no completed orders for that timeframe.
9. Never invent, extrapolate, or speculate on financial metrics without explicit database evidence.
10. Keep answers structured, professional, and actionable for restaurant owners and shift managers."""


class SalesIntelligenceAgent(CafeAgent):
    """
    Specialized AI Agent for Restaurant Sales Intelligence & Revenue Analytics.
    Restricted to sales-specific database tools and configured with strict numerical grounding rules.
    """

    def __init__(self, name: str = "SalesIntelligenceAgent", llm_provider=None):
        super().__init__(name=name, llm_provider=llm_provider)
        
        # Restrict tools exclusively to sales analysis functions
        sales_tool_keys = [
            "get_sales_performance",
            "get_top_selling_items",
            "get_sales_trends_and_comparison",
            "get_peak_hours_and_dayparts",
            "get_payment_methods_breakdown",
            "get_today_sales"
        ]
        self.tools = {k: TOOL_REGISTRY[k] for k in sales_tool_keys if k in TOOL_REGISTRY}
        self.system_prompt = SALES_AGENT_SYSTEM_PROMPT

    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Specialized tool routing for Sales Intelligence in deterministic simulation mode.
        """
        req_lower = user_request.lower()

        if any(k in req_lower for k in ["compare", "growth", "trend", "versus", "vs", "weekly comparison"]):
            return {"tool_name": "get_sales_trends_and_comparison", "reason": "Query requests period comparisons or sales trends."}
        elif any(k in req_lower for k in ["top", "best seller", "most popular", "highest revenue", "sold the most"]):
            return {"tool_name": "get_top_selling_items", "reason": "Query asks for top-selling items or best-sellers."}
        elif any(k in req_lower for k in ["peak", "busiest hour", "daypart", "morning", "evening", "rush"]):
            return {"tool_name": "get_peak_hours_and_dayparts", "reason": "Query asks about peak hours or daypart demand."}
        elif any(k in req_lower for k in ["payment", "upi", "card", "cash", "wallet"]):
            return {"tool_name": "get_payment_methods_breakdown", "reason": "Query asks about payment method distribution."}
        elif any(k in req_lower for k in ["sales", "revenue", "orders", "performance", "aov", "channel", "discount"]):
            return {"tool_name": "get_sales_performance", "reason": "Query asks about overall sales totals and channel performance."}
        
        return super().decide_tool(user_request)

    def synthesize_response(
        self,
        user_request: str,
        tool_name: Optional[str],
        tool_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Specialized response formatter for sales tools in simulation mode.
        """
        if tool_result and tool_result.get("status") == "error":
            return f"Error executing {tool_name}: {tool_result.get('message', 'Database error')}"

        data = tool_result.get("data", {}) if tool_result else {}

        if tool_name == "get_sales_performance":
            summary = data.get("summary", {})
            channels = data.get("channel_breakdown", [])
            ch_str = "\n".join([f"  - {ch['channel'].title()}: INR {ch['revenue_inr']:.2f} ({ch['order_count']} orders, {ch['revenue_percentage']}%)" for ch in channels])
            discounts = data.get("discount_impact", {})

            tot_rev = summary.get("total_revenue_inr", 0.0)
            subtot = summary.get("subtotal_inr", 0.0)
            tax = summary.get("tax_inr", 0.0)
            svc = summary.get("service_charge_inr", 0.0)
            comp_orders = summary.get("completed_orders", 0)
            tot_orders = summary.get("total_orders", 0)
            canc_orders = summary.get("cancelled_orders", 0)
            ref_orders = summary.get("refunded_orders", 0)
            aov = summary.get("average_order_value_inr", 0.0)
            tot_disc = discounts.get("total_discount_given_inr", 0.0)
            disc_items = discounts.get("discounted_items_count", 0)

            return (
                f"Sales Performance Analysis [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Gross Billed Revenue: INR {tot_rev:.2f} (includes net sales subtotal: INR {subtot:.2f}, tax: INR {tax:.2f}, service charges: INR {svc:.2f})\n"
                f"* Net Sales Subtotal: INR {subtot:.2f} (pure food & beverage sales after discounts)\n"
                f"* Order Breakdown: {comp_orders} completed orders out of {tot_orders} total logged (Cancelled: {canc_orders}, Refunded: {ref_orders})\n"
                f"* Average Order Value (AOV): INR {aov:.2f} per completed order (denominator: {comp_orders} completed orders; cancelled and refunded orders are excluded)\n"
                f"* Discount Impact: Total INR {tot_disc:.2f} given across {disc_items} items (Note: discounts are already deducted from the subtotal and gross revenue; do not subtract again)\n"
                f"* Channel Breakdown:\n{ch_str}\n"
                f"* Data Origin: {data.get('data_origin', 'SYNTHETIC')}"
            )

        if tool_name == "get_top_selling_items":
            items = data.get("top_items", [])
            items_str = "\n".join([f"  {idx+1}. {it['item_name']} ({it['category_name']}) - {it['quantity_sold']} units sold, INR {it['revenue_inr']:.2f} revenue" for idx, it in enumerate(items)])
            return (
                f"Top Selling Items [{data.get('period_start')} to {data.get('period_end')}] ranked by {data.get('ranked_by')}:\n"
                f"{items_str}\n"
                f"* Note: Data based on completed orders in synthetic dataset."
            )

        if tool_name == "get_sales_trends_and_comparison":
            curr = data.get("current_period", {})
            prev = data.get("previous_period", {})
            growth = data.get("comparison_growth", {})
            return (
                f"Period-over-Period Sales Comparison (Synthetic Dataset):\n"
                f"* Current Period [{curr.get('start_date')} to {curr.get('end_date')}]: INR {curr.get('total_revenue_inr', 0.0):.2f} ({curr.get('total_orders', 0)} orders, AOV INR {curr.get('average_order_value_inr', 0.0):.2f})\n"
                f"* Previous Period [{prev.get('start_date')} to {prev.get('end_date')}]: INR {prev.get('total_revenue_inr', 0.0):.2f} ({prev.get('total_orders', 0)} orders, AOV INR {prev.get('average_order_value_inr', 0.0):.2f})\n"
                f"* Growth / Delta: Revenue change INR {growth.get('revenue_change_inr', 0.0):.2f} ({growth.get('revenue_growth_percentage', 0.0):+0.2f}%), Orders change {growth.get('orders_change', 0):+d} ({growth.get('orders_growth_percentage', 0.0):+0.2f}%)."
            )

        if tool_name == "get_peak_hours_and_dayparts":
            busiest = data.get("busiest_hour", {})
            dayparts = data.get("daypart_summary", [])
            dp_str = "\n".join([f"  - {dp['daypart']}: {dp['order_count']} orders, INR {dp['revenue_inr']:.2f}" for dp in dayparts])
            return (
                f"Peak Hours & Daypart Demand Analysis [{data.get('period_start')} to {data.get('period_end')}]:\n"
                f"* Busiest Hour: {busiest.get('time_window')} with {busiest.get('order_count')} completed orders (INR {busiest.get('revenue_inr', 0.0):.2f})\n"
                f"* Daypart Performance:\n{dp_str}"
            )

        if tool_name == "get_payment_methods_breakdown":
            methods = data.get("methods", [])
            m_str = "\n".join([f"  - {m['payment_method'].upper()}: INR {m['total_amount_inr']:.2f} ({m['transaction_count']} txns, {m['percentage_share']}%)" for m in methods])
            return (
                f"Payment Method Settlement Breakdown [{data.get('period_start')} to {data.get('period_end')}]:\n"
                f"* Total Settled: INR {data.get('total_settled_amount_inr', 0.0):.2f}\n"
                f"{m_str}"
            )

        return super().synthesize_response(user_request, tool_name, tool_result)


# =============================================================================
# SPECIALIZED MENU INTELLIGENCE AGENT
# =============================================================================

MENU_AGENT_SYSTEM_PROMPT = """You are the Menu Intelligence Agent for restaurant operations and menu engineering.
Your role is to analyze menu item performance, best and worst sellers, zero-sales items, category breakdowns, pricing vs realized sales, availability, and identify evidence-based menu optimization opportunities.

STRICT OPERATIONAL GUIDELINES:
1. Ground every single claim, numerical metric, and ranking strictly in database evidence returned by your menu tools.
2. Explicitly state the exact date range / analysis period (e.g. '2026-10-02 to 2026-10-08') for every performance metric.
3. Clearly distinguish between list price, average realized price, units sold, total revenue (INR), order appearances, and category revenue share %.
4. Clearly distinguish between concrete data evidence and analytical recommendations. When proposing items to investigate or change, explicitly cite the supporting data (e.g. 0 units sold, low order appearances, high discount rate, or inactive status).
5. Never invent or speculate on food costs, profit margins, recipe elasticity, or customer taste preferences when the required data is absent from the database.
6. Clearly disclose that current dataset findings come from synthetic benchmark data (data_origin: 'SYNTHETIC').
7. If the database returns no matching records, state clearly that the dataset has no matching menu items or sales records.
8. If a database or Gemini call fails, report the error safely; never fall back to mock data or fabricated business insights."""


class MenuIntelligenceAgent(CafeAgent):
    """
    Specialized AI Agent for Restaurant Menu Intelligence, Category Analysis & Menu Engineering.
    Restricted to menu-specific database tools and configured with strict evidence-grounding guidelines.
    """

    def __init__(self, name: str = "MenuIntelligenceAgent", llm_provider=None):
        super().__init__(name=name, llm_provider=llm_provider)

        # Restrict tools exclusively to menu analysis functions
        menu_tool_keys = [
            "get_menu_performance",
            "get_category_performance",
            "get_menu_item_comparison",
            "get_menu"
        ]
        self.tools = {k: TOOL_REGISTRY[k] for k in menu_tool_keys if k in TOOL_REGISTRY}
        self.system_prompt = MENU_AGENT_SYSTEM_PROMPT

    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Specialized tool routing for Menu Intelligence in deterministic simulation mode.
        """
        req_lower = user_request.lower()

        if any(k in req_lower for k in ["category", "categories", "category performance", "category share"]):
            return {"tool_name": "get_category_performance", "reason": "Query requests category-level sales or performance comparison."}
        elif any(k in req_lower for k in ["compare", "versus", "vs", "pricing analysis", "deep dive"]):
            return {"tool_name": "get_menu_item_comparison", "reason": "Query asks for side-by-side comparison or pricing analysis of specific items."}
        elif any(k in req_lower for k in ["best", "worst", "perform", "sold", "zero sales", "least popular", "top items", "investigate", "opportunity", "rank"]):
            return {"tool_name": "get_menu_performance", "reason": "Query asks for menu item sales rankings, best/worst performers, or items to investigate."}
        elif any(k in req_lower for k in ["menu", "drinks", "food", "list", "options", "available", "dietary"]):
            return {"tool_name": "get_menu", "reason": "Query asks for general menu catalog, prices, or availability."}

        return super().decide_tool(user_request)

    def synthesize_response(
        self,
        user_request: str,
        tool_name: Optional[str],
        tool_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Specialized response formatter for menu tools in simulation mode.
        """
        if tool_result and tool_result.get("status") == "error":
            return f"Error executing {tool_name}: {tool_result.get('message', 'Database error')}"

        data = tool_result.get("data", {}) if tool_result else {}

        if tool_name == "get_menu_performance":
            summary = data.get("summary", {})
            items = data.get("items", [])
            zero_sales = data.get("zero_sales_items", [])
            
            top_5 = items[:5]
            top_str = "\n".join([f"  {it['rank']}. {it['item_name']} ({it['category_name']}) - {it['quantity_sold']} sold, INR {it['revenue_inr']:.2f} rev (List: INR {it['list_price_inr']:.2f})" for it in top_5])
            
            zero_str = ""
            if zero_sales:
                zero_sample = zero_sales[:5]
                zero_str = "\n\nItems with Zero Sales in Period (Investigation Candidates):\n" + "\n".join([f"  - {z['item_name']} ({z['category_name']}, List: INR {z['list_price_inr']:.2f}, Available: {z['is_available']})" for z in zero_sample])
                if len(zero_sales) > 5:
                    zero_str += f"\n  ...and {len(zero_sales) - 5} more items with zero orders."

            return (
                f"Menu Performance Analysis [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Menu Items Analyzed: {summary.get('total_menu_items_analyzed', 0)} ({summary.get('zero_sales_items_count', 0)} with zero sales)\n"
                f"* Total Units Sold: {summary.get('total_units_sold', 0)} units | Total Revenue: INR {summary.get('total_revenue_inr', 0.0):.2f}\n\n"
                f"Top Performers ({data.get('sorted_by')}):\n{top_str}{zero_str}\n\n"
                f"* Recommendation: Investigate items with zero or low order volume against ingredient holding costs. Note: Data origin is synthetic."
            )

        if tool_name == "get_category_performance":
            cats = data.get("categories", [])
            cat_str = "\n".join([
                f"  - {c['category_name']}: INR {c['revenue_inr']:.2f} ({c['quantity_sold']} units sold, {c['revenue_share_percentage']}% share, {c['active_items']}/{c['total_items']} active items, Top: {c['top_performing_item']['name']})"
                for c in cats
            ])
            return (
                f"Category Performance Breakdown [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Revenue: INR {data.get('total_revenue_inr', 0.0):.2f} across {data.get('total_categories', 0)} categories\n"
                f"{cat_str}"
            )

        if tool_name == "get_menu_item_comparison":
            compared = data.get("compared_items", [])
            if not compared:
                return f"No menu items found matching the comparison criteria for [{data.get('period_start')} to {data.get('period_end')}]."
            
            comp_str = "\n".join([
                f"  - {it['item_name']} ({it['category_name']}): List Price INR {it['list_price_inr']:.2f}, Sold: {it['quantity_sold']} units, Revenue: INR {it['revenue_inr']:.2f}, Avg Realized: INR {it['average_realized_price_inr']:.2f}, Discount Given: INR {it['discount_inr']:.2f}, Available: {it['is_available']}"
                for it in compared
            ])
            return (
                f"Menu Item Comparison Analysis [{data.get('period_start')} to {data.get('period_end')}]:\n"
                f"{comp_str}\n"
                f"* Note: Figures derived from completed orders in synthetic benchmark dataset."
            )

        return super().synthesize_response(user_request, tool_name, tool_result)


# =============================================================================
# SPECIALIZED FEEDBACK INTELLIGENCE AGENT
# =============================================================================

FEEDBACK_AGENT_SYSTEM_PROMPT = """You are the Feedback Intelligence Agent for restaurant customer satisfaction and quality assurance.
Your role is to analyze customer reviews, rating distributions, sentiment patterns, complaint drivers, item-specific feedback, and period-over-period satisfaction shifts.

STRICT OPERATIONAL GUIDELINES:
1. Ground every single metric, rating average, complaint count, and customer observation strictly in the SQL-derived review records returned by your tools.
2. Explicitly state the exact date range / analysis period (e.g. '2026-09-09 to 2026-10-09') and total review sample size for every feedback insight.
3. Clearly distinguish between concrete SQL data metrics (rating numbers, issue percentages, praise counts) and analytical recommendations.
4. Protect customer privacy: Never display customer IDs, names, or unnecessary personal identifying details in responses.
5. Never invent or hallucinate review text quotes, customer opinions, complaint numbers, or sentiment statistics.
6. Clearly disclose that current dataset findings come from synthetic benchmark data (data_origin: 'SYNTHETIC').
7. When sample size is small (e.g. < 5 reviews), explicitly state that findings are based on a limited feedback sample.
8. If a database or Gemini call fails, report the error safely; never fall back to mock data or fabricated customer reviews.

TOOL USAGE & EFFICIENCY RULES:
9. MINIMIZE TOOL INVOCATIONS TO PRESERVE QUOTA:
   - For general feedback, ratings, sentiment breakdowns, or top complaint categories: call 'get_feedback_overview' ONLY.
   - For period-over-period trend analysis: call 'get_feedback_trends_and_issues' ONLY.
   - Call 'get_item_reviews_summary' ONLY when the request explicitly requires dish-level ratings, dish-level sentiment, verbatim review text, or customer quotes that 'get_feedback_overview' does not provide.
   - Do NOT call 'get_item_reviews_summary' after 'get_feedback_overview' if the overview already provides sufficient evidence to fulfill the request.
10. REUSE TOOL RESULTS & AVOID DUPLICATES:
   - Never call the same tool with identical or overlapping parameters within the same interaction.
   - Synthesize your final response immediately once the required evidence has been gathered."""


class FeedbackIntelligenceAgent(CafeAgent):
    """
    Specialized AI Agent for Restaurant Feedback Intelligence, Sentiment Analysis & Complaint Tracking.
    Restricted to feedback-specific database tools and configured with strict evidence-grounding guidelines.
    """

    def __init__(self, name: str = "FeedbackIntelligenceAgent", llm_provider=None):
        super().__init__(name=name, llm_provider=llm_provider)

        # Restrict tools exclusively to feedback analysis functions
        feedback_tool_keys = [
            "get_feedback_overview",
            "get_item_reviews_summary",
            "get_feedback_trends_and_issues",
            "get_menu"
        ]
        self.tools = {k: TOOL_REGISTRY[k] for k in feedback_tool_keys if k in TOOL_REGISTRY}
        self.system_prompt = FEEDBACK_AGENT_SYSTEM_PROMPT

    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Specialized tool routing for Feedback Intelligence in deterministic simulation mode.
        """
        req_lower = user_request.lower()

        if any(k in req_lower for k in ["trend", "trends", "shift", "change", "versus", "vs", "improving", "worsening", "period comparison"]):
            return {"tool_name": "get_feedback_trends_and_issues", "reason": "Query asks for feedback trends or period comparisons."}
        elif any(k in req_lower for k in ["item", "dish", "praised", "complained", "what do customers say", "comment", "quotes", "text", "specific"]):
            return {"tool_name": "get_item_reviews_summary", "reason": "Query asks for item-level feedback, comments, or praise/complaint details."}
        elif any(k in req_lower for k in ["feedback", "review", "reviews", "rating", "sentiment", "complaint", "issue", "satisfaction", "stars"]):
            return {"tool_name": "get_feedback_overview", "reason": "Query asks for overall customer feedback, ratings, sentiment, or issues."}
        elif any(k in req_lower for k in ["menu", "drinks", "food", "options"]):
            return {"tool_name": "get_menu", "reason": "Query asks for menu catalog reference."}

        return super().decide_tool(user_request)

    def synthesize_response(
        self,
        user_request: str,
        tool_name: Optional[str],
        tool_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Specialized response formatter for feedback tools in simulation mode.
        """
        if tool_result and tool_result.get("status") == "error":
            return f"Error executing {tool_name}: {tool_result.get('message', 'Database error')}"

        data = tool_result.get("data", {}) if tool_result else {}

        if tool_name == "get_feedback_overview":
            summary = data.get("summary", {})
            dist = data.get("rating_distribution", {})
            issues = data.get("issue_breakdown", [])
            
            dist_str = ", ".join([f"{k.replace('_', ' ').title()}: {v['count']} ({v['percentage']}%)" for k, v in dist.items()])
            issue_str = "\n".join([f"  - {iss['issue_category'].replace('_', ' ').title()}: {iss['count']} complaints ({iss['percentage_of_reviews']}%)" for iss in issues[:5]])

            return (
                f"Customer Feedback Overview [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Reviews: {summary.get('total_reviews', 0)} | Average Rating: {summary.get('average_rating', 0.0):.2f} / 5.00\n"
                f"* Sentiment: Positive: {summary.get('positive_sentiment_percentage', 0.0)}% | Neutral: {summary.get('neutral_sentiment_percentage', 0.0)}% | Negative: {summary.get('negative_sentiment_percentage', 0.0)}%\n"
                f"* Rating Breakdown: {dist_str}\n"
                f"* Top Feedback & Issue Themes:\n{issue_str}\n\n"
                f"* Recommendation: Focus quality interventions on leading complaint categories. Note: Data is synthetic."
            )

        if tool_name == "get_item_reviews_summary":
            items = data.get("items_summary", [])
            reviews = data.get("sample_reviews", [])

            item_str = "\n".join([
                f"  - {it['item_name']} ({it['category_name']}): Avg Rating {it['average_rating']:.2f} ({it['review_count']} reviews: {it['positive_reviews']} pos, {it['negative_reviews']} neg)"
                for it in items[:5]
            ])
            sample_str = "\n".join([
                f"  [{r['rating']}/5 stars | {r['sentiment'].upper()} | {r['issue_category'].replace('_', ' ').title()}] \"{r['review_text']}\" — ({r['item_name']}, {r['review_date']})"
                for r in reviews[:3]
            ])

            return (
                f"Item-Specific Feedback Summary [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Items Analyzed: {data.get('items_analyzed_count', 0)}\n{item_str}\n\n"
                f"Sample Customer Feedback:\n{sample_str}\n\n"
                f"* Note: Customer identifiers excluded for privacy. Data origin is synthetic."
            )

        if tool_name == "get_feedback_trends_and_issues":
            curr = data.get("current_period", {})
            prev = data.get("previous_period", {})
            comp = data.get("comparison", {})
            issues = data.get("issue_trends", [])
            praised = data.get("most_praised_items", [])
            complained = data.get("most_complained_items", [])

            iss_str = "\n".join([f"  - {iss['issue_category'].replace('_', ' ').title()}: {iss['current_count']} (prior: {iss['previous_count']}, delta: {iss['change']:+d})" for iss in issues[:4]])
            praised_str = ", ".join([f"{p['item_name']} ({p['positive_reviews']} pos)" for p in praised[:3]])
            complained_str = ", ".join([f"{c['item_name']} ({c['negative_reviews']} neg)" for c in complained[:3]])

            return (
                f"Feedback Trends & Period Comparison (Synthetic Dataset):\n"
                f"* Current Period [{curr.get('start_date')} to {curr.get('end_date')}]: Avg Rating {curr.get('average_rating', 0.0):.2f} / 5.00 ({curr.get('review_count', 0)} reviews, {curr.get('positive_percentage', 0.0)}% pos, {curr.get('negative_percentage', 0.0)}% neg)\n"
                f"* Previous Period [{prev.get('start_date')} to {prev.get('end_date')}]: Avg Rating {prev.get('average_rating', 0.0):.2f} / 5.00 ({prev.get('review_count', 0)} reviews, {prev.get('positive_percentage', 0.0)}% pos, {prev.get('negative_percentage', 0.0)}% neg)\n"
                f"* Period Shift: Rating Delta {comp.get('average_rating_delta', 0.0):+0.2f}, Review Volume Change {comp.get('review_volume_change', 0):+d}, Positive Share Shift {comp.get('positive_sentiment_shift', 0.0):+0.2f}%\n"
                f"* Issue Category Trends:\n{iss_str}\n"
                f"* Top Praised: {praised_str or 'None'}\n"
                f"* Top Issues: {complained_str or 'None'}"
            )

        return super().synthesize_response(user_request, tool_name, tool_result)


INVENTORY_AGENT_SYSTEM_PROMPT = """You are the specialized Inventory & Waste Intelligence AI Agent for the restaurant.
Your role is to analyze current stock levels, low-stock reorder alerts, historical ingredient consumption, stock movements, and operational variances between recorded usage and recipe expectations.

STRICT DATA INTEGRITY & EVIDENCE RULES:
1. Ground all quantitative statements in the tool results. Explicitly state the analysis date range and measurement units (e.g. g, ml, each) for every ingredient.
2. Clearly distinguish:
   - Live Facts: Current on-hand quantity, reorder thresholds, recorded stock movements.
   - Calculated Estimates: Recipe-based expected consumption from completed orders, daily burn rates, days of stock left.
   - Operational Discrepancies / Waste Indicators: Differences between physical movements and recipe calculations.
   - Actionable Recommendations: Prioritized restocking, portion checks, investigation candidates.
3. Waste & Spoilage Caution:
   - Do NOT claim that an ingredient was wasted merely because its stock decreased or because recipe math differs from stock movements.
   - The current database does NOT contain dedicated spoilage/waste logs, purchase invoice costs, or expiry dates. Acknowledge these limitations and label variances as potential indicators (e.g., preparation shrinkage, portion deviations, recording lag), not confirmed waste.
4. Explain why an ingredient is flagged (e.g., "Current stock is below reorder threshold" or "Burn rate suggests stockout in 2.1 days").
5. Clearly label findings with the data origin: "Synthetic Dataset".
6. If a database or Gemini call fails, report the error safely; never fall back to mock data or fabricated inventory levels."""


class InventoryIntelligenceAgent(CafeAgent):
    """
    Specialized AI Agent for Restaurant Inventory, Stock Health, Consumption & Waste Variance Analysis.
    Restricted to inventory-specific database tools and configured with strict evidence-grounding guidelines.
    """

    def __init__(self, name: str = "InventoryIntelligenceAgent", llm_provider=None):
        super().__init__(name=name, llm_provider=llm_provider)

        # Restrict tools exclusively to inventory analysis functions
        inventory_tool_keys = [
            "get_inventory_status",
            "get_ingredient_consumption",
            "get_stock_movement_summary",
            "get_inventory_variance",
            "get_inventory"
        ]
        self.tools = {k: TOOL_REGISTRY[k] for k in inventory_tool_keys if k in TOOL_REGISTRY}
        self.system_prompt = INVENTORY_AGENT_SYSTEM_PROMPT

    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Specialized tool routing for Inventory Intelligence in deterministic simulation mode.
        """
        req_lower = user_request.lower()

        if any(k in req_lower for k in ["variance", "waste", "spoilage", "recipe vs actual", "discrepancy", "shrinkage", "unusual consumption"]):
            return {"tool_name": "get_inventory_variance", "reason": "Query asks about inventory variance, recipe comparison, or waste indicators."}
        elif any(k in req_lower for k in ["movement", "movements", "inflow", "outflow", "receipt", "purchase", "logs", "stock delta"]):
            return {"tool_name": "get_stock_movement_summary", "reason": "Query asks about physical stock movement logs, inflows, or outflows."}
        elif any(k in req_lower for k in ["consumption", "used", "burn rate", "velocity", "usage", "consumed", "runout", "how fast"]):
            return {"tool_name": "get_ingredient_consumption", "reason": "Query asks about ingredient consumption or burn rates from sales."}
        elif any(k in req_lower for k in ["status", "low stock", "critical", "reorder", "threshold", "replenish", "supplies", "shortage"]):
            return {"tool_name": "get_inventory_status", "reason": "Query asks about live inventory status, health levels, or replenishment."}
        elif any(k in req_lower for k in ["inventory", "stock", "ingredients"]):
            return {"tool_name": "get_inventory_status", "reason": "Query asks for general inventory stock levels."}

        return super().decide_tool(user_request)

    def synthesize_response(
        self,
        user_request: str,
        tool_name: Optional[str],
        tool_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Specialized response formatter for inventory tools in simulation mode.
        """
        if tool_result and tool_result.get("status") == "error":
            return f"Error executing {tool_name}: {tool_result.get('message', 'Database error')}"

        data = tool_result.get("data", {}) if tool_result else {}

        if tool_name in ("get_inventory_status", "get_inventory"):
            if tool_name == "get_inventory":
                inv_items = list(data.values()) if isinstance(data, dict) else []
                total_items = tool_result.get("summary", {}).get("total_items", len(inv_items))
                low_stock_items = [it for it in inv_items if "Low Stock" in it.get("status", "")]
                priority_lines = [
                    f"  - [Reorder Needed] {it.get('item_name', '')} ({it.get('category', 'general')}): Current {it.get('current_stock', 0)} {it.get('unit', '')} (Reorder Level: {it.get('min_reorder_level', 0)} {it.get('unit', '')})"
                    for it in low_stock_items[:5]
                ]
                priority_str = "\n".join(priority_lines)
                return (
                    f"Inventory Status & Stock Health Overview (Synthetic Dataset):\n"
                    f"* Total Ingredients Tracked: {total_items}\n"
                    f"* Low Stock Items Count: {len(low_stock_items)}\n\n"
                    f"Replenishment Priorities:\n{priority_str or '  No immediate replenishments required. All items healthy.'}\n\n"
                    f"* Note: Data origin is synthetic. Reorder decisions should be confirmed against supplier delivery lead times."
                )

            summary = data.get("summary", {})
            priorities = data.get("replenishment_priorities", [])
            items = data.get("items", [])

            priority_str = "\n".join([
                f"  - [{p['urgency']}] {p['ingredient_name']} ({p['category']}): Current {p['current_stock']} {p['unit']} (Reorder Level: {p['reorder_level']} {p['unit']}, Deficit: {p['deficit']} {p['unit']})"
                for p in priorities[:5]
            ])

            return (
                f"Inventory Status & Stock Health Overview (Synthetic Dataset):\n"
                f"* Total Ingredients Tracked: {summary.get('total_items', 0)}\n"
                f"* Stock Health Breakdown: Critical: {summary.get('critical_items_count', 0)}, Low Stock: {summary.get('low_stock_items_count', 0)}, Approaching Reorder: {summary.get('approaching_reorder_count', 0)}, Healthy: {summary.get('healthy_items_count', 0)}\n\n"
                f"Replenishment Priorities:\n{priority_str or '  No immediate replenishments required. All items healthy.'}\n\n"
                f"* Note: Data origin is synthetic. Reorder decisions should be confirmed against supplier delivery lead times."
            )

        if tool_name == "get_ingredient_consumption":
            consumed = data.get("consumed_ingredients", [])
            velocity = data.get("top_consumed_by_velocity", [])
            risks = data.get("stockout_risk_ingredients", [])

            vel_str = "\n".join([
                f"  - {v['ingredient_name']} ({v['category']}): {v['total_consumed_quantity']} {v['unit']} consumed ({v['daily_burn_rate']} {v['unit']}/day, Current Stock: {v['current_stock']} {v['unit']})"
                for v in velocity[:5]
            ])
            risk_str = "\n".join([
                f"  - {r['ingredient_name']}: Stock {r['current_stock']} {r['unit']}, Burn Rate {r['daily_burn_rate']} {r['unit']}/day (Est. {r['estimated_days_of_stock_left']} days left)"
                for r in risks[:3]
            ])

            return (
                f"Ingredient Consumption Analysis [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Ingredients Consumed: {data.get('ingredients_analyzed_count', 0)}\n"
                f"* Top Consumed Ingredients by Velocity:\n{vel_str}\n\n"
                f"Stockout Risk Alerts (<= 3 Days Left):\n{risk_str or '  No imminent stockout risks identified.'}\n\n"
                f"* Methodology: Calculated from completed orders and recipe portion specifications. Data origin is synthetic."
            )

        if tool_name == "get_stock_movement_summary":
            types_sum = data.get("movement_types_summary", [])
            ing_mov = data.get("ingredient_movements", [])

            types_str = "\n".join([
                f"  - {t['movement_type'].replace('_', ' ').title()} ({t['unit']}): Inflow +{t['total_inflow']}, Outflow -{t['total_outflow']}, Net Delta {t['net_delta']:+0.2f} ({t['movement_count']} movements)"
                for t in types_sum
            ])
            top_outflows = "\n".join([
                f"  - {im['ingredient_name']}: Inflow +{im['total_inflow']} {im['unit']}, Outflow -{im['total_outflow']} {im['unit']} (Net: {im['net_delta']:+0.2f} {im['unit']})"
                for im in ing_mov[:5]
            ])

            return (
                f"Stock Movements Summary [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Movement Records: {data.get('total_movements_count', 0)}\n"
                f"* Movement Types Breakdown:\n{types_str}\n\n"
                f"Top Ingredient Outflows:\n{top_outflows}\n\n"
                f"* Note: Data origin is synthetic."
            )

        if tool_name == "get_inventory_variance":
            summary = data.get("summary", {})
            variances = data.get("variance_details", [])

            var_str = "\n".join([
                f"  - {v['ingredient_name']} ({v['category']}): Expected {v['expected_recipe_consumption']} {v['unit']} vs Recorded Outflow {v['recorded_movement_outflow']} {v['unit']} (Variance: {v['variance_quantity']:+0.2f} {v['unit']}, Status: {v['status']})"
                for v in variances[:5]
            ])

            return (
                f"Inventory Variance & Waste Indicator Analysis [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Ingredients Analyzed: {data.get('ingredients_analyzed_count', 0)}\n"
                f"* Variance Status: Exact Matches: {summary.get('exact_matches_count', 0)}, Elevated Outflows: {summary.get('elevated_outflows_count', 0)}, Lower Outflows: {summary.get('lower_outflows_count', 0)}\n\n"
                f"Ingredient Variance Breakdown:\n{var_str}\n\n"
                f"* Waste Advisory: {data.get('waste_and_variance_advisory', '')}\n"
                f"* Note: Data origin is synthetic."
            )

        return super().synthesize_response(user_request, tool_name, tool_result)


DECISION_AGENT_SYSTEM_PROMPT = """You are the specialized Decision & Recommendation AI Agent for the restaurant intelligence multi-agent system.
Your role is to synthesize factual evidence across sales performance, menu popularity, customer reviews/sentiment, and inventory stock health into prioritized, actionable business recommendations.

CORE OPERATIONAL PRINCIPLES:
1. Grounding & Evidence:
   - Ground every recommendation strictly in numerical and factual database evidence returned by your tools.
   - Do NOT invent, speculate, or extrapolate figures. Quote specific metrics, sample periods, and units.
   - Trace every quantitative claim to actual query results.

2. Three-Part Distinction:
   For every recommendation or assessment, clearly distinguish:
   - Observations: Verified empirical facts directly returned by database tools (e.g. stock quantities, review counts, sales volumes).
   - Inferences: Data-supported analytical conclusions drawn from combining multiple facts (e.g. high sales + critical stock = imminent stockout risk).
   - Recommendations: Concrete, actionable operational decisions prioritized by urgency.

3. Structured Output Contract:
   Where supported, every recommendation must include:
   - recommendation_id: Unique identifier (e.g. REC-INV-001, REC-OPS-001, REC-MNU-001)
   - title: Clear, concise action title
   - priority: Exactly one of [critical, high, medium, low]
   - category: Domain category (e.g. inventory_stockout_risk, operational_efficiency, quality_intervention, menu_catalog_optimization)
   - observation: Verified empirical data from database queries
   - supporting_evidence: Specific key metrics, date ranges, and quantities
   - recommended_action: Precise operational step for staff or management
   - expected_impact: Qualitative business impact or defensible quantitative outcome
   - confidence: high, medium, or low based on evidence completeness
   - data_origin: "SYNTHETIC" (Always label data provenance clearly)
   - limitations: Explicitly acknowledge unrecorded parameters (e.g. absence of wholesale invoice costs, supplier lead times, or expiry dates)

4. Strict Boundaries & Limitations:
   - Never invent profit margins without ingredient wholesale invoice costs.
   - Never invent supplier lead times, minimum order quantities, or product expiry dates.
   - Preserve customer privacy: Never fabricate or expose customer identities.
   - If evidence is insufficient to justify an action, explicitly state that available data is insufficient.
   - Never fall back to mock data or simulated success if a database query fails.
"""


class DecisionRecommendationAgent(CafeAgent):
    """
    Specialized AI Agent for Cross-Domain Decision Support & Executive Recommendations.
    Synthesizes evidence across sales, menu items, reviews/complaints, and inventory into
    prioritized business interventions with clear output contracts and provenance.
    """

    def __init__(self, name: str = "DecisionRecommendationAgent", llm_provider=None):
        super().__init__(name=name, llm_provider=llm_provider)

        # Restrict tools exclusively to recommendation engine and supporting specialist tools
        recommendation_tool_keys = [
            "get_actionable_recommendations",
            "get_stockout_risk_recommendations",
            "get_quality_and_complaint_recommendations",
            "get_underperforming_menu_recommendations",
            "get_sales_performance",
            "get_inventory_status",
            "get_feedback_overview",
            "get_menu_performance"
        ]
        self.tools = {k: TOOL_REGISTRY[k] for k in recommendation_tool_keys if k in TOOL_REGISTRY}
        self.system_prompt = DECISION_AGENT_SYSTEM_PROMPT

    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Specialized tool routing for Decision & Recommendation in deterministic simulation mode.
        """
        req_lower = user_request.lower()

        if any(k in req_lower for k in ["stockout", "risk", "revenue at risk", "urgent restock", "dishes running out", "bottleneck"]):
            return {"tool_name": "get_stockout_risk_recommendations", "reason": "Query asks specifically about inventory stockout risks or revenue at risk."}
        elif any(k in req_lower for k in ["quality", "complaint", "complaints", "packaging", "service time", "kitchen prep", "feedback action", "bad reviews", "dissatisfaction"]):
            return {"tool_name": "get_quality_and_complaint_recommendations", "reason": "Query asks about operational quality interventions or recurring complaints."}
        elif any(k in req_lower for k in ["underperforming", "zero sales", "delist", "worst selling", "catalog", "low selling", "zero orders"]):
            return {"tool_name": "get_underperforming_menu_recommendations", "reason": "Query asks about underperforming or zero-sales menu items."}
        elif any(k in req_lower for k in ["recommendation", "recommendations", "decision", "decisions", "action plan", "what should we do", "priorities", "executive", "suggest", "actions"]):
            return {"tool_name": "get_actionable_recommendations", "reason": "Query asks for cross-domain strategic recommendations or executive action plan."}
        elif any(k in req_lower for k in ["inventory", "stock", "supplies"]):
            return {"tool_name": "get_inventory_status", "reason": "Query asks for supporting inventory status."}
        elif any(k in req_lower for k in ["feedback", "review", "reviews", "sentiment"]):
            return {"tool_name": "get_feedback_overview", "reason": "Query asks for supporting feedback overview."}
        elif any(k in req_lower for k in ["sales", "revenue", "orders"]):
            return {"tool_name": "get_sales_performance", "reason": "Query asks for supporting sales performance."}
        elif any(k in req_lower for k in ["menu", "dishes"]):
            return {"tool_name": "get_menu_performance", "reason": "Query asks for supporting menu performance."}

        # Check greetings
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
        if any(g in req_lower for g in greetings):
            return {
                "tool_name": None,
                "reason": "Greeting or general introduction. No recommendation query."
            }

        return {"tool_name": "get_actionable_recommendations", "reason": "Defaulting to comprehensive cross-domain actionable recommendations."}

    def synthesize_response(
        self,
        user_request: str,
        tool_name: Optional[str],
        tool_result: Optional[Dict[str, Any]]
    ) -> str:
        """
        Specialized response formatter for recommendation tools in simulation mode.
        """
        if tool_result and tool_result.get("status") == "error":
            return f"Error executing {tool_name}: {tool_result.get('message', 'Database error')}"

        data = tool_result.get("data", {}) if tool_result else {}

        if tool_name == "get_actionable_recommendations":
            recs = data.get("recommendations", [])
            priority_counts = data.get("priority_breakdown", {})
            exec_summary = data.get("executive_summary", "")

            rec_blocks = []
            for r in recs[:6]:
                rec_blocks.append(
                    f"[{r.get('priority', '').upper()}] {r.get('title', '')} ({r.get('recommendation_id', '')})\n"
                    f"  - Category: {r.get('category', '')}\n"
                    f"  - Observation: {r.get('observation', '')}\n"
                    f"  - Recommended Action: {r.get('recommended_action', '')}\n"
                    f"  - Expected Impact: {r.get('expected_impact', '')}\n"
                    f"  - Confidence: {r.get('confidence', '')} | Limitations: {r.get('limitations', '')}"
                )

            recs_text = "\n\n".join(rec_blocks) if rec_blocks else "No recommendations generated for the specified criteria."

            return (
                f"Executive Decision & Action Plan [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Recommendations: {data.get('total_recommendations', 0)}\n"
                f"* Priority Breakdown: Critical: {priority_counts.get('critical', 0)}, High: {priority_counts.get('high', 0)}, Medium: {priority_counts.get('medium', 0)}, Low: {priority_counts.get('low', 0)}\n"
                f"* Summary: {exec_summary}\n\n"
                f"Prioritized Recommendations:\n{recs_text}\n\n"
                f"* Data Origin: SYNTHETIC. {data.get('general_limitations', '')}"
            )

        if tool_name == "get_stockout_risk_recommendations":
            recs = data.get("recommendations", [])
            rec_blocks = []
            for r in recs:
                rec_blocks.append(
                    f"[{r.get('priority', '').upper()}] {r.get('title', '')} ({r.get('recommendation_id', '')})\n"
                    f"  - Observation: {r.get('observation', '')}\n"
                    f"  - Recommended Action: {r.get('recommended_action', '')}\n"
                    f"  - Expected Impact: {r.get('expected_impact', '')}\n"
                    f"  - Confidence: {r.get('confidence', '')} | Limitations: {r.get('limitations', '')}"
                )
            recs_text = "\n\n".join(rec_blocks) if rec_blocks else "No immediate ingredient stockout risks identified."

            return (
                f"Stockout Risk & Replenishment Recommendations [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Risks Identified: {data.get('total_stockout_risks', len(recs))}\n\n"
                f"{recs_text}\n\n"
                f"* Data Origin: SYNTHETIC. Wholesale costs and supplier lead times not recorded in database."
            )

        if tool_name == "get_quality_and_complaint_recommendations":
            recs = data.get("recommendations", [])
            rec_blocks = []
            for r in recs:
                rec_blocks.append(
                    f"[{r.get('priority', '').upper()}] {r.get('title', '')} ({r.get('recommendation_id', '')})\n"
                    f"  - Observation: {r.get('observation', '')}\n"
                    f"  - Recommended Action: {r.get('recommended_action', '')}\n"
                    f"  - Expected Impact: {r.get('expected_impact', '')}\n"
                    f"  - Confidence: {r.get('confidence', '')} | Limitations: {r.get('limitations', '')}"
                )
            recs_text = "\n\n".join(rec_blocks) if rec_blocks else "No significant quality complaints identified."

            return (
                f"Quality & Customer Experience Recommendations [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Total Interventions: {data.get('total_quality_recommendations', len(recs))}\n\n"
                f"{recs_text}\n\n"
                f"* Data Origin: SYNTHETIC. Customer identities preserved; feedback sample size per dish is limited."
            )

        if tool_name == "get_underperforming_menu_recommendations":
            recs = data.get("recommendations", [])
            rec_blocks = []
            for r in recs:
                rec_blocks.append(
                    f"[{r.get('priority', '').upper()}] {r.get('title', '')} ({r.get('recommendation_id', '')})\n"
                    f"  - Observation: {r.get('observation', '')}\n"
                    f"  - Recommended Action: {r.get('recommended_action', '')}\n"
                    f"  - Expected Impact: {r.get('expected_impact', '')}\n"
                    f"  - Confidence: {r.get('confidence', '')} | Limitations: {r.get('limitations', '')}"
                )
            recs_text = "\n\n".join(rec_blocks) if rec_blocks else "All menu items met or exceeded sales thresholds."

            return (
                f"Underperforming Menu Item Recommendations [{data.get('period_start')} to {data.get('period_end')}] (Synthetic Dataset):\n"
                f"* Zero-Sales Items Count: {data.get('zero_sales_count', 0)}\n"
                f"* Low-Sales Items Count: {data.get('low_sales_count', 0)}\n\n"
                f"{recs_text}\n\n"
                f"* Data Origin: SYNTHETIC. Ingredient spoilage and carrying cost data unavailable."
            )

        return super().synthesize_response(user_request, tool_name, tool_result)


# =============================================================================
# SPECIALIZED RESTAURANT KNOWLEDGE INTELLIGENCE AGENT
# =============================================================================

KNOWLEDGE_AGENT_SYSTEM_PROMPT = """You are the Restaurant Knowledge Intelligence Agent.
Your role is to answer questions about cafe standard operating procedures (SOP), food safety policies, hygiene rules, storage temperatures, inventory policies, and operational manuals using semantic retrieval from Supabase pgvector.

STRICT OPERATIONAL GUIDELINES:
1. Ground every claim and policy answer strictly in the retrieved document chunks and source citations.
2. If the retrieved context does not contain enough information to answer the inquiry, explicitly state: "The available documents do not contain enough information to answer this inquiry."
3. Always include source citations (e.g. [Document Title v1.0, Chunk 0, Page 1]) when explaining policies.
4. Never invent, hallucinate, or extrapolate policy rules, temperatures, or procedures not present in the retrieved passages.
5. Clearly state that document records originate from the synthetic restaurant SOP repository (data_origin: 'SYNTHETIC').
6. If the database or Gemini call fails, report the error safely; never fall back to mock data or fabricated procedures."""


class RestaurantKnowledgeAgent(CafeAgent):
    """
    Specialized AI Agent for Restaurant Knowledge, SOP Policies & Regulatory Guidance.
    Restricted to knowledge retrieval tools and configured with strict document-grounding guidelines.
    """

    def __init__(self, name: str = "RestaurantKnowledgeAgent", llm_provider=None):
        super().__init__(name=name, llm_provider=llm_provider)

        knowledge_tool_keys = [
            "search_restaurant_knowledge",
            "search_cafe_knowledge"
        ]
        self.tools = {k: TOOL_REGISTRY[k] for k in knowledge_tool_keys if k in TOOL_REGISTRY}
        self.system_prompt = KNOWLEDGE_AGENT_SYSTEM_PROMPT

    def decide_tool(self, user_request: str) -> Dict[str, Any]:
        """
        Specialized tool routing for Knowledge Intelligence in deterministic simulation mode.
        """
        req_lower = user_request.lower()

        # Check greetings
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
        if any(g in req_lower for g in greetings):
            return {
                "tool_name": None,
                "reason": "Greeting or general introduction. No policy lookup required."
            }

        return {
            "tool_name": "search_restaurant_knowledge",
            "reason": "Query asks for restaurant SOP or operational policy guidelines. Querying Supabase pgvector."
        }








