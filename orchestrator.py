"""
orchestrator.py - Unified Orchestration for Restaurant Intelligence Multi-Agent System

Coordinates the six specialized capabilities:
1. Sales Intelligence (SalesIntelligenceAgent)
2. Menu Intelligence (MenuIntelligenceAgent)
3. Feedback Intelligence (FeedbackIntelligenceAgent)
4. Inventory & Waste Intelligence (InventoryIntelligenceAgent)
5. Decision & Recommendation (DecisionRecommendationAgent)
6. Restaurant Knowledge / RAG (RestaurantKnowledgeAgent)

Provides:
- Transparent, deterministic intent routing
- Multi-agent coordination and selective execution
- Consolidated synthesis without duplicate claims or fabricated numbers
- Strict evidence grounding and synthetic provenance retention
- Common response contract with error and limitation disclosure
"""

import re
import logging
from typing import Dict, Any, List, Optional

from agent import (
    SalesIntelligenceAgent,
    MenuIntelligenceAgent,
    FeedbackIntelligenceAgent,
    InventoryIntelligenceAgent,
    DecisionRecommendationAgent,
    RestaurantKnowledgeAgent,
    CafeAgent
)
from db import sanitize_error, execute_single

logger = logging.getLogger("restaurant_orchestrator")


# Domain limitations by agent capability
DOMAIN_LIMITATIONS = {
    "sales": "Sales metrics derived from completed orders in synthetic benchmark dataset.",
    "menu": "Wholesale ingredient costs and profit margins are not available in the database schema.",
    "feedback": "Customer personal identifying details are withheld to preserve privacy; feedback sample sizes per dish may be limited.",
    "inventory": "Wholesale invoice costs, supplier delivery lead times, and dedicated spoilage logs are not recorded in the database. Variances represent operational indicators, not confirmed waste.",
    "recommendations": "Wholesale invoice purchase costs, supplier MOQ, and product expiration dates are unrecorded in database. Financial profit margins cannot be calculated.",
    "knowledge": "Policy guidance is strictly bounded by uploaded synthetic cafe SOP documents in Supabase pgvector."
}


