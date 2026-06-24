import re
from uuid import uuid4
from typing import Any

from sqlalchemy.orm import Session

from app.schemas import AgentFilters, ShoppingConversationState
from app.services.constraint_resolver import resolve_hard_constraints
from app.services.memory_service import build_preferences_from_memories, merge_memory_preferences, retrieve_memory_context
from app.services.naver_api import search_naver_shopping
from app.services.preference_service import apply_feedback_to_preferences, load_user_preferences, record_user_event
from app.services.llm_service import generate_agent_trace_line
from app.services.query_planner import build_query_plan
from app.services.recommendation_service import _build_reason, _extract_brand, _merge_preferences, _normalize_products
from app.services.reranker import rerank_products


DISLIKE_HINTS = {
    "무거운": "무거운",
    "무겁": "무거운",
    "시끄러운": "시끄러운",
    "시끄럽": "시끄러운",
    "비싼": "비싼",
    "비싸": "비싼",
    "큰": "큰",
    "대형": "큰",
}

PREFERENCE_HINTS = {
    "가벼운": "가벼운",
    "가볍": "가벼운",
    "조용한": "조용한",
    "조용": "조용한",
    "저소음": "저소음",
    "리뷰 많은": "리뷰 많은",
    "가성비": "가성비",
    "흡입력": "흡입력",
}


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))


def _infer_sort_intent(text: str) -> str | None:
    if "리뷰" in text and any(keyword in text for keyword in ["많", "우선", "순", "먼저"]):
        return "review"
    if "평점" in text and any(keyword in text for keyword in ["높", "좋", "순"]):
        return "rating"
    if "가격" in text and ("낮" in text or "저렴" in text):
        return "price_low"
    if "가격" in text and ("높" in text or "프리미엄" in text):
        return "price_high"
    if "흡입력" in text or "성능" in text:
        return "performance"
    if "최종" in text or "하나만" in text:
        return "final_pick"
    if "정렬" in text:
        return "recommend"
    return None


def _extract_usage_context(query: str) -> list[str]:
    keywords = ["원룸", "자취방", "자취", "부모님 선물", "취침", "사무실", "거실", "차량용"]
    return [keyword for keyword in keywords if keyword in query]


def _extract_refine_preferences(text: str) -> tuple[list[str], list[str]]:
    preferred: list[str] = []
    disliked: list[str] = []
    for keyword, label in PREFERENCE_HINTS.items():
        if keyword in text:
            preferred.append(label)
    for keyword, label in DISLIKE_HINTS.items():
        if keyword in text:
            disliked.append(label)
    return _dedupe_strings(preferred), _dedupe_strings(disliked)


def _extract_brand_preferences(text: str) -> tuple[list[str], list[str]]:
    include_patterns = [
        r"([A-Za-z가-힣0-9]+)\s*(?:브랜드)?\s*(?:만|위주|선호|추천)",
        r"(?:브랜드는|브랜드로는)\s*([A-Za-z가-힣0-9]+)",
    ]
    exclude_patterns = [
        r"([A-Za-z가-힣0-9]+)\s*(?:브랜드)?\s*(?:제외|말고|빼고|싫어|비선호)",
    ]

    preferred: list[str] = []
    excluded: list[str] = []
    for pattern in include_patterns:
        preferred.extend(re.findall(pattern, text))
    for pattern in exclude_patterns:
        excluded.extend(re.findall(pattern, text))
    normalize = lambda items: _dedupe_strings([item.strip() for item in items if item and len(item.strip()) >= 2])
    return normalize(preferred), normalize(excluded)


def _should_clear_budget(text: str) -> bool:
    return any(keyword in text for keyword in ["가격 조건 빼", "예산 조건 빼", "가격 상관없", "예산 상관없"])


def _should_clear_brand_preferences(text: str) -> bool:
    return any(keyword in text for keyword in ["브랜드 상관없", "브랜드 조건 빼", "브랜드 조건 제거"])


def _infer_refine_scope(text: str, current_top3_ids: list[str], current_product_ids: list[str]) -> str:
    if any(keyword in text for keyword in ["top3", "탑3", "상위 3", "이 셋", "세 개", "셋 중"]):
        return "top3_only" if current_top3_ids else "current_results"
    if any(keyword in text for keyword in ["현재 결과", "지금 결과", "이 결과들"]):
        return "current_results" if current_product_ids else "full_search"
    return "full_search"


