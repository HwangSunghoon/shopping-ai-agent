import type {
  AgentFilters,
  AgentSearchResponse,
  ChatResponse,
  FeedbackEventType,
  FeedbackResponse,
  HistoryItem,
  RecommendResponse,
  SearchDetail,
  SearchResponse,
  UIProduct,
} from "../types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function parseError(response: Response, fallbackMessage: string) {
  const err = await response.json().catch(() => null);
  return err?.detail || fallbackMessage;
}

export async function fetchHistory() {
  const response = await fetch(`${API_BASE_URL}/api/history`);
  if (!response.ok) {
    throw new Error(await parseError(response, "검색 기록을 불러오지 못했습니다."));
  }
  return (await response.json()) as HistoryItem[];
}

export async function fetchSearch(query: string) {
  const response = await fetch(`${API_BASE_URL}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "검색 요청에 실패했습니다."));
  }

  return (await response.json()) as SearchResponse;
}

export async function fetchRecommend(userId: string, query: string, limit = 20) {
  const response = await fetch(`${API_BASE_URL}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      query,
      limit,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "개인화 추천을 불러오지 못했습니다."));
  }

  return (await response.json()) as RecommendResponse;
}

export async function fetchSearchDetail(searchId: number) {
  const response = await fetch(`${API_BASE_URL}/api/search/${searchId}`);
  if (!response.ok) {
    throw new Error(await parseError(response, "검색 기록을 불러오지 못했습니다."));
  }
  return (await response.json()) as SearchDetail;
}

type ChatPayload = {
  searchId: number;
  message: string;
  selectedProductLink?: string | null;
  selectedProductTitle?: string | null;
};

export async function fetchChatResponse(payload: ChatPayload) {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      search_id: payload.searchId,
      message: payload.message,
      selected_product_link: payload.selectedProductLink || null,
      selected_product_title: payload.selectedProductTitle || null,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "추가 안내를 불러오지 못했습니다."));
  }

  return (await response.json()) as ChatResponse;
}

type FeedbackPayload = {
  userId: string;
  eventType: FeedbackEventType;
  query?: string | null;
  product?: UIProduct | null;
  reason?: string | null;
};

export async function fetchFeedback(payload: FeedbackPayload) {
  const response = await fetch(`${API_BASE_URL}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      event_type: payload.eventType,
      query: payload.query || null,
      product: payload.product
        ? {
            product_id: payload.product.id,
            title: payload.product.title,
            price: payload.product.lprice,
            category: payload.product.category,
            brand: payload.product.title.split(" ")[0] || null,
            mallName: payload.product.mall_name || payload.product.seller,
          }
        : null,
      reason: payload.reason || null,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "피드백 저장에 실패했습니다."));
  }

  return (await response.json()) as FeedbackResponse;
}

type AgentSearchPayload = {
  userId: string;
  query: string;
  conversationId?: string | null;
  filters?: AgentFilters;
  page?: number;
  display?: number;
  trackEvent?: boolean;
  searchTermLimit?: number;
  conversationContext?: unknown;
};

export async function fetchAgentSearch(payload: AgentSearchPayload) {
  const response = await fetch(`${API_BASE_URL}/api/agent/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      query: payload.query,
      conversation_id: payload.conversationId || null,
      filters: payload.filters,
      page: payload.page || 1,
      display: payload.display || 20,
      track_event: payload.trackEvent ?? true,
      search_term_limit: payload.searchTermLimit || null,
      conversation_context: payload.conversationContext || null,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "상품 검색에 실패했습니다."));
  }

  return (await response.json()) as AgentSearchResponse;
}

type AgentRefinePayload = {
  userId: string;
  conversationId: string;
  message: string;
  filters?: AgentFilters;
  page?: number;
  display?: number;
  currentProductIds?: string[];
  currentTop3Ids?: string[];
  currentProducts?: unknown[];
  currentTop3Products?: unknown[];
  conversationContext?: unknown;
};

export async function fetchAgentRefine(payload: AgentRefinePayload) {
  const response = await fetch(`${API_BASE_URL}/api/agent/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      conversation_id: payload.conversationId,
      message: payload.message,
      filters: payload.filters,
      page: payload.page || 1,
      display: payload.display || 20,
      current_product_ids: payload.currentProductIds || [],
      current_top3_ids: payload.currentTop3Ids || [],
      current_products: payload.currentProducts || [],
      current_top3_products: payload.currentTop3Products || [],
      conversation_context: payload.conversationContext || null,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "조건 반영에 실패했습니다."));
  }

  return (await response.json()) as AgentSearchResponse;
}

type AgentFeedbackPayload = {
  userId: string;
  conversationId?: string | null;
  productId: string;
  eventType: FeedbackEventType;
  metadata?: Record<string, unknown>;
};

export async function fetchAgentFeedback(payload: AgentFeedbackPayload) {
  const response = await fetch(`${API_BASE_URL}/api/agent/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      conversation_id: payload.conversationId || null,
      product_id: payload.productId,
      event_type: payload.eventType,
      metadata: payload.metadata || {},
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "피드백 저장에 실패했습니다."));
  }

  return (await response.json()) as FeedbackResponse;
}

type AgentFinalSelectPayload = {
  userId: string;
  conversationId: string;
  productId: string;
  product?: Record<string, unknown>;
};

export async function fetchAgentFinalSelect(payload: AgentFinalSelectPayload) {
  const response = await fetch(`${API_BASE_URL}/api/agent/final-select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      conversation_id: payload.conversationId,
      product_id: payload.productId,
      product: payload.product || null,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "최종 선택 저장에 실패했습니다."));
  }

  return (await response.json()) as { status: string; event_id: number; product_id: string };
}
