export type ApiProduct = {
  title: string;
  link: string;
  image?: string | null;
  mall_name?: string | null;
  category?: string | null;
  lprice?: number | null;
  score: number;
  reason: string;
  caution?: string;
  rank?: number | null;
  brand?: string | null;
  rating?: number | null;
  review_count?: number | null;
  shipping_badges?: string[];
  ai_tags?: string[];
  short_reason?: string;
  final_score?: number;
  final_selected?: boolean;
};

export type SearchIntent = {
  keyword?: string;
  product_group?: string;
  max_price?: number | null;
  min_price?: number | null;
  important_features?: string[];
  exclude_keywords?: string[];
  use_case?: string | null;
  comparison_criteria?: string[];
};

export type SearchResponse = {
  search_id: number;
  query: string;
  intent: SearchIntent;
  search_terms: string[];
  raw_result_count: number;
  candidate_count: number;
  products: ApiProduct[];
  recommendations: ApiProduct[];
  assistant_message: string;
  summary_mode: string;
  fallback_active: boolean;
  fallback_reason?: string | null;
  needs_clarification: boolean;
  clarification_questions: string[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  message: string;
  created_at?: string;
};

export type SearchDetail = SearchResponse & {
  chat_history: ChatMessage[];
};

export type HistoryItem = {
  id: number;
  query: string;
  assistant_message: string;
  fallback_active: boolean;
  created_at: string;
  search_terms: string[];
};

export type ChatResponse = {
  search_id: number;
  user_message: string;
  assistant_message: string;
  fallback_active: boolean;
  fallback_reason?: string | null;
  summary_mode: string;
  selected_product_link?: string | null;
  selected_product_title?: string | null;
  chat_history: ChatMessage[];
};

export type UIProduct = ApiProduct & {
  id: string;
  seller: string;
  rating: number;
  reviewCount: number;
  shippingLabel: string;
  badges: string[];
  aiTags: string[];
  highlight?: string;
  brand?: string | null;
  finalSelected?: boolean;
};

export type HomeShowcaseSection = {
  id: string;
  title: string;
  query: string;
  products: UIProduct[];
  hasMore: boolean;
  nextPage: number | null;
  loadingMore?: boolean;
  imageOnly?: boolean;
};

export type FeedbackEventType =
  | "click"
  | "like"
  | "save"
  | "purchase_intent"
  | "dislike"
  | "remove"
  | "not_relevant"
  | "too_expensive"
  | "low_quality"
  | "review_too_low";

export type FeedbackResponse = {
  status: string;
  event_id: number;
  updated_preference_count: number;
  preferences: Record<string, unknown>;
};

export type RecommendPreferenceItem = {
  key: string;
  value: unknown;
};

export type RecommendResponse = {
  answer: string;
  products: ApiProduct[];
  user_preference_used: RecommendPreferenceItem[];
  debug?: Record<string, unknown> | null;
};

export type DebugSnapshot = {
  query: string;
  searchTerms: string[];
  interpretation: string[];
  activeCategory: string;
  activeShippingFilters: string[];
  activePriceRange: string;
  activeSort: string;
  selectedProductTitle?: string | null;
  feedbackPreferences?: Record<string, unknown> | null;
  recommendationPreferences?: RecommendPreferenceItem[];
  recommendationDebug?: Record<string, unknown> | null;
  feedbackMessage?: string;
};

export type AgentFilters = {
  categories: string[];
  price_ranges: string[];
  shipping: string[];
  review: string[];
  brands: string[];
  malls: string[];
  product_state: string[];
  user_preferences: string[];
};

export type ShoppingConversationState = {
  original_query: string;
  refined_queries: string[];
  extracted_preferences: {
    category?: string | null;
    subcategories: string[];
    budget_min?: number | null;
    budget_max?: number | null;
    usage_context: string[];
    preferred_features: string[];
    disliked_features: string[];
    preferred_brands: string[];
    excluded_brands: string[];
    sort_intent?: string | null;
  };
  constraints: {
    min_review_count?: number | null;
    min_rating?: number | null;
    required_shipping: string[];
    result_limit?: number | null;
    scope_mode?: string | null;
  };
  user_feedback: {
    liked_product_ids: string[];
    disliked_product_ids: string[];
    too_expensive_product_ids: string[];
    hidden_product_ids: string[];
  };
  final_selected_product_id?: string | null;
};

export type AgentSearchResponse = {
  conversation_id: string;
  original_query: string;
  applied_query: string;
  products: ApiProduct[];
  has_more: boolean;
  next_page?: number | null;
  interpreted_intent: SearchIntent;
  expanded_queries: string[];
  available_filters: Record<string, string[]>;
  selected_filters: AgentFilters;
  top_recommendation?: ApiProduct | null;
  recommendation_reason: string;
  assistant_trace: string;
  conversation_context: ShoppingConversationState;
  debug?: Record<string, unknown> | null;
};