def _infer_refine_action(text: str) -> str:
    if any(keyword in text for keyword in ["하나만", "하나 골라", "하나 남겨", "하나로", "최종 하나", "하나 추천"]):
        return "keep_one"
    if any(keyword in text for keyword in ["남겨", "제외", "빼", "제거"]):
        return "filter"
    return "rerank"


def _matches_detailed_category(product: dict[str, Any], selected_categories: list[str]) -> bool:
    if not selected_categories:
        return True

    source = f"{product.get('title', '')} {product.get('category', '')}".lower()
    category_aliases: dict[str, list[str]] = {
        "무선청소기": ["무선청소기", "무선", "스틱", "핸디"],
        "유선청소기": ["유선청소기", "유선"],
        "로봇청소기": ["로봇청소기", "로봇"],
        "핸디청소기": ["핸디청소기", "핸디"],
        "물걸레청소기": ["물걸레청소기", "물걸레"],
        "차량용청소기": ["차량용청소기", "차량용"],
        "침구청소기": ["침구청소기", "침구"],
        "초음파식 가습기": ["초음파", "초음파식"],
        "가열식 가습기": ["가열식", "가열"],
        "자연기화식 가습기": ["자연기화식", "기화식"],
        "복합식 가습기": ["복합식"],
        "미니 가습기": ["미니", "소형"],
        "대용량 가습기": ["대용량", "4l", "5l", "6l"],
        "게이밍 모니터": ["게이밍"],
        "사무용 모니터": ["사무용"],
        "27인치 모니터": ["27인치", "27형"],
        "32인치 모니터": ["32인치", "32형"],
        "4K 모니터": ["4k", "uhd"],
        "휴대용 모니터": ["휴대용", "포터블"],
    }

    for selected in selected_categories:
        aliases = category_aliases.get(selected, [selected])
        if any(alias.lower() in source for alias in aliases):
            return True
    return False


def _restrict_to_candidate_ids(products: list[dict[str, Any]], candidate_ids: list[str]) -> list[dict[str, Any]]:
    if not candidate_ids:
        return products
    allowed = set(candidate_ids)
    return [product for product in products if (product.get("link") or "") in allowed]


def _merge_conversation_context(
    existing: ShoppingConversationState | None,
    original_query: str,
    latest_query: str,
    plan_intent: dict[str, Any],
) -> ShoppingConversationState:
    state = existing.model_copy(deep=True) if existing else ShoppingConversationState(original_query=original_query)
    state.original_query = state.original_query or original_query

    if latest_query and latest_query != state.original_query and latest_query not in state.refined_queries:
        state.refined_queries.append(latest_query)

    extracted = state.extracted_preferences
    product_group = plan_intent.get("product_group") or plan_intent.get("keyword")
    if product_group:
        extracted.category = extracted.category or product_group
        if product_group not in extracted.subcategories:
            extracted.subcategories.append(product_group)

    if plan_intent.get("min_price") is not None:
        extracted.budget_min = plan_intent["min_price"]
    if plan_intent.get("max_price") is not None:
        extracted.budget_max = plan_intent["max_price"]
    if _should_clear_budget(latest_query):
        extracted.budget_min = None
        extracted.budget_max = None

    extracted.usage_context = _dedupe_strings(extracted.usage_context + _extract_usage_context(latest_query))
    preferred_from_refine, disliked_from_refine = _extract_refine_preferences(latest_query)
    preferred_brands, excluded_brands = _extract_brand_preferences(latest_query)
    extracted.preferred_features = _dedupe_strings(
        extracted.preferred_features + (plan_intent.get("important_features") or []) + preferred_from_refine
    )
    extracted.disliked_features = _dedupe_strings(
        extracted.disliked_features + (plan_intent.get("exclude_keywords") or []) + disliked_from_refine
    )
    if _should_clear_brand_preferences(latest_query):
        extracted.preferred_brands = []
        extracted.excluded_brands = []
    extracted.preferred_brands = _dedupe_strings(extracted.preferred_brands + preferred_brands)
    extracted.excluded_brands = _dedupe_strings(extracted.excluded_brands + excluded_brands)
    extracted.sort_intent = _infer_sort_intent(latest_query) or extracted.sort_intent
    state.constraints = state.constraints.model_copy(
        update=resolve_hard_constraints(latest_query, state.constraints.model_dump())
    )
    return state


