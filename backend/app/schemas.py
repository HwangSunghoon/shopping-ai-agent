from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["20만원 이하 자취방용 조용한 제습기 추천해줘"])
    user_id: str = "demo-user"


class ShoppingConditions(BaseModel):
    keyword: str = ""
    product_group: str = ""
    max_price: int | None = None
    min_price: int | None = None
    important_features: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    use_case: str | None = None
    comparison_criteria: list[str] = Field(default_factory=list)


class Product(BaseModel):
    title: str
    link: str
    image: str | None = None
    mall_name: str | None = None
    category: str | None = None
    lprice: int | None = None
    score: int = 0
    reason: str = ""
    caution: str = ""
    rank: int | None = None


class ChatMessage(BaseModel):
    role: str
    message: str
    created_at: str


class HistoryItem(BaseModel):
    id: int
    query: str
    assistant_message: str
    fallback_active: bool = False
    created_at: str
    search_terms: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    search_id: int
    query: str
    intent: dict[str, Any]
    search_terms: list[str]
    raw_result_count: int
    candidate_count: int
    products: list[Product]
    recommendations: list[Product]
    assistant_message: str
    summary_mode: str = "llm"
    fallback_active: bool = False
    fallback_reason: str | None = None
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)


class SearchDetailResponse(SearchResponse):
    chat_history: list[ChatMessage] = Field(default_factory=list)


class ChatRequest(BaseModel):
    search_id: int = Field(..., ge=1)
    message: str = Field(..., min_length=1)
    selected_product_link: str | None = None
    selected_product_title: str | None = None


class ChatResponse(BaseModel):
    search_id: int
    user_message: str
    assistant_message: str
    fallback_active: bool = False
    fallback_reason: str | None = None
    summary_mode: str = "llm"
    selected_product_link: str | None = None
    selected_product_title: str | None = None
    chat_history: list[ChatMessage] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    user_id: str = "demo-user"
    query: str
    limit: int = 20


class FeedbackRequest(BaseModel):
    user_id: str = "demo-user"
    event_type: str
    query: str | None = None
    product: dict[str, Any] | None = None
    reason: str | None = None


class RecommendResponse(BaseModel):
    answer: str
    products: list[dict[str, Any]] = Field(default_factory=list)
    user_preference_used: list[dict[str, Any]] = Field(default_factory=list)
    debug: dict[str, Any] | None = None


class AgentFilters(BaseModel):
    categories: list[str] = Field(default_factory=list)
    price_ranges: list[str] = Field(default_factory=list)
    shipping: list[str] = Field(default_factory=list)
    review: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    malls: list[str] = Field(default_factory=list)
    product_state: list[str] = Field(default_factory=list)
    user_preferences: list[str] = Field(default_factory=list)


class ConversationPreferenceState(BaseModel):
    category: str | None = None
    subcategories: list[str] = Field(default_factory=list)
    budget_min: int | None = None
    budget_max: int | None = None
    usage_context: list[str] = Field(default_factory=list)
    preferred_features: list[str] = Field(default_factory=list)
    disliked_features: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)
    sort_intent: str | None = None


class ConversationFeedbackState(BaseModel):
    liked_product_ids: list[str] = Field(default_factory=list)
    disliked_product_ids: list[str] = Field(default_factory=list)
    too_expensive_product_ids: list[str] = Field(default_factory=list)
    hidden_product_ids: list[str] = Field(default_factory=list)


class ConversationConstraintState(BaseModel):
    min_review_count: int | None = None
    min_rating: float | None = None
    required_shipping: list[str] = Field(default_factory=list)
    result_limit: int | None = None
    scope_mode: str | None = None


class ShoppingConversationState(BaseModel):
    original_query: str = ""
    refined_queries: list[str] = Field(default_factory=list)
    extracted_preferences: ConversationPreferenceState = Field(default_factory=ConversationPreferenceState)
    constraints: ConversationConstraintState = Field(default_factory=ConversationConstraintState)
    user_feedback: ConversationFeedbackState = Field(default_factory=ConversationFeedbackState)
    final_selected_product_id: str | None = None


class AgentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    conversation_id: str | None = None
    filters: AgentFilters = Field(default_factory=AgentFilters)
    page: int = Field(default=1, ge=1)
    display: int = Field(default=20, ge=1, le=40)
    track_event: bool = True
    search_term_limit: int | None = Field(default=None, ge=1, le=6)
    conversation_context: ShoppingConversationState | None = None


class AgentRefineRequest(BaseModel):
    conversation_id: str
    message: str = Field(..., min_length=1)
    user_id: str = "demo-user"
    current_product_ids: list[str] = Field(default_factory=list)
    current_top3_ids: list[str] = Field(default_factory=list)
    current_products: list[dict[str, Any]] = Field(default_factory=list)
    current_top3_products: list[dict[str, Any]] = Field(default_factory=list)
    filters: AgentFilters = Field(default_factory=AgentFilters)
    page: int = Field(default=1, ge=1)
    display: int = Field(default=20, ge=1, le=40)
    conversation_context: ShoppingConversationState | None = None


class AgentFeedbackRequest(BaseModel):
    user_id: str = "demo-user"
    conversation_id: str | None = None
    product_id: str
    event_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentFinalSelectRequest(BaseModel):
    user_id: str = "demo-user"
    conversation_id: str
    product_id: str
    product: dict[str, Any] | None = None


class AgentSearchResponse(BaseModel):
    conversation_id: str
    original_query: str
    applied_query: str
    products: list[dict[str, Any]] = Field(default_factory=list)
    has_more: bool = False
    next_page: int | None = None
    interpreted_intent: dict[str, Any] = Field(default_factory=dict)
    expanded_queries: list[str] = Field(default_factory=list)
    available_filters: dict[str, list[str]] = Field(default_factory=dict)
    selected_filters: dict[str, list[str]] = Field(default_factory=dict)
    top_recommendation: dict[str, Any] | None = None
    recommendation_reason: str = ""
    assistant_trace: str = ""
    conversation_context: ShoppingConversationState
    debug: dict[str, Any] | None = None
