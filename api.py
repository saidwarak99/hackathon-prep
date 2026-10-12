"""
api.py - FastAPI Backend for Restaurant Intelligence Multi-Agent System
"""

import sys
import os
import re
import logging

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pathlib import Path
_ENV_PATH = Path(__file__).resolve().parent / ".env"
try:
    from dotenv import load_dotenv
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
    else:
        load_dotenv(override=True)
except ImportError:
    pass

from db import test_connection, sanitize_error
from tools import get_menu, get_inventory, get_today_sales
from agent import (
    CafeAgent,
    SalesIntelligenceAgent,
    MenuIntelligenceAgent,
    FeedbackIntelligenceAgent,
    InventoryIntelligenceAgent,
    DecisionRecommendationAgent,
    RestaurantKnowledgeAgent
)
from orchestrator import AgentOrchestrator
from llm_provider import (
    GeminiProvider,
    QuotaExhaustedError,
    RateLimitError,
    ProviderOverloadError,
    ProviderAuthError,
    ModelNotFoundError,
    LLMProviderError,
    get_gemini_api_key
)
from rag.retrieval import search_restaurant_knowledge
from rag.ingestion import ingest_document
from dataset_ingestion import (
    preview_dataset,
    ingest_dataset,
    list_datasets,
    get_dataset_metadata,
    DatasetIngestionConfig
)

# Setup structured logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("restaurant_api")


def resolve_error_status_and_detail(agent_label: str, e: Exception) -> tuple[int, str]:
    """
    Returns appropriate HTTP status code and clear, sanitized error message.
    Distinguishes quota exhaustion (429), rate limits (429), 503 overloads, and database connection failures (503).
    Ensures no credentials, internal secrets, or raw provider tokens are exposed.
    """
    if isinstance(e, QuotaExhaustedError):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"{agent_label} service encountered an error [QUOTA_EXHAUSTED]: Gemini request quota has been exhausted. Please wait for daily quota reset or configure a paid API tier."
        )
    if isinstance(e, RateLimitError):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"{agent_label} service encountered an error [RATE_LIMIT_EXCEEDED]: Gemini request rate limit exceeded. Please retry after a brief pause."
        )
    if isinstance(e, ProviderOverloadError):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{agent_label} service encountered an error [PROVIDER_OVERLOADED]: Gemini provider is temporarily overloaded (503 UNAVAILABLE)."
        )
    if isinstance(e, ProviderAuthError):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{agent_label} service encountered an error [PROVIDER_AUTH_ERROR]: LLM Provider is not properly configured."
        )
    if isinstance(e, ModelNotFoundError):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{agent_label} service encountered an error [MODEL_ERROR]: {sanitize_error(e)}"
        )

    safe_msg = sanitize_error(e)
    safe_lower = safe_msg.lower()
    if any(k in safe_lower for k in ["quota", "resource_exhausted", "rate limit"]):
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"{agent_label} service encountered an error [QUOTA_EXHAUSTED]: {safe_msg}"
        )

    is_unavailable = any(keyword in safe_lower for keyword in [
        "503", "unavailable", "database", "connection", "connect", "timeout", "overloaded"
    ])
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE if is_unavailable else status.HTTP_500_INTERNAL_SERVER_ERROR
    return (status_code, f"{agent_label} service encountered an error: {safe_msg}")

app = FastAPI(
    title="Restaurant Intelligence API",
    description="Backend API exposing Supabase-connected restaurant data and multi-agent intelligence.",
    version="1.0.0"
)

# Configure CORS for frontend integration
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env.strip():
    allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
    origin_regex = None
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]
    # Allow any local port on localhost or 127.0.0.1 for seamless multi-port dev server support
    origin_regex = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

# In accordance with W3C fetch spec, allow_credentials must be False if wildcard is used
allow_creds = False if "*" in allowed_origins else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=origin_regex,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Pydantic Request & Response Models
# -----------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    database: str = Field(..., example="connected")
    server_version: Optional[str] = Field(None, example="PostgreSQL 15.1")