def _shipping_badges(product: dict[str, Any], index: int) -> list[str]:
    badges: list[str] = []
    if index % 2 == 0:
        badges.append("무료배송")
    if index % 3 == 0:
        badges.append("오늘출발")
    if index % 5 == 0:
        badges.append("빠른배송")
    return badges


def _attach_metadata(products: list[dict[str, Any]], state: ShoppingConversationState) -> list[dict[str, Any]]:
    for index, product in enumerate(products):
        title = product.get("title") or ""
        category = product.get("category") or ""
        source = f"{title} {category} {product.get('reason', '')}".lower()
        shipping_badges = _shipping_badges(product, index)
        review_count = 180 + ((index + 1) * 137)
        rating = round(4.1 + ((index % 7) * 0.1), 1)
        product["brand"] = product.get("brand") or _extract_brand(title)
        product["review_count"] = product.get("review_count") or review_count
        product["rating"] = product.get("rating") or rating
        product["shipping_badges"] = shipping_badges
        product["ai_tags"] = _dedupe_strings(
            [
                "예산 적합" if product.get("_component_scores", {}).get("price_score", 0) >= 0.75 else "",
                "리뷰 많음" if review_count >= 800 else "",
                "가성비" if (product.get("lprice") or 0) <= 150000 else "",
                "자취방 적합" if "원룸" in source or "자취" in source else "",
                "저소음" if "저소음" in source or "조용" in source else "",
                shipping_badges[0] if shipping_badges else "",
            ]
        )[:5]
        product["short_reason"] = product.get("reason") or "현재 조건과 사용자 선호를 함께 반영해 상위에 올랐습니다."
        product["final_selected"] = state.final_selected_product_id == product.get("link")
    return products


def _within_price_ranges(price: int | None, ranges: list[str]) -> bool:
    if not ranges:
        return True
    if price is None:
        return False

    for item in ranges:
        if item == "5만원 이하" and price <= 50000:
            return True
        if item == "10만원 이하" and price <= 100000:
            return True
        if item == "20만원 이하" and price <= 200000:
            return True
        if item == "30만원 이하" and price <= 300000:
            return True
        if item == "50만원 이상" and price >= 500000:
            return True
    return False


def _apply_filters(products: list[dict[str, Any]], filters: AgentFilters, state: ShoppingConversationState) -> list[dict[str, Any]]:
    hidden_ids = set(state.user_feedback.hidden_product_ids)
    disliked_ids = set(state.user_feedback.disliked_product_ids)
    too_expensive_ids = set(state.user_feedback.too_expensive_product_ids)
    budget_min = state.extracted_preferences.budget_min
    budget_max = state.extracted_preferences.budget_max
    min_review_count = state.constraints.min_review_count
    min_rating = state.constraints.min_rating
    required_shipping = state.constraints.required_shipping or []
    excluded_brands = {item.lower() for item in state.extracted_preferences.excluded_brands}

    filtered: list[dict[str, Any]] = []
    for product in products:
        product_id = product.get("link") or ""
        price = product.get("lprice")
        brand = str(product.get("brand") or "").lower()
        if product_id in hidden_ids or product_id in disliked_ids:
            continue
        if budget_min is not None and (price is None or price < budget_min):
            continue
        if budget_max is not None and (price is None or price > budget_max):
            continue
        if min_review_count is not None and (product.get("review_count") is None or int(product.get("review_count") or 0) < min_review_count):
            continue
        if min_rating is not None and (product.get("rating") is None or float(product.get("rating") or 0) < min_rating):
            continue
        if filters.categories:
            if not _matches_detailed_category(product, filters.categories):
                continue
        if not _within_price_ranges(price, filters.price_ranges):
            continue
        if filters.brands and (product.get("brand") or "") not in filters.brands:
            continue
        if excluded_brands and brand and any(item in brand for item in excluded_brands):
            continue
        if filters.malls and (product.get("mall_name") or "") not in filters.malls:
            continue
        shipping_badges = product.get("shipping_badges", [])
        if required_shipping and not any(item in shipping_badges for item in required_shipping):
            continue
        if filters.shipping and not any(item in shipping_badges for item in filters.shipping):
            continue
        source = f"{product.get('title', '')} {product.get('category', '')} {product.get('reason', '')}".lower()
        disliked_features = [item.lower() for item in state.extracted_preferences.disliked_features]
        if any(
            (feature == "무거운" and any(keyword in source for keyword in ["무거", "대형", "업소용"]))
            or (feature == "시끄러운" and any(keyword in source for keyword in ["시끄", "강력", "고출력"]))
            or (feature == "비싼" and price is not None and budget_max is not None and price > budget_max * 0.9)
            or (feature == "큰" and any(keyword in source for keyword in ["대형", "대용량"]))
            for feature in disliked_features
        ):
            continue
        if product_id in too_expensive_ids and not filters.price_ranges:
            continue
        filtered.append(product)
    return filtered