class AgentOrchestrator:
    """
    Unified Orchestrator coordinating the six restaurant intelligence agents.
    Routes queries, manages cross-agent dependencies, and synthesizes grounded answers.
    """

    def __init__(self, llm_provider=None, strict_mode: bool = True, dataset_id: Optional[str] = None):
        self.llm_provider = llm_provider
        self.strict_mode = strict_mode
        self.dataset_id = dataset_id

        # Factory mapping for the 6 capabilities
        self.agent_factories = {
            "sales": lambda llm: SalesIntelligenceAgent(llm_provider=llm),
            "menu": lambda llm: MenuIntelligenceAgent(llm_provider=llm),
            "feedback": lambda llm: FeedbackIntelligenceAgent(llm_provider=llm),
            "inventory": lambda llm: InventoryIntelligenceAgent(llm_provider=llm),
            "recommendations": lambda llm: DecisionRecommendationAgent(llm_provider=llm),
            "knowledge": lambda llm: RestaurantKnowledgeAgent(llm_provider=llm)
        }

        self.agent_class_names = {
            "sales": "SalesIntelligenceAgent",
            "menu": "MenuIntelligenceAgent",
            "feedback": "FeedbackIntelligenceAgent",
            "inventory": "InventoryIntelligenceAgent",
            "recommendations": "DecisionRecommendationAgent",
            "knowledge": "RestaurantKnowledgeAgent"
        }

    # -------------------------------------------------------------------------
    # 1. TRANSPARENT INTENT ROUTING
    # -------------------------------------------------------------------------
    def route_query(self, query: str) -> List[str]:
        """
        Determines which of the six specialist agents are required to answer the query.
        Uses deterministic, testable pattern matching without requiring an unnecessary second LLM call.

        Returns:
            List[str]: List of agent keys e.g. ["sales"], ["menu", "inventory"], or [] if ambiguous.
        """
        if not query or not query.strip():
            return []

        q = query.lower().strip()

        # Check for pure greetings
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
        if q in greetings or any(q.startswith(g + " ") for g in greetings if len(q) < 15):
            return ["greeting"]

        # Check for completely ambiguous / empty queries
        if len(q.split()) <= 1 and q not in ["sales", "menu", "inventory", "reviews", "recommendations", "sop"]:
            return []

        selected = []

        # ---------------------------------------------------------------------
        # Capability 6: Restaurant Knowledge / RAG
        # ---------------------------------------------------------------------
        knowledge_patterns = [
            r"\bsop\b", r"\bsops\b", r"\bpolicy\b", r"\bpolicies\b",
            r"standard operating procedure", r"\bprocedure\b", r"\bprocedures\b",
            r"\bhandbook\b", r"\bmanual\b", r"\bguideline\b", r"\bguidelines\b",
            r"food safety", r"storage policy", r"milk storage", r"temperature check",
            r"holding time", r"\bhygiene\b", r"shift handover", r"dress code", r"cleaning rule"
        ]
        if any(re.search(pat, q) for pat in knowledge_patterns):
            selected.append("knowledge")

        # ---------------------------------------------------------------------
        # Capability 5: Decision & Recommendation
        # ---------------------------------------------------------------------
        rec_patterns = [
            r"\brecommendation\b", r"\brecommendations\b", r"action plan",
            r"what should we do", r"what should management do", r"what actions",
            r"\bprioritize\b", r"\bpriority\b", r"\bpriorities\b", r"strategic",
            r"executive summary", r"operational intervention", r"actionable"
        ]
        # Distinguish "recommend a dish / menu item" from "executive recommendations"
        is_menu_rec = ("recommend" in q or "suggest" in q) and any(w in q for w in ["dish", "item", "food", "drink", "beverage", "eat"])
        if any(re.search(pat, q) for pat in rec_patterns) and not is_menu_rec:
            selected.append("recommendations")

        # ---------------------------------------------------------------------
        # Capability 4: Inventory & Waste Intelligence
        # ---------------------------------------------------------------------
        inventory_patterns = [
            r"\bingredient\b", r"\bingredients\b", r"\bstock\b", r"\binventory\b",
            r"\brestock\b", r"\brestocking\b", r"\breorder\b", r"\bthreshold\b",
            r"\bshortage\b", r"\bdeficit\b", r"burn rate", r"consumption",
            r"stockout", r"supplies", r"\bmovement\b", r"\bmovements\b",
            r"\binflow\b", r"\boutflow\b", r"\bvariance\b", r"\bwaste\b",
            r"\bspoilage\b", r"\bshrinkage\b", r"running low", r"run out"
        ]
        if any(re.search(pat, q) for pat in inventory_patterns):
            selected.append("inventory")

        # ---------------------------------------------------------------------
        # Capability 3: Feedback Intelligence
        # ---------------------------------------------------------------------
        feedback_patterns = [
            r"\bfeedback\b", r"\breview\b", r"\breviews\b", r"\bcomplaint\b",
            r"\bcomplaints\b", r"\bcomplain\b", r"\bcomplaining\b", r"\brating\b",
            r"\bratings\b", r"\bsentiment\b", r"\bdissatisfaction\b", r"\bcustomer\b",
            r"\bcustomers\b", r"customer say", r"customer sentiment",
            r"\bpraise\b", r"\bstars\b", r"customer feedback", r"customer satisfaction",
            r"poor ratings", r"bad reviews"
        ]
        if any(re.search(pat, q) for pat in feedback_patterns):
            selected.append("feedback")

        # ---------------------------------------------------------------------
        # Capability 2: Menu Intelligence
        # ---------------------------------------------------------------------
        menu_patterns = [
            r"\bmenu item\b", r"\bmenu items\b", r"\bdish\b", r"\bdishes\b",
            r"category share", r"zero sales", r"\bdelist\b", r"item performance",
            r"menu catalog", r"vegetarian", r"non-vegetarian", r"least popular",
            r"worst selling", r"best selling dish", r"popular dish", r"popular dishes",
            r"perform poorly", r"underperforming menu"
        ]
        if any(re.search(pat, q) for pat in menu_patterns) or is_menu_rec:
            selected.append("menu")

        # ---------------------------------------------------------------------
        # Capability 1: Sales Intelligence
        # ---------------------------------------------------------------------
        sales_patterns = [
            r"\bsales\b", r"\brevenue\b", r"order volume", r"orders completed",
            r"how many orders", r"\baov\b", r"average order value", r"daily sales",
            r"sales trend", r"payment method", r"\bupi\b", r"discount impact",
            r"\bfinancial\b", r"channel breakdown", r"dine-in vs delivery",
            r"busiest hour", r"peak hours"
        ]
        if any(re.search(pat, q) for pat in sales_patterns):
            selected.append("sales")

        # If "menu" is just mentioned in a generic phrase like "menu" alone and nothing else matched
        if not selected and "menu" in q:
            selected.append("menu")

        # If general question asking about restaurant performance or executive overview
        if not selected and any(w in q for w in ["performance", "how are we doing", "overview", "status", "health"]):
            # For broad overview, recommendations agent is designed to synthesize cross-domain health
            selected.append("recommendations")

        return selected

    # -------------------------------------------------------------------------
    # 2. CROSS-AGENT EXECUTION & COORDINATION
    # -------------------------------------------------------------------------
    def orchestrate(
        self,
        query: str,
        restaurant_id: str = "default_restaurant",
        run_mode: str = "auto",
        dataset_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates selective execution of specialist agents based on routed intent.

        Parameters:
            query (str): Natural language user question.
            restaurant_id (str): Tenant identifier for dataset scoping.
            run_mode (str): 'auto' (uses LLM if configured), 'llm' (forces LLM), 'simulation' (forces deterministic).
            dataset_id (str, optional): Target uploaded dataset identifier to query instead of baseline.

        Returns:
            Dict[str, Any]: Common response contract.
        """
        active_dataset = dataset_id or self.dataset_id
        logger.info(f"Orchestrating query: '{query}' (tenant: {restaurant_id}, dataset_id: {active_dataset})")

        # Tenant isolation check for dataset-scoped queries
        if active_dataset:
            try:
                ds_row = execute_single(
                    "SELECT dataset_id, restaurant_id FROM datasets WHERE dataset_id = %s",
                    (active_dataset,)
                )
                if not ds_row:
                    return {
                        "status": "error",
                        "answer": f"⚠️ Target dataset '{active_dataset}' was not found in the system.",
                        "route": [],
                        "selected_agents": [],
                        "agent_results": {},
                        "evidence_sources": [],
                        "data_origin": "UPLOADED",
                        "dataset_id": active_dataset,
                        "limitations": [f"Target dataset '{active_dataset}' does not exist."],
                        "errors": [{"agent": "Orchestrator", "error": f"Dataset '{active_dataset}' not found."}]
                    }
                if restaurant_id and ds_row.get("restaurant_id") != restaurant_id:
                    logger.warning(
                        f"Tenant isolation mismatch: request tenant '{restaurant_id}' attempted to access dataset '{active_dataset}' belonging to '{ds_row.get('restaurant_id')}'"
                    )
                    return {
                        "status": "error",
                        "answer": "⚠️ Tenant access violation: You are not authorized to access datasets belonging to another restaurant tenant.",
                        "route": [],
                        "selected_agents": [],
                        "agent_results": {},
                        "evidence_sources": [],
                        "data_origin": "UPLOADED",
                        "dataset_id": active_dataset,
                        "limitations": ["Cross-tenant dataset access is strictly prohibited."],
                        "errors": [{"agent": "Orchestrator", "error": f"Unauthorized cross-tenant access to dataset '{active_dataset}'."}]
                    }
            except Exception as e:
                logger.error(f"Tenant isolation check encountered an error: {sanitize_error(e)}")

        # Step 1: Intent Routing
        route = self.route_query(query)

        # Handle Greetings
        if route == ["greeting"]:
            greeting_msg = (
                "Hello! I am your Unified Restaurant Intelligence Orchestrator.\n"
                "I coordinate six specialized AI capabilities for your restaurant:\n"
                "1. Sales Intelligence (Revenue, order volumes, AOV, payment methods)\n"
                "2. Menu Intelligence (Dish rankings, category shares, pricing, zero-sales items)\n"
                "3. Feedback Intelligence (Customer ratings, sentiment, complaint drivers)\n"
                "4. Inventory & Waste Intelligence (Stock levels, reorder alerts, burn rates, variances)\n"
                "5. Decision & Recommendation (Prioritized, actionable executive action plans)\n"
                "6. Restaurant Knowledge (Standard operating procedures, food safety, storage policies)\n\n"
                "How can I assist your restaurant operations today?"
            )
            return {
                "status": "success",
                "answer": greeting_msg,
                "route": ["greeting"],
                "selected_agents": [],
                "agent_results": {},
                "evidence_sources": [],
                "data_origin": "SYNTHETIC",
                "limitations": ["Demonstration system operating on synthetic benchmark restaurant data."],
                "errors": None
            }

        # Handle Ambiguous / Unroutable Queries
        if not route:
            clarification_msg = (
                "Your inquiry is broad or ambiguous. To provide an accurate, evidence-backed answer, "
                "please clarify which area you would like to analyze:\n"
                "- Sales & Revenue (e.g., 'How many orders did we complete last week?')\n"
                "- Menu Performance (e.g., 'Which menu items perform poorly?')\n"
                "- Customer Feedback (e.g., 'What are customers complaining about?')\n"
                "- Inventory & Supplies (e.g., 'What ingredients need restocking?')\n"
                "- Management Actions (e.g., 'What actions should management prioritize?')\n"
                "- Restaurant SOP Policies (e.g., 'What does our food safety SOP say?')"
            )
            return {
                "status": "clarification_needed",
                "answer": clarification_msg,
                "route": [],
                "selected_agents": [],
                "agent_results": {},
                "evidence_sources": [],
                "data_origin": "SYNTHETIC",
                "limitations": ["Inquiry lacked specific operational domain keywords."],
                "errors": None
            }

        selected_agents = [self.agent_class_names[k] for k in route if k in self.agent_class_names]
        agent_results = {}
        evidence_sources = set()
        limitations = set()
        errors = []

        use_llm = (run_mode == "llm") or (run_mode == "auto" and self.llm_provider is not None)

        # Step 2: Execute each selected agent selectively
        for agent_key in route:
            if agent_key not in self.agent_factories:
                continue

            agent_name = self.agent_class_names[agent_key]
            limitations.add(DOMAIN_LIMITATIONS.get(agent_key, "Synthetic benchmark data."))

            try:
                agent_instance = self.agent_factories[agent_key](self.llm_provider if use_llm else None)
                agent_instance.dataset_id = active_dataset

                if use_llm:
                    exec_res = agent_instance.run_llm(query)
                else:
                    exec_res = agent_instance.run_simulation(query)

                final_resp = exec_res.get("final_response", "")
                tools_used = exec_res.get("executed_tools", [])

                # Track evidence sources
                for t in tools_used:
                    if isinstance(t, dict):
                        t_name = t.get("tool_name") or t.get("name")
                        if t_name:
                            evidence_sources.add(t_name)
                    elif isinstance(t, str):
                        evidence_sources.add(t)

                agent_results[agent_key] = {
                    "agent": agent_name,
                    "status": "success",
                    "answer": final_resp,
                    "executed_tools": tools_used
                }

            except Exception as e:
                err_msg = sanitize_error(e)
                logger.error(f"Agent execution failure [{agent_name}]: {err_msg}")
                errors.append({
                    "agent": agent_name,
                    "agent_key": agent_key,
                    "error": err_msg,
                    "message": f"Execution failed for {agent_name}: {err_msg}"
                })
                agent_results[agent_key] = {
                    "agent": agent_name,
                    "status": "error",
                    "error": err_msg,
                    "answer": f"⚠️ Evidence unavailable: {agent_name} encountered an error ({err_msg}).",
                    "executed_tools": []
                }

        # Step 3: Check execution outcomes
        successful_agents = [k for k, res in agent_results.items() if res.get("status") == "success"]
        failed_agents = [k for k, res in agent_results.items() if res.get("status") == "error"]

        if not successful_agents:
            overall_status = "error"
            consolidated_answer = (
                "⚠️ All requested specialist agents encountered errors during execution:\n"
                + "\n".join([f"  - {err['agent']}: {err['error']}" for err in errors])
                + "\n\nPlease check server logs, database connectivity, or LLM provider configuration."
            )
        elif failed_agents:
            overall_status = "partial_success"
            consolidated_answer = self._consolidate_answers(
                query=query,
                route=route,
                agent_results=agent_results,
                errors=errors,
                use_llm=use_llm
            )
        else:
            overall_status = "success"
            consolidated_answer = self._consolidate_answers(
                query=query,
                route=route,
                agent_results=agent_results,
                errors=[],
                use_llm=use_llm
            )

        if active_dataset:
            limitations.add(f"Grounded exclusively in uploaded dataset '{active_dataset}'. Baseline records are excluded.")

        return {
            "status": overall_status,
            "answer": consolidated_answer,
            "route": route,
            "selected_agents": selected_agents,
            "agent_results": agent_results,
            "evidence_sources": sorted(list(evidence_sources)),
            "data_origin": "UPLOADED" if active_dataset else "SYNTHETIC",
            "dataset_id": active_dataset,
            "limitations": sorted(list(limitations)),
            "errors": errors if errors else None
        }

    # -------------------------------------------------------------------------
    # 3. CONSOLIDATION WITHOUT FABRICATION OR DUPLICATION
    # -------------------------------------------------------------------------
    def _consolidate_answers(
        self,
        query: str,
        route: List[str],
        agent_results: Dict[str, Any],
        errors: List[Dict[str, Any]],
        use_llm: bool
    ) -> str:
        """
        Consolidates multi-agent findings into a unified, non-duplicated response.
        If a single agent answered, uses that answer directly.
        If multiple agents answered, synthesizes findings while preserving provenance and citations.
        """
        successful_keys = [k for k in route if agent_results.get(k, {}).get("status") == "success"]

        # Case A: Exactly one agent succeeded and no errors
        if len(successful_keys) == 1 and not errors:
            return agent_results[successful_keys[0]]["answer"]

        # Case B: LLM Synthesis for multi-agent evidence
        if use_llm and self.llm_provider and len(successful_keys) > 1:
            try:
                evidence_blocks = []
                for k in successful_keys:
                    agent_meta = agent_results[k]
                    evidence_blocks.append(
                        f"[{agent_meta['agent']} Findings]:\n{agent_meta['answer']}"
                    )
                combined_evidence = "\n\n" + ("=" * 40) + "\n\n".join(evidence_blocks)

                error_disclosures = ""
                if errors:
                    err_lines = [f"- {e['agent']}: {e['error']}" for e in errors]
                    error_disclosures = (
                        "\n\nDISCLOSED AGENT FAILURES (Disclose that these areas could not be verified):\n"
                        + "\n".join(err_lines)
                    )

                prompt = f"""You are the Unified Restaurant Intelligence Orchestrator.
The user asked: "{query}"

You have gathered verified factual evidence from the following specialized agents:
{combined_evidence}{error_disclosures}

STRICT CONSOLIDATION INSTRUCTIONS:
1. Synthesize a unified, structured executive answer addressing all facets of the user's inquiry.
2. Ground every single claim, metric, stock quantity, and recommendation strictly in the gathered evidence above.
3. Do NOT invent, extrapolate, or hallucinate metrics, prices, stock amounts, revenue numbers, or citations.
4. Deduplicate findings: Do not repeat identical metrics across different sections.
5. Clearly distinguish observed facts/data from analytical inferences and recommendations.
6. If document citations are present (e.g. [Document Title v1.0, Chunk X]), preserve them verbatim.
7. Retain data provenance disclosure: Explicitly mention that data origin is SYNTHETIC benchmark data.
8. If any agent failed, explicitly state which domain evidence is unavailable rather than pretending data is complete.
9. Keep the output clean, professional, and directly actionable."""

                res = self.llm_provider.generate(
                    messages=[{"role": "user", "content": prompt}],
                    tools=[],
                    system_instruction="You are an expert restaurant intelligence synthesizer. Ground everything strictly in the provided evidence."
                )
                if res.get("content"):
                    return res["content"].strip()
            except Exception as e:
                logger.warning(f"LLM consolidation failed: {e}. Falling back to deterministic consolidation.")

        # Case C: Deterministic Multi-Agent Assembly (Simulation or LLM fallback)
        sections = []
        sections.append("### Unified Restaurant Intelligence Report (Synthetic Benchmark Dataset)")

        for k in successful_keys:
            agent_meta = agent_results[k]
            sections.append(f"\n#### {agent_meta['agent']} Evidence:\n{agent_meta['answer']}")

        if errors:
            sections.append("\n#### ⚠️ Disclosed Limitations & Unavailable Data:")
            for err in errors:
                sections.append(f"- **{err['agent']}**: Failed to retrieve live data ({err['error']}). Findings for this domain are withheld.")

        sections.append("\n* Provenance: Grounded strictly in live Supabase queries and pgvector semantic retrieval. Data origin: SYNTHETIC.")

        return "\n".join(sections)