class MenuItemModel(BaseModel):
    menu_item_id: str
    name: str
    price: float
    dietary: List[str]
    description: Optional[str] = None
    is_available: bool


class MenuCategoryModel(BaseModel):
    category_name: str
    items: List[MenuItemModel]


class MenuResponse(BaseModel):
    status: str = Field(..., example="success")
    categories: List[MenuCategoryModel]
    total_items: int


class InventoryItemModel(BaseModel):
    item_name: str
    category: str
    current_stock: float
    unit: str
    min_reorder_level: float
    last_count_date: str
    status: str


class InventoryResponse(BaseModel):
    status: str = Field(..., example="success")
    items: Dict[str, InventoryItemModel]
    total_items: int
    low_stock_items_count: int


class SalesSummaryModel(BaseModel):
    total_orders: int
    total_revenue: float
    average_order_value: float
    busiest_hour: str


class TopSellingItemModel(BaseModel):
    item: str
    quantity_sold: int
    revenue: float


class SalesResponse(BaseModel):
    status: str = Field(..., example="success")
    date: str
    shift_status: str
    summary: SalesSummaryModel
    top_selling_items: List[TopSellingItemModel]
    payment_breakdown: Dict[str, float]


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question or query for the Restaurant Intelligence Agent"
    )


class ChatResponse(BaseModel):
    status: str = Field(..., example="success")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class SalesChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question for the Sales Intelligence Agent"
    )


class SalesChatResponse(BaseModel):
    status: str = Field(..., example="success")
    agent: str = Field("SalesIntelligenceAgent", example="SalesIntelligenceAgent")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class MenuChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question for the Menu Intelligence Agent"
    )


class MenuChatResponse(BaseModel):
    status: str = Field(..., example="success")
    agent: str = Field("MenuIntelligenceAgent", example="MenuIntelligenceAgent")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class FeedbackChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question for the Feedback Intelligence Agent"
    )


class FeedbackChatResponse(BaseModel):
    status: str = Field(..., example="success")
    agent: str = Field("FeedbackIntelligenceAgent", example="FeedbackIntelligenceAgent")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class InventoryChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question for the Inventory & Waste Intelligence Agent"
    )


class InventoryChatResponse(BaseModel):
    status: str = Field(..., example="success")
    agent: str = Field("InventoryIntelligenceAgent", example="InventoryIntelligenceAgent")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class RecommendationChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question or strategic request for the Decision & Recommendation Agent"
    )


class RecommendationChatResponse(BaseModel):
    status: str = Field(..., example="success")
    agent: str = Field("DecisionRecommendationAgent", example="DecisionRecommendationAgent")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class KnowledgeChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question for the Restaurant Knowledge / SOP Intelligence Agent"
    )


class KnowledgeChatResponse(BaseModel):
    status: str = Field(..., example="success")
    agent: str = Field("RestaurantKnowledgeAgent", example="RestaurantKnowledgeAgent")
    answer: str
    executed_tools: Optional[List[Dict[str, Any]]] = None


class UnifiedChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or request for the unified restaurant intelligence multi-agent system"
    )
    restaurant_id: Optional[str] = Field(
        "default_restaurant",
        max_length=64,
        description="Tenant / restaurant identifier for dataset scoping"
    )
    dataset_id: Optional[str] = Field(
        None,
        max_length=64,
        description="Optional uploaded dataset identifier to query instead of baseline"
    )


class UnifiedChatResponse(BaseModel):
    status: str = Field(..., example="success")
    answer: str
    route: List[str] = Field(..., example=["sales"])
    selected_agents: List[str] = Field(..., example=["SalesIntelligenceAgent"])
    agent_results: Dict[str, Any]
    evidence_sources: List[str]
    data_origin: str = "SYNTHETIC"
    dataset_id: Optional[str] = None
    limitations: List[str]
    errors: Optional[List[Dict[str, Any]]] = None