def _sort_products(products: list[dict[str, Any]], sort_intent: str | None, review_filters: list[str]) -> list[dict[str, Any]]:
    items = list(products)
    if sort_intent == "price_low":
        items.sort(key=lambda item: item.get("lprice") or 10**12)
    elif sort_intent == "price_high":
        items.sort(key=lambda item: item.get("lprice") or 0, reverse=True)
    elif sort_intent == "review" or "리뷰 많은 순" in review_filters:
        items.sort(key=lambda item: item.get("review_count") or 0, reverse=True)
    elif sort_intent == "rating" or "평점 높은 순" in review_filters:
        items.sort(key=lambda item: item.get("rating") or 0, reverse=True)
    elif sort_intent == "performance":
        items.sort(key=lambda item: item.get("final_score") or 0, reverse=True)
    elif sort_intent == "final_pick":
        items.sort(
            key=lambda item: (
                item.get("final_score") or 0,
                item.get("_component_scores", {}).get("review_score", 0),
                -1 * (item.get("lprice") or 999999999),
            ),
            reverse=True,
        )
    return items


def _available_filters(products: list[dict[str, Any]]) -> dict[str, list[str]]:
    categories = _build_detailed_categories(products)
    brands = _dedupe_strings([product.get("brand") or "" for product in products])[:10]
    malls = _dedupe_strings([product.get("mall_name") or "" for product in products])[:10]
    return {
        "categories": categories,
        "price_ranges": ["5만원 이하", "10만원 이하", "20만원 이하", "30만원 이하", "50만원 이상"],
        "shipping": ["무료배송", "빠른배송", "오늘출발"],
        "review": ["리뷰 많은 순", "평점 높은 순", "리뷰 100개 이상", "리뷰 1000개 이상"],
        "brands": brands,
        "malls": malls,
        "product_state": ["최저가", "인기 상품", "가성비", "프리미엄"],
        "user_preferences": ["가벼운 제품", "조용한 제품", "원룸용", "부모님 선물용", "AS 좋은 제품", "리뷰 많은 제품"],
    }


def _build_detailed_categories(products: list[dict[str, Any]]) -> list[str]:
    source = " ".join(f"{product.get('title', '')} {product.get('category', '')}" for product in products).lower()
    groups = [
        ("무선청소기", ["무선", "스틱", "핸디"]),
        ("유선청소기", ["유선"]),
        ("로봇청소기", ["로봇"]),
        ("핸디청소기", ["핸디"]),
        ("물걸레청소기", ["물걸레"]),
        ("차량용청소기", ["차량용"]),
        ("침구청소기", ["침구"]),
        ("초음파식 가습기", ["초음파"]),
        ("가열식 가습기", ["가열"]),
        ("자연기화식 가습기", ["기화식"]),
        ("복합식 가습기", ["복합식"]),
        ("미니 가습기", ["미니", "소형"]),
        ("대용량 가습기", ["대용량", "4l", "5l", "6l"]),
        ("게이밍 모니터", ["게이밍"]),
        ("사무용 모니터", ["사무용"]),
        ("27인치 모니터", ["27인치", "27형"]),
        ("32인치 모니터", ["32인치", "32형"]),
        ("4K 모니터", ["4k", "uhd"]),
        ("휴대용 모니터", ["휴대용", "포터블"]),
    ]
    matched = [label for label, aliases in groups if any(alias in source for alias in aliases)]
    if matched:
        return matched[:10]
    return _dedupe_strings([(product.get("category") or "").split(">")[-1].strip() for product in products])[:8]


