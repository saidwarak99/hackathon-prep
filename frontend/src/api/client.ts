import {
  HealthResponse,
  MenuResponse,
  InventoryResponse,
  SalesResponse,
  UnifiedChatRequest,
  UnifiedChatResponse,
  AgentChatResponse,
  KnowledgeSearchRequest,
  KnowledgeSearchResponse,
  KnowledgeIngestRequest,
  KnowledgeIngestResponse,
  DatasetPreviewResponse,
  DatasetIngestResponse,
  DatasetListResponse,
  DatasetDetailResponse,
} from './types';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  detail: any;

  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorDetail: any = null;
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        errorDetail = await response.json();
        if (typeof errorDetail === 'string') {
          errorMessage = errorDetail;
        } else if (errorDetail && typeof errorDetail.detail === 'string') {
          errorMessage = errorDetail.detail;
        } else if (errorDetail && typeof errorDetail.message === 'string') {
          errorMessage = errorDetail.message;
        } else if (errorDetail && errorDetail.detail) {
          errorMessage = JSON.stringify(errorDetail.detail);
        }
      } catch {
        // Not a JSON response
      }
      throw new ApiError(response.status, errorMessage, errorDetail);
    }

    return (await response.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(0, err?.message || 'Network request failed. Is the backend server running?');
  }
}

export const apiClient = {
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health');
  },

  async getMenu(category?: string): Promise<MenuResponse> {
    const query = category ? `?category=${encodeURIComponent(category)}` : '';
    return request<MenuResponse>(`/api/menu${query}`);
  },

  async getInventory(lowStockOnly: boolean = false): Promise<InventoryResponse> {
    const query = lowStockOnly ? `?low_stock_only=true` : '';
    return request<InventoryResponse>(`/api/inventory${query}`);
  },

  async getSales(date?: string): Promise<SalesResponse> {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    return request<SalesResponse>(`/api/sales${query}`);
  },

  async sendUnifiedChat(data: UnifiedChatRequest): Promise<UnifiedChatResponse> {
    return request<UnifiedChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async sendAgentChat(
    agentType: 'sales' | 'menu' | 'feedback' | 'inventory' | 'recommendations' | 'general',
    message: string
  ): Promise<AgentChatResponse> {
    let endpoint = '/api/agents/chat';
    if (agentType === 'sales') endpoint = '/api/agents/sales/chat';
    else if (agentType === 'menu') endpoint = '/api/agents/menu/chat';
    else if (agentType === 'feedback') endpoint = '/api/agents/feedback/chat';
    else if (agentType === 'inventory') endpoint = '/api/agents/inventory/chat';
    else if (agentType === 'recommendations') endpoint = '/api/agents/recommendations/chat';

    return request<AgentChatResponse>(endpoint, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },

  async searchKnowledge(req: KnowledgeSearchRequest): Promise<KnowledgeSearchResponse> {
    return request<KnowledgeSearchResponse>('/api/knowledge/search', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async ingestKnowledge(req: KnowledgeIngestRequest): Promise<KnowledgeIngestResponse> {
    return request<KnowledgeIngestResponse>('/api/knowledge/ingest', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async previewDataset(file: File, restaurantId: string = 'default_restaurant'): Promise<DatasetPreviewResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('restaurant_id', restaurantId);

    return request<DatasetPreviewResponse>('/api/datasets/preview', {
      method: 'POST',
      body: formData,
    });
  },

  async ingestDataset(
    file: File,
    datasetName?: string,
    restaurantId: string = 'default_restaurant'
  ): Promise<DatasetIngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (datasetName) {
      formData.append('dataset_name', datasetName);
    }
    formData.append('restaurant_id', restaurantId);

    return request<DatasetIngestResponse>('/api/datasets/ingest', {
      method: 'POST',
      body: formData,
    });
  },

  async listDatasets(restaurantId?: string): Promise<DatasetListResponse> {
    const query = restaurantId ? `?restaurant_id=${encodeURIComponent(restaurantId)}` : '';
    return request<DatasetListResponse>(`/api/datasets${query}`);
  },

  async getDatasetDetail(datasetId: string): Promise<DatasetDetailResponse> {
    return request<DatasetDetailResponse>(`/api/datasets/${encodeURIComponent(datasetId)}`);
  },
};