class FilePreviewSummaryModel(BaseModel):
    filename: str
    detected_section: str
    row_count: int
    valid_rows_count: Optional[int] = None
    headers: List[str]
    column_mapping: Optional[Dict[str, str]] = None
    sample_records: Optional[List[Dict[str, Any]]] = None
    missing_required: Optional[List[str]] = None
    error: Optional[str] = None


class DatasetPreviewResponse(BaseModel):
    status: str
    is_valid: bool
    filename: str
    content_hash: str
    is_duplicate: bool
    existing_dataset_id: Optional[str] = None
    total_rows: int
    detected_sections: List[str]
    files_summary: List[FilePreviewSummaryModel]
    validation_errors: List[str]
    warnings: List[str]


class DatasetIngestResponse(BaseModel):
    status: str
    message: str
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    restaurant_id: Optional[str] = None
    detected_sections: Optional[List[str]] = None
    rows_ingested: Optional[int] = None
    content_hash: Optional[str] = None
    data_origin: str = "UPLOADED"
    warnings: Optional[List[str]] = None
    validation_errors: Optional[List[str]] = None
    limitations: Optional[List[str]] = None


class DatasetMetadataModel(BaseModel):
    dataset_id: str
    restaurant_id: str
    dataset_name: str
    detected_section: str
    original_filename: str
    upload_timestamp: str
    ingestion_status: str
    row_count: int
    data_origin: str


class DatasetListResponse(BaseModel):
    status: str
    total_datasets: int
    datasets: List[DatasetMetadataModel]


class DatasetDetailResponse(BaseModel):
    status: str
    dataset: Dict[str, Any]


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language question or search phrase for restaurant SOP and knowledge"
    )
    top_k: int = Field(3, ge=1, le=10, description="Maximum number of relevant chunks to retrieve")
    restaurant_id: str = Field("default_restaurant", max_length=50, description="Restaurant tenant identifier")


class KnowledgeChunkItem(BaseModel):
    chunk_id: str
    document_id: str
    source_title: str
    source_version: str
    chunk_index: int
    page_number: Optional[int] = 1
    chunk_text: str
    similarity: float
    citation: str
    effective_date: Optional[str] = None
    data_origin: str = "SYNTHETIC"


class KnowledgeSearchResponse(BaseModel):
    status: str
    query: str
    total_results: int
    results: List[KnowledgeChunkItem]
    citations: List[str]
    data_origin: str = "SYNTHETIC"


class KnowledgeIngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Title of the document")
    content: str = Field(..., min_length=1, max_length=500000, description="Raw text or markdown content of the document")
    document_type: str = Field("sop", max_length=50, description="Type tag (e.g. sop, manual, policy)")
    version: str = Field("1.0", max_length=20, description="Document version string")
    restaurant_id: str = Field("default_restaurant", max_length=50, description="Restaurant tenant identifier")
    force_reprocess: bool = Field(False, description="Whether to force re-embedding if document exists")


class KnowledgeIngestResponse(BaseModel):
    status: str
    document_id: str
    title: str
    chunks_indexed: int
    embedding_model: str
    embedding_dimension: int
    restaurant_id: str
    data_origin: str = "SYNTHETIC"





# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """
    Checks the API health and PostgreSQL database connectivity.
    Returns HTTP 200 when database is connected, or HTTP 503 if unavailable.
    """
    db_res = test_connection()
    if db_res.get("status") == "connected":
        return HealthResponse(
            status="ok",
            database="connected",
            server_version=db_res.get("server_version")
        )
    else:
        logger.warning(f"Health check failed: database unavailable - {db_res.get('message')}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": "unavailable",
                "message": "Database connection is unavailable."
            }
        )


@app.get("/api/menu", response_model=MenuResponse, tags=["Restaurant Data"])
def get_menu_endpoint(
    category: Optional[str] = Query(None, max_length=50, description="Optional category name filter")
):
    """
    Retrieves cafe menu items organized by categories from Supabase.
    """
    result = get_menu(category=category.strip() if category else None)
    if result.get("status") == "error":
        logger.error(f"Error fetching menu: {result.get('message')}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Database error fetching menu.")
        )
    
    data = result.get("data", {})
    return MenuResponse(
        status="success",
        categories=data.get("categories", []),
        total_items=data.get("total_items", 0)
    )


@app.get("/api/inventory", response_model=InventoryResponse, tags=["Restaurant Data"])
def get_inventory_endpoint(
    low_stock_only: bool = Query(False, description="Filter to return only items at or below reorder levels")
):
    """
    Retrieves current stock levels, units, and low-stock alerts from Supabase.
    """
    result = get_inventory(low_stock_only=low_stock_only)
    if result.get("status") == "error":
        logger.error(f"Error fetching inventory: {result.get('message')}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Database error fetching inventory.")
        )

    data = result.get("data", {})
    summary = result.get("summary", {})
    return InventoryResponse(
        status="success",
        items=data,
        total_items=summary.get("total_items", 0),
        low_stock_items_count=summary.get("low_stock_items_count", 0)
    )


@app.get("/api/sales", response_model=SalesResponse, tags=["Restaurant Data"])
def get_sales_endpoint(
    date: Optional[str] = Query(None, description="Optional target date in YYYY-MM-DD format")
):
    """
    Retrieves financial metrics, top sellers, and payment breakdowns from completed orders.
    """
    if date:
        date_clean = date.strip()
        # Validate date format and validity
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_clean):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Expected YYYY-MM-DD."
            )
        try:
            datetime.strptime(date_clean, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid calendar date provided."
            )
    else:
        date_clean = None

    result = get_today_sales(date_str=date_clean)
    if result.get("status") == "error":
        logger.error(f"Error fetching sales: {result.get('message')}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.get("message", "Database error fetching sales.")
        )

    data = result.get("data", {})
    summary = data.get("summary", {})
    return SalesResponse(
        status="success",
        date=data.get("date", "N/A"),
        shift_status=data.get("shift_status", "N/A"),
        summary=SalesSummaryModel(
            total_orders=summary.get("total_orders", 0),
            total_revenue=summary.get("total_revenue", 0.0),
            average_order_value=summary.get("average_order_value", 0.0),
            busiest_hour=summary.get("busiest_hour", "N/A")
        ),
        top_selling_items=data.get("top_selling_items", []),
        payment_breakdown=data.get("payment_breakdown", {})
    )


@app.post("/api/chat", response_model=UnifiedChatResponse, tags=["Unified Intelligence"])
def unified_chat_endpoint(request: UnifiedChatRequest):
    """
    Unified Orchestration endpoint for the Restaurant Intelligence Multi-Agent System.
    Accepts natural-language inquiries, selectively routes to the 6 specialized agents,
    and synthesizes a grounded, non-duplicated response with complete provenance.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    restaurant_id = request.restaurant_id.strip() if request.restaurant_id else "default_restaurant"

    try:
        llm_provider = GeminiProvider()
        orchestrator = AgentOrchestrator(llm_provider=llm_provider, dataset_id=request.dataset_id)
        res = orchestrator.orchestrate(
            cleaned_message,
            restaurant_id=restaurant_id,
            run_mode="llm",
            dataset_id=request.dataset_id
        )

        if res.get("status") == "error":
            error_details = res.get("errors") or []
            error_msg = "; ".join([e.get("message", "Agent error") for e in error_details]) if error_details else "All requested agents failed."
            is_unavailable = any(keyword in error_msg.lower() for keyword in ["503", "unavailable", "database", "connection", "connect", "timeout", "resource_exhausted", "quota"])
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE if is_unavailable else status.HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(
                status_code=status_code,
                detail=f"Unified orchestrator encountered an error: {error_msg}"
            )

        return UnifiedChatResponse(
            status=res["status"],
            answer=res["answer"],
            route=res["route"],
            selected_agents=res["selected_agents"],
            agent_results=res["agent_results"],
            evidence_sources=res["evidence_sources"],
            data_origin=res.get("data_origin", "SYNTHETIC"),
            dataset_id=res.get("dataset_id"),
            limitations=res.get("limitations", []),
            errors=res.get("errors")
        )
    except HTTPException:
        raise
    except Exception as e:
        safe_msg = sanitize_error(e)
        logger.error(f"Unified chat orchestration failed: {safe_msg}")
        safe_lower = safe_msg.lower()
        is_unavailable = any(keyword in safe_lower for keyword in ["503", "unavailable", "database", "connection", "connect", "timeout", "resource_exhausted", "quota"])
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if is_unavailable else status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(
            status_code=status_code,
            detail=f"Unified orchestrator failed: {safe_msg}"
        )