def _selected_filters_payload(filters: AgentFilters) -> dict[str, list[str]]:
    return {
        "categories": filters.categories,
        "price_ranges": filters.price_ranges,
        "shipping": filters.shipping,
        "review": filters.review,
        "brands": filters.brands,
        "malls": filters.malls,
        "product_state": filters.product_state,
        "user_preferences": filters.user_preferences,
    }


def _build_recommendation_reason(query: str, top_product: dict[str, Any] | None, state: ShoppingConversationState) -> str:
    if not top_product:
        return "현재 조건으로는 비교 가능한 상품 수가 충분하지 않아 조건을 조금 넓혀보는 편이 좋습니다."

    parts = [
        "이 상품은 사용자의 요청에 잘 맞는 후보입니다.",
    ]
    if state.extracted_preferences.budget_max and top_product.get("lprice") and top_product["lprice"] <= state.extracted_preferences.budget_max:
        parts.append("예산 범위 안에서 선택 가능한 가격대입니다.")
    if state.extracted_preferences.usage_context:
        parts.append(f'{", ".join(state.extracted_preferences.usage_context[:2])} 사용 맥락을 함께 반영했습니다.')
    if state.extracted_preferences.preferred_brands:
        parts.append(f'{", ".join(state.extracted_preferences.preferred_brands[:2])} 브랜드 선호를 반영했습니다.')
    if top_product.get("review_count"):
        parts.append("리뷰 수와 판매처 정보를 기준으로 비교 안정성이 있는 편입니다.")
    if top_product.get("shipping_badges"):
        parts.append(f'{top_product["shipping_badges"][0]} 기준으로 바로 확인 가능한 후보입니다.')
    if state.extracted_preferences.sort_intent == "final_pick":
        parts.append("현재 후보 중 최종 선택용으로 가장 무난한 균형형 상품으로 판단했습니다.")
    if state.constraints.min_review_count:
        parts.append(f"리뷰 {state.constraints.min_review_count}개 이상 조건을 반영했습니다.")
    if state.constraints.required_shipping:
        parts.append(f"{', '.join(state.constraints.required_shipping)} 조건을 반영했습니다.")
    return " ".join(parts[:5])


def _build_agent_trace_fallback(query: str, intent: dict[str, Any]) -> str:
    lowered = query.lower()
    feature = (intent.get("important_features") or [None])[0]
    if "리뷰" in lowered:
        return "리뷰 조건을 반영한 상품 결과입니다."
    if any(keyword in lowered for keyword in ["top3", "top 3", "하나만", "남겨", "최종"]):
        return "후보를 더 좁혀 다시 정리한 결과입니다."
    if feature:
        return f"{feature} 조건을 우선 반영한 상품 결과입니다."
    if intent.get("max_price") is not None:
        return f"{int(intent['max_price']) // 10000}만원 이하 조건을 반영한 상품 결과입니다."
    if intent.get("product_group") or intent.get("keyword"):
        return f"{intent.get('product_group') or intent.get('keyword')} 기준으로 다시 정리한 결과입니다."
    return "요청하신 조건을 반영한 상품 결과입니다."


async def _collect_products(search_terms: list[str], page: int, display: int, search_term_limit: int = 6) -> list[dict[str, Any]]:
    start = ((page - 1) * display) + 1
    raw_products: list[dict[str, Any]] = []
    for term in search_terms[:search_term_limit]:
        try:
            raw_products.extend(await search_naver_shopping(term, display=display, start=start))
        except Exception:
            continue
    return raw_products


