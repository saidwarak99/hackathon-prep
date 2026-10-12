// API Schema types matching FastAPI backend in api.py

export interface HealthResponse {
  status: string;
  database: string;
  server_version?: string;
}

export interface MenuItem {
  menu_item_id: string;
  name: string;
  price: number;
  dietary: string[];
  description?: string;
  is_available: boolean;
}

export interface MenuCategory {
  category_name: string;
  items: MenuItem[];
}

export interface MenuResponse {
  status: string;
  categories: MenuCategory[];
  total_items: number;
}

export interface InventoryItem {
  item_name: string;
  category: string;
  current_stock: number;
  unit: string;
  min_reorder_level: number;
  last_count_date: string;
  status: string;
}

export interface InventoryResponse {
  status: string;
  items: Record<string, InventoryItem>;
  total_items: number;
  low_stock_items_count: number;
}

export interface SalesSummary {
  total_orders: number;
  total_revenue: number;
  average_order_value: number;
  busiest_hour: string;
}

export interface TopSellingItem {
  item: string;
  quantity_sold: number;
  revenue: number;
}

export interface SalesResponse {
  status: string;
  date: string;
  shift_status: string;
  summary: SalesSummary;
  top_selling_items: TopSellingItem[];
  payment_breakdown: Record<string, number>;
}

export interface UnifiedChatRequest {
  message: string;
  restaurant_id?: string;
  dataset_id?: string;
}

export interface UnifiedChatResponse {
  status: string;
  answer: string;
  route: string[];
  selected_agents: string[];
  agent_results: Record<string, any>;
  evidence_sources: string[];
  data_origin: string;
  dataset_id?: string;
  limitations: string[];
  errors?: Array<{ agent?: string; message?: string; [key: string]: any }>;
}

export interface AgentChatResponse {
  status: string;
  agent?: string;
  answer: string;
  executed_tools?: Array<{
    tool_name?: string;
    tool?: string;
    args?: Record<string, any>;
    result?: any;
    [key: string]: any;
  }>;
}

export interface KnowledgeSearchRequest {
  query: string;
  top_k?: number;
  restaurant_id?: string;
}

export interface KnowledgeChunkItem {
  chunk_id: string;
  document_id: string;
  source_title: string;
  source_version: string;
  chunk_index: number;
  page_number: number;
  chunk_text: string;
  similarity: number;
  citation: string;
  effective_date?: string;
  data_origin: string;
}

export interface KnowledgeSearchResponse {
  status: string;
  query: string;
  total_results: number;
  results: KnowledgeChunkItem[];
  citations: string[];
  data_origin: string;
}

export interface KnowledgeIngestRequest {
  title: string;
  content: string;
  document_type?: string;
  version?: string;
  restaurant_id?: string;
  force_reprocess?: boolean;
}

export interface KnowledgeIngestResponse {
  status: string;
  document_id: string;
  title: string;
  chunks_indexed: number;
  embedding_model: string;
  embedding_dimension: number;
  restaurant_id: string;
  data_origin: string;
}

export interface FilePreviewSummary {
  filename: string;
  detected_section: string;
  row_count: number;
  valid_rows_count?: number;
  headers: string[];
  column_mapping?: Record<string, string>;
  sample_records?: Array<Record<string, any>>;
  missing_required?: string[];
  error?: string;
}

export interface DatasetPreviewResponse {
  status: string;
  is_valid: boolean;
  filename: string;
  content_hash: string;
  is_duplicate: boolean;
  existing_dataset_id?: string;
  total_rows: number;
  detected_sections: string[];
  files_summary: FilePreviewSummary[];
  validation_errors: string[];
  warnings: string[];
}

export interface DatasetIngestResponse {
  status: string;
  message: string;
  dataset_id?: string;
  dataset_name?: string;
  restaurant_id?: string;
  detected_sections?: string[];
  rows_ingested?: number;
  content_hash?: string;
  data_origin: string;
  warnings?: string[];
  validation_errors?: string[];
  limitations?: string[];
}

export interface DatasetMetadata {
  dataset_id: string;
  restaurant_id: string;
  dataset_name: string;
  detected_section: string;
  original_filename: string;
  upload_timestamp: string;
  ingestion_status: string;
  row_count: number;
  data_origin: string;
}

export interface DatasetListResponse {
  status: string;
  total_datasets: number;
  datasets: DatasetMetadata[];
}

export interface DatasetDetailResponse {
  status: string;
  dataset: Record<string, any>;
}