@app.post("/api/agents/chat", response_model=ChatResponse, tags=["Agent Intelligence"])
def chat_agent_endpoint(request: ChatRequest):
    """
    Communicates with the Restaurant Intelligence Agent.
    Executes the multi-tool Gemini agent loop backed by live Supabase queries and RAG.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        # Create request-scoped provider and agent to prevent shared state issues
        llm_provider = GeminiProvider()
        agent = CafeAgent(name="BaristaBot", llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return ChatResponse(
            status="success",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Agent", e)
        logger.error(f"Chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/agents/sales/chat", response_model=SalesChatResponse, tags=["Agent Intelligence"])
def sales_chat_endpoint(request: SalesChatRequest):
    """
    Communicates with the specialized Sales Intelligence Agent.
    Executes multi-tool revenue, volume, and period-over-period sales analytics grounded in database records.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        # Create request-scoped provider and agent to prevent shared state issues
        llm_provider = GeminiProvider()
        agent = SalesIntelligenceAgent(llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return SalesChatResponse(
            status="success",
            agent="SalesIntelligenceAgent",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Sales agent", e)
        logger.error(f"Sales chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/agents/menu/chat", response_model=MenuChatResponse, tags=["Agent Intelligence"])
def menu_chat_endpoint(request: MenuChatRequest):
    """
    Communicates with the specialized Menu Intelligence Agent.
    Executes menu performance, best/worst seller rankings, category share, and menu optimization analysis.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        # Create request-scoped provider and agent to prevent shared state issues
        llm_provider = GeminiProvider()
        agent = MenuIntelligenceAgent(llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return MenuChatResponse(
            status="success",
            agent="MenuIntelligenceAgent",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Menu agent", e)
        logger.error(f"Menu chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/agents/feedback/chat", response_model=FeedbackChatResponse, tags=["Agent Intelligence"])
def feedback_chat_endpoint(request: FeedbackChatRequest):
    """
    Communicates with the specialized Feedback Intelligence Agent.
    Executes customer review analytics, rating distributions, sentiment breakdown, complaint trends, and item feedback.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        # Create request-scoped provider and agent to prevent shared state issues
        llm_provider = GeminiProvider()
        agent = FeedbackIntelligenceAgent(llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return FeedbackChatResponse(
            status="success",
            agent="FeedbackIntelligenceAgent",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Feedback agent", e)
        logger.error(f"Feedback chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/agents/inventory/chat", response_model=InventoryChatResponse, tags=["Agent Intelligence"])
def inventory_chat_endpoint(request: InventoryChatRequest):
    """
    Communicates with the specialized Inventory & Waste Intelligence Agent.
    Analyzes current stock health, low-stock reorder priorities, ingredient burn rates, stock movements, and waste variance.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        # Create request-scoped provider and agent to prevent shared state issues
        llm_provider = GeminiProvider()
        agent = InventoryIntelligenceAgent(llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return InventoryChatResponse(
            status="success",
            agent="InventoryIntelligenceAgent",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Inventory agent", e)
        logger.error(f"Inventory chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/agents/recommendations/chat", response_model=RecommendationChatResponse, tags=["Agent Intelligence"])
def recommendations_chat_endpoint(request: RecommendationChatRequest):
    """
    Communicates with the specialized Decision & Recommendation Agent.
    Synthesizes multi-domain evidence (sales, menu performance, customer complaints, and inventory stock health)
    into prioritized, actionable restaurant business recommendations.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        # Create request-scoped provider and agent to prevent shared state issues
        llm_provider = GeminiProvider()
        agent = DecisionRecommendationAgent(llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return RecommendationChatResponse(
            status="success",
            agent="DecisionRecommendationAgent",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Recommendation agent", e)
        logger.error(f"Recommendation chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/agents/knowledge/chat", response_model=KnowledgeChatResponse, tags=["Agent Intelligence"])
def knowledge_chat_endpoint(request: KnowledgeChatRequest):
    """
    Communicates with the specialized Restaurant Knowledge Intelligence Agent.
    Retrieves and reasons over restaurant SOPs, hygiene rules, and storage policies grounded in Supabase pgvector.
    """
    cleaned_message = request.message.strip()
    if not cleaned_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty or whitespace only."
        )

    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key is not configured in environment.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Provider is not configured on the server."
        )

    try:
        llm_provider = GeminiProvider()
        agent = RestaurantKnowledgeAgent(llm_provider=llm_provider)
        agent_result = agent.run_llm(cleaned_message)

        return KnowledgeChatResponse(
            status="success",
            agent="RestaurantKnowledgeAgent",
            answer=agent_result.get("final_response", ""),
            executed_tools=agent_result.get("executed_tools", [])
        )
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Knowledge agent", e)
        logger.error(f"Knowledge chat agent execution failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


@app.post("/api/knowledge/search", response_model=KnowledgeSearchResponse, tags=["Restaurant Knowledge"])
def search_knowledge_endpoint(request: KnowledgeSearchRequest):
    """
    Performs semantic vector search across restaurant SOPs, policies, and operational manuals
    stored in Supabase pgvector. Returns ranked text chunks, similarity scores, and citations.
    """
    cleaned_query = request.query.strip()
    if not cleaned_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query cannot be empty or whitespace only."
        )

    res = search_restaurant_knowledge(
        query=cleaned_query,
        top_k=request.top_k,
        restaurant_id=request.restaurant_id.strip()
    )

    if res.get("status") == "error":
        raw_msg = res.get("message", "Error executing knowledge retrieval.")
        safe_msg = sanitize_error(raw_msg)
        is_quota = any(k in safe_msg.lower() for k in ["quota", "resource_exhausted", "429", "rate limit"])
        status_code = status.HTTP_429_TOO_MANY_REQUESTS if is_quota else status.HTTP_503_SERVICE_UNAVAILABLE
        detail_text = (
            f"Knowledge search service encountered an error [QUOTA_EXHAUSTED]: {safe_msg}"
            if is_quota else f"Knowledge search service encountered an error: {safe_msg}"
        )
        raise HTTPException(
            status_code=status_code,
            detail=detail_text
        )

    return KnowledgeSearchResponse(
        status=res.get("status", "success"),
        query=cleaned_query,
        total_results=res.get("total_results", 0),
        results=res.get("results", []),
        citations=res.get("citations", []),
        data_origin=res.get("data_origin", "SYNTHETIC")
    )


@app.post("/api/knowledge/ingest", response_model=KnowledgeIngestResponse, tags=["Restaurant Knowledge"])
def ingest_knowledge_endpoint(request: KnowledgeIngestRequest):
    """
    Ingests text or markdown operational documentation into Supabase pgvector.
    Extracts text, splits into cohesive chunks, generates dense Gemini embeddings,
    and indexes for semantic retrieval with duplicate avoidance.
    """
    cleaned_title = request.title.strip()
    cleaned_content = request.content.strip()

    if not cleaned_title or not cleaned_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title and content cannot be empty or whitespace only."
        )

    try:
        res = ingest_document(
            raw_content=cleaned_content,
            title=cleaned_title,
            document_type=request.document_type.strip(),
            version=request.version.strip(),
            restaurant_id=request.restaurant_id.strip(),
            force_reprocess=request.force_reprocess
        )

        if res.get("status") in ("success", "already_indexed"):
            return KnowledgeIngestResponse(
                status=res.get("status"),
                document_id=res.get("document_id", "DOC_UNKNOWN"),
                title=res.get("title", cleaned_title),
                chunks_indexed=res.get("chunks_indexed", res.get("chunks_count", 0)),
                embedding_model=res.get("embedding_model", "gemini-embedding-2"),
                embedding_dimension=res.get("embedding_dimension", 768),
                restaurant_id=request.restaurant_id.strip(),
                data_origin=res.get("data_origin", "SYNTHETIC")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=res.get("message", "Ingestion failed.")
            )

    except HTTPException:
        raise
    except Exception as e:
        status_code, detail_msg = resolve_error_status_and_detail("Knowledge ingestion", e)
        logger.error(f"Knowledge ingestion failed: {detail_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=detail_msg
        )


# -----------------------------------------------------------------------------
# Dynamic Dataset Ingestion Endpoints (Phase 4)
# -----------------------------------------------------------------------------

@app.post("/api/datasets/preview", response_model=DatasetPreviewResponse, tags=["Dataset Ingestion"])
async def preview_dataset_endpoint(
    file: UploadFile = File(...),
    restaurant_id: str = Form("default_restaurant")
):
    """
    Validates and dry-runs an uploaded CSV or ZIP archive.
    Does NOT mutate or save records to the database.
    Detects target sections, normalizes column aliases, checks types,
    and returns error/warning summaries with sample previews.
    """
    filename = file.filename or "upload.csv"
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty (0 bytes)."
        )

    if len(file_bytes) > DatasetIngestionConfig.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {DatasetIngestionConfig.MAX_FILE_SIZE_BYTES} bytes."
        )

    res = preview_dataset(
        file_bytes=file_bytes,
        original_filename=filename,
        restaurant_id=restaurant_id.strip() if restaurant_id else "default_restaurant"
    )

    return DatasetPreviewResponse(**res)


@app.post("/api/datasets/ingest", response_model=DatasetIngestResponse, tags=["Dataset Ingestion"])
async def ingest_dataset_endpoint(
    file: UploadFile = File(...),
    dataset_name: Optional[str] = Form(None),
    restaurant_id: str = Form("default_restaurant")
):
    """
    Atomically imports a validated CSV file or ZIP archive into Supabase dataset_records.
    Generates a unique dataset_id for scoped query isolation.
    Preserves existing baseline synthetic records.
    """
    filename = file.filename or "upload.csv"
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty (0 bytes)."
        )

    if len(file_bytes) > DatasetIngestionConfig.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {DatasetIngestionConfig.MAX_FILE_SIZE_BYTES} bytes."
        )

    res = ingest_dataset(
        file_bytes=file_bytes,
        original_filename=filename,
        dataset_name=dataset_name,
        restaurant_id=restaurant_id.strip() if restaurant_id else "default_restaurant"
    )

    if res.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res
        )

    return DatasetIngestResponse(**res)