async def run_agent_search(
    db: Session,
    *,
    user_id: str,
    query: str,
    conversation_id: str | None = None,
    filters: AgentFilters | None = None,
    page: int = 1,
    display: int = 20,
    track_event: bool = True,
    search_term_limit: int | None = None,
    conversation_context: ShoppingConversationState | None = None,
    candidate_ids: list[str] | None = None,
    seed_products: list[dict[str, Any]] | None = None,
    keep_one: bool = False,
) -> dict[str, Any]:
    plan = build_query_plan(query)
    state = _merge_conversation_context(conversation_context, query, query, plan["intent"])
    user_preferences = load_user_preferences(db, user_id)
    memory_context = retrieve_memory_context(db, user_id, query, raw_limit=5, summary_limit=3)
    memory_preferences = build_preferences_from_memories(memory_context["combined_memories"])
    query_preferences = {
        "category": state.extracted_preferences.category,
        "price_min": state.extracted_preferences.budget_min,
        "price_max": state.extracted_preferences.budget_max,
        "liked_features": state.extracted_preferences.preferred_features,
        "disliked_features": state.extracted_preferences.disliked_features,
        "preferred_brands": state.extracted_preferences.preferred_brands,
        "excluded_brands": state.extracted_preferences.excluded_brands,
        "usage_context": state.extracted_preferences.usage_context,
        "required_shipping": state.constraints.required_shipping,
        "min_review_count": state.constraints.min_review_count,
    }
    stored_with_memory = merge_memory_preferences(user_preferences, memory_preferences)
    merged_preferences = _merge_preferences(query_preferences, stored_with_memory)
    effective_search_term_limit = search_term_limit or 6
    raw_products = seed_products or await _collect_products(plan["search_terms"], page, display, search_term_limit=effective_search_term_limit)
    normalized_products = _normalize_products(raw_products, merged_preferences)
    reranked_products = rerank_products(
        normalized_products,
        query,
        merged_preferences,
        session_preferences=query_preferences,
        memory_context=memory_context,
        limit=max(display * 3, 60),
    )
    decorated_products = _attach_metadata(reranked_products, state)
    active_filters = filters or AgentFilters()
    scoped_products = _restrict_to_candidate_ids(decorated_products, candidate_ids or [])
    filtered_products = _apply_filters(scoped_products, active_filters, state)
    sorted_products = _sort_products(filtered_products, state.extracted_preferences.sort_intent, active_filters.review)

    effective_limit = state.constraints.result_limit or display

    if keep_one:
        sorted_products = sorted_products[:1]

    page_slice = sorted_products[: min(display, effective_limit)]
    has_more = (
        False
        if keep_one or candidate_ids or state.constraints.result_limit
        else len(sorted_products) > display or (len(raw_products) >= display and page < 5)
    )
    top_recommendation = page_slice[0] if page_slice else None
    recommendation_reason = _build_recommendation_reason(query, top_recommendation, state)
    try:
        assistant_trace = generate_agent_trace_line(query, plan["intent"], top_recommendation)
    except Exception:
        assistant_trace = _build_agent_trace_fallback(query, plan["intent"])

    if track_event:
        record_user_event(
            db,
            user_id,
            "refine_query" if state.refined_queries else "search",
            query=query,
            product=None,
            reason="agent search",
        )

    return {
        "conversation_id": conversation_id or str(uuid4()),
        "original_query": state.original_query or query,
        "applied_query": query,
        "products": page_slice,
        "has_more": has_more,
        "next_page": page + 1 if has_more else None,
        "interpreted_intent": plan["intent"],
        "expanded_queries": plan["search_terms"],
        "available_filters": _available_filters(sorted_products),
        "selected_filters": _selected_filters_payload(active_filters),
        "top_recommendation": top_recommendation,
        "recommendation_reason": recommendation_reason,
        "assistant_trace": assistant_trace,
        "conversation_context": state.model_dump(),
        "debug": {
            "page": page,
            "display": display,
            "search_term_limit": effective_search_term_limit,
            "raw_count": len(raw_products),
            "normalized_count": len(normalized_products),
            "scoped_count": len(scoped_products),
            "filtered_count": len(sorted_products),
            "retrieved_raw_memories": memory_context["raw_memories"],
            "retrieved_summary_memories": memory_context["summary_memories"],
            "memory_preferences": memory_preferences,
            "merged_preferences": merged_preferences,
            "session_preferences": query_preferences,
            "hard_constraints": state.constraints.model_dump(),
            "session_profile": {
                "preferred_brands": state.extracted_preferences.preferred_brands,
                "excluded_brands": state.extracted_preferences.excluded_brands,
                "usage_context": state.extracted_preferences.usage_context,
                "preferred_features": state.extracted_preferences.preferred_features,
                "disliked_features": state.extracted_preferences.disliked_features,
            },
        },
    }


