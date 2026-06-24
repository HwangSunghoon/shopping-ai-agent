import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.embedding_service import build_product_document
from app.services.memory_service import build_preferences_from_memories, merge_memory_preferences, retrieve_memory_context
from app.services.naver_api import search_naver_shopping
from app.services.preference_service import (
    extract_preferences_from_query,
    load_user_preferences,
    record_user_event,
    update_user_preferences,
)
from app.services.query_planner import build_query_plan
from app.services.reranker import rerank_products
from app.services.fallback_service import build_search_summary_fallback


def _extract_brand(title: str | None) -> str | None:
    raw = (title or "").strip()
    if not raw:
        return None
    token = re.split(r"[\s/]", raw)[0].strip()
    return token if len(token) >= 2 else None


def _extract_features_from_product(product: dict[str, Any], merged_preferences: dict[str, Any]) -> list[str]:
    source = f"{product.get('title', '')} {product.get('category', '')}".lower()
    features = []
    for feature in merged_preferences.get("liked_features", []):
        if feature.lower() in source:
            features.append(feature)
    for keyword in ["저소음", "무선", "원룸", "세척", "가성비", "대용량", "소형"]:
        if keyword.lower() in source and keyword not in features:
            features.append(keyword)
    return features


def _merge_preferences(query_preferences: dict[str, Any], stored_preferences: dict[str, Any]) -> dict[str, Any]:
    merged = dict(stored_preferences)
    merged["price_min"] = query_preferences.get("price_min") if query_preferences.get("price_min") is not None else stored_preferences.get("price_min")
    merged["price_max"] = query_preferences.get("price_max") if query_preferences.get("price_max") is not None else stored_preferences.get("price_max")

    category = query_preferences.get("category")
    if category:
        merged["liked_categories"] = list(dict.fromkeys([category, *stored_preferences.get("liked_categories", [])]))

    merged["liked_features"] = list(
        dict.fromkeys([*(query_preferences.get("liked_features") or []), *stored_preferences.get("liked_features", [])])
    )
    merged["disliked_features"] = list(
        dict.fromkeys([*(query_preferences.get("disliked_features") or []), *stored_preferences.get("disliked_features", [])])
    )
    merged["liked_brands"] = list(
        dict.fromkeys([*(query_preferences.get("preferred_brands") or []), *stored_preferences.get("liked_brands", [])])
    )
    merged["disliked_brands"] = list(
        dict.fromkeys([*(query_preferences.get("excluded_brands") or []), *stored_preferences.get("disliked_brands", [])])
    )
    merged["usage_context"] = list(
        dict.fromkeys([*(query_preferences.get("usage_context") or []), *stored_preferences.get("usage_context", [])])
    )
    merged["required_shipping"] = list(
        dict.fromkeys([*(query_preferences.get("required_shipping") or []), *stored_preferences.get("required_shipping", [])])
    )
    if query_preferences.get("min_review_count") is not None:
        merged["min_review_count"] = query_preferences.get("min_review_count")
    return merged


def _build_search_terms(query: str, query_preferences: dict[str, Any]) -> list[str]:
    plan = build_query_plan(query)
    terms = plan.get("search_terms") or []
    category = query_preferences.get("category")
    if category and category not in terms:
        terms.insert(0, category)
    if query not in terms:
        terms.append(query)
    return list(dict.fromkeys([term.strip() for term in terms if term and term.strip()]))[:5]


def _normalize_products(products: list[dict[str, Any]], merged_preferences: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    for product in products:
        link = (product.get("link") or "").strip()
        if not link or link in seen_links:
            continue
        seen_links.add(link)
        normalized_product = dict(product)
        normalized_product["brand"] = _extract_brand(product.get("title"))
        normalized_product["review_count"] = None
        normalized_product["rating"] = None
        normalized_product["features"] = _extract_features_from_product(product, merged_preferences)
        normalized.append(normalized_product)
    return normalized


def _build_reason(product: dict[str, Any], merged_preferences: dict[str, Any]) -> str:
    reasons: list[str] = []
    component_scores = product.get("_component_scores", {})

    if component_scores.get("semantic_score", 0) >= 0.55:
        reasons.append("검색어와 상품명/카테고리의 관련성이 높습니다.")
    if component_scores.get("price_score", 0) >= 0.8:
        reasons.append("선호하는 가격대 안에서 비교하기 좋습니다.")
    if component_scores.get("preference_score", 0) >= 0.65:
        reasons.append("기존 선호 조건과 잘 맞는 후보입니다.")
    if product.get("features"):
        reasons.append(f"상품 정보에서 {', '.join(product['features'][:2])} 조건이 직접 확인됩니다.")
    if product.get("mall_name"):
        reasons.append(f"{product.get('mall_name')} 판매 채널 기준으로 비교 가능합니다.")

    if not reasons:
        reasons.append("검색 조건과 사용자 선호를 함께 반영해 상위권에 올랐습니다.")
    return " ".join(reasons[:3])


async def recommend_products(db: Session, user_id: str, query: str, limit: int = 20) -> dict[str, Any]:
    query_preferences = extract_preferences_from_query(query)
    stored_preferences = load_user_preferences(db, user_id)
    memory_context = retrieve_memory_context(db, user_id, query, raw_limit=5, summary_limit=3)
    memory_preferences = build_preferences_from_memories(memory_context["combined_memories"])
    stored_with_memory = merge_memory_preferences(stored_preferences, memory_preferences)
    merged_preferences = _merge_preferences(query_preferences, stored_with_memory)

    search_terms = _build_search_terms(query, query_preferences)

    raw_products: list[dict[str, Any]] = []
    for term in search_terms:
        try:
            raw_products.extend(await search_naver_shopping(term, display=30))
        except Exception:
            continue

    normalized_products = _normalize_products(raw_products, merged_preferences)
    reranked_products = rerank_products(
        normalized_products,
        query,
        merged_preferences,
        session_preferences=query_preferences,
        memory_context=memory_context,
        limit=max(limit, 20),
    )

    for product in reranked_products:
        product["reason"] = _build_reason(product, merged_preferences)
        product["document"] = build_product_document(product)

    update_user_preferences(db, user_id, query_preferences, source="chat")
    record_user_event(db, user_id, "search", query=query, product=None, reason="recommendation search")

    recommendations = reranked_products[:limit]
    answer = build_search_summary_fallback(query, merged_preferences, recommendations[:3], fallback_active=False)

    preference_used = [
        {"key": "price_min", "value": merged_preferences.get("price_min")},
        {"key": "price_max", "value": merged_preferences.get("price_max")},
        {"key": "liked_brands", "value": merged_preferences.get("liked_brands", [])},
        {"key": "liked_categories", "value": merged_preferences.get("liked_categories", [])},
        {"key": "liked_features", "value": merged_preferences.get("liked_features", [])},
        {"key": "disliked_features", "value": merged_preferences.get("disliked_features", [])},
    ]

    return {
        "answer": answer,
        "products": recommendations,
        "user_preference_used": preference_used,
        "debug": {
            "query_preferences": query_preferences,
            "stored_preferences": stored_preferences,
            "retrieved_raw_memories": memory_context["raw_memories"],
            "retrieved_summary_memories": memory_context["summary_memories"],
            "memory_preferences": memory_preferences,
            "merged_preferences": merged_preferences,
            "search_terms": search_terms,
            "candidate_count": len(normalized_products),
        },
    }