@app.get("/api/datasets", response_model=DatasetListResponse, tags=["Dataset Ingestion"])
def list_datasets_endpoint(
    restaurant_id: Optional[str] = Query(None, description="Optional tenant filter")
):
    """
    Lists all uploaded datasets, their row counts, ingestion statuses, and upload timestamps.
    """
    ds_list = list_datasets(restaurant_id=restaurant_id.strip() if restaurant_id else None)
    return DatasetListResponse(
        status="success",
        total_datasets=len(ds_list),
        datasets=[DatasetMetadataModel(**d) for d in ds_list]
    )


@app.get("/api/datasets/{dataset_id}", response_model=DatasetDetailResponse, tags=["Dataset Ingestion"])
def get_dataset_endpoint(
    dataset_id: str,
    restaurant_id: Optional[str] = Query(None, description="Optional tenant identifier for scoped authorization")
):
    """
    Retrieves metadata, section summaries, and validation information for a specific dataset.
    Validates tenant ownership when restaurant_id is supplied.
    """
    meta = get_dataset_metadata(dataset_id.strip())
    if not meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found."
        )
    if restaurant_id and meta.get("restaurant_id") != restaurant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Dataset belongs to another restaurant tenant."
        )
    return DatasetDetailResponse(
        status="success",
        dataset=meta
    )