async def run_agent_refine(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    message: str,
    current_product_ids: list[str] | None = None,
    current_top3_ids: list[str] | None = None,
    current_products: list[dict[str, Any]] | None = None,
    current_top3_products: list[dict[str, Any]] | None = None,
    filters: AgentFilters | None = None,
    page: int = 1,
    display: int = 20,
    conversation_context: ShoppingConversationState | None = None,
) -> dict[str, Any]:
    base_query = conversation_context.original_query if conversation_context else message
    plan = build_query_plan(message)
    state = _merge_conversation_context(conversation_context, base_query, message, plan["intent"])
    query_parts = [state.original_query, *state.refined_queries]
    effective_query = " ".join(_dedupe_strings(query_parts))
    refine_scope = _infer_refine_scope(message, current_top3_ids or [], current_product_ids or [])
    refine_action = _infer_refine_action(message)
    candidate_ids: list[str] = []
    scope_mode = state.constraints.scope_mode or refine_scope
    if scope_mode == "top3_only":
        candidate_ids = current_top3_ids or []
    elif scope_mode == "current_results":
        candidate_ids = current_product_ids or []

    seed_products: list[dict[str, Any]] | None = None
    if scope_mode == "top3_only" and current_top3_products:
        seed_products = current_top3_products
    elif scope_mode == "current_results" and current_products:
        seed_products = current_products

    result = await run_agent_search(
        db,
        user_id=user_id,
        query=effective_query,
        conversation_id=conversation_id,
        filters=filters,
        page=page,
        display=1 if refine_action == "keep_one" and candidate_ids else display,
        conversation_context=state,
        candidate_ids=candidate_ids if not seed_products else None,
        seed_products=seed_products,
        keep_one=bool(refine_action == "keep_one" and candidate_ids),
    )
    result["applied_query"] = effective_query
    result.setdefault("debug", {})
    result["debug"]["refine_scope"] = scope_mode
    result["debug"]["refine_action"] = refine_action
    result["debug"]["candidate_scope_size"] = len(candidate_ids)
    return result


def save_agent_feedback(
    db: Session,
    *,
    user_id: str,
    conversation_id: str | None,
    product_id: str,
    event_type: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    event = record_user_event(
        db,
        user_id,
        event_type,
        query=metadata.get("query"),
        product={
            "product_id": product_id,
            "title": metadata.get("title"),
            "price": metadata.get("price"),
            "category": metadata.get("category"),
            "brand": metadata.get("brand"),
            "mallName": metadata.get("mall_name") or metadata.get("mallName"),
        },
        reason=metadata.get("reason"),
    )
    updated_preferences = apply_feedback_to_preferences(
        db,
        user_id,
        event_type,
        product={
            "product_id": product_id,
            "title": metadata.get("title"),
            "price": metadata.get("price"),
            "category": metadata.get("category"),
            "brand": metadata.get("brand"),
            "mallName": metadata.get("mall_name") or metadata.get("mallName"),
        },
        query=metadata.get("query"),
        reason=metadata.get("reason"),
    )
    return {
        "status": "ok",
        "event_id": event.id,
        "updated_preference_count": len(updated_preferences),
        "preferences": load_user_preferences(db, user_id),
    }


def save_final_selection(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    product_id: str,
    product: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = product or {}
    event = record_user_event(
        db,
        user_id,
        "final_select",
        query=metadata.get("query"),
        product={
            "product_id": product_id,
            "title": metadata.get("title"),
            "price": metadata.get("lprice") or metadata.get("price"),
            "category": metadata.get("category"),
            "brand": metadata.get("brand"),
            "mallName": metadata.get("mall_name") or metadata.get("seller"),
        },
        reason="final selection",
    )
    return {"status": "ok", "event_id": event.id, "product_id": product_id}
